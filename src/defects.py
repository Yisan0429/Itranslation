"""
译文问题族注册表 — 跨书复用的翻译质量缺陷模式。

借鉴 LifeBook 的 defect family 理念：每个问题不是孤立 bug，
而是可能系统性复现的"族"——定义症状、检测正则、风险、修复模式。

用法:
    from defects import DEFECT_FAMILIES, get_family
"""

DEFECT_FAMILIES = [
    {
        "id": "passive_overuse",
        "name": "被字句过度使用",
        "severity": "P2",
        "symptom": "中文译文中出现不必要的被动语态（被/给/让/叫），英文原文并非强制被动",
        "detection": [
            (r"被\S{1,6}(了|过|的|，|。)", "被字句"),
            (r"给\S{1,6}(了|过|的|，|。)", "给字句（被动）"),
        ],
        "risk": "译文读起来有翻译腔，中文偏好主动表达",
        "fix": "改为主动句式：把字句、话题-陈述结构，或直接省略施事",
        "example": "✗ 书被他放在了桌子上 → ✓ 他把书放在了桌子上",
    },
    {
        "id": "long_modifier",
        "name": "长定语（前置修饰语过长）",
        "severity": "P2",
        "symptom": "中文句子中前置修饰语超过 20 字，读起来头重脚轻",
        "detection": [
            (r"的[\u4e00-\u9fff]{20,}的", "长定语链"),
            (r"一个[\u4e00-\u9fff]{15,}的", "长修饰+的"),
        ],
        "risk": "读者需要回读才能理解句子主干",
        "fix": "拆分为流水句：提取中心语前置，修饰部分后置为分句",
        "example": "✗ 一个有着悠久历史和丰富文化底蕴的城市 → ✓ 这座城市历史悠久，文化底蕴丰厚",
    },
    {
        "id": "calque_in_case_of",
        "name": "在...的情况下（硬译句式）",
        "severity": "P3",
        "symptom": "英文 in the case of / when / if 被机械译为'在...的情况下'",
        "detection": [
            (r"在.{2,20}的情况下", "在...的情况下"),
        ],
        "risk": "译文臃肿，中文有更简洁的表达方式",
        "fix": "用'...时''一旦...'或直接省略",
        "example": "✗ 在发生火灾的情况下 → ✓ 一旦发生火灾",
    },
    {
        "id": "calque_shi_de",
        "name": "是...的（强调句式滥用）",
        "severity": "P3",
        "symptom": "英文 it is ... that / what ... is 被机械译为'是...的'结构",
        "detection": [
            (r"是[\u4e00-\u9fff]{4,30}的[，。]", "是...的结构"),
        ],
        "risk": "译文生硬，连续使用破坏节奏",
        "fix": "省略'是...的'，用更自然的中文句式",
        "example": "✗ 这个问题是可以解决的 → ✓ 这个问题能解决",
    },
    {
        "id": "noun_heavy",
        "name": "名词化风格（抽象名词堆砌）",
        "severity": "P2",
        "symptom": "英文抽象名词（-tion/-ity/-ness）被直译为中文名词，而非动词化表达",
        "detection": [
            (r"的(进行|实现|完成|开展|实施|产生|发生|出现)", "名词化动词"),
            (r"性[，。]", "X性结尾"),
        ],
        "risk": "学术类译文尤其严重，读起来像翻译而不是写作",
        "fix": "把名词恢复为动词：'进行讨论'→'讨论'，'实现增长'→'增长'",
        "example": "✗ 对数据进行处理 → ✓ 处理数据",
    },
    {
        "id": "pronoun_unclear",
        "name": "代词指代不清",
        "severity": "P1",
        "symptom": "英文 it/they/this/that 被直译为'它/它们/这/那'，中文指代不明",
        "detection": [
            (r"[^，。；：]{0,10}(它|它们|这|那)[^，。；：]{0,10}", "模糊代词"),
        ],
        "risk": "读者不知道指代什么，影响理解",
        "fix": "还原被指代的名词，或用'这一定义''此方法'等明确指代",
        "example": "✗ 它表明了这一观点 → ✓ 这一数据证实了前述观点",
    },
    {
        "id": "literal_idiom",
        "name": "习语硬译",
        "severity": "P2",
        "symptom": "英文习语被逐字翻译而非替换为中文等价表达",
        "detection": [
            (r"在.{2,8}的尽头[，。]", "at the end of the day 等"),
            (r"把.{2,8}放在.{2,8}", "put X into perspective 等"),
            (r"从.{2,10}的角度来看", "from X's perspective (可简化为'在X看来')"),
        ],
        "risk": "中文读者无法理解原意，或产生误解",
        "fix": "找到中文对应的习语或意译",
        "example": "✗ 从长期的角度来看 → ✓ 长远来看",
    },
    {
        "id": "sentence_too_long",
        "name": "句子过长",
        "severity": "P3",
        "symptom": "中文单句超过 80 字符，包含 3 个以上逗号分隔的从句",
        "detection": [
            (r"[^。！？\n]{80,}", "超长句"),
        ],
        "risk": "读者跟丢句子主语，需要回读",
        "fix": "在逻辑断点处拆分：转折/因果/并列/递进",
        "example": "✗ 一句话 80+ 字 → 拆成两到三句",
    },
    {
        "id": "term_inconsistency",
        "name": "术语不一致",
        "severity": "P1",
        "symptom": "同一英文术语在全书中有多个中文译法（由 consistency model 检测）",
        "detection": [],
        "risk": "读者困惑，学术著作尤为致命",
        "fix": "统一为 glossary 中的首选译法",
    },
    {
        "id": "bare_source_word",
        "name": "裸露源语词",
        "severity": "P1",
        "symptom": "英文人名/地名/术语以拉丁字母直接出现在中文正文中",
        "detection": [
            (r"[\u4e00-\u9fff][A-Z][a-z]{2,}[\u4e00-\u9fff，。]", "中英混杂"),
        ],
        "risk": "破坏阅读流畅性",
        "fix": "翻译或音译为目标语形式",
        "example": "✗ 他去了 Paris → ✓ 他去了巴黎",
    },
]


def get_family(family_id: str) -> dict | None:
    """按 ID 查找问题族。"""
    for f in DEFECT_FAMILIES:
        if f["id"] == family_id:
            return f
    return None
