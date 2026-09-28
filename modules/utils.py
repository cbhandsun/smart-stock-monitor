"""股票代码格式化等通用工具函数"""


def format_symbol(code: str) -> str:
    """将纯数字股票代码转换为带交易所前缀的格式 (sh/sz)。

    规则：6 开头 → sh（上海），其余 → sz（深圳）
    如果已有前缀则原样返回。
    """
    code = code.strip()
    if code.startswith(("sh", "sz")):
        return code
    return f"sh{code}" if code.startswith("6") else f"sz{code}"
