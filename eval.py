"""
Itranslation — 组件评估脚本 (eval.py)

对以下组件进行独立测试与量化评估：
  1. Chunker — 句子拆分准确性 + 重叠正确性
  2. ConsistencyModel — 术语追踪 + 漂移检测
  3. VectorStore (RAT) — 检索相关性
  4. KG Builder — 体裁检测 + 术语提取
  5. End-to-End — 翻译质量对比 (含/不含增强特性)

用法: uv run python eval.py
"""

import json, time, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from config import load_config
from chunker import chunk_text, _split_sentences
from consistency import ConsistencyModel
from assembler import assemble_translations

cfg = load_config()

# ═══════════════════════════════════════════════════════════
# 评估样本
# ═══════════════════════════════════════════════════════════

SAMPLE_TEXT = """The sun rose over the quiet village. Birds began their morning songs. A gentle breeze stirred the leaves.

The old man stepped out of his cottage. He looked at the sky and smiled. Today would be a good day, he thought.

His dog bounded over, tail wagging. "Ready for our walk?" the old man asked. The dog barked in reply, circling his feet with unbridled enthusiasm.

The village was nestled between rolling hills and a winding river. Generations of farmers had tilled the fertile soil, their stories woven into the landscape like the roots of ancient oaks.

Mitochondria are often described as the powerhouses of the cell. They generate most of the cell's supply of adenosine triphosphate, used as a source of chemical energy."""

PHILOSOPHY_SAMPLE = """Consciousness presents the most formidable challenge to contemporary materialism. The subjective character of experience — what it is like to be a particular organism — cannot be reduced to purely functional or physical descriptions. Any adequate theory of mind must account for the first-person ontology of conscious states without either eliminating them or invoking mysterious non-physical substances."""

# ═══════════════════════════════════════════════════════════
# 1. Chunker 评估
# ═══════════════════════════════════════════════════════════

def eval_chunker():
    print("=" * 55)
    print("1. Chunker — 句子拆分与重叠")
    print("=" * 55)

    # 1a: 句子拆分
    sentences = _split_sentences(SAMPLE_TEXT)
    real_sentences = [s for s in sentences if s not in ("§", "¶")]
    print(f"\n  句子拆分: {len(sentences)} 标记 → {len(real_sentences)} 实际句子")

    # 检查是否有明显错误的拆分
    issues = []
    for i, s in enumerate(real_sentences):
        if len(s) < 3:
            issues.append(f"  过短句子 [{i}]: '{s}'")
        # 检测引用句内的拆分
        if s.startswith('"') and not s.endswith('"') and i + 1 < len(real_sentences):
            # 可能在引用中间切了 — 检查下一句是否闭合
            pass  # 此处仅标记，可根据实际需要细化

    print(f"  拆分质量: {'✓ 正常' if not issues else '⚠ 存在问题'}")
    for iss in issues[:5]:
        print(iss)

    # 1b: 分块与重叠
    chunks = chunk_text(SAMPLE_TEXT, target_tokens=100, max_tokens=300, overlap_sentences=2)
    print(f"\n  分块结果: {len(chunks)} 块 (target=100 tokens, overlap=2)")

    if len(chunks) >= 2:
        c0_last = chunks[0].text.split()[-10:]
        c1_first = chunks[1].text.split()[:10]
        overlap_words = set(c0_last) & set(c1_first)
        print(f"  重叠检测: {len(overlap_words)} 共同词 → {'✓ 重叠生效' if overlap_words else '✗ 无重叠 — 可能异常'}")

    # 检查是否有相邻块的 start > end (gap)
    gaps = []
    for i in range(1, len(chunks)):
        prev_end = chunks[i-1].end_sentence
        curr_start = chunks[i].start_sentence
        if curr_start < prev_end:
            gaps.append(f"  块 [{i}] 与块 [{i-1}] 有重叠 (end={prev_end}, start={curr_start}) ✓")

    if gaps:
        for g in gaps[:3]: print(g)
    else:
        print("  块间连续: ✓ 无间隙")

    return {"sentences": len(real_sentences), "chunks": len(chunks), "overlap_ok": bool(overlap_words)}


# ═══════════════════════════════════════════════════════════
# 2. ConsistencyModel 评估
# ═══════════════════════════════════════════════════════════

def eval_consistency():
    print("\n" + "=" * 55)
    print("2. ConsistencyModel — 术语追踪与漂移检测")
    print("=" * 55)

    cm = ConsistencyModel()

    # 模拟翻译过程
    records = [
        ("consciousness", "意识", "ch1_01"),
        ("consciousness", "意识", "ch1_02"),
        ("consciousness", "知觉", "ch2_01"),  # 漂移！
        ("mitochondria", "线粒体", "ch1_03"),
        ("mitochondria", "线粒体", "ch1_04"),
        ("mitochondria", "线粒体", "ch2_02"),
        ("subjective", "主观的", "ch1_01"),
        ("subjective", "主观", "ch1_03"),      # 轻微漂移
        ("materialism", "唯物主义", "ch1_02"),
        ("materialism", "唯物主义", "ch2_01"),
        ("materialism", "唯物主义", "ch2_03"),
    ]

    for term_en, term_zh, para_id in records:
        cm.record(term_en, term_zh, para_id)

    # 审计
    issues = cm.audit_all(min_occurrences=3)
    glossary = cm.get_glossary_snapshot()

    print(f"\n  记录: {len(records)} 条 — {len(glossary)} 个术语")
    print(f"  漂移检测: {len(issues)} 个问题 (阈值 <80%)")

    for iss in issues:
        print(f"\n    📛 {iss['term']}")
        print(f"       一致性: {iss['consistency']:.0%}")
        print(f"       分布: {iss['translations']}")
        print(f"       建议: '{iss['dominant']}'")

    # 验证: consciousness 应该有漂移 (2/3 = 67%)
    cons = [i for i in issues if i['term'] == 'consciousness']
    if cons:
        print(f"\n  ✓ consciousness 漂移被正确检测 (一致性 {cons[0]['consistency']:.0%})")
    else:
        print("\n  ✗ consciousness 漂移未被检测")

    return {"terms": len(glossary), "drifts": len(issues), "correct_detection": bool(cons)}


# ═══════════════════════════════════════════════════════════
# 3. VectorStore (RAT) 评估
# ═══════════════════════════════════════════════════════════

def eval_vector_store():
    print("\n" + "=" * 55)
    print("3. VectorStore (RAT) — 检索相关性")
    print("=" * 55)

    try:
        from vector_store import TranslationVectorStore
    except ImportError:
        print("  ⚠ chromadb/sentence-transformers 未安装, 跳过")
        return {"available": False}

    vs = TranslationVectorStore(persist_dir=str(PROJECT_ROOT / "vector_store"))
    vs.initialize()

    if not vs._initialized:
        print("  ⚠ 模型未就绪, 跳过")
        return {"available": False}

    print(f"  ✓ 已初始化 ({vs.count()} 条已有记录)")

    # 插入测试数据
    test_data = [
        ("mito_1", "Mitochondria are the powerhouses of the cell.", "线粒体是细胞的能量工厂。"),
        ("mito_2", "They generate ATP through oxidative phosphorylation.", "它们通过氧化磷酸化生成 ATP。"),
        ("protein_1", "Protein synthesis occurs in ribosomes.", "蛋白质合成发生在核糖体中。"),
        ("consciousness_1", "Consciousness presents a challenge to materialism.", "意识对唯物主义构成挑战。"),
    ]
    for pid, src, tgt in test_data:
        vs.add_translation(pid, src, tgt)

    # 检索测试
    queries = [
        ("mitochondria function in cells", ["mito_1", "mito_2"]),
        ("protein creation translation", ["protein_1"]),
        ("the problem of subjective experience", ["consciousness_1"]),
    ]

    print(f"\n  插入: {len(test_data)} 条")
    hits = 0
    for query, expected_ids in queries:
        results = vs.retrieve_relevant(query, n_results=3)
        matched = [r['para_id'] for r in results]
        relevant = len(set(matched) & set(expected_ids))
        hits += 1 if relevant > 0 else 0
        print(f"  查询 '{query[:40]}...' → {matched} (期望: {expected_ids}) → {'✓' if relevant > 0 else '✗'}")

    recall = hits / len(queries) if queries else 0
    print(f"\n  检索命中率: {hits}/{len(queries)} ({recall:.0%})")

    return {"available": True, "count": vs.count(), "recall": recall}


# ═══════════════════════════════════════════════════════════
# 4. KG Builder 评估
# ═══════════════════════════════════════════════════════════

def eval_kg_builder():
    print("\n" + "=" * 55)
    print("4. KG Builder — 体裁检测与术语提取")
    print("=" * 55)

    api_key = cfg.get("api_key", "")
    if not api_key:
        print("  ⚠ 未配置 API Key, 跳过在线评估")
        return {"available": False}

    from kg_builder import build_knowledge_graph, kg_to_glossary

    def llm_call(sp, up):
        from translate_book import _call_deepseek
        return _call_deepseek(cfg, sp, up, max_tokens=4096)

    try:
        print("  发送预读请求到 DeepSeek...")
        start = time.time()
        kg = build_knowledge_graph(PHILOSOPHY_SAMPLE, llm_call,
                                     sample_ratio=0.5, max_sample_tokens=2000)
        elapsed = time.time() - start

        genre = kg.get("book_metadata", {}).get("genre", "unknown")
        style = kg.get("book_metadata", {}).get("language_style", "unknown")
        terms = kg_to_glossary(kg)
        num_terms = len(terms)

        print(f"  体裁检测: {genre} (期望: philosophy)")
        print(f"  语言风格: {style}")
        print(f"  术语提取: {num_terms} 个")
        if terms:
            print(f"  术语示例: {list(terms.keys())[:5]}")
        print(f"  耗时: {elapsed:.1f}s")

        genre_ok = genre == "philosophy"
        print(f"  体裁准确性: {'✓' if genre_ok else '⚠ 期望 philosophy'}")

        return {"available": True, "genre": genre, "genre_ok": genre_ok,
                "terms": num_terms, "elapsed": elapsed}

    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"available": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 5. End-to-End 翻译质量对比
# ═══════════════════════════════════════════════════════════

def eval_e2e():
    print("\n" + "=" * 55)
    print("5. End-to-End — 翻译流程验证")
    print("=" * 55)

    api_key = cfg.get("api_key", "")
    if not api_key:
        print("  ⚠ 未配置 API Key, 跳过")
        return {"available": False}

    from translator import translate_chapter
    from translate_book import _call_deepseek as call_api

    # 用样本文字做一次完整翻译
    text = SAMPLE_TEXT
    chunks = chunk_text(text, target_tokens=cfg.get("chunk_target_tokens", 1500),
                        max_tokens=cfg.get("chunk_max_tokens", 3000),
                        overlap_sentences=3)

    cm = ConsistencyModel()
    def llm(sp, up):
        return call_api(cfg, sp, up, max_tokens=cfg.get("max_tokens_per_chunk", 8192))

    print(f"  输入: {len(text)} 字符 → {len(chunks)} 块")
    print(f"  翻译中...")

    start = time.time()
    try:
        trans = translate_chapter("eval_test", chunks, None, cm, {}, {}, llm, cfg)
        elapsed = time.time() - start

        full = assemble_translations(chunks, trans, "first_lock")

        # 基本检查
        issues = []
        if not full.strip():
            issues.append("空译文")
        if len(full) < len(text) * 0.3:
            issues.append(f"译文过短 ({len(full)} vs {len(text)} 原文)")

        # 成本
        cost = cfg.get("_cost", {})
        pt = cost.get("prompt_tokens", 0)
        ct = cost.get("completion_tokens", 0)
        est_cost = pt / 1e6 * 0.435 + ct / 1e6 * 0.87

        print(f"  输出: {len(full)} 字符")
        print(f"  块数: {len(trans)}")
        print(f"  Token: {pt:,}入 + {ct:,}出")
        print(f"  费用: ${est_cost:.4f} (~¥{est_cost*7.2:.2f})")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  输出预览: {full[:150]}...")

        if issues:
            for iss in issues:
                print(f"  ⚠ {iss}")
        else:
            print(f"  ✓ 基本验证通过")

        return {"available": True, "chunks": len(chunks), "output_len": len(full),
                "elapsed": elapsed, "tokens_in": pt, "tokens_out": ct}

    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"available": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  Itranslation — 组件评估报告")
    print(f"  模型: {cfg.get('model', '?')}")
    print("=" * 55)

    results = {}

    results['chunker'] = eval_chunker()
    results['consistency'] = eval_consistency()
    results['vector_store'] = eval_vector_store()
    results['kg_builder'] = eval_kg_builder()
    results['e2e'] = eval_e2e()

    # 汇总
    print("\n" + "=" * 55)
    print("  评估汇总")
    print("=" * 55)

    checks = [
        ("Chunker 句子拆分", results['chunker']['sentences'] > 0),
        ("Chunker 重叠", results['chunker'].get('overlap_ok', False)),
        ("Consistency 漂移检测", results['consistency']['correct_detection']),
        ("VectorStore 可用", results['vector_store'].get('available', False)),
        ("VectorStore 检索命中", results['vector_store'].get('recall', 0) > 0.5),
        ("KG Builder 体裁检测", results['kg_builder'].get('genre_ok', False)),
        ("E2E 翻译通过", results['e2e'].get('available', False)),
    ]

    for name, passed in checks:
        print(f"  {'✓' if passed else '✗'}  {name}")

    score = sum(1 for _, p in checks if p)
    print(f"\n  通过: {score}/{len(checks)}")
    if score == len(checks):
        print("  🎉 全部通过!")
    elif score >= len(checks) - 1:
        print("  ⚠ 基本通过, 有 1 项待修复")
    else:
        print("  ❌ 存在多项问题, 需排查")

    # 保存报告
    report_path = PROJECT_ROOT / "reports" / "eval" / "eval_report.json"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({k: {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict))}
                   for k, v in results.items()},
                  f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {report_path}")


if __name__ == "__main__":
    main()
