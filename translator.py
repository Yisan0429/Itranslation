"""
Phase 2: RAT 翻译引擎。

Retrieval-Augmented Translation:
1. 从向量库检索最相似已翻译段落
2. 从 KG/glossary 注入术语
3. 附加上一块重叠上下文
4. 调用 LLM 翻译
5. 存储结果到向量库 + 更新一致性模型
"""

import json
import time
from typing import Callable
from rich.console import Console

from vector_store import TranslationVectorStore
from consistency import ConsistencyModel
from assembler import SENTENCE_SEPARATOR, SENTENCE_INSTRUCTION

console = Console()

BATCH_DELIMITER = "\n\n␞␞␞\n\n"


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
) -> list[str]:
    console.print(f"\n[bold]📖 翻译章节: {chapter_title} ({len(chunks)} 块)[/bold]")

    if vector_store is not None:
        vector_store.initialize()

    checkpoint = _load_checkpoint(checkpoint_path) if checkpoint_path else {}
    done_ids = set(checkpoint.get("completed_chunks", []))

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

        # 3. 调用 LLM
        result, usage = _call_with_retry(
            llm_call, system_prompt, user_prompt, chunk.id, config
        )

        # 累加成本
        total_cost = config.setdefault("_cost", {"prompt_tokens": 0, "completion_tokens": 0})
        total_cost["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_cost["completion_tokens"] += usage.get("completion_tokens", 0)

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
            )

        # 7. 每 N 块审计
        interval = config.get("consistency_check_interval", 20)
        if (i + 1) % interval == 0:
            issues = consistency_model.audit_all()
            if issues:
                console.print(f"  [yellow]⚠️ 一致性审计: {len(issues)} 个术语漂移[/yellow]")
                for iss in issues[:3]:
                    console.print(f"     {iss['term']}: {iss['consistency']:.0%} → 建议 '{iss['dominant']}'")

        console.print(f"  [{i+1}/{len(chunks)}] ✅ {chunk.id}")

    return translations


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
    max_retries = config.get("max_retries", 3)
    network_max_retries = max(config.get("network_max_retries", max_retries), max_retries)
    base_delay = config.get("retry_base_delay", 2)
    max_delay = config.get("retry_max_delay", 60)

    last_error = None
    attempt = 0
    last_retry_limit = max_retries
    while True:
        try:
            result, usage = llm_call(system_prompt, user_prompt)
            if not result or not result.strip():
                raise ValueError("LLM returned empty response")
            return result.strip(), usage
        except Exception as e:
            last_error = e
            retry_limit = network_max_retries if getattr(e, "retryable", False) else max_retries
            last_retry_limit = retry_limit

            if attempt < retry_limit - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                console.print(f"  [yellow]⚠️ {chunk_id} 第{attempt+1}次失败: {e}，{delay}s 后重试[/yellow]")
                time.sleep(delay)
            else:
                break
        attempt += 1

    raise RuntimeError(f"{chunk_id} 翻译失败（{last_retry_limit} 次重试后）: {last_error}")


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


def _save_checkpoint(path: str, translations: dict, chapter: str, done: int, total: int):
    data = {
        "chapter": chapter,
        "completed": done,
        "total": total,
        "completed_chunks": list(translations.keys()),
        "translations": translations,
        "updated_at": time.time(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
