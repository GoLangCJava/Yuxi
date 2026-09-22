#!/usr/bin/env python3
"""后端静态调用图：提取 方法级 调用边（含 Depends 依赖边、实例方法推断、唯一方法名启发式）。"""
import ast, os, json, collections

ROOT = "/home/user/Yuxi/backend"
OUT = "/home/user/Yuxi/analysis/callgraph_backend.json"

py_files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in {"test", "__pycache__", ".venv", "node_modules"}]
    for fn in sorted(filenames):
        if fn.endswith(".py"):
            py_files.append(os.path.relpath(os.path.join(dirpath, fn), "/home/user/Yuxi"))

def module_of(rel):
    p = rel
    for prefix in ("backend/package/", "backend/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
            break
    p = p[:-3]
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")

mods = {}
for rel in py_files:
    src = open("/home/user/Yuxi/" + rel, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None
    info = {"rel": rel, "module": module_of(rel), "tree": tree}
    info["funcs"] = set()
    info["classes"] = {}
    info["imports"] = {}
    if tree is not None:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info["funcs"].add(node.name)
            elif isinstance(node, ast.ClassDef):
                info["classes"][node.name] = {
                    m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    for a in node.names:
                        info["imports"][a.asname or a.name] = (node.module, a.name)
                elif node.level > 0:
                    base = module_of(rel).split(".")
                    base_pkg = ".".join(base[: len(base) - node.level])
                    target = f"{base_pkg}.{node.module}" if node.module else base_pkg
                    for a in node.names:
                        info["imports"][a.asname or a.name] = (target, a.name)
    mods[info["module"]] = info

def resolve_symbol(module, name, depth=0):
    if depth > 6 or module not in mods:
        return None
    info = mods[module]
    if name in info["funcs"]:
        return (module, "func", None)
    if name in info["classes"]:
        return (module, "class", info["classes"][name])
    for local, (m, orig) in info["imports"].items():
        if local == name:
            return resolve_symbol(m, orig, depth + 1)
    return None

def file_of(module):
    return mods[module]["rel"] if module in mods else None

# 全局唯一方法名索引（同名方法只在一个类里出现时，可安全解析 var.method()）
method_owner = collections.defaultdict(set)
for module, info in mods.items():
    for cls, ms in info["classes"].items():
        for mname in ms:
            method_owner[mname].add((module, cls))
unique_method = {k: next(iter(v)) for k, v in method_owner.items() if len(v) == 1}

# 常见容器/框架方法名 + 常见框架变量名：禁用启发式（避免把 list.append、session.commit 误判为业务方法）
HEUR_BLOCK_METHODS = {
    "append", "add", "get", "put", "set", "pop", "push", "update", "insert", "remove", "clear",
    "copy", "count", "index", "extend", "items", "keys", "values", "join", "split", "strip",
    "format", "encode", "decode", "read", "write", "seek", "tell", "flush", "close", "open",
    "save", "load", "create", "delete", "drop", "info", "warn", "warning", "error", "debug",
    "exception", "log", "start", "stop", "run", "call", "invoke", "emit", "send", "post",
    "patch", "head", "options", "execute", "executemany", "fetchall", "fetchone", "commit",
    "rollback", "begin", "query", "filter", "all", "first", "scalar", "one", "exists", "search",
    "find", "list", "next", "enter", "exit", "init", "main", "serialize", "cancel", "validate",
    "resolve", "shutdown", "submit", "request", "reset", "match", "group", "sub", "isfile",
    "isdir", "exists", "mkdir", "unlink", "readlink", "iterdir", "rglob", "walk", "connect",
    "disconnect", "aclose", "acquire", "release", "lock", "unlock", "poll", "wait", "notify",
}
HEUR_BLOCK_VARS = {
    "db", "session", "conn", "request", "req", "response", "resp", "logger", "log", "app",
    "router", "ctx", "environ", "settings", "payload", "data", "result", "results", "ret",
}

edges = []

def extract_calls(info):
    results = collections.defaultdict(list)
    if info["tree"] is None:
        return results
    module = info["module"]

    def walk_func(fn_node, qualname, class_ctx=None, class_methods=None):
        var_types = {}
        for node in ast.walk(fn_node):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
            value = getattr(node, "value", None)
            if not targets or not isinstance(value, ast.Call):
                continue
            f = value.func
            cname = f.id if isinstance(f, ast.Name) else None
            if cname:
                r = resolve_symbol(module, cname)
                if r and r[1] == "class":
                    for t in targets:
                        var_types[t.id] = (r[0], cname, r[2])
        seen = set()
        for node in ast.walk(fn_node):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            hits = []
            # FastAPI Depends(x) 依赖边
            if isinstance(f, ast.Name) and f.id == "Depends" and node.args and isinstance(node.args[0], ast.Name):
                dep = node.args[0].id
                if dep in info["imports"]:
                    m, orig = info["imports"][dep]
                    r = resolve_symbol(m, orig)
                    if r:
                        hits.append((r[0], orig, "depends"))
                elif dep in info["funcs"]:
                    hits.append((module, dep, "depends"))
                elif dep in info["classes"]:
                    hits.append((module, dep, "depends"))
            elif isinstance(f, ast.Name):
                n = f.id
                if n in info["imports"]:
                    m, orig = info["imports"][n]
                    r = resolve_symbol(m, orig)
                    if r:
                        hits.append((r[0], orig, r[1]))
                elif n in info["funcs"]:
                    hits.append((module, n, "func"))
                elif n in info["classes"]:
                    hits.append((module, n, "instantiate"))
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                base, attr = f.value.id, f.attr
                if base == "self" and class_methods and attr in class_methods:
                    hits.append((module, f"{class_ctx}.{attr}", "method"))
                elif base in info["imports"]:
                    m, orig = info["imports"][base]
                    r = resolve_symbol(m, orig)
                    if r and r[1] == "class" and attr in (r[2] or set()):
                        hits.append((r[0], f"{orig}.{attr}", "method"))
                elif base in info["classes"] and attr in info["classes"][base]:
                    hits.append((module, f"{base}.{attr}", "method"))
                elif base in var_types:
                    cm, cname, methods = var_types[base]
                    if attr in (methods or set()):
                        hits.append((cm, f"{cname}.{attr}", "method"))
                elif attr in unique_method and base not in info["imports"] and base not in HEUR_BLOCK_VARS and attr not in HEUR_BLOCK_METHODS and len(attr) >= 5:
                    # 变量类型未知但方法名全局唯一 → 启发式归属
                    cm, cname = unique_method[attr]
                    hits.append((cm, f"{cname}.{attr}", "method*"))
            for hm, hs, kind in hits:
                key = (hm, hs, kind)
                if key not in seen:
                    seen.add(key)
                    results[qualname].append(key)

    for node in info["tree"].body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            walk_func(node, node.name)
        elif isinstance(node, ast.ClassDef):
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk_func(m, f"{node.name}.{m.name}", class_ctx=node.name, class_methods=info["classes"][node.name])
    return results

for module, info in mods.items():
    for caller, targets in extract_calls(info).items():
        for tm, ts, kind in targets:
            tf = file_of(tm)
            if tf:
                edges.append({"cf": info["rel"], "caller": caller, "tf": tf, "callee": ts, "kind": kind, "tm": tm})

json.dump(edges, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
cross = [e for e in edges if e["cf"] != e["tf"]]
print("总边数:", len(edges), " 跨文件边:", len(cross), " 涉及调用方文件:", len({e['cf'] for e in edges}))
print("启发式边(method*):", sum(1 for e in edges if e["kind"] == "method*"))
print("Depends 边:", sum(1 for e in edges if e["kind"] == "depends"))
