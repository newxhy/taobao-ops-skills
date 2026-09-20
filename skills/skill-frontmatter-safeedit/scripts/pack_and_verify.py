# -*- coding: utf-8 -*-
"""技能打包器：打包前强制 LF 化 + 打包后解包复验。

为什么需要它：`check_frontmatter.py` 只验**源目录**，而**包内的字节是另一份**。
实测（2026-09-20）源目录已被改干净、zip 里却仍有 1357 个裸 CR —— 平台报「解析失败」。
所以「校验源目录 → 打包 → 打包后再校验一次**包内**」必须是一条链，本脚本就是这条链。

用法:
  python scripts/pack_and_verify.py <源技能目录> [<输出zip路径>] [--root 包内根名]
  python scripts/pack_and_verify.py <源技能目录> --outdir <输出目录>

默认输出: <源技能目录>/../dist/<技能名>.zip
退出码: 0=通过, 1=存在问题
"""
import sys, os, re, zipfile

TEXT_EXT = (".md", ".html", ".sh", ".py", ".json", ".txt", ".yaml", ".yml", ".css", ".js")
SKIP_SUFFIX = (".pyc", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico")
# 备份文件识别：`.bak` / `_bak` / `_backup` / `.orig` / `.old` / `xxx~`
# 实测教训（2026-09-20）：只认 `.bak` 会漏掉 `SKILL.md.presanitize_bak` 这类文件，
# 备份被静默打进包。识别不到就报出来，宁可疑杀不可放过。
BACKUP_PAT = re.compile(r"(_bak\b|_bak\d|\.bak\b|_backup\b|\.orig\b|\.old\b|~$)", re.I)

# 平台实测上限（见 SKILL.md 坑 ④）。None = 未实测，仅告警不判负。
LIMITS = {
    "name": (64, True),
    "version": (32, True),
    "display_name": (30, True),
    "display_name_en": (60, False),
    "description": (1000, True),
    "description_zh": (500, True),
    "description_en": (1000, True),
}
REQUIRED = ["name", "version", "display_name", "description", "description_zh", "description_en"]


def lf_normalize(root):
    """把源目录里所有文本文件统一成 LF（保留 BOM 状态）。返回 [(相对路径, 原CR数)]"""
    fixed = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith(TEXT_EXT) or f.endswith(SKIP_SUFFIX):
                continue
            p = os.path.join(dp, f)
            b = open(p, "rb").read()
            bom = b.startswith(b"\xef\xbb\xbf")
            body = b[3:] if bom else b
            n = body.count(b"\r")
            if not n:
                continue
            body = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            open(p, "wb").write((b"\xef\xbb\xbf" if bom else b"") + body)
            fixed.append((os.path.relpath(p, root), n))
    return fixed


def parse_fm(text):
    """极简 frontmatter 解析：够用即可（支持单行 scalar 与块标量续行）。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    fm, key = {}, None
    for line in text[3:end].split("\n"):
        if not line.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key = m.group(1)
            fm[key] = m.group(2).strip()
        elif key is not None:
            fm[key] = (fm.get(key, "") + " " + line.strip()).strip()
    return fm


def verify_zip(zp, verbose=True):
    ok = True
    z = zipfile.ZipFile(zp)
    bad = z.testzip()
    if bad:
        print(f"  [X] zip 损坏: {bad}")
        return False
    # 全量文件：CR / BOM / UTF-8
    for n in z.namelist():
        b = z.read(n)
        cr = b.count(b"\r")
        bom = b[:3] == b"\xef\xbb\xbf"
        try:
            b.decode("utf-8")
            u8 = True
        except Exception:
            u8 = False
        if cr or bom or not u8:
            msg = []
            if cr:
                msg.append(f"裸CR={cr}")
            if bom:
                msg.append("BOM")
            if not u8:
                msg.append("非UTF8")
            print(f"  [X] {n}: {', '.join(msg)}")
            ok = False
    if ok and verbose:
        print(f"  [OK] 包内 {len(z.namelist())} 文件：无裸CR / 无BOM / 全UTF-8")

    # SKILL.md frontmatter
    sps = [n for n in z.namelist() if n.endswith("SKILL.md")]
    if len(sps) != 1:
        print(f"  [X] SKILL.md 数量异常: {sps}")
        return False
    txt = None
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            txt = z.read(sps[0]).decode(enc)
            break
        except Exception:
            continue
    if txt is None:
        print("  [X] SKILL.md 无法解码")
        return False
    fm = parse_fm(txt)
    if fm is None:
        print("  [X] frontmatter 解析失败")
        return False
    for k in REQUIRED:
        v = (fm.get(k) or "").strip().strip('"').strip("'")
        if not v:
            print(f"  [X] 必填字段缺失/为空: {k}")
            ok = False
            continue
        lim, hard = LIMITS.get(k, (9999, False))
        ln = len(v)
        if ln > lim:
            tag = "X" if hard else "!"
            print(f"  [{tag}] {k:16s} len={ln:5d} > {lim}  超限")
            if hard:
                ok = False
        elif verbose:
            print(f"  [OK] {k:16s} len={ln:5d}/{lim}")
    # 目录名 vs name
    root_in_zip = sps[0].split("/")[0]
    if fm.get("name", "").strip() != root_in_zip:
        print(f"  [!] name({fm.get('name','')}) 与包内根目录({root_in_zip}) 不一致")
    return ok


def main():
    args = [a for a in sys.argv[1:]]
    root_override = None
    outdir = None
    if "--root" in args:
        i = args.index("--root")
        root_override = args[i + 1]
        del args[i:i + 2]
    if "--outdir" in args:
        i = args.index("--outdir")
        outdir = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 1
    src = os.path.abspath(args[0])
    name = os.path.basename(os.path.normpath(src))
    if len(args) > 1:
        out = os.path.abspath(args[1])
    else:
        base = outdir or os.path.join(os.path.dirname(src), "dist")
        out = os.path.join(base, f"{name}.zip")
    root = root_override or name

    print(f"源目录 : {src}")
    print(f"包内根 : {root}")
    print(f"输出   : {out}")

    print("--- ① 打包前 LF 化（源目录）---")
    fx = lf_normalize(src)
    if fx:
        for p, n in fx:
            print(f"  [LF化] {p}: CR {n} -> 0")
    else:
        print("  [OK] 无需修正（源目录已是全 LF）")

    print("--- ② 打包 ---")
    files, skipped = [], []
    for dp, _, fs in os.walk(src):
        for f in fs:
            if f.endswith(SKIP_SUFFIX):
                continue
            if BACKUP_PAT.search(f):
                skipped.append(os.path.relpath(os.path.join(dp, f), src).replace("\\", "/"))
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, src).replace("\\", "/")
            files.append((full, f"{root}/{rel}"))
    for s in skipped:
        print(f"  [跳过·疑似备份] {s}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for full, arc in sorted(files, key=lambda x: x[1]):
            zi = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, open(full, "rb").read())
    print(f"  [OK] 写入 {len(files)} 文件, {os.path.getsize(out)} bytes")

    print("--- ③ 打包后解包复验（包内字节）---")
    ok = verify_zip(out)
    print("=" * 60)
    print("结论:", "✅ 可以上传" if ok else "❌ 存在问题，不要上传")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
