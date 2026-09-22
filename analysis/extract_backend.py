#!/usr/bin/env python3
"""提取后端每个文件的 类/函数 清单（含 docstring）→ analysis/inventory_backend.json"""
import ast, json, os

ROOT = "/home/user/Yuxi/backend"
OUT = "/home/user/Yuxi/analysis/inventory_backend.json"
out = []

def doc_of(node):
    d = ast.get_docstring(node)
    if not d:
        return ""
    d = d.strip().split("\n\n")[0].replace("\n", " ").strip()
    return d[:240]

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in {"test", "__pycache__", ".venv", "node_modules"}]
    for fn in sorted(filenames):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, "/home/user/Yuxi")
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception as e:
            out.append({"file": rel, "error": str(e)})
            continue
        mod_doc = ast.get_docstring(tree) or ""
        mod_doc = mod_doc.strip().split("\n")[0].strip()[:200]
        entries = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                entries.append({"kind": "func", "name": node.name, "line": node.lineno, "doc": doc_of(node)})
            elif isinstance(node, ast.ClassDef):
                methods = []
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({"kind": "method", "name": m.name, "line": m.lineno, "doc": doc_of(m)})
                entries.append({"kind": "class", "name": node.name, "line": node.lineno, "doc": doc_of(node), "methods": methods})
        out.append({"file": rel, "mod_doc": mod_doc, "entries": entries})

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("files:", len(out))
