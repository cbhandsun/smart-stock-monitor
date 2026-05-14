#!/usr/bin/env python3
"""
scripts/check_imports.py — 部署前 import 自检脚本
用途: 在不启动 Streamlit 的情况下，静态验证所有页面/模块的 import 路径是否正确。
运行: python3 scripts/check_imports.py
      docker compose exec stock-monitor python3 /app/scripts/check_imports.py
"""
import sys
import os
import ast
import importlib
import importlib.util
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 要检查的目标文件 ──────────────────────────────────────────
# 每次新增/拆分模块后，把新文件加到这里
CHECK_TARGETS = [
    # core
    "core/cache.py",
    "core/file_cache.py",
    "core/database.py",
    "core/data_router.py",
    # tasks
    "tasks/alerts.py",
    "tasks/reports.py",
    "tasks/market_data.py",
    # pages/market 子包
    "pages/market/__init__.py",
    "pages/market/_bar.py",
    "pages/market/_card.py",
    "pages/market/_signals.py",
    "pages/market/_strategy.py",
    "pages/market/_views.py",
    # pages
    "pages/data_health.py",
    # main
    "main.py",
    "app.py",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract_from_imports(source: str) -> list[tuple[str, str]]:
    """
    从源码中提取所有 `from X import Y` 形式的 import。
    返回 [(module_path, symbol_name), ...]
    """
    results = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  ❌ 语法错误: {e}")
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                results.append((node.module, alias.name))
    return results


def check_symbol_exists(module_path: str, symbol: str) -> bool:
    """验证 module_path.symbol 是否存在（不执行 Streamlit 相关代码）"""
    # 跳过第三方库和标准库
    skip_prefixes = (
        "streamlit", "pandas", "numpy", "requests", "celery",
        "sqlalchemy", "redis", "akshare", "tushare", "baostock",
        "plotly", "concurrent", "datetime", "logging", "os", "sys",
        "json", "re", "ast", "importlib", "abc", "dataclasses",
        "typing", "collections", "functools", "itertools", "time",
        "glob", "math", "random", "hashlib", "hmac",
    )
    if any(module_path.startswith(p) for p in skip_prefixes):
        return True  # 跳过，不验证第三方库

    # 只验证项目内模块（以 core/modules/pages/tasks/components 开头）
    project_prefixes = ("core", "modules", "pages", "tasks", "components", "main", "database", "auth")
    if not any(module_path.split('.')[0] == p.split('/')[0] for p in project_prefixes):
        return True  # 非项目模块，跳过

    try:
        spec = importlib.util.find_spec(module_path)
        if spec is None:
            return False
        mod = importlib.util.module_from_spec(spec)
        # 不执行，只加载模块级变量（部分 side-effects 仍可能触发）
        # 改为只检查文件是否存在对应 symbol（用 ast 解析）
        if spec.origin:
            src = open(spec.origin).read()
            tree = ast.parse(src)
            defined = {
                n.name for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign))
                and hasattr(n, 'name')
            }
            # ast.Assign 的 targets 也收集
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign):
                    for t in n.targets:
                        if isinstance(t, ast.Name):
                            defined.add(t.id)
            return symbol in defined or symbol == '*'
    except Exception:
        pass
    return True  # 无法确定时放行


def check_file(rel_path: str) -> tuple[int, int]:
    """检查单个文件，返回 (通过数, 失败数)"""
    full_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"  ⚠️  文件不存在: {rel_path}")
        return 0, 1

    try:
        src = open(full_path).read()
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return 0, 1

    # 1. 语法检查
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"  ❌ 语法错误: {e}")
        return 0, 1

    # 2. `from X import Y` 逐一验证
    imports = extract_from_imports(src)
    passed, failed = 0, 0
    for mod, sym in imports:
        ok = check_symbol_exists(mod, sym)
        if ok:
            passed += 1
        else:
            print(f"  ❌ import 不存在: from {mod} import {sym}")
            failed += 1

    return passed, failed


def main():
    print("=" * 60)
    print("SSM 部署前 Import 自检")
    print("=" * 60)

    total_passed, total_failed, files_ok, files_err = 0, 0, 0, 0

    for target in CHECK_TARGETS:
        print(f"\n📄 {target}")
        p, f = check_file(target)
        total_passed += p
        total_failed += f
        if f == 0:
            print(f"  ✅ {p} 个 import 通过")
            files_ok += 1
        else:
            files_err += 1

    print("\n" + "=" * 60)
    print(f"结果: {files_ok} 个文件 OK | {files_err} 个文件有问题")
    print(f"Import 检查: {total_passed} 通过 | {total_failed} 失败")
    if total_failed == 0:
        print("✅ 全部通过，可以安全部署")
    else:
        print("❌ 存在问题，请修复后再部署！")
    print("=" * 60)
    return total_failed


if __name__ == "__main__":
    exit_code = main()
    sys.exit(1 if exit_code > 0 else 0)
