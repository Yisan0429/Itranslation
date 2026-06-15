"""
Itranslation 十项测试语料库 — 覆盖所有体裁和边界情况。

每项含: id, genre, source, reference, tests(测试目标)
用法:
    from test_corpus import CORPUS
    # 或作为 benchmark 的替代语料库
    uv run python src/benchmark.py --corpus test_corpus
"""

CORPUS = [
    # ═══ 1. 文学 — 海明威风格短句 ═══
    {
        "id": "lit_hemingway",
        "genre": "literature",
        "source": (
            "In the late summer of that year we lived in a house in a village "
            "that looked across the river and the plain to the mountains. "
            "In the bed of the river there were pebbles and boulders, dry and white in the sun, "
            "and the water was clear and swiftly moving and blue in the channels."
        ),
        "reference": (
            "那年夏末，我们住在村里一栋房子里，从那里可以望见河对岸的平原和群山。"
            "河床里铺着卵石和大石块，在阳光下又干又白，"
            "河水清澈，在河道里湍急地流淌，泛着蓝色。"
        ),
        "tests": [
            "节奏感：原文三个长句，中文是否保持流水句节奏",
            "意象保留：pebbles/boulders/clear/swiftly/blue 是否准确传达",
            "无翻译腔：不应该出现'在...里''被...'等硬译结构",
        ],
    },
    # ═══ 2. 文学 — 对话 ═══
    {
        "id": "lit_dialogue",
        "genre": "literature",
        "source": (
            '"You don\'t have to go if you don\'t want to," she said quietly, '
            'not looking at him. "But I think you\'d regret it later. Not today, maybe. '
            'But someday. When it\'s too late to do anything about it."'
        ),
        "reference": (
            '"你要是不想去，就不用去，"她轻声说，目光没有看他。'
            '"但我觉得你以后会后悔的。也许不是今天。但总有一天。等到什么都来不及的时候。"'
        ),
        "tests": [
            "对话自然度：中文是否读起来像真实对话",
            "引号处理：嵌套引号是否正确",
            "节奏保留：原文短句节奏是否保持（不是今天。但总有一天。）",
        ],
    },
    # ═══ 3. 哲学 — 术语密集 ═══
    {
        "id": "phil_terminology",
        "genre": "philosophy",
        "source": (
            "The phenomenological reduction, or epoché, suspends our natural attitude toward the world. "
            "It does not deny the existence of the external world but brackets it, "
            "allowing us to examine the structures of consciousness as they present themselves "
            "in lived experience. The noema is not the object itself but the object as intended."
        ),
        "reference": (
            "现象学还原——即悬置——将我们对世界的自然态度悬搁起来。"
            "它并不否认外部世界的存在，而是将其加括号，"
            "使我们能够考察意识结构在活生生的经验中呈现自身的样态。"
            "意向对象并非事物本身，而是被意向指向的事物。"
        ),
        "tests": [
            "术语一致性：epoché/reduction/noema 是否统一译法",
            "长句处理：原文第四句嵌套是否被正确拆分",
            "哲学语气：是否保持了学术严谨而非口语化",
        ],
    },
    # ═══ 4. 自然科学 — 数据+单位 ═══
    {
        "id": "sci_data",
        "genre": "natural_science",
        "source": (
            "The reaction was carried out at 37°C for 24 hours in a phosphate buffer (pH 7.4). "
            "The enzyme activity was measured at 340 nm using a spectrophotometer. "
            "Under optimal conditions, the Km value was determined to be 2.3 ± 0.1 mM "
            "and Vmax reached 45.7 μmol/min/mg. All measurements were performed in triplicate (n=3)."
        ),
        "reference": (
            "反应在 37°C 下于磷酸盐缓冲液（pH 7.4）中进行 24 小时。"
            "使用分光光度计在 340 nm 处测定酶活性。"
            "在最优条件下，Km 值测定为 2.3 ± 0.1 mM，"
            "Vmax 达到 45.7 μmol/min/mg。所有测量均重复三次（n=3）。"
        ),
        "tests": [
            "数据保护：37°C/pH 7.4/340 nm/2.3 ± 0.1 mM/45.7 μmol/min/mg 必须原样保留",
            "单位符号：mM/μmol/min/mg 是否不变",
            "术语准确：phosphate buffer/Km/Vmax/spectrophotometer 是否标准译法",
        ],
    },
    # ═══ 5. 自然科学 — 概念解释 ═══
    {
        "id": "sci_concept",
        "genre": "natural_science",
        "source": (
            "CRISPR-Cas9 is a genome editing tool that uses a guide RNA to direct "
            "the Cas9 nuclease to a specific DNA sequence, where it creates a double-strand break. "
            "The cell's natural repair mechanisms then either introduce small insertions or deletions "
            "via non-homologous end joining, or use a donor template for precise edits "
            "via homology-directed repair."
        ),
        "reference": (
            "CRISPR-Cas9 是一种基因组编辑工具，利用向导 RNA 将 Cas9 核酸酶引导至特定 DNA 序列，"
            "在该处产生双链断裂。细胞的天然修复机制随后通过非同源末端连接引入小的插入或缺失，"
            "或通过同源定向修复利用供体模板进行精确编辑。"
        ),
        "tests": [
            "专有名词：CRISPR-Cas9/Cas9 必须原样保留",
            "术语准确：guide RNA/双链断裂/非同源末端连接/同源定向修复",
            "概念完整：两步修复机制是否都正确传达",
        ],
    },
    # ═══ 6. 社会科学 — 引用+统计 ═══
    {
        "id": "soc_citation",
        "genre": "social_science",
        "source": (
            "According to a longitudinal study by Chetty et al. (2014), "
            "intergenerational income mobility varies substantially across the United States. "
            "The probability that a child born to parents in the bottom quintile reaches the top quintile "
            "ranges from 4.4% in Charlotte to 12.9% in San Jose. "
            "\"Geography matters,\" the authors conclude, \"in ways that challenge the American Dream narrative.\""
        ),
        "reference": (
            "根据 Chetty 等人（2014）的一项纵向研究，"
            "代际收入流动性在美国各地差异显著。"
            "父母处于底层五分位的子女进入顶层五分位的概率，"
            "从夏洛特的 4.4% 到圣何塞的 12.9% 不等。"
            '作者总结道：\u201c地理因素很重要，其影响方式对美国梦叙事构成了挑战。\u201d'
        ),
        "tests": [
            "引用保留：Chetty et al. (2014) 是否原样保留",
            "数据精确：4.4%/12.9%/bottom quintile/top quintile 是否准确",
            "引号嵌套：英文双引号内的直接引用是否正确转换",
        ],
    },
    # ═══ 7. 技术文档 — 代码+命令 ═══
    {
        "id": "tech_commands",
        "genre": "technical",
        "source": (
            "To initialize the database, run:\n"
            "```bash\n"
            "python manage.py migrate --database=production\n"
            "```\n"
            "The configuration file at `/etc/app/config.yaml` must contain "
            "a valid `DATABASE_URL` in the format `postgresql://user:pass@localhost:5432/dbname`. "
            "Do NOT hardcode credentials in `settings.py` — use environment variables instead."
        ),
        "reference": (
            "要初始化数据库，请运行：\n"
            "```bash\n"
            "python manage.py migrate --database=production\n"
            "```\n"
            "位于 `/etc/app/config.yaml` 的配置文件必须包含"
            "格式为 `postgresql://user:pass@localhost:5432/dbname` 的有效 `DATABASE_URL`。"
            "切勿在 `settings.py` 中硬编码凭据——请使用环境变量代替。"
        ),
        "tests": [
            "代码块保护：```bash 代码块必须原样保留",
            "路径/URL 保护：/etc/app/config.yaml/postgresql://... 必须不变",
            "文件名保护：settings.py/DATABASE_URL 必须保留原文大小写",
            "格式保护器验证：占位符 → 翻译 → 还原是否完整",
        ],
    },
    # ═══ 8. 混合格式 — 公式+引用+列表 ═══
    {
        "id": "mixed_formats",
        "genre": "natural_science",
        "source": (
            "The relationship between pressure and volume is given by the ideal gas law: "
            "$$PV = nRT$$\n"
            "where P is pressure (Pa), V is volume (m³), n is the number of moles, "
            "R is the gas constant (8.314 J/mol·K), and T is temperature (K).\n\n"
            "Key assumptions:\n"
            "- Gas particles have negligible volume\n"
            "- No intermolecular forces\n"
            "- Collisions are perfectly elastic\n\n"
            "For further details, see [Kinetic Theory of Gases](https://en.wikipedia.org/wiki/Kinetic_theory_of_gases)."
        ),
        "reference": (
            "压强与体积的关系由理想气体状态方程给出：\n"
            "$$PV = nRT$$\n"
            "其中 P 为压强（Pa），V 为体积（m³），n 为摩尔数，"
            "R 为气体常数（8.314 J/mol·K），T 为温度（K）。\n\n"
            "关键假设：\n"
            "- 气体粒子体积可忽略\n"
            "- 无分子间作用力\n"
            "- 碰撞为完全弹性碰撞\n\n"
            "更多细节参见[气体动理论](https://en.wikipedia.org/wiki/Kinetic_theory_of_gases)。"
        ),
        "tests": [
            "公式保护：$$PV = nRT$$ 是否原样保留（含 $$ 定界符）",
            "列表保护：markdown 列表项是否保持格式",
            "URL 保护：维基百科链接是否完整",
            "单位符号：Pa/m³/J/mol·K 是否不变",
        ],
    },
    # ═══ 9. 长难句 — 嵌套从句 ═══
    {
        "id": "complex_syntax",
        "genre": "literature",
        "source": (
            "It was the kind of afternoon that made you forget, however briefly, "
            "that the world outside the garden walls was not, as the poets would have it, "
            "a place of quiet contemplation and gentle breezes, "
            "but rather a churning chaos of obligations and deadlines and unpaid bills "
            "that would, sooner or later, demand to be acknowledged."
        ),
        "reference": (
            "就是那种下午——让你一时忘却，无论多么短暂，"
            "花园围墙之外的世界并非诗人们所说的那样，"
            "是一个可以静思冥想、微风拂面的地方，"
            "而是一团翻腾的混乱：义务、截止日期、未付的账单，"
            "迟早要你正视它们。"
        ),
        "tests": [
            "长句拆分：英文一句话嵌套 5 层，中文是否拆成合理的流水句",
            "插入语处理：however briefly/as the poets would have it 的中文表达",
        ],
    },
    # ═══ 10. 专有名词密集 — 人名/地名/机构 ═══
    {
        "id": "proper_nouns",
        "genre": "social_science",
        "source": (
            "Dr. Sarah Chen of the Max Planck Institute for Evolutionary Anthropology "
            "presented her findings at the 15th International Conference on Human Origins "
            "in Addis Ababa on March 12, 2024. Her team's analysis of mitochondrial DNA "
            "from the Denisova Cave in Siberia suggests that Neanderthals and Denisovans "
            "interbred with Homo sapiens at multiple points between 50,000 and 100,000 years ago, "
            "challenging the single-origin hypothesis first proposed by Stringer and Andrews (1988)."
        ),
        "reference": (
            "马克斯·普朗克进化人类学研究所的陈莎拉博士于 2024 年 3 月 12 日"
            "在亚的斯亚贝巴举行的第十五届国际人类起源大会上展示了她的研究成果。"
            "她的团队对西伯利亚丹尼索瓦洞穴线粒体 DNA 的分析表明，"
            "尼安德特人和丹尼索瓦人在 5 万至 10 万年前与智人多次杂交，"
            "这对 Stringer 和 Andrews（1988）首次提出的单一起源假说构成了挑战。"
        ),
        "tests": [
            "人名处理：Sarah Chen → 陈莎拉（华人姓氏正确还原）",
            "机构名：Max Planck Institute 标准译法",
            "地名：Addis Ababa/Denisova Cave/Siberia 标准译名",
            "学术引用：Stringer and Andrews (1988) 是否原样保留",
            "数字格式：March 12, 2024/50,000/100,000 是否正确",
        ],
    },
]

# 体裁分布统计
GENRE_DISTRIBUTION = {
    "literature": 3,     # lit_hemingway, lit_dialogue, complex_syntax
    "philosophy": 1,     # phil_terminology
    "natural_science": 3,  # sci_data, sci_concept, mixed_formats
    "social_science": 2,  # soc_citation, proper_nouns
    "technical": 1,      # tech_commands
}

# 测试覆盖矩阵
TEST_COVERAGE = {
    "基础翻译":         ["lit_hemingway", "phil_terminology", "sci_concept"],
    "数据+单位保护":    ["sci_data", "mixed_formats"],
    "格式保护":         ["tech_commands", "mixed_formats"],
    "对话自然度":       ["lit_dialogue"],
    "长句拆分":         ["complex_syntax", "phil_terminology"],
    "专有名词":         ["proper_nouns", "soc_citation"],
    "引用+统计":        ["soc_citation"],
    "公式+代码":        ["tech_commands", "mixed_formats"],
}


def get_corpus_stats() -> str:
    """生成语料库统计报告。"""
    lines = [
        "Test Corpus Statistics",
        "======================",
        f"Total samples: {len(CORPUS)}",
        f"Total source chars: {sum(len(c['source']) for c in CORPUS):,}",
        f"Total reference chars: {sum(len(c['reference']) for c in CORPUS):,}",
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
        print(f"  [{c['id']}] {c['genre']}: {len(c['source'])} chars → {len(c['reference'])} chars")
