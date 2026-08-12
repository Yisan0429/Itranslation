"""
Itranslation Benchmark — 翻译质量量化评估。

评估维度：
  1. BLEU / chrF — 与参考译文的 n-gram 匹配度
  2. LLM-as-Judge — LLM 对准确度/流畅度/术语/风格的独立评分
  3. 组件基准 — Chunker / Consistency / RAT / KG 回归测试

用法:
    uv run python src/benchmark.py                    # 全部测试
    uv run python src/benchmark.py --quick            # 快速测试 (仅组件)
    uv run python src/benchmark.py --model gpt-4o     # 指定模型
"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import load_config, calc_cost, MODEL_PRESETS
from chunker import chunk_text, _split_sentences
from consistency import ConsistencyModel
from assembler import assemble_translations

cfg = load_config()

# ═══════════════════════════════════════════════════════════
# Benchmark Corpus — 多体裁源文 + 人工参考译文
# ═══════════════════════════════════════════════════════════

BENCHMARK_CORPUS = [
    {
        "id": "lit_01",
        "genre": "literature",
        "source": "The old man had fished alone in the Gulf Stream for eighty-four days now without taking a fish. In the first forty days a boy had been with him. But after forty days without a fish the boy's parents had told him that the old man was now definitely and finally salao, which is the worst form of unlucky.",
        "reference": "老人独自在墨西哥湾流中钓鱼，已经八十四天没有捕到一条鱼了。头四十天里，有个男孩一直陪着他。但四十天没捕到鱼之后，男孩的父母告诉他，这老头如今是彻彻底底地倒了霉——那是最糟糕的一种厄运。",
    },
    {
        "id": "lit_02",
        "genre": "literature",
        "source": "It was a bright cold day in April, and the clocks were striking thirteen. Winston Smith, his chin nuzzled into his breast in an effort to escape the vile wind, slipped quickly through the glass doors of Victory Mansions.",
        "reference": "四月里一个晴朗而寒冷的日子，钟敲了十三下。温斯顿·史密斯缩着脖子，想要躲开那刺骨的寒风，快步溜进了胜利大厦的玻璃门。",
    },
    {
        "id": "phil_01",
        "genre": "philosophy",
        "source": "The limits of my language mean the limits of my world. Logic pervades the world; the limits of the world are also its limits. We cannot think what we cannot think; therefore we cannot say what we cannot think.",
        "reference": "我的语言的界限意味着我的世界的界限。逻辑充满世界；世界的界限也是逻辑的界限。我们不能思考我们不能思考的东西；因此我们也不能说出我们不能思考的东西。",
    },
    {
        "id": "sci_01",
        "genre": "natural_science",
        "source": "DNA replication is the process by which a double-stranded DNA molecule is copied to produce two identical DNA molecules. This process is essential for cell division and occurs during the S phase of the cell cycle. The enzyme DNA polymerase plays a crucial role in synthesizing new DNA strands.",
        "reference": "DNA 复制是指双链 DNA 分子被复制以产生两个相同 DNA 分子的过程。这一过程对细胞分裂至关重要，发生在细胞周期的 S 期。DNA 聚合酶在合成新的 DNA 链中起着关键作用。",
    },
    {
        "id": "sci_02",
        "genre": "natural_science",
        "source": "The Second Law of Thermodynamics states that the total entropy of an isolated system can never decrease over time. In practical terms, this means that heat flows spontaneously from hotter to colder bodies, and that perpetual motion machines of the second kind are impossible.",
        "reference": "热力学第二定律指出，孤立系统的总熵随时间推移永远不会减少。从实际角度来看，这意味着热量自发地从高温物体流向低温物体，第二类永动机是不可能存在的。",
    },
    {
        "id": "soc_01",
        "genre": "social_science",
        "source": "Social stratification refers to a society's categorization of its people into rankings based on factors like wealth, income, education, family background, and power. Sociologists recognize that these hierarchies are socially constructed and vary across cultures and historical periods.",
        "reference": "社会分层是指一个社会根据财富、收入、教育、家庭背景和权力等因素将人们划分为不同等级。社会学家认识到这些等级制度是社会建构的，并因文化和历史时期而异。",
    },
]


# ═══════════════════════════════════════════════════════════
# 1. BLEU / chrF 自动评分
# ═══════════════════════════════════════════════════════════

def compute_bleu(references: list[str], hypothesis: str) -> dict:
    """使用 sacrebleu 计算 BLEU 和 chrF 分数。"""
    try:
        import sacrebleu
    except ImportError:
        return {"bleu": None, "chrf": None, "error": "sacrebleu 未安装"}

    # sacrebleu expects references as Sequence[str]
    refs = references  # already a list of strings

    try:
        bleu = sacrebleu.sentence_bleu(hypothesis, refs, tokenize="zh")
        chrf = sacrebleu.sentence_chrf(hypothesis, refs, word_order=2)
        return {
            "bleu": round(bleu.score, 1),
            "chrf": round(chrf.score, 1),
        }
    except Exception as e:
        return {"bleu": None, "chrf": None, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 2. LLM-as-Judge 质量评分
# ═══════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """You are a professional translation quality evaluator. Score the given translation on four dimensions:

1. accuracy (1-10): How faithfully does it convey the source meaning? No omissions or additions.
2. fluency (1-10): How natural and idiomatic is the Chinese? No translationese.
3. terminology (1-10): Are domain-specific terms translated correctly and consistently?
4. style (1-10): Does the tone match the genre? Literary for literature, precise for science.

Output ONLY valid JSON:
{"accuracy": N, "fluency": N, "terminology": N, "style": N, "overall": N, "comments": "brief note"}"""


def judge_translation(source: str, translation: str, genre: str, reference: str = "") -> dict:
    """LLM 评分翻译质量。"""
    api_key = cfg.get("api_key", "")
    if not api_key:
        return {"error": "未配置 API Key"}

    from api_client import call_api

    user_prompt = f"""Genre: {genre}

Source (English):
{source[:1500]}

Translation (Chinese):
{translation[:1500]}"""

    if reference:
        user_prompt += f"\n\nReference (for comparison):\n{reference[:1000]}"

    try:
        result, usage = call_api(
            api_key=api_key,
            api_base=cfg.get("api_base", "https://api.deepseek.com/v1"),
            model=cfg.get("model", "deepseek-v4-pro"),
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=512,
            temperature=0.1,
            provider=cfg.get("provider", "custom"),
        )
        if not result or not result.strip():
            return {"error": "LLM returned empty response"}
        # 清洗 JSON：去除 markdown 代码块包裹
        text = result.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取第一个 { ... } 块
        import re
        match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"error": f"JSON parse failed: {result[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# 3. 翻译 + 评估一条龙
# ═══════════════════════════════════════════════════════════

def translate_sample(source: str, genre: str) -> tuple[str, dict]:
    """翻译单个样本。"""
    from api_client import call_api

    api_key = cfg.get("api_key", "")
    if not api_key:
        return "", {"error": "未配置 API Key"}

    provider = cfg.get("provider", "custom")

    genre_styles = {
        "literature": "Literary translation. Preserve rhetoric, rhythm, emotional tone. Elegant modern Chinese.",
        "philosophy": "Faithful direct translation. Preserve logical structure. Consistent terminology.",
        "natural_science": "Faithful direct translation. Terminology accuracy over fluency. Preserve data and units.",
        "social_science": "Faithful translation with readability. Consistent terminology. Preserve citations.",
    }
    style_instruction = genre_styles.get(genre, genre_styles["natural_science"])

    system = f"""You are a professional English→Chinese translator.
Genre: {genre}
{style_instruction}
Return ONLY the translated text, no explanations."""

    try:
        result, usage = call_api(
            api_key=api_key,
            api_base=cfg.get("api_base", "https://api.deepseek.com/v1"),
            model=cfg.get("model", "deepseek-v4-pro"),
            system_prompt=system,
            user_prompt=f"Translate to Chinese:\n\n{source}",
            max_tokens=2048,
            temperature=0.3,
            provider=provider,
        )
        return result, usage
    except Exception as e:
        return "", {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# 4. 组件基准测试
# ═══════════════════════════════════════════════════════════

def bench_chunker() -> dict:
    """Chunker 基准测试。"""
    from chunker import chunk_text, _split_sentences

    test_text = "Hello world. This is a test. Another sentence here. And one more for good measure."

    sentences = _split_sentences(test_text)
    real = [s for s in sentences if s not in ("§", "¶")]

    chunks = chunk_text(test_text, target_tokens=20, max_tokens=100, overlap_sentences=1)

    return {
        "sentences_detected": len(real),
        "expected_sentences": 4,
        "chunks_created": len(chunks),
        "sentence_accuracy": len(real) == 4,
    }


def bench_consistency() -> dict:
    """ConsistencyModel 基准测试。"""
    cm = ConsistencyModel()

    # 注入已知模式
    cm.record("entropy", "熵", "p1")
    cm.record("entropy", "熵", "p2")
    cm.record("entropy", "熵", "p3")
    cm.record("entropy", "熵值", "p4")  # 漂移 3/4 = 75% < 80%

    cm.record("quantum", "量子", "p1")
    cm.record("quantum", "量子", "p2")
    cm.record("quantum", "量子", "p3")

    issues = cm.audit_all(min_occurrences=3)

    entropy_issue = [i for i in issues if i["term"] == "entropy"]
    quantum_ok = not any(i["term"] == "quantum" for i in issues)

    return {
        "total_terms": len(cm.get_glossary_snapshot()),
        "drifts_detected": len(issues),
        "entropy_drift_caught": len(entropy_issue) > 0,
        "quantum_no_false_positive": quantum_ok,
    }


def bench_assembler() -> dict:
    """Assembler 去重叠基准测试。"""
    class Chunk:
        def __init__(self, sid, eid, text):
            self.id = f"chunk_{sid}"
            self.start_sentence = sid
            self.end_sentence = eid
            self.text = text

    chunks = [
        Chunk(0, 3, "A. B. C. D."),
        Chunk(2, 5, "C. D. E. F."),
    ]
    translations = [
        "甲␟乙␟丙␟丁",
        "丙␟丁␟戊␟己",
    ]

    result = assemble_translations(chunks, translations, strategy="first_lock")

    # 去重后应该是 6 个唯一句子（甲-己），丙和丁只出现一次
    dedup_ok = result.count("丙") == 1 and result.count("丁") == 1 and "甲" in result and "己" in result
    return {
        "input_chunks": 2,
        "dedup_effective": dedup_ok,
    }


# ═══════════════════════════════════════════════════════════
# 5. 全文 Benchmark 报告
# ═══════════════════════════════════════════════════════════

def run_full_benchmark(quick: bool = False):
    """运行完整基准测试。"""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    provider = cfg.get("provider", "custom")
    model = cfg.get("model", "deepseek-v4-pro")

    console.print()
    console.print("=" * 60)
    console.print(f"[bold]  Itranslation Benchmark Report[/bold]")
    console.print(f"  Provider: {provider}  |  Model: {model}")
    console.print("=" * 60)

    results = {
        "meta": {
            "provider": provider,
            "model": model,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "components": {},
        "translation": [],
        "summary": {},
    }

    # ── 4a. 组件基准 ──
    console.print("\n[bold cyan]── 组件基准测试 ──[/bold cyan]")

    results["components"]["chunker"] = bench_chunker()
    c = results["components"]["chunker"]
    console.print(f"  Chunker:   {c['sentences_detected']}/{c['expected_sentences']} 句 → {'✓' if c['sentence_accuracy'] else '✗'}")

    results["components"]["consistency"] = bench_consistency()
    c = results["components"]["consistency"]
    console.print(f"  Consistency: {c['drifts_detected']} 漂移检测 → {'✓' if c['entropy_drift_caught'] else '✗'} (entropy) {'✓' if c['quantum_no_false_positive'] else '✗'} (no false+)")

    results["components"]["assembler"] = bench_assembler()
    c = results["components"]["assembler"]
    console.print(f"  Assembler:  去重 → {'✓' if c['dedup_effective'] else '✗'}")

    # ── 4b. 翻译质量评估 ──
    if not quick:
        console.print("\n[bold cyan]── 翻译质量评估 (BLEU + LLM Judge) ──[/bold cyan]")

        api_key = cfg.get("api_key", "")
        if not api_key:
            console.print("  [yellow]⚠ 未配置 API Key，跳过翻译评估[/yellow]")
        else:
            total_bleu = 0
            total_chrf = 0
            total_overall = 0
            count = 0
            total_cost = 0

            for sample in BENCHMARK_CORPUS:
                sid = sample["id"]
                genre = sample["genre"]
                console.print(f"\n  [{sid}] {genre} ...")

                # 翻译
                translation, usage = translate_sample(sample["source"], genre)
                if not translation:
                    console.print(f"    [red]✗ 翻译失败: {usage.get('error', 'unknown')}[/red]")
                    continue

                # BLEU/chrF
                bleu_result = compute_bleu([sample["reference"]], translation)

                # LLM Judge
                judge_result = judge_translation(
                    sample["source"], translation, genre, sample["reference"]
                )

                # 成本
                pt = usage.get("prompt_tokens", 0)
                ct = usage.get("completion_tokens", 0)
                cost_val, _ = calc_cost(model, pt, ct)

                entry = {
                    "id": sid,
                    "genre": genre,
                    "translation": translation[:200],
                    "bleu": bleu_result.get("bleu"),
                    "chrf": bleu_result.get("chrf"),
                    "judge": judge_result,
                    "tokens": {"prompt": pt, "completion": ct},
                    "cost_usd": cost_val,
                }
                results["translation"].append(entry)

                # 打印
                bleu_str = f"BLEU={bleu_result.get('bleu', '?')}" if bleu_result.get('bleu') else "BLEU=N/A"
                chrf_str = f"chrF={bleu_result.get('chrf', '?')}" if bleu_result.get('chrf') else ""
                overall = judge_result.get("overall", "?") if isinstance(judge_result, dict) else "?"

                console.print(f"    {bleu_str}  {chrf_str}  Judge={overall}/10  ${cost_val:.4f}" if cost_val else f"    {bleu_str}  {chrf_str}  Judge={overall}/10")

                if bleu_result.get("bleu"):
                    total_bleu += bleu_result["bleu"]
                if bleu_result.get("chrf"):
                    total_chrf += bleu_result["chrf"]
                if isinstance(judge_result, dict) and "overall" in judge_result:
                    total_overall += judge_result["overall"]
                if cost_val:
                    total_cost += cost_val
                count += 1

            # 汇总
            if count > 0:
                results["summary"] = {
                    "samples": count,
                    "avg_bleu": round(total_bleu / count, 1) if total_bleu else None,
                    "avg_chrf": round(total_chrf / count, 1) if total_chrf else None,
                    "avg_judge_score": round(total_overall / count, 1) if total_overall else None,
                    "total_cost_usd": round(total_cost, 4),
                }

                console.print(f"\n[bold green]── 汇总 ──[/bold green]")
                s = results["summary"]
                console.print(f"  样本: {s['samples']}")
                console.print(f"  平均 BLEU: {s['avg_bleu']}")
                console.print(f"  平均 chrF: {s['avg_chrf']}")
                console.print(f"  平均 Judge 评分: {s['avg_judge_score']}/10")
                console.print(f"  总费用: ${s['total_cost_usd']:.4f}")

    # ── 保存报告 ──
    report_dir = PROJECT_ROOT / "reports" / "benchmark"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    console.print(f"\n[dim]报告已保存: {report_path}[/dim]")

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Itranslation Benchmark")
    parser.add_argument("--quick", action="store_true", help="仅组件基准（无需 API）")
    parser.add_argument("--model", help="指定模型", default=None)
    parser.add_argument("--provider", help="指定 provider", default=None)
    args = parser.parse_args()

    if args.model:
        cfg["model"] = args.model
    if args.provider:
        cfg["provider"] = args.provider

    run_full_benchmark(quick=args.quick)


if __name__ == "__main__":
    main()
