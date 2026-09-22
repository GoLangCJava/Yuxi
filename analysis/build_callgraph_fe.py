#!/usr/bin/env python3
"""前端轻量调用图：apis 对象方法调用 + 具名导入函数调用（对象边界截取版）。"""
import re, os, json

SRC = "/home/user/Yuxi/web/src"
OUT = "/home/user/Yuxi/analysis/callgraph_frontend.json"

files = []
for dirpath, dirnames, filenames in os.walk(SRC):
    dirnames[:] = [d for d in dirnames if d not in {"node_modules", "dist", "__pycache__"}]
    for fn in sorted(filenames):
        if fn.endswith((".js", ".vue")):
            files.append(os.path.join(dirpath, fn))

def rel(p):
    return os.path.relpath(p, "/home/user/Yuxi")

api_objects = {}
api_named_exports = {}
for p in files:
    r = rel(p)
    if os.path.dirname(r) != "web/src/apis":
        continue
    text = open(p, encoding="utf-8").read()
    for m in re.finditer(r'export\s+const\s+(\w+)\s*=\s*\{', text):
        obj = m.group(1)
        start = m.end()
        end = text.find("\n}", start)
        body = text[start:end if end != -1 else len(text)]
        methods = set(re.findall(r'^\s{2,}(\w+)\s*:\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z_$])', body, re.M))
        methods |= set(re.findall(r'^\s{2,}(\w+)\s*,\s*$', body, re.M))
        api_objects[obj] = {"file": r, "methods": methods}
    for m in re.finditer(r'export\s+(?:async\s+)?function\s+(\w+)', text):
        api_named_exports[m.group(1)] = r
    for m in re.finditer(r'export\s+const\s+(\w+)\s*=\s*(?:async\s*)?\(', text):
        api_named_exports[m.group(1)] = r

inv = json.load(open("/home/user/Yuxi/analysis/inventory_frontend.json", encoding="utf-8"))
inv_by_file = {f["file"]: f for f in inv}

def resolve_import_path(spec, cur_file):
    if spec.startswith("@/"):
        cand = os.path.join(SRC, spec[2:])
    elif spec.startswith("./") or spec.startswith("../"):
        cand = os.path.normpath(os.path.join(os.path.dirname("/home/user/Yuxi/" + cur_file), spec))
    else:
        return None
    for ext in ("", ".js", ".vue"):
        if os.path.isfile(cand + ext):
            return rel(cand + ext)
    return None

edges = []
for p in files:
    r = rel(p)
    text = open(p, encoding="utf-8").read()
    named_map = {}
    for m in re.finditer(r'import\s*\{([^}]+)\}\s*from\s*[\'"]([^\'"]+)[\'"]', text):
        names, spec = m.group(1), m.group(2)
        if spec == "@/apis":
            for item in names.split(","):
                item = item.strip()
                if not item:
                    continue
                if " as " in item:
                    orig, local = [x.strip() for x in item.split(" as ")]
                else:
                    local = orig = item
                if orig in api_objects:
                    named_map[local] = ("@api", orig, True)
                elif orig in api_named_exports:
                    named_map[local] = (api_named_exports[orig], orig, False)
        else:
            src_file = resolve_import_path(spec, r)
            if src_file:
                for item in names.split(","):
                    item = item.strip()
                    if not item:
                        continue
                    if " as " in item:
                        orig, local = [x.strip() for x in item.split(" as ")]
                    else:
                        local = orig = item
                    named_map[local] = (src_file, orig, False)
    if not named_map:
        continue
    f_info = inv_by_file.get(r)
    if not f_info or not f_info.get("entries"):
        continue
    ents = sorted(f_info["entries"], key=lambda e: e["line"])
    lines = text.splitlines()
    for i, e in enumerate(ents):
        start = e["line"]
        end = ents[i + 1]["line"] - 1 if i + 1 < len(ents) else start + 500
        seg = "\n".join(lines[max(0, start - 1):end])
        seen = set()
        for local, (srcf, orig, is_api) in named_map.items():
            if is_api:
                continue
            if re.search(r'\b' + re.escape(local) + r'\s*\(', seg):
                if (srcf, orig) not in seen:
                    seen.add((srcf, orig))
                    edges.append({"cf": r, "caller": e["name"], "tf": srcf, "callee": orig, "kind": "func"})
        for local, (srcf, orig, is_api) in named_map.items():
            if not is_api:
                continue
            for mm in re.finditer(r'\b' + re.escape(local) + r'\.(\w+)\s*\(', seg):
                meth = mm.group(1)
                if meth in api_objects[orig]["methods"]:
                    key = (api_objects[orig]["file"], f"{orig}.{meth}")
                    if key not in seen:
                        seen.add(key)
                        edges.append({"cf": r, "caller": e["name"],
                                      "tf": api_objects[orig]["file"], "callee": f"{orig}.{meth}", "kind": "api"})

json.dump(edges, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("前端总边数:", len(edges), " 跨文件:", sum(1 for e in edges if e["cf"] != e["tf"]))
