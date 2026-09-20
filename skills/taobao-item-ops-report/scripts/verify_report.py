#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单品运营报表 · 校验器
=====================================================================
用法：
    python verify_report.py <报告.html>

检查项：
    1. 标签配平        div / table / tr / td / th / span / ul / li / h2 / h3 ...
    2. 残留占位符      必须为 0（否则说明有值没填进去）
    3. 段落完整性      h2 段数应为 15（缺段 = 模板被改坏或段落被误删）
    4. 垃圾值          None / NaN / undefined / inf 不得出现在正文
    5. 表格结构        每个 table 的 thead 列数应与 tbody 每行列数一致
    6. 推广三行自洽    全站推广 + 关键词推广 + 店铺直达 == 合计（花费、点击各验一次）
                      —— 这是 SKILL §6.9 的硬要求：只列两行一定对不上合计

退出码：0 = 全过；1 = 有失败项
"""

import io
import os
import re
import sys

TAGS = ["div", "table", "tbody", "thead", "tr", "td", "th",
        "span", "ul", "li", "ol", "h1", "h2", "h3", "p"]
EXPECT_SECTIONS = 15
JUNK = [r"\bNone\b", r"\bNaN\b", r"\bundefined\b", r"\bnan\b", r"\binf\b"]

PH = re.compile(r"\{\{[^{}]+\}\}")
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("  %s %-22s %s" % ("✓" if ok else "✗", name, detail))


def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def text_of(seg):
    t = re.sub(r"<[^>]+>", " ", seg)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()


def num(s):
    """从单元格文本抽数字（去掉 千分位/货币/百分号）"""
    s = str(s).replace(",", "").replace("¥", "").replace("￥", "")
    s = s.replace("%", "").replace("元", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def table_of(html, keyword):
    """抽某段落的第一个表格，返回 rows（每行单元格文本列表）"""
    m = re.search(r"<h2[^>]*>[^<]*" + re.escape(keyword) + r".*?</table>", html, re.S)
    if not m:
        return []
    seg = m.group(0)
    rows = []
    for r in re.findall(r"<tr\b.*?</tr>", seg, re.S):
        cells = [text_of(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
        kind = "th" if re.search(r"<th\b", r) else "td"
        if cells:
            rows.append((kind, cells))
    return rows


# ---------------------------------------------------------------- 检查项

def check_tags(html):
    bad = []
    for tag in TAGS:
        o = len(re.findall(r"<%s\b" % tag, html, re.I))
        c = len(re.findall(r"</%s>" % tag, html, re.I))
        if o != c:
            bad.append("%s(%d开/%d闭)" % (tag, o, c))
    record("标签配平", not bad, "全部配平" if not bad else "不配平: " + ", ".join(bad))


def check_placeholders(html):
    left = PH.findall(html)
    record("残留占位符", not left, "0" if not left else "%d 个: %s" % (len(left), left[:5]))


def check_sections(html):
    secs = [text_of(m) for m in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S)]
    ok = len(secs) == EXPECT_SECTIONS
    record("段落完整性", ok, "h2 = %d（期望 %d）" % (len(secs), EXPECT_SECTIONS))
    if not ok:
        print("     实际段落: %s" % " | ".join(secs))


def check_junk(html):
    hits = []
    for p in JUNK:
        n = len(re.findall(p, html))
        if n:
            hits.append("%s×%d" % (p, n))
    record("垃圾值", not hits, "无" if not hits else ", ".join(hits))


def check_tables(html):
    bad = []
    for i, m in enumerate(re.findall(r"<table\b.*?</table>", html, re.S), 1):
        head = re.search(r"<thead\b.*?</thead>", m, re.S)
        if not head:
            continue
        ncol = len(re.findall(r"<th\b", head.group(0)))
        for r in re.findall(r"<tr\b.*?</tr>", m, re.S):
            if re.search(r"<th\b", r):
                continue
            n = len(re.findall(r"<td\b", r))
            if n and ncol and n != ncol:
                bad.append("表%d: 表头%d列 vs 数据%d列" % (i, ncol, n))
                break
    record("表格结构", not bad, "列数一致" if not bad else "; ".join(bad))


def check_promo(html):
    """推广三行自洽：全站 + 关键词 + 店铺直达 == 合计"""
    rows = table_of(html, "推广表现")
    if not rows:
        record("推广三行自洽", False, "未找到「推广表现」表格")
        return

    data = [c for k, c in rows if k == "td"]
    if not data:
        record("推广三行自洽", False, "表内无数据行")
        return

    total = None
    parts = []
    for cells in data:
        label = cells[0]
        if "合计" in label:
            total = cells
        elif len(parts) < 3:
            parts.append(cells)

    if total is None or not parts:
        record("推广三行自洽", False, "缺「合计」行或分项行")
        return

    detail = []
    ok = True
    for col, cname in ((1, "花费"), (2, "点击")):
        vals = [num(p[col]) for p in parts if col < len(p)]
        vals = [v for v in vals if v is not None]
        t = num(total[col]) if col < len(total) else None
        if t is None or not vals:
            detail.append("%s 未取到" % cname)
            continue
        s = sum(vals)
        good = abs(s - t) <= max(0.02, abs(t) * 0.005)   # 容差 0.5%
        ok = ok and good
        detail.append("%s %s=%s vs 合计 %s %s" % (
            cname, "+".join("%g" % v for v in vals), "%g" % s, "%g" % t,
            "✓" if good else "✗"))
    record("推广三行自洽", ok, " ｜ ".join(detail))


# ---------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    path = sys.argv[1]
    if not os.path.isfile(path):
        print("✗ 文件不存在: %s" % path)
        return 1

    html = read(path)
    print("校验: %s  (%d 字节)\n" % (path, len(html.encode("utf-8"))))

    check_tags(html)
    check_placeholders(html)
    check_sections(html)
    check_junk(html)
    check_tables(html)
    check_promo(html)

    failed = [n for n, ok, _ in RESULTS if not ok]
    print()
    if failed:
        print("结果: ✗ %d/%d 项未通过 -> %s" % (len(failed), len(RESULTS), ", ".join(failed)))
        return 1
    print("结果: ✓ 全部 %d 项通过" % len(RESULTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
