#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单品运营报表 · 渲染引擎
=====================================================================
用法：
    python gen_report.py <数据.json> <输出.html> [模板.html]

行为：
    1. 剥离模板头部 HTML 注释（注释里含占位符示例，不能参与替换）
    2. 删除「所有占位符都未提供」的 <tr> 行（用于裁剪空行：只给 3 个渠道就只出 3 行）
    3. 替换剩余 {{占位符}}；缺失的写「未取到」（样式类占位符缺失则留空）
    4. 输出统计：字节数 / 残留占位符 / 未提供的键

数据格式（JSON，UTF-8）：
    { "商品名": "xxx", "结论1": "xxx", ... }
    也支持包一层： { "fields": { ... } }

约定：
    · 值写 null 或 "" 等价于「未取到」
    · 以「方向」或「色」结尾的占位符 = CSS 样式类 → 缺失时替换为空串（不写"未取到"）
"""

import io
import json
import os
import re
import sys

MISSING = "未取到"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TPL = os.path.join(HERE, "..", "assets", "item_report_template.html")

PH = re.compile(r"\{\{([^{}]+)\}\}")
# 可整行裁剪的"行"：表格行 / 简单列表项 / 内部无子标签的简单 div
ROW = re.compile(
    r"[ \t]*(?:"
    r"<tr\b.*?</tr>"
    r"|<li\b[^>]*>[^<]*</li>"
    r"|<div\b[^>]*>[^<]*</div>"
    r")\s*\n?",
    re.S,
)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def is_style_key(name):
    """样式类占位符：缺失时留空，避免出现 class="未取到" """
    return name.endswith("方向") or name.endswith("色")


def provided(data, name):
    v = data.get(name)
    return v is not None and str(v).strip() != ""


def strip_empty_rows(html, data):
    """整行占位符都未提供 -> 删掉该行"""
    removed = [0]

    def repl(m):
        row = m.group(0)
        names = [n.strip() for n in PH.findall(row)]
        if not names:
            return row
        if all(not provided(data, n) for n in names):
            removed[0] += 1
            return ""
        return row

    out = ROW.sub(repl, html)
    return out, removed[0]


def fill(html, data):
    missing = []

    def repl(m):
        name = m.group(1).strip()
        if provided(data, name):
            return str(data[name])
        if is_style_key(name):
            return ""
        missing.append(name)
        return MISSING

    return PH.sub(repl, html), missing


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    data_path, out_path = sys.argv[1], sys.argv[2]
    tpl_path = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_TPL

    if not os.path.isfile(tpl_path):
        print("✗ 模板不存在: %s" % tpl_path)
        return 1

    data = json.loads(read_text(data_path))
    if isinstance(data, dict) and isinstance(data.get("fields"), dict):
        data = data["fields"]
    if not isinstance(data, dict):
        print("✗ 数据顶层必须是对象（字典）")
        return 1

    tpl = COMMENT.sub("", read_text(tpl_path))       # 1. 剥注释
    html, removed_rows = strip_empty_rows(tpl, data)  # 2. 裁空行
    html, missing = fill(html, data)                  # 3. 填值

    write_text(out_path, html)

    leftover = PH.findall(html)
    print("写出: %s" % out_path)
    print("字节: %d" % len(html.encode("utf-8")))
    print("裁剪空行: %d 行" % removed_rows)
    print("残留占位符: %d  %s" % (len(leftover), "✓" if not leftover else "✗ " + str(leftover[:5])))
    if missing:
        uniq = sorted(set(missing))
        print("未提供 %d 个键（已写「%s」）: %s" % (len(uniq), MISSING, ", ".join(uniq[:40])))
    else:
        print("未提供键: 0 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
