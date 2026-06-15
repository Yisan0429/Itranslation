"""
Itranslation 十项测试语料库。

源文位于 input/test/ 目录下，可直接用 CLI 翻译。
本模块提供参考译文和测试元数据，供 benchmark 使用。

用法:
    from test_corpus import CORPUS, get_corpus_stats
    # CLI: uv run python translate_book.py input/test/01-literature-hemingway.txt --genre literature
"""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_TEST_DIR = _PROJECT_ROOT / "input" / "test"


def _load_source(filename: str) -> str:
    """从 input/test/ 加载源文。"""
    path = _TEST_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


CORPUS = [
    # ═══ 1. 文学 — 海明威风格 ═══
    {
        "id": "lit_hemingway",
        "genre": "literature",
        "file": "01-literature-hemingway.txt",
        "reference": (
            "那年夏末，我们住在村里一栋房子里，从那里可以望见河对岸的平原和群山。"
            "河床里铺着卵石和大石块，在阳光下又干又白，"
            "河水清澈，在河道里湍急地流淌，泛着蓝色。"
        ),
        "tests": ["节奏感：流水句节奏", "意象保留：pebbles/boulders/clear/swiftly/blue", "无翻译腔"],
    },
    # ═══ 2. 文学 — 对话 ═══
    {
        "id": "lit_dialogue",
        "genre": "literature",
        "file": "02-literature-dialogue.txt",
        "reference": (
            "\u201c你要是不想去，就不用去，\u201d她轻声说，目光没有看他。"
            "\u201c但我觉得你以后会后悔的。也许不是今天。但总有一天。等到什么都来不及的时候。\u201d"
        ),
        "tests": ["对话自然度", "引号处理", "短句节奏保留"],
    },
    # ═══ 3. 哲学 — 术语密集 ═══
    {
        "id": "phil_terminology",
        "genre": "philosophy",
        "file": "03-philosophy-terminology.txt",
        "reference": (
            "现象学还原——即悬置——将我们对世界的自然态度悬搁起来。"
            "它并不否认外部世界的存在，而是将其加括号，"
            "使我们能够考察意识结构在活生生的经验中呈现自身的样态。"
            "意向对象并非事物本身，而是被意向指向的事物。"
        ),
        "tests": ["术语一致性：epoch\u00e9/reduction/noema", "长句拆分", "学术语气"],
    },
    # ═══ 4. 自然科学 — 数据+单位 ═══
    {
        "id": "sci_data",
        "genre": "natural_science",
        "file": "04-science-data.txt",
        "reference": (
            "反应在 37\u00b0C 下于磷酸盐缓冲液（pH 7.4）中进行 24 小时。"
            "使用分光光度计在 340 nm 处测定酶活性。"
            "在最优条件下，Km 值测定为 2.3 \u00b1 0.1 mM，"
            "Vmax 达到 45.7 \u03bcmol/min/mg。所有测量均重复三次（n=3）。"
        ),
        "tests": ["数据保护：37\u00b0C/pH/340nm/2.3\u00b10.1mM", "单位符号不变", "术语标准译法"],
    },
    # ═══ 5. 自然科学 — CRISPR ═══
    {
        "id": "sci_concept",
        "genre": "natural_science",
        "file": "05-science-crispr.txt",
        "reference": (
            "CRISPR-Cas9 是一种基因组编辑工具，利用向导 RNA 将 Cas9 核酸酶引导至特定 DNA 序列，"
            "在该处产生双链断裂。细胞的天然修复机制随后通过非同源末端连接引入小的插入或缺失，"
            "或通过同源定向修复利用供体模板进行精确编辑。"
        ),
        "tests": ["专有名词保留：CRISPR-Cas9/Cas9", "术语准确", "概念完整性"],
    },
    # ═══ 6. 社会科学 — 引用+统计 ═══
    {
        "id": "soc_citation",
        "genre": "social_science",
        "file": "06-social-science-citation.txt",
        "reference": (
            "根据 Chetty 等人（2014）的一项纵向研究，"
            "代际收入流动性在美国各地差异显著。"
            "父母处于底层五分位的子女进入顶层五分位的概率，"
            "从夏洛特的 4.4% 到圣何塞的 12.9% 不等。"
            "作者总结道：地理因素很重要，其影响方式对美国梦叙事构成了挑战。"
        ),
        "tests": ["引用保留：Chetty et al. (2014)", "数据精确：4.4%/12.9%/quintile", "引号处理"],
    },
    # ═══ 7. 技术文档 — 代码+命令 ═══
    {
        "id": "tech_commands",
        "genre": "technical",
        "file": "07-technical-commands.txt",
        "reference": (
            "要初始化数据库，请运行：\n"
            "```bash\n"
            "python manage.py migrate --database=production\n"
            "```\n"
            "位于 `/etc/app/config.yaml` 的配置文件必须包含"
            "格式为 `postgresql://user:***@localhost:5432/dbname` 的有效 `DATABASE_URL`。"
            "切勿在 `settings.py` 中硬编码凭据——请使用环境变量代替。"
        ),
        "tests": ["代码块保护：```bash```", "路径保护：/etc/app/config.yaml", "文件名保护：settings.py"],
    },
    # ═══ 8. 混合格式 — 公式+列表+链接 ═══
    {
        "id": "mixed_formats",
        "genre": "natural_science",
        "file": "08-mixed-formats.txt",
        "reference": (
            "压强与体积的关系由理想气体状态方程给出：\n"
            "$$PV = nRT$$\n"
            "其中 P 为压强（Pa），V 为体积（m\u00b3），n 为摩尔数，"
            "R 为气体常数（8.314 J/mol\u00b7K），T 为温度（K）。\n\n"
            "关键假设：\n"
            "- 气体粒子体积可忽略\n"
            "- 无分子间作用力\n"
            "- 碰撞为完全弹性碰撞\n\n"
            "更多细节参见 https://en.wikipedia.org/wiki/Kinetic_theory_of_gases"
        ),
        "tests": ["公式保护：$$PV=nRT$$", "列表格式保留", "URL 完整"],
    },
    # ═══ 9. 长难句 — 嵌套从句 ═══
    {
        "id": "complex_syntax",
        "genre": "literature",
        "file": "09-complex-syntax.txt",
        "reference": (
            "就是那种下午——让你一时忘却，无论多么短暂，"
            "花园围墙之外的世界并非诗人们所说的那样，"
            "是一个可以静思冥想、微风拂面的地方，"
            "而是一团翻腾的混乱：义务、截止日期、未付的账单，"
            "迟早要你正视它们。"
        ),
        "tests": ["5 层嵌套从句拆分", "插入语处理", "流水句自然度"],
    },
    # ═══ 10. 专有名词密集 ═══
    {
        "id": "proper_nouns",
        "genre": "social_science",
        "file": "10-proper-nouns.txt",
        "reference": (
            "马克斯\u00b7普朗克进化人类学研究所的陈莎拉博士于 2024 年 3 月 12 日"
            "在亚的斯亚贝巴举行的第十五届国际人类起源大会上展示了她的研究成果。"
            "她的团队对西伯利亚丹尼索瓦洞穴线粒体 DNA 的分析表明，"
            "尼安德特人和丹尼索瓦人在 5 万至 10 万年前与智人多次杂交，"
            "这对 Stringer 和 Andrews（1988）首次提出的单一起源假说构成了挑战。"
        ),
        "tests": ["人名：Sarah Chen→陈莎拉", "机构名标准译法", "地名标准译名", "学术引用保留", "数字格式"],
    },
]

# 回填 source（从文件读取）
for entry in CORPUS:
    if "file" in entry and not entry.get("source"):
        entry["source"] = _load_source(entry["file"])

GENRE_DISTRIBUTION = {
    "literature": 3,
    "philosophy": 1,
    "natural_science": 3,
    "social_science": 2,
    "technical": 1,
}

TEST_COVERAGE = {
    "基础翻译": ["lit_hemingway", "phil_terminology", "sci_concept"],
    "数据+单位保护": ["sci_data", "mixed_formats"],
    "格式保护": ["tech_commands", "mixed_formats"],
    "对话自然度": ["lit_dialogue"],
    "长句拆分": ["complex_syntax", "phil_terminology"],
    "专有名词": ["proper_nouns", "soc_citation"],
    "引用+统计": ["soc_citation"],
    "公式+代码": ["tech_commands", "mixed_formats"],
}


def get_corpus_stats() -> str:
    lines = [
        "Test Corpus Statistics",
        "======================",
        f"Total samples: {len(CORPUS)}",
        f"Files: input/test/",
        "",
        "Genre Distribution:",
    ]
    for genre, count in sorted(GENRE_DISTRIBUTION.items()):
        lines.append(f"  {genre}: {count}")
    lines.append("")
    lines.append("Test Coverage:")
    for area, samples in TEST_COVERAGE.items():
        lines.append(f"  {area}: {len(samples)} samples")
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_corpus_stats())
    print()
    for c in CORPUS:
        src_len = len(c.get("source", ""))
        ref_len = len(c["reference"])
        print(f"  [{c['id']}] {c['genre']}: {src_len} chars → {ref_len} chars  ({c['file']})")
