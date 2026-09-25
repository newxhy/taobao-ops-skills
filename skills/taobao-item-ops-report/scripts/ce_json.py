#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 bsk 的 --json 输出里取一个 id 字段（宽容匹配，不依赖具体字段名）。

用法:  <bsk --json 输出> | python ce_json.py session_id
       <bsk --json 输出> | python ce_json.py tab_id

为什么单独放一个文件：这段逻辑嵌在 bash 的 -c '...' 里会和 shell 引号打架
（正则里带引号字符就把单引号串截断了），独立成文件最省事。
"""
import json
import re
import sys


def find(obj, key):
    wanted = {key, key + "_id", "id"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.replace("-", "_").lower() in wanted:
                if isinstance(v, (str, int)) and str(v).strip():
                    return str(v)
            got = find(v, key)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = find(v, key)
            if got:
                return got
    return ""


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "id"
    raw = sys.stdin.read()
    try:
        print(find(json.loads(raw), key))
        return 0
    except Exception:
        pass
    # 回退：从人类可读输出里正则抓（字段名后跟 = 或 :）
    m = re.search(re.escape(key) + r"[_\s=:]+([A-Za-z0-9_-]+)", raw)
    print(m.group(1) if m else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
