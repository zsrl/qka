"""从源码 docstring 自动更新 skills/references API 签名

用法:
    python tools/generate_api_ref.py

流程:
    1. 扫描 qka/core/*.py
    2. 用 ast 提取类/方法/参数/返回值/docstring
    3. 更新 skills/qka/references/*.md 的 AUTO 区

只覆写 <!-- AUTO -->...<!-- /AUTO --> 之间的内容，手写部分不动。
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

QKA_CORE = Path(__file__).resolve().parent.parent / "qka" / "core"
SKILLS_REF = Path(__file__).resolve().parent.parent / "skills" / "qka" / "references"

# 文件映射：模块名 → 对应的 reference 文件名
MODULE_REF_MAP = {
    "data.py": "data.md",
    "strategy.py": "strategy.md",
    "broker.py": "broker.md",
    "sizing.py": "sizing.md",
    "backtest.py": "backtest.md",
    "report.py": None,  # report 无类，全手写
    "accessor.py": "strategy.md",  # DataAccessor 合到 strategy 里
}


def parse_docstring_summary(docstring: str) -> str:
    """提取 docstring 的第一段作为摘要"""
    if not docstring:
        return ""
    lines = docstring.strip().split("\n")
    result = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith(("Args:", "Returns:", "Attributes:", "Example", "Note:", "Raises:")):
            break
        result.append(line)
    summary = " ".join(result).strip()
    if len(summary) > 200:
        summary = summary[:200] + "..."
    return summary


def get_return_type(node: ast.FunctionDef) -> str:
    """提取返回类型注解"""
    if node.returns:
        return ast.unparse(node.returns)
    doc = ast.get_docstring(node)
    if doc:
        m = re.search(r"Returns:\s*(.*)", doc, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def get_arg_defaults(node: ast.FunctionDef) -> Dict[str, str]:
    """提取参数默认值"""
    defaults = {}
    pos_defaults = node.args.defaults
    pos_args = node.args.args[-len(pos_defaults):] if pos_defaults else []
    for arg, default in zip(pos_args, pos_defaults):
        defaults[arg.arg] = ast.unparse(default)
    kw_defaults = node.args.kw_defaults
    kw_args = node.args.kwonlyargs
    for arg, default in zip(kw_args, kw_defaults):
        if default is not None:
            defaults[arg.arg] = ast.unparse(default)
    return defaults


def format_method_signature(class_name: str, node: ast.FunctionDef) -> str:
    """格式化成 markdown 签名行"""
    method_name = node.name
    if method_name == "__init__":
        display_name = f"{class_name}"
    else:
        display_name = f"{class_name}.{method_name}"

    args = []
    defaults = get_arg_defaults(node)

    func_args = [a for a in node.args.args if a.arg != "self"]

    for arg in func_args:
        arg_name = arg.arg
        type_hint = ast.unparse(arg.annotation) if arg.annotation else ""
        default = defaults.get(arg_name, "")

        parts = [f"**{arg_name}**"]
        if type_hint:
            parts.append(f"`{type_hint}`")
        if default:
            parts.append(f"= {default}")

        args.append(" ".join(parts))

    for arg in node.args.kwonlyargs:
        arg_name = arg.arg
        type_hint = ast.unparse(arg.annotation) if arg.annotation else ""
        default = defaults.get(arg_name, "")

        parts = [f"**{arg_name}**"]
        if type_hint:
            parts.append(f"`{type_hint}`")
        if default:
            parts.append(f"= {default}")

        args.append(" ".join(parts))

    signature = f"{display_name}({', '.join(args)})"
    ret = get_return_type(node)
    if ret:
        signature += f" → `{ret}`"

    return f"### `{signature}`"


def extract_methods(tree: ast.Module, class_name: str) -> List[str]:
    """提取类中公开方法的签名"""
    lines = ["", f"### {class_name}", ""]

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    name = item.name
                    if name.startswith("_") and name != "__init__":
                        continue

                    sig_line = format_method_signature(class_name, item)
                    lines.append(sig_line)

                    doc = ast.get_docstring(item)
                    summary = parse_docstring_summary(doc)
                    if summary:
                        lines.append(f"\n    {summary}\n")
    return lines


def scan_module(filepath: Path) -> str:
    """扫描单个模块，生成 API 参考 markdown"""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    lines = []
    lines.append("<!-- AUTO: API 签名 -->")
    lines.append("")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_lines = extract_methods(tree, node.name)
            lines.extend(class_lines)

    lines.append("")
    lines.append("<!-- /AUTO -->")

    return "\n".join(lines)


def update_reference_file(ref_path: Path, new_auto_content: str) -> bool:
    """更新 reference 文件的 AUTO 区，保留手写内容"""
    if not ref_path.exists():
        with open(ref_path, "w", encoding="utf-8") as f:
            f.write(new_auto_content + "\n\n<!-- 手写内容：示例、反例、A股规则 -->\n")
        return True

    with open(ref_path, "r", encoding="utf-8") as f:
        content = f.read()

    auto_pattern = r"<!-- AUTO: API 签名 -->.*?<!-- /AUTO -->"
    if re.search(auto_pattern, content, re.DOTALL):
        new_content = re.sub(
            auto_pattern,
            new_auto_content.strip(),
            content,
            count=1,
            flags=re.DOTALL,
        )
    else:
        new_content = new_auto_content + "\n\n" + content

    if new_content == content:
        return False

    with open(ref_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def main():
    os.makedirs(SKILLS_REF, exist_ok=True)

    # 按 ref_file 分组，一个 reference 文件可能有多个源文件
    groups: Dict[str, list] = {}
    for py_file, ref_file in MODULE_REF_MAP.items():
        if ref_file is None:
            continue
        groups.setdefault(ref_file, []).append(py_file)

    updated = []

    for ref_file, py_files in groups.items():
        ref_path = SKILLS_REF / ref_file

        # 合并所有源文件的内容
        all_contents = []

        for py_file in py_files:
            src_path = QKA_CORE / py_file
            if not src_path.exists():
                print(f"[SKIP] 不存在: {src_path}")
                continue

            print(f"[SCAN] {py_file} → {ref_file}")
            new_auto = scan_module(src_path)

            # 去掉 AUTO 包裹标签，只取中间内容
            inner = re.sub(
                r"<!-- AUTO: API 签名 -->\s*|\s*<!-- /AUTO -->",
                "",
                new_auto,
                flags=re.DOTALL,
            ).strip()
            if inner:
                all_contents.append(inner)

        if not all_contents:
            print(f"[SKIP] {ref_file} 无内容可生成")
            continue

        # 拼装最终 AUTO 区
        combined = "<!-- AUTO: API 签名 -->\n\n"
        combined += "\n\n".join(all_contents)
        combined += "\n\n<!-- /AUTO -->"

        if update_reference_file(ref_path, combined):
            updated.append(ref_file)
            print(f"   [UPDATED] {ref_file}")
        else:
            print(f"   [SAME] {ref_file}")

    if updated:
        print(f"\n[DONE] 更新了 {len(updated)} 个文件: {', '.join(updated)}")
        print("[WARN] 记得检查 git diff 后一起提交")
    else:
        print("\n[DONE] 所有文件已是最新，无需更新")


if __name__ == "__main__":
    main()
