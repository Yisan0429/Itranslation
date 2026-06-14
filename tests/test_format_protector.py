"""测试格式保护器的占位符保留率。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from format_protector import protect, restore, has_protected_content

# 包含代码块、公式、URL 的测试文本
TEST_TEXT = """
# Introduction

The function `calculate_loss()` computes the gradient:

```python
def calculate_loss(x, y):
    return (x - y) ** 2
```

The mathematical formulation is $$L(x, y) = \\frac{1}{N}\\sum_{i=1}^{N}(x_i - y_i)^2$$
where $N$ is the batch size.

For more information, visit https://example.com/docs.

## Key Points

- First, initialize the model with `model.load()`
- Second, run training with the formula $\\alpha = 0.001$
- Third, save checkpoints using `torch.save()`

The inline code `torch.nn.Module` is the base class.
"""


def test_format_protector():
    print("=" * 60)
    print("格式保护器测试")
    print("=" * 60)

    # 1. 检查是否有受保护内容
    assert has_protected_content(TEST_TEXT), "应检测到受保护内容"

    # 2. 保护
    protected, ph = protect(TEST_TEXT, verbose=True)
    assert len(ph) > 0, "应有占位符"

    print(f"\n占位符数量: {len(ph)}")
    for key, val in list(ph.items())[:5]:
        print(f"  {key} → {val[:60]}...")

    # 3. 验证原始内容不出现在保护后的文本中
    for original in ph.values():
        if len(original) > 5:  # 短字符串可能偶然匹配
            assert original not in protected, \
                f"原始内容应被替换: {original[:50]}..."

    print("\n✓ 原始内容已全部替换")

    # 4. 模拟翻译（什么都不改，直接还原）
    restored = restore(protected, ph, verbose=True)
    assert len(restored) == len(TEST_TEXT), \
        f"长度应一致，实际: {len(restored)} vs {len(TEST_TEXT)}"

    # 5. 验证关键内容完整
    checks = [
        "```python",
        "def calculate_loss",
        "$$L(x, y)",
        "https://example.com/docs",
        "`torch.nn.Module`",
    ]
    for check in checks:
        assert check in restored, f"缺失: {check}"

    print("\n✓ 所有内容完整保留")

    # 6. 测试空文本
    empty, empty_ph = protect("", verbose=False)
    assert empty == "" and not empty_ph
    print("\n✓ 空文本处理正常")

    # 7. 测试纯文本（无保护内容）
    plain = "This is a simple sentence without any code or math."
    plain_protected, plain_ph = protect(plain, verbose=False)
    assert plain == plain_protected
    print("✓ 纯文本不变")

    print("\n" + "=" * 60)
    print("✅ 全部测试通过")
    print("=" * 60)


if __name__ == "__main__":
    test_format_protector()
