#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safe_multi_edit.py —— 对同一文件做多处替换的原子编辑器

为什么需要它：
    Edit 工具在同一消息里对**同一文件**并行发多个替换会互相覆盖，
    工具回执却全报「成功」——改动**静默丢失**。
    实测两次：
      · 2026-09-22：4 处 Edit 只落地 3 处
      · 2026-09-23：3 处 Edit 只落地 2 处（load_category 改了，main 段落没改，
                    直接导致测试出现「写着 whitening 却判 ✅ 通过」的假绿）

本脚本的做法：
    1. 先把**全部**替换在内存里算一遍，逐个断言命中次数（默认必须 == 1）；
    2. 只要有一处不达标 → **整批不写盘**，报告哪一处错了；
    3. 全部达标才写盘，写前备份，写后**回读校验**（新串在、旧串已消失）。

用法：
    # 1) 命令行：edits.json 形如
    #    [{"old": "旧串", "new": "新串"}, {"old": "...", "new": "...", "expect": 2}]
    python safe_multi_edit.py <目标文件> <edits.json> [--partial] [--newline lf|keep]

    # 2) 当库用
    from safe_multi_edit import apply_edits
    report = apply_edits(path, [(old, new), ...])

退出码：0 = 全部成功；1 = 有未命中（未写盘）；2 = 参数/读取错误
"""
import io, os, sys, json, shutil, datetime, tempfile

def read_text(p):
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return io.open(p, encoding=enc).read()
        except Exception:
            continue
    raise IOError("无法读取（尝试过 utf-8-sig / utf-8 / gbk）: %s" % p)

def write_text(p, s, newline="lf"):
    kw = {}
    if newline == "lf":
        kw["newline"] = "\n"
    with io.open(p, "w", encoding="utf-8", **kw) as f:
        f.write(s)

def apply_edits(path, edits, expect_default=1, partial=False,
                newline="lf", backup=True, allow_identical=False):
    """edits: [(old, new)] 或 [{'old':..,'new':..,'expect':N}]
    返回 {'ok':bool,'applied':int,'failed':[(idx,old,count,expect)],'backup':path|None}"""
    s = read_text(path)
    norm = []
    for e in edits:
        if isinstance(e, dict):
            norm.append((e["old"], e["new"], int(e.get("expect", expect_default))))
        else:
            norm.append((e[0], e[1], expect_default))

    failed, applied = [], 0
    for i, (old, new, exp) in enumerate(norm, 1):
        if not allow_identical and old == new:
            failed.append((i, old, "new==old（无意义替换）", exp))
            continue
        c = s.count(old)
        if c != exp:
            failed.append((i, old, c, exp))
            continue
        s = s.replace(old, new)
        applied += 1

    rep = {"ok": not failed or partial, "applied": applied, "failed": failed, "backup": None}
    if failed and not partial:
        return rep   # 整批不写盘

    bak = None
    if backup:
        # 备份一律放到系统 temp —— 绝不留在被编辑的目录里。
        # 理由：技能目录内出现 *_bak / *.bak 会被打包器告警，
        # 换别的工具打包还可能被误打进包（本技能坑 ⑤ 的同类问题）。
        bakdir = os.path.join(tempfile.gettempdir(), "safe_multi_edit_bak")
        os.makedirs(bakdir, exist_ok=True)
        bak = os.path.join(bakdir, os.path.basename(path) + "." +
                           datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copyfile(path, bak)
    write_text(path, s, newline=newline)

    # 回读校验：新串必须在，旧串必须已消失
    chk = read_text(path)
    bad = []
    for i, (old, new, exp) in enumerate(norm, 1):
        if i in [f[0] for f in failed]:
            continue
        if new and new not in chk:
            bad.append((i, "新串未落地"))
        # 注意：若 new 本身包含 old（典型的追加型替换），
        # 替换后 old 当然还在文件里——这不是失败。此时只校验新串已落地。
        # 2026-09-23 实测踩到：3 处全成功，却因这条误报判为失败。
        if old != new and old not in new and old in chk:
            bad.append((i, "旧串仍在"))
    rep["backup"] = bak
    rep["verify_failed"] = bad
    rep["ok"] = (not failed or partial) and not bad
    return rep

# ---------------------- CLI ----------------------
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = set(a for a in sys.argv[1:] if a.startswith("--"))
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    path, edits_file = args[0], args[1]
    newline = "keep" if "--newline" in flags and "keep" in sys.argv else "lf"
    try:
        edits = json.load(io.open(edits_file, encoding="utf-8"))
    except Exception as e:
        print("读取 edits.json 失败：%s" % e)
        sys.exit(2)

    rep = apply_edits(path, edits, partial=("--partial" in flags), newline=newline)

    print("=" * 68)
    print("safe_multi_edit  →  %s" % os.path.basename(path))
    print("=" * 68)
    print("内存中匹配成功：%d / %d" % (rep["applied"], len(edits)))
    wrote = not (rep["failed"] and "--partial" not in flags)
    print("是否写盘：%s" % ("是" if wrote else "否（有未命中，整批放弃，文件保持原样）"))
    if rep.get("backup"):
        print("备份：%s" % rep["backup"])
    if rep["failed"]:
        print()
        print("未命中（整批未写盘，文件保持原样）：" if "--partial" not in flags else "未命中（--partial 已部分写入）：")
        for i, old, cnt, exp in rep["failed"]:
            print("  ✗ 第 %d 处：实际命中 %s 次，期望 %s 次" % (i, cnt, exp))
            print("      片段：%s" % str(old)[:100].replace("\n", "⏎"))
    if rep.get("verify_failed"):
        print()
        print("回读校验失败：")
        for i, why in rep["verify_failed"]:
            print("  ✗ 第 %d 处：%s" % (i, why))
    print()
    print("结论：%s" % ("✅ 全部落地并通过回读校验" if rep["ok"] else "❌ 有改动未落地"))
    sys.exit(0 if rep["ok"] else 1)

if __name__ == "__main__":
    main()
