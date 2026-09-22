# -*- coding: utf-8 -*-
"""渲染辅助：目录分组、文件卡片（含方法级调用边）、调用树。"""
import json, html, os
from report_data import (INV_B, INV_F, DIR_DESCR_B, FILE_DESCR_B, CORE_FILES,
                         DIR_DESCR_F, FILE_DESCR_F, CORE_FILES_F, esc)

EDGES_B = json.load(open("/home/user/Yuxi/analysis/callgraph_backend.json", encoding="utf-8"))
EDGES_F = json.load(open("/home/user/Yuxi/analysis/callgraph_frontend.json", encoding="utf-8"))

def build_indexes(edges):
    fwd_all, fwd_cross, rev_cross, inst_rev = {}, {}, {}, {}
    for e in edges:
        fwd_all.setdefault((e["cf"], e["caller"]), []).append((e["tf"], e["callee"], e["kind"]))
        if e["cf"] != e["tf"]:
            fwd_cross.setdefault((e["cf"], e["caller"]), []).append((e["tf"], e["callee"], e["kind"]))
            rev_cross.setdefault((e["tf"], e["callee"]), []).append((e["cf"], e["caller"]))
            if e["kind"] == "instantiate":
                inst_rev.setdefault((e["tf"], e["callee"]), []).append((e["cf"], e["caller"]))
    for d in (fwd_all, fwd_cross):
        for k in d:
            d[k] = sorted(set(d[k]))
    for k in rev_cross:
        rev_cross[k] = sorted(set(rev_cross[k]))
    for k in inst_rev:
        inst_rev[k] = sorted(set(inst_rev[k]))
    return fwd_all, fwd_cross, rev_cross, inst_rev

FWD_ALL_B, FWD_B, REV_B, INST_B = build_indexes(EDGES_B)
FWD_ALL_F, FWD_F, REV_F, INST_F = build_indexes(EDGES_F)

# apis 对象方法（如 agentApi.createAgentRun）不是顶层函数，单独建反查索引
from collections import defaultdict
API_METHOD_CALLERS = defaultdict(lambda: defaultdict(list))
for e in EDGES_F:
    if e["kind"] == "api" and e["cf"] != e["tf"]:
        API_METHOD_CALLERS[e["tf"]][e["callee"]].append((e["cf"], e["caller"]))

def short_b(tf):
    s = tf.replace("backend/package/yuxi/", "").replace("backend/server/", "").replace("backend/", "")
    parts = s.split("/")
    return "/".join(parts[-2:]) if len(parts) > 1 else s

def short_f(tf):
    s = tf.replace("web/src/", "")
    return s

KIND_MARK = {"method*": "≈", "depends": "⭢", "instantiate": "new ", "class": "new ", "api": "", "func": "", "method": ""}

def callee_chips(cf, caller, fwd, short_fn, limit=6):
    lst = fwd.get((cf, caller))
    if not lst:
        return ""
    shown, more = lst[:limit], len(lst) - limit
    def one(t, c, k):
        mark = KIND_MARK.get(k, "")
        name = esc(c) + ("" if k in ("instantiate", "class") else "()")
        return f'{mark}<code class="cc">{name}</code><span class="cf">@{esc(short_fn(t))}</span>'
    chips = " · ".join(one(t, c, k) for t, c, k in shown)
    more_html = f'<span class="cmore">+{more}</span>' if more > 0 else ""
    return f'<div class="mchips out">→ 调用 {chips}{more_html}</div>'

def caller_chips(cf, caller, rev, short_fn, limit=4):
    lst = rev.get((cf, caller))
    if not lst:
        return ""
    shown, more = lst[:limit], len(lst) - limit
    chips = " · ".join(f'<code class="cc">{esc(c)}()</code><span class="cf">@{esc(short_fn(f))}</span>' for f, c in shown)
    more_html = f'<span class="cmore">+{more}</span>' if more > 0 else ""
    return f'<div class="mchips in">← 被调 {chips}{more_html}</div>'

def inst_chips(tf, cls, inst_rev, short_fn, limit=4):
    lst = inst_rev.get((tf, cls))
    if not lst:
        return ""
    shown, more = lst[:limit], len(lst) - limit
    chips = " · ".join(f'<code class="cc">{esc(c)}()</code><span class="cf">@{esc(short_fn(f))}</span>' for f, c in shown)
    more_html = f'<span class="cmore">+{more}</span>' if more > 0 else ""
    return f'<div class="mchips in">← 被实例化于 {chips}{more_html}</div>'

# ================= 调用树 =================
TREE_NOISE_FILES = ("utils/datetime_utils", "utils/logging_config", "utils/singleton")

def layer_of(tf):
    if "/routers/" in tf or tf.endswith("server/main.py"): return "r"
    if "/services/" in tf: return "s"
    if "/repositories/" in tf: return "q"
    if "/agents/" in tf: return "a"
    if "/storage/" in tf: return "t"
    if "/knowledge/" in tf: return "k"
    if "/models/" in tf: return "m"
    return "o"

def tree_node(cf, caller, fwd_all, short_fn, depth=0, visited=None, budget=None):
    """返回 (html, 展开的节点数)。"""
    if visited is None:
        visited = set()
    if budget is None:
        budget = [130]
    key = (cf, caller)
    is_root = not visited
    label = f'<span class="tn">{esc(caller)}()</span><span class="tfb l-{layer_of(cf)}">{esc(short_fn(cf))}</span>'
    if key in visited:
        return f'<li class="trep">↻ {label}<span class="tdup">（上方已展开）</span></li>', 0
    visited.add(key)
    children = [c for c in fwd_all.get(key, [])
                if not any(n in c[0] for n in TREE_NOISE_FILES)]
    children = sorted(set(children), key=lambda x: (x[0], x[1]))
    if not children:
        return f"<li>{label}</li>", 1
    if depth >= 5 or budget[0] <= 0:
        return f'<li>{label}<span class="tdup"> …（深度/节点数已达上限，完整出边见文件卡片）</span></li>', 1
    parts = [f"<li>{label}<ul>"]
    count = 1
    max_children = 24 if depth == 0 else 16
    shown = children[:max_children]
    for tf, callee, kind in shown:
        if budget[0] <= 0:
            parts.append(f'<li class="trep">… 还有 {len(children) - max_children + 1} 个调用</li>')
            break
        mark = KIND_MARK.get(kind, "")
        if kind in ("instantiate", "class"):
            parts.append(f'<li><span class="tnew">new</span> <span class="tn">{esc(callee)}</span><span class="tfb l-{layer_of(tf)}">{esc(short_fn(tf))}</span></li>')
            count += 1
            budget[0] -= 1
        else:
            sub, n = tree_node(tf, callee, fwd_all, short_fn, depth + 1, visited, budget)
            mark = KIND_MARK.get(kind, "")
            if mark and sub.startswith("<li>"):
                sub = "<li>" + f'<span class="tmark">{mark}</span> ' + sub[4:]
            parts.append(sub)
            count += n
            budget[0] -= 1
    if len(children) > max_children and budget[0] > 0:
        parts.append(f'<li class="trep">… 还有 {len(children) - max_children} 个调用见文件卡片</li>')
    parts.append("</ul></li>")
    return "".join(parts), count

def render_tree(title, desc, cf, caller, fwd_all, short_fn):
    html_tree, n = tree_node(cf, caller, fwd_all, short_fn)
    return (f'<details class="treebox" open><summary><b>{esc(title)}</b>'
            f'<span class="treecnt">{n} 个节点</span><span class="chev">展开/收起</span></summary>'
            f'<div class="treedesc">{desc}</div>'
            f'<ul class="tree">{html_tree}</ul></details>')

# ================= 分组与卡片 =================
def backend_group(path):
    if path.startswith("backend/server"): return ("A", "入口与路由层（backend/server）")
    if "yuxi/services" in path: return ("B", "用例层 services（43 个服务文件）")
    if "yuxi/agents" in path: return ("C", "智能体体系 agents")
    if "yuxi/repositories" in path: return ("D", "数据访问层 repositories")
    if "yuxi/storage" in path: return ("E", "存储适配 storage")
    if "yuxi/knowledge" in path: return ("F", "知识域 knowledge")
    if "yuxi/models" in path: return ("G", "模型适配 models")
    if "yuxi/workspace" in path: return ("H", "用户工作区 workspace")
    return ("I", "配置 / 工具 / 迁移（config·utils·permissions·migrations）")

def frontend_group(path):
    if path in ("web/src/main.js", "web/src/App.vue") or "layouts" in path or "router" in path: return ("FA", "入口 / 路由 / 布局")
    if "/apis/" in path: return ("FB", "接口封装层 apis")
    if "/stores/" in path: return ("FC", "状态仓库 stores")
    if "/composables/" in path: return ("FD", "组合式逻辑 composables")
    if "/views/" in path: return ("FE", "页面 views")
    if "/components/" in path: return ("FF", "组件 components")
    return ("FG", "工具函数 utils")

def class_doc_fallback(f):
    for e in f.get("entries", []):
        if e.get("doc"):
            return e["doc"]
    return ""

def method_li_b(cf, m, cls=None):
    q = f"{cls}.{m['name']}" if cls else m["name"]
    doc = f'<span class="mdoc">{esc(m["doc"])}</span>' if m.get("doc") else ""
    chips = callee_chips(cf, q, FWD_B, short_b) + caller_chips(cf, q, REV_B, short_b)
    return (f'<li><div class="mhead"><code class="mname">{esc(m["name"])}()</code> <span class="mln">L{m["line"]}</span>{doc}</div>{chips}</li>')

def render_entries_b(f):
    ents = f.get("entries", [])
    cf = f["file"]
    if not ents:
        return '<p class="nomethod">（本文件没有顶层函数/类，或只有常量与导入）</p>'
    out = ['<ul class="mlist">']
    for e in ents:
        if e["kind"] == "func":
            doc = f'<span class="mdoc">{esc(e["doc"])}</span>' if e.get("doc") else ""
            chips = callee_chips(cf, e["name"], FWD_B, short_b) + caller_chips(cf, e["name"], REV_B, short_b)
            out.append(f'<li><div class="mhead"><span class="badge fn">函数</span> <code class="mname">{esc(e["name"])}()</code> <span class="mln">L{e["line"]}</span>{doc}</div>{chips}</li>')
        else:
            doc = f'<span class="mdoc">{esc(e["doc"])}</span>' if e.get("doc") else ""
            chips = inst_chips(cf, e["name"], INST_B, short_b)
            out.append(f'<li><div class="mhead"><span class="badge cls">类</span> <code class="mname">{esc(e["name"])}</code> <span class="mln">L{e["line"]}</span>{doc}</div>{chips}')
            mts = [m for m in e.get("methods", []) if not m["name"].startswith("__")]
            if mts:
                out.append('<ul class="mlist sub">' + "".join(method_li_b(cf, m, cls=e["name"]) for m in mts) + "</ul>")
            out.append("</li>")
    out.append("</ul>")
    return "".join(out)

def render_entries_f(f):
    ents = f.get("entries", [])
    cf = f["file"]
    out = []
    if not ents:
        out.append('<p class="nomethod">（该文件以模板为主，或函数较少：直接阅读源码最直观）</p>')
    else:
        out.append('<ul class="mlist">')
        for e in ents:
            if e["name"] in ("main", "default"):
                continue
            doc = f'<span class="mdoc">{esc(e["doc"])}</span>' if e.get("doc") else ""
            chips = callee_chips(cf, e["name"], FWD_F, short_f) + caller_chips(cf, e["name"], REV_F, short_f)
            out.append(f'<li><div class="mhead"><code class="mname">{esc(e["name"])}()</code> <span class="mln">L{e["line"]}</span>{doc}</div>{chips}</li>')
        out.append("</ul>")
    # apis 文件：附加「API 对象方法 ← 被谁调用」
    methods = API_METHOD_CALLERS.get(cf)
    if methods:
        out.append('<div class="apisech">API 对象方法（跨文件调用情况）：</div><ul class="mlist">')
        for meth in sorted(methods):
            callers = sorted(set(methods[meth]))[:4]
            more = len(set(methods[meth])) - 4
            chips = " · ".join(
                f'<code class="cc">{esc(c)}()</code><span class="cf">@{esc(short_f(fl))}</span>' for fl, c in callers)
            more_html = f'<span class="cmore">+{more}</span>' if more > 0 else ""
            out.append(f'<li><div class="mhead"><code class="mname">{esc(meth)}</code></div><div class="mchips in">← 被调 {chips}{more_html}</div></li>')
        out.append("</ul>")
    return "".join(out)

def render_file_card(f, is_backend):
    path = f["file"]
    if is_backend:
        descr = FILE_DESCR_B.get(path) or f.get("mod_doc") or class_doc_fallback(f) or "（见所属目录说明）"
        core = path in CORE_FILES
        body = render_entries_b(f)
    else:
        descr = FILE_DESCR_F.get(path)
        if not descr:
            hdr = f.get("header") or ""
            if hdr:
                descr = hdr
            else:
                for e in f.get("entries", []):
                    if e.get("doc"):
                        descr = "主要函数：" + e["doc"]
                        break
                else:
                    descr = "（见所属目录说明）"
        core = path in CORE_FILES_F
        body = render_entries_f(f)
    star = '<span class="star" title="核心链路文件">★</span>' if core else ""
    nm = os.path.basename(path)
    return (f'<details class="filecard{" core" if core else ""}"><summary>{star}<code class="fname">{esc(nm)}</code>'
            f'<span class="fdesc">{esc(descr)}</span><span class="chev">展开/收起</span></summary>'
            f'<div class="fpath">{esc(path)}</div>'
            f'{body}</details>')

def render_catalog(inventory, group_fn, dir_descr, is_backend, id_prefix):
    groups = {}
    for f in inventory:
        g = group_fn(f["file"])
        groups.setdefault(g[0], (g[1], []))[1].append(f)
    html_parts = []
    for key in sorted(groups):
        title, files = groups[key]
        by_dir = {}
        for f in files:
            by_dir.setdefault(os.path.dirname(f["file"]), []).append(f)
        html_parts.append(f'<h3 class="grouph" id="{id_prefix}-{key}">{esc(title)}<span class="cnt">{len(files)} 个文件</span></h3>')
        for d in sorted(by_dir):
            dd = dir_descr.get(d, "")
            ddhtml = f'<div class="dirdesc">📁 {esc(d)} — {esc(dd)}</div>' if dd else f'<div class="dirdesc">📁 {esc(d)}</div>'
            html_parts.append(ddhtml)
            for f in sorted(by_dir[d], key=lambda x: x["file"]):
                html_parts.append(render_file_card(f, is_backend))
    return "".join(html_parts)

# ---------------- 统计 ----------------
n_b = len(INV_B)
n_f = len(INV_F)
n_m_b = sum(
    len([e for e in f.get("entries", []) if not e["name"].startswith("__")])
    + sum(len([m for m in e.get("methods", []) if not m["name"].startswith("__")]) for e in f.get("entries", []) if e["kind"] == "class")
    for f in INV_B)
n_m_f = sum(len(f.get("entries", [])) for f in INV_F)

def step(n, actor, title, refs, body, note=None):
    refs_clean = [r.lstrip("→ ").strip() for r in refs]
    refs_html = "".join(f'<div class="ref">→ <code>{esc(r)}</code></div>' for r in refs_clean)
    note_html = f'<div class="note">💡 {note}</div>' if note else ""
    return f'''<div class="step"><div class="stephead"><span class="stepnum">{n}</span><span class="actor {actor[1]}">{actor[0]}</span><span class="steptitle">{esc(title)}</span></div>
<div class="stepbody"><div class="refs">{refs_html}</div><div class="steptext">{body}</div>{note_html}</div></div>'''

def arrow():
    return '<div class="arr">▼</div>'
