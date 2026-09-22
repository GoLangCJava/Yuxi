#!/usr/bin/env python3
"""提取前端每个文件的函数清单 → analysis/inventory_frontend.json"""
import json, os, re

ROOT = "/home/user/Yuxi/web/src"
OUT = "/home/user/Yuxi/analysis/inventory_frontend.json"
out = []

FUNC_RE = re.compile(r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)')
CONST_FN_RE = re.compile(r'^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(')

def doc_before(lines, idx):
    j = idx - 1
    comments = []
    while j >= 0 and lines[j].strip().startswith(("*", "/*", "//")):
        comments.insert(0, lines[j].strip().lstrip("/*").rstrip("*/").strip())
        j -= 1
    text = " ".join(c for c in comments if c)
    return re.sub(r"@[a-zA-Z]+\s+\S+.*$", "", text).strip()[:200]

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in {"node_modules", "dist", "__pycache__"}]
    for fn in sorted(filenames):
        if not (fn.endswith(".js") or fn.endswith(".vue")):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, "/home/user/Yuxi")
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except Exception as e:
            out.append({"file": rel, "error": str(e)})
            continue
        entries = []
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line.strip()) or CONST_FN_RE.match(line.strip())
            if m:
                entries.append({"kind": "func", "name": m.group(1), "line": i + 1, "doc": doc_before(lines, i)})
        header = ""
        if fn.endswith(".vue"):
            for l in lines[:12]:
                if l.strip().startswith("<!--"):
                    header += l.strip().strip("<!--> ") + " "
                if "<!--" in l:
                    break
            header = header.strip()[:300]
        out.append({"file": rel, "header": header, "entries": entries})

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("files:", len(out), "funcs:", sum(len(f.get("entries", [])) for f in out))
