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

REFLECTION_SYSTEM_PROMPT = """You are a translation quality reviewer. Your task is to review an English→Chinese translation and identify specific issues.

For each issue, state:
1. The type: accuracy (mistranslation), fluency (awkward Chinese), terminology (inconsistent term), style (tone mismatch), omission (missing content)
2. The specific problem
3. A suggested fix

Be concise and actionable. If the translation is excellent, say so briefly.

Output format:
[ISSUE_TYPE] problem description → suggested fix
...

If no issues: [OK] Translation is accurate and natural."""

REVISION_SYSTEM_PROMPT = """You are a professional translator. Your initial translation has been reviewed and the following issues were identified:

{reflection_feedback}

Please revise the translation to address ALL identified issues. Output ONLY the revised translation, no explanations."""


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
) -> list[str]:
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

    enable_reflection = config.get("enable_reflection", False)
    reflection_depth = config.get("reflection_depth", 1)

    translations = []

    for i, chunk in enumerate(chunks):
        if chunk.id in done_ids:
            prev = checkpoint.get("translations", {})
            if chunk.id in prev:
                translations.append(prev[chunk.id])
                console.print(f"  [{i+1}/{len(chunks)}] ⏭️ 跳过（已翻译）")
                continue

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
            vector_store.add_translation(
                para_id=f"{chapter_title}_{chunk.id}",
                source=chunk.text,
                target=result,
            )

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

    return translations


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
    initial, usage1 = _call_with_retry(llm_call, system_prompt, user_prompt, chunk.id, config)
    total_usage = dict(usage1)

    current = initial

    for round_num in range(depth):
        # Step 2: Reflection — LLM 审查翻译质量
        reflect_user = _build_reflection_prompt(chunk.text, current, genre)
        try:
            reflection, usage_r = llm_call(REFLECTION_SYSTEM_PROMPT, reflect_user)
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
        revision_user = f"Source text:\n{chunk.text}\n\nInitial translation:\n{current}\n\nPlease revise."
        try:
            revised, usage_v = llm_call(revision_system, revision_user)
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


def _build_reflection_prompt(source: str, translation: str, genre: str) -> str:
    """构建 Reflection 审查提示。"""
    focus = ["accuracy", "fluency", "terminology", "style"]
    focus_str = ", ".join(focus)

    return f"""Review this English→Chinese translation ({genre} genre).

Source (English):
{source[:2000]}

Translation (Chinese):
{translation[:2000]}

Check for: {focus_str}.
Be specific: what exactly is wrong and how to fix it."""


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

    system = f"""You are a professional translator specializing in English→Chinese translation.
Genre: {genre}
{style}

Translate accurately and naturally. Preserve paragraph breaks.

Output rules:
1. Return ONLY the translated text, no explanations
2. Preserve markdown formatting (**, *, ``, etc.)
3. Proper nouns: translate established ones, keep unfamiliar ones in English
4. Numbers and dates: keep original format"""

    if glossary:
        glossary_text = "\nTerminology (prefer these translations):\n"
        for en, info in list(glossary.items())[:20]:
            glossary_text += f"  {en} → {info['zh']}"
            if info.get("context"):
                glossary_text += f"  ({info['context']})"
            glossary_text += "\n"
        system += "\n" + glossary_text

    user_parts = []

    if rat_context:
        evidence = "Previously translated similar passages (for reference):\n\n"
        for i, ev in enumerate(rat_context[:3], 1):
            evidence += f"[Reference {i}]\n"
            evidence += f"EN: {ev['source'][:400]}...\n"
            evidence += f"ZH: {ev['target'][:300]}...\n\n"
        user_parts.append(evidence)

    user_parts.append(
        f"{SENTENCE_INSTRUCTION}\n\n"
        f"Translate to Chinese:\n\n{chunk.text}"
    )

    return system, "\n".join(user_parts)


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


def _call_with_retry(llm_call: Callable, system_prompt: str, user_prompt: str, chunk_id: str, config: dict) -> tuple[str, dict]:
    """API 调用包装器。call_api 已内置重试，此处提供友好错误处理。"""
    try:
        result, usage = llm_call(system_prompt, user_prompt)
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


def _save_checkpoint(path: str, translations: dict, chapter: str, done: int, total: int, content_hash: str = ""):
    data = {
        "chapter": chapter,
        "completed": done,
        "total": total,
        "completed_chunks": list(translations.keys()),
        "translations": translations,
        "content_hash": content_hash,
        "updated_at": time.time(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
