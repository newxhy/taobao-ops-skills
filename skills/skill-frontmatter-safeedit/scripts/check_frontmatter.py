#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SKILL.md frontmatter 校验器（零依赖）

用法:
    python check_frontmatter.py <技能目录|SKILL.md> [...]            # 日常：只查硬问题
    python check_frontmatter.py --upload <技能目录> [...]           # 上传前：加查平台必填字段

日常模式查：裸 CR / YAML 可解析 / name 与 description / name 合规 / 版本一致性 / 字段长度
上传模式另查：version / display_name / description_zh / description_en 是否齐全
              （缺任一 → 平台「配置技能」阶段直接报「解析失败」拒收）

⚠️ 平台两道硬门槛（都是实测被拒换来的）：
   ① 字段齐全 —— 缺 description_zh / description_en 直接拒收；
   ② 字段长度 —— 英文描述上限 1000 字符（报错原文「Skill 英文描述: 当前 N 字符, 上限 1000 字符」）。

⚠️ 官方 quick_validate.py 只查 name / description 两条，**永远报 Skill is valid!**
   → 不能拿它当上传前的准绳，必须跑本脚本的 --upload 模式。
"""
import io, os, re, sys

CORE = ['name', 'description']                      # 日常必须有
# 上传平台必须另有：实测被拒两次的字段（2026-09 两次上传失败记录）
#   第 1 次：缺 version / display_name / description_zh / description_en（4 个）
#   第 2 次：缺 description_zh / description_en（2 个，即第一次只补了前两个）
UPLOAD_EXTRA = ['version', 'display_name', 'description_zh', 'description_en']


def load_frontmatter(p):
    s = io.open(p, 'r', encoding='utf-8', newline='').read()
    if not s.startswith('---'):
        return None, s, '文件未以 --- 开头（无 frontmatter）'
    end = s.find('\n---', 3)
    if end < 0:
        return None, s, 'frontmatter 未闭合（找不到结束的 ---）'
    return s[4:end + 1], s, None


def check(raw, upload=False):
    p = os.path.join(raw, 'SKILL.md') if os.path.isdir(raw) else raw
    if not os.path.isfile(p):
        print('✗ 找不到 %s' % p)
        return

    d = os.path.dirname(p)
    print('=' * 72)
    print('检查: %s%s' % (p, '   [上传模式]' if upload else ''))
    fm, body, err = load_frontmatter(p)
    if err:
        print('  ✗ %s' % err)
        return

    ok = True

    # 1 裸 CR —— CRLF 文件被截取时产生，会破坏 YAML 结构
    bare = [m.start() for m in re.finditer(r'\r(?!\n)', body)]
    if bare:
        ok = False
        print('  ✗ 裸 CR %d 处（会破坏 YAML 结构）' % len(bare))
        for i in bare[:3]:
            print('      @%d ...%s...' % (i, repr(body[max(0, i - 35):i + 35])))
    else:
        print('  ✓ 无裸 CR')

    # 2 YAML 可解析
    data = None
    try:
        import yaml
        data = yaml.safe_load(fm)
        print('  ✓ YAML 可解析')
    except ImportError:
        print('  ~ 无 pyyaml，跳过严格解析')
    except Exception as e:
        ok = False
        print('  ✗ YAML 解析失败: %s' % str(e).replace('\n', ' ')[:200])

    def has(k):
        return (k in data) if isinstance(data, dict) else bool(re.search(r'^%s\s*:' % k, fm, re.M))

    # 3 必填字段（分场景）
    miss_core = [k for k in CORE if not has(k)]
    for k in miss_core:
        ok = False
        print('  ✗ 缺必填字段: %s' % k)
    if not miss_core:
        print('  ✓ 必填字段（%s）' % ' / '.join(CORE))

    miss_up = [k for k in UPLOAD_EXTRA if not has(k)]
    if miss_up:
        if upload:
            ok = False
            print('  ✗ 缺上传必需字段: %s  → 平台会拒收' % ' / '.join(miss_up))
        else:
            print('  ⚠ 缺上传字段: %s（自用无妨；一旦要上传必须先补）' % ' / '.join(miss_up))
    elif upload:
        print('  ✓ 上传必需字段齐全')

    # 4 name 合规 + 与目录名一致
    nm = (data or {}).get('name') if isinstance(data, dict) else None
    if not nm:
        m = re.search(r'^name\s*:\s*(.+)$', fm, re.M)
        nm = m.group(1).strip().strip('"\'') if m else ''
    if nm:
        if not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', nm):
            ok = False
            print('  ✗ name 不合规（须小写字母/数字/连字符）: %s' % nm)
        else:
            print('  ✓ name 合规: %s' % nm)
        if os.path.basename(d) and os.path.basename(d) != nm:
            print('  ⚠ 目录名(%s) 与 name(%s) 不一致' % (os.path.basename(d), nm))

    # 5 描述字段的健康度：空值 / 半角 ": " —— 后者在 plain scalar 里会被当成 mapping
    for key in ['description_zh', 'description_en']:
        m = re.search(r'^%s\s*:\s*(.*)$' % key, fm, re.M)
        if not m:
            continue
        v = m.group(1).strip()
        if v in ('', '|', '>', '|-', '>-'):
            print('  ~ %s 用了块标量或空值，请人工确认平台能否解析' % key)
            continue
        if re.search(r': ', v):
            ok = False
            print('  ✗ %s 的值里含半角 ": " → 会被当成 mapping' % key)
            j = v.find(': ')
            print('      ...%s...' % v[max(0, j - 40):j + 40])
        else:
            print('  ✓ %s 单行 plain scalar（%d 字符，无 ": "）' % (key, len(v)))

    # 5.5 字段长度上限（2026-09-20 实测：平台报「Skill 英文描述: 当前 1330 字符, 上限 1000 字符」）
    #     hard=True 的是平台实测硬上限；其余是为避开同类坑设的保守护栏（未实测，超了只告警）
    LIMITS = [
        ('description_en', 1000, True,  '英文描述'),
        ('description_zh', 500,  False, '中文描述'),
        ('description',    1000, False, '主描述（召回用）'),
        ('display_name',   30,   False, '中文名'),
        ('display_name_en', 60,  False, '英文名'),
    ]
    for key, cap, hard, label in LIMITS:
        if not has(key):
            continue
        v = (data or {}).get(key) if isinstance(data, dict) else None
        if v is None:
            m = re.search(r'^%s\s*:\s*(.*)$' % key, fm, re.M)
            v = m.group(1) if m else ''
        n = len(str(v))
        if n > cap:
            if hard:
                ok = False
                print('  ✗ %s 长度 %d 字符 > 上限 %d（平台会报「解析失败」）'
                      % (label + ' ' + key, n, cap))
            else:
                print('  ⚠ %s 长度 %d 字符 > 保守护栏 %d（平台上限未实测，建议压缩）'
                      % (label + ' ' + key, n, cap))
        elif hard:
            print('  ✓ %s 长度合规: %d / %d 字符' % (label + ' ' + key, n, cap))

    # 6 版本一致性（正文标记 vs frontmatter）
    ver = (data or {}).get('version') if isinstance(data, dict) else None
    if not ver:
        m = re.search(r'^version\s*:\s*([\d.]+)$', fm, re.M)
        ver = m.group(1) if m else None
    if ver:
        # 剔除代码块与行内代码 —— 文档里「举例提到」的版本号不算自己的标记
        body_nocode = re.sub(r'```.*?```', '', body, flags=re.S)
        body_nocode = re.sub(r'`[^`\n]*`', '', body_nocode)
        marks = sorted(set(re.findall(r'v(\d+\.\d+)', body_nocode)))
        newer = [x for x in marks if x > ver]
        if newer:
            ok = False
            print('  ✗ 正文标了更高的版本 %s，但 version=%s（改了内容忘升版本号）'
                  % (', '.join('v' + x for x in newer), ver))
        else:
            print('  ✓ 版本一致性（正文标记: %s）' % (', '.join('v' + x for x in marks) or '无'))
    elif not upload:
        print('  ~ 无 version，跳过版本一致性检查')

    print('  → 结论: %s' % ('✅ 可以打包上传' if ok else '❌ 有问题，先修再传'))


def main(argv):
    upload = False
    args = []
    for a in argv:
        if a in ('--upload', '--strict'):
            upload = True
        else:
            args.append(a)
    if not args:
        print(__doc__)
        return 1
    for a in args:
        check(a, upload)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
