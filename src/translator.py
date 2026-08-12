"""
Phase 2: RAT 翻译引擎 + Reflection 反思工作流。

Retrieval-Augmented Translation:
1. 从向量库检索最相似已翻译段落
2. 从 KG/glossary 注入术语
3. 附加上一块重叠上下文
4. 调用 LLM 翻译
5. [可选] Reflection: LLM 自审 → 修订
6. 存储结果到向量库 + 更新一致性模型
"""

from __future__ import annotations

import json
import time
import threading
from typing import Callable
from rich.console import Console

from vector_store import TranslationVectorStore
from consistency import ConsistencyModel
from assembler import SENTENCE_SEPARATOR, SENTENCE_INSTRUCTION

console = Console()

BATCH_DELIMITER = "\n\n␞␞␞\n\n"

# ── Reflection Prompts ──────────────────────────────────────────────

REFLECTION_SYSTEM_PROMPT = """You are an expert translation quality reviewer specializing in English→Chinese literary and academic translation. Your review must be thorough, specific, and actionable.

Review dimensions (check ALL of them):

1. ACCURACY: Are there mistranslations, omissions, or additions? Does the Chinese faithfully convey the exact meaning of the English?
2. FLUENCY: Is the Chinese natural and idiomatic? Or does it read like translationese (硬译腔)? Are there awkward collocations, unnatural word order, or calques from English?
3. TERMINOLOGY: Are domain-specific terms translated consistently with the provided glossary? Are proper nouns handled correctly?
4. STYLE: Does the tone match the genre? Literary texts should preserve rhetorical devices and rhythm. Academic texts should maintain logical precision. Technical texts should keep code/commands verbatim.
5. CULTURAL ADAPTATION: Are culture-specific references (idioms, metaphors, allusions) appropriately localized? Or are they translated literally in a way that loses meaning?
6. SENTENCE STRUCTURE: Are long English sentences broken into natural Chinese clause chains? Or are they preserved as unwieldy run-on sentences?

Output format — use EXACTLY this structure:

[ISSUE_TYPE] specific problem description → suggested fix
[ISSUE_TYPE] specific problem description → suggested fix
...

If the translation is excellent across all dimensions: [OK] Accurate, fluent, and stylistically appropriate.

CRITICAL: Be specific. Don't say "could be better." Say "line 3 uses 被字句 where Chinese would prefer active voice → rewrite as 主动句式."
"""

REVISION_SYSTEM_PROMPT = """You are a professional English→Chinese translator revising your own work based on expert review feedback.

Below is your initial translation and the reviewer's feedback. Please revise to address EVERY issue identified.

Revision principles:
- Accuracy first: if meaning is wrong, fix it regardless of fluency
- Natural Chinese: avoid 被字句 overuse, avoid long modifier chains (长定语), prefer verb-driven sentences over noun-heavy ones
- Consistency: use the same term for the same concept throughout
- If the reviewer identified a terminology issue, use the EXACT term they suggested
- If a sentence is too long in Chinese, split it — Chinese prefers shorter clauses (流水句)

CRITICAL: Output ONLY the revised Chinese text. No explanations, no commentary, no markdown.

Reviewer feedback:
{reflection_feedback}"""


# ── Translation Prompts (v1.4 improved) ──────────────────────────────

TRANSLATION_SYSTEM_PROMPT = """You are an expert literary and academic translator specializing in English→Chinese translation. Your translations are published by major Chinese publishing houses.

## Translation Philosophy

1. FAITHFULNESS FIRST: Never sacrifice accuracy for elegance. If a passage is ambiguous, preserve the ambiguity rather than resolving it.
2. NATURAL CHINESE: Write Chinese that a native speaker would actually write. Avoid:
   - Excessive 被字句 (passive voice) — Chinese prefers active constructions
   - Long modifier chains before nouns (长定语) — break into clauses
   - Calques like "在...的情况下" for "in the case of..." — use natural alternatives
   - Noun-heavy academic style where Chinese prefers verbs
3. GENRE AWARENESS: Adapt tone per genre (see genre-specific instructions below).
4. CONSISTENCY: Use the same Chinese term for the same English term throughout the book.
5. FORMAT PRESERVATION: Keep markdown formatting, code blocks, and numbers exactly as-is.

## Output Format

Use the sentence separator character exactly as instructed in the user message. Each sentence on its own line.
Return ONLY the translated text — no preambles, no notes, no markdown wrapping.

## Genre: {genre}

{style_instruction}

## Terminology Reference

{glossary_section}

## Context from Previous Translations

{rat_section}"""


TRANSLATION_USER_PROMPT = """{sentence_instruction}{context_section}

## Source Text (translate ONLY the sentences below)

{source_text}"""


def translate_chapter(
    chapter_title: str,
    chunks: list,
    vector_store: TranslationVectorStore | None,
    consistency_model: ConsistencyModel,
    glossary: dict,
    kg: dict,
    llm_call: Callable,
    config: dict,
    checkpoint_path: str = None,
    cost_lock: threading.Lock = None,
) -> tuple[list[str], list[dict]]:
    """翻译一个章节的所有块。

    Returns:
        (translations, errors) — errors 列表每项含 {chunk_id, error, stage}
    """
    console.print(f"\n[bold]📖 翻译章节: {chapter_title} ({len(chunks)} 块)[/bold]")

    if vector_store is not None:
        vector_store.initialize()

    # 内容哈希 — 文件改动后自动失效
    import hashlib
    content_hash = hashlib.md5("".join(c.text for c in chunks).encode()).hexdigest()

    checkpoint = _load_checkpoint(checkpoint_path) if checkpoint_path else {}
    # 内容变了 → 丢弃旧缓存
    if checkpoint.get("content_hash") != content_hash:
        checkpoint = {}
    done_ids = set(checkpoint.get("completed_chunks", []))
    # 旧版 checkpoint 可能把失败占位符存为已完成译文，恢复时将其排除并重译
    stale_failed = {
        cid for cid, text in checkpoint.get("translations", {}).items()
        if isinstance(text, str) and text.startswith("[翻译失败:")
    }
    done_ids -= stale_failed

    enable_reflection = config.get("enable_reflection", False)
    reflection_depth = config.get("reflection_depth", 1)

    translations = []
    errors = []

    failed_ids = []

    for i, chunk in enumerate(chunks):
        if chunk.id in done_ids:
            prev = checkpoint.get("translations", {})
            if chunk.id in prev:
                translations.append(prev[chunk.id])
                console.print(f"  [{i+1}/{len(chunks)}] ⏭️ 跳过（已翻译）")
                continue

        try:
            # 1. RAT 检索
            rat_context = _build_rat_context(chunk, vector_store, glossary, kg, config)

            # 2. 构建 prompt
            system_prompt, user_prompt = _build_translation_prompt(
                chunk, rat_context, glossary, kg, config
            )

            # 3. 调用 LLM 翻译（可能含 reflection）
            if enable_reflection:
                result, usage = _translate_with_reflection(
                    llm_call, system_prompt, user_prompt, chunk,
                    config, reflection_depth, cost_lock,
                )
            else:
                result, usage = _call_with_retry(
                    llm_call, system_prompt, user_prompt, chunk.id, config
                )

            # 累加成本（线程安全）
            if cost_lock:
                with cost_lock:
                    _accumulate_cost(config, usage)
            else:
                _accumulate_cost(config, usage)

            # 4. 存储到向量库
            if vector_store is not None:
                try:
                    vector_store.add_translation(
                        para_id=f"{chapter_title}_{chunk.id}",
                        source=chunk.text,
                        target=result,
                    )
                except Exception as e:
                    console.print(f"  [dim]⚠️ 向量库写入失败 (非致命): {e}[/dim]")

            # 5. 更新一致性模型
            _update_consistency(chunk.text, result, glossary, consistency_model, chunk.id)

            translations.append(result)

            # 6. 保存 checkpoint
            if checkpoint_path:
                _save_checkpoint(
                    checkpoint_path,
                    {ch.id: t for ch, t in zip(chunks[:len(translations)], translations)},
                    chapter_title,
                    len(translations),
                    len(chunks),
                    content_hash,
                    failed_ids,
                )

            # 7. 每 N 块审计
            interval = config.get("consistency_check_interval", 20)
            if (i + 1) % interval == 0:
                issues = consistency_model.audit_all()
                if issues:
                    console.print(f"  [yellow]⚠️ 一致性审计: {len(issues)} 个术语漂移[/yellow]")
                    for iss in issues[:3]:
                        console.print(f"     {iss['term']}: {iss['consistency']:.0%} → 建议 '{iss['dominant']}'")

            tag = "🔄" if enable_reflection else "✅"
            console.print(f"  [{i+1}/{len(chunks)}] {tag} {chunk.id}")

        except Exception as e:
            error_msg = str(e)[:200]
            console.print(f"  [{i+1}/{len(chunks)}] [red]✗ {chunk.id}: {error_msg}[/red]")
            errors.append({
                "chunk_id": chunk.id,
                "chapter": chapter_title,
                "error": error_msg,
                "stage": "translate",
            })
            # 填充占位，保持索引对齐；记录失败块（不入 completed，重跑时重译）
            translations.append(f"[翻译失败: {error_msg[:80]}]")
            failed_ids.append(chunk.id)
            if checkpoint_path:
                _save_checkpoint(
                    checkpoint_path,
                    {ch.id: t for ch, t in zip(chunks[:len(translations)], translations)},
                    chapter_title,
                    len(translations),
                    len(chunks),
                    content_hash,
                    failed_ids,
                )

    return translations, errors


def _translate_with_reflection(
    llm_call: Callable,
    system_prompt: str,
    user_prompt: str,
    chunk,
    config: dict,
    depth: int,
    cost_lock: threading.Lock | None,
) -> tuple[str, dict]:
    """带 Reflection 反思的翻译：翻译 → 自审 → 修订。"""
    genre = config.get("genre", "auto")

    # Step 1: 初始翻译
    initial, usage1 = _call_with_retry(llm_call, system_prompt, user_prompt, chunk.id, config, tier="strong")
    total_usage = dict(usage1)

    current = initial

    for round_num in range(depth):
        # Step 2: Reflection — LLM 审查翻译质量
        reflect_user = _build_reflection_prompt(
            chunk.body_text() if hasattr(chunk, "body_text") else chunk.text,
            current, genre,
        )
        try:
            reflection, usage_r = llm_call(REFLECTION_SYSTEM_PROMPT, reflect_user, tier="cheap")
        except Exception as e:
            console.print(f"  [yellow]⚠️ Reflection 失败: {e}，跳过修订[/yellow]")
            break

        _merge_usage(total_usage, usage_r)
        if cost_lock:
            with cost_lock:
                _accumulate_cost(config, usage_r)
        else:
            _accumulate_cost(config, usage_r)

        # 如果翻译已经很好，跳过修订
        if reflection.strip().startswith("[OK]"):
            console.print(f"    [dim]Reflection #{round_num+1}: 翻译质量良好，跳过修订[/dim]")
            break

        # Step 3: Revision — 根据反馈修订
        revision_system = REVISION_SYSTEM_PROMPT.format(reflection_feedback=reflection)
        body_src = chunk.body_text() if hasattr(chunk, "body_text") else chunk.text
        revision_user = (
            "Source text:\n" + body_src + "\n\n"
            + "Initial translation:\n" + current + "\n\n"
            + "Please revise."
        )
        try:
            revised, usage_v = llm_call(revision_system, revision_user, tier="strong")
        except Exception as e:
            console.print(f"  [yellow]⚠️ Revision 失败: {e}，保留当前版本[/yellow]")
            break

        _merge_usage(total_usage, usage_v)
        if cost_lock:
            with cost_lock:
                _accumulate_cost(config, usage_v)
        else:
            _accumulate_cost(config, usage_v)

        current = revised
        console.print(f"    [dim]Reflection #{round_num+1}: 已修订[/dim]")

    return current, total_usage


def _get_style_instruction(genre: str) -> str:
    styles = {
        "literature": (
            "Literary translation. Preserve rhetorical devices, rhythm, and emotional tone. "
            "Use elegant, natural modern Chinese. Adapt idioms to Chinese equivalents rather than literal translation. "
            "For dialogue, use colloquial Chinese that fits the character's voice. "
            "For descriptive passages, maintain the original's pacing and imagery. "
            "CRITICAL: Avoid 翻译腔 — no excessive 被字句, no long modifier chains, no calques."
        ),
        "philosophy": (
            "Faithful direct translation. Preserve logical structure and argument flow precisely. "
            "Do not simplify complex sentences — philosophical German/English sentence structures carry meaning. "
            "Use established Chinese philosophical terminology (意向性, 此在, 延异, etc.) where applicable. "
            "Maintain the author's distinctive voice. Consistency with glossary terms is paramount."
        ),
        "natural_science": (
            "Terminology accuracy above all. Preserve data, formulas, units, and scientific notation exactly. "
            "Use standard Chinese scientific terminology. Prefer precise but readable Chinese over elegant but vague. "
            "Do not simplify or paraphrase technical explanations. "
            "Latin species names and chemical formulas must remain unchanged."
        ),
        "social_science": (
            "Balanced translation: faithful to argument structure while readable in Chinese. "
            "Preserve citation format and author names exactly. Use standard Chinese social science terminology. "
            "For statistical claims, preserve numbers and methodology descriptions verbatim. "
            "Avoid introducing political or cultural bias — maintain the original author's stance."
        ),
        "technical": (
            "Accurate technical translation. Code, commands, configuration values, API names, and file paths "
            "must remain completely unchanged. Only translate surrounding explanatory text. "
            "Use standard Chinese technical terms (not transliterations). "
            "Warn if a term has multiple possible Chinese translations."
        ),
    }
    return styles.get(genre, styles["natural_science"])


def _build_reflection_prompt(source: str, translation: str, genre: str) -> str:
    """构建 Reflection 审查提示。包含体裁特定的审查重点。"""
    genre_focus = {
        "literature": "Pay special attention to: dialogue naturalness, rhetorical device preservation, emotional tone, idiom adaptation.",
        "philosophy": "Pay special attention to: logical connective accuracy, term consistency, preservation of ambiguity, sentence structure fidelity.",
        "natural_science": "Pay special attention to: term accuracy, data/unit preservation, formula integrity, standard Chinese scientific usage.",
        "social_science": "Pay special attention to: argument structure, citation preservation, statistical accuracy, terminology consistency.",
        "technical": "Pay special attention to: code/command integrity, API name preservation, technical term accuracy, file path preservation.",
    }
    extra = genre_focus.get(genre, "")

    return f"""Review this English→Chinese translation ({genre} genre).

{extra}

Source (English):
{source[:2000]}

Translation (Chinese):
{translation[:2000]}

For each issue found, use format: [TYPE] problem → fix
If no issues: [OK] Accurate, fluent, and stylistically appropriate."""


def _merge_usage(total: dict, usage: dict):
    """合并 token 用量。"""
    for k in ("prompt_tokens", "completion_tokens"):
        total[k] = total.get(k, 0) + usage.get(k, 0)


def _accumulate_cost(config: dict, usage: dict):
    """累加翻译 token 成本到 config['_cost']。"""
    total_cost = config.setdefault("_cost", {"prompt_tokens": 0, "completion_tokens": 0})
    total_cost["prompt_tokens"] += usage.get("prompt_tokens", 0)
    total_cost["completion_tokens"] += usage.get("completion_tokens", 0)


def _build_rat_context(chunk, vector_store, glossary: dict, kg: dict, config: dict) -> list[dict]:
    if vector_store is None:
        return []

    top_k = config.get("rat_top_k", 5)

    similar = vector_store.retrieve_relevant(chunk.text, n_results=top_k)
    current_terms = _extract_glossary_terms(chunk.text, glossary)
    term_results = vector_store.retrieve_by_terms(current_terms, n_results=3)

    seen = set()
    merged = []
    for item in similar + term_results:
        if item["para_id"] not in seen:
            merged.append(item)
            seen.add(item["para_id"])

    merged.sort(key=lambda x: x.get("distance", 1.0))
    return merged[:top_k]


def _build_translation_prompt(chunk, rat_context: list[dict], glossary: dict, kg: dict, config: dict) -> tuple[str, str]:
    genre = kg.get("book_metadata", {}).get("genre", config.get("genre", "auto"))
    style = _get_style_instruction(genre)

    # 术语表
    glossary_section = "None provided."
    if glossary:
        lines = []
        for en, info in list(glossary.items())[:20]:
            line = f"  {en} → {info['zh']}"
            if info.get("context"):
                line += f"  ({info['context']})"
            lines.append(line)
        glossary_section = "Use these translations consistently:\n" + "\n".join(lines)

    # RAT 上下文
    rat_section = "None available."
    if rat_context:
        parts = []
        for i, ev in enumerate(rat_context[:3], 1):
            parts.append(
                f"[Example {i}]\n"
                f"EN: {ev['source'][:300]}...\n"
                f"ZH: {ev['target'][:250]}..."
            )
        rat_section = "Previously translated similar passages — maintain consistent style and terminology:\n\n" + "\n\n".join(parts)

    system = TRANSLATION_SYSTEM_PROMPT.format(
        genre=genre,
        style_instruction=style,
        glossary_section=glossary_section,
        rat_section=rat_section,
    )

    # 重叠上下文句仅供理解，不翻译；只翻译正文句
    context_text = chunk.context_text() if hasattr(chunk, "context_text") else ""
    source_text = chunk.body_text() if hasattr(chunk, "body_text") else chunk.text

    context_section = ""
    if context_text.strip():
        context_section = (
            "\n\n## Context - previous sentences for understanding only, "
            "DO NOT translate them\n\n"
            + context_text
        )

    body_count = getattr(chunk, "body_sentence_count", None)
    count_line = ""
    if body_count is not None:
        count_line = (
            "\nThe 'Source Text' section contains exactly " + str(body_count)
            + " sentences. Output exactly " + str(body_count)
            + " translated sentences."
        )

    user = TRANSLATION_USER_PROMPT.format(
        sentence_instruction=SENTENCE_INSTRUCTION + count_line,
        context_section=context_section,
        source_text=source_text,
    )

    return system, user


def _get_style_instruction(genre: str) -> str:
    styles = {
        "literature": "Literary translation. Preserve rhetorical devices, rhythm, emotional tone. Use elegant modern Chinese. Adapt idioms naturally.",
        "philosophy": "Faithful direct translation. Preserve logical structure. Do not split long sentences. Consistent terminology.",
        "natural_science": "Faithful direct translation. Terminology accuracy over fluency. Preserve data, units, scientific notation exactly.",
        "social_science": "Faithful translation with readability. Consistent terminology. Preserve citations.",
        "technical": "Accurate technical translation. Preserve code, commands, config values unchanged.",
    }
    return styles.get(genre, styles["natural_science"])


def _extract_glossary_terms(text: str, glossary: dict) -> list[str]:
    found = []
    text_lower = text.lower()
    for en_term in glossary:
        if en_term.lower() in text_lower:
            found.append(en_term)
    return found


def _call_with_retry(llm_call: Callable, system_prompt: str, user_prompt: str, chunk_id: str, config: dict, tier: str = None) -> tuple[str, dict]:
    """API 调用包装器。call_api 已内置重试，此处提供友好错误处理。"""
    try:
        result, usage = llm_call(system_prompt, user_prompt, tier=tier)
        if not result or not result.strip():
            raise ValueError("LLM returned empty response")
        return result.strip(), usage
    except Exception as e:
        raise RuntimeError(f"{chunk_id} 翻译失败: {e}")


def _update_consistency(source: str, target: str, glossary: dict, model: ConsistencyModel, chunk_id: str):
    for en_term in _extract_glossary_terms(source, glossary):
        zh_expected = glossary[en_term]["zh"]
        if zh_expected in target:
            model.record(en_term, zh_expected, chunk_id)
        else:
            model.record(en_term, f"[非标准] {zh_expected}", chunk_id)


def _load_checkpoint(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_checkpoint(path: str, translations: dict, chapter: str, done: int, total: int, content_hash: str = "", failed_ids: list = None):
    """保存 checkpoint。失败块不进入 completed_chunks/translations，重跑时会被重新翻译。"""
    failed_ids = failed_ids or []
    failed_set = set(failed_ids)
    ok_translations = {k: v for k, v in translations.items() if k not in failed_set}
    data = {
        "chapter": chapter,
        "completed": len(ok_translations),
        "total": total,
        "completed_chunks": list(ok_translations.keys()),
        "failed_chunks": list(failed_ids),
        "translations": ok_translations,
        "content_hash": content_hash,
        "updated_at": time.time(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

