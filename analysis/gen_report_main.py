# -*- coding: utf-8 -*-
"""生成最终 HTML 报告（v2：含方法级调用图）。"""
import os
from gen_report import (render_catalog, render_tree, step, arrow, n_b, n_f, n_m_b, n_m_f,
                        INV_B, INV_F, DIR_DESCR_B, DIR_DESCR_F, esc,
                        FWD_ALL_B, FWD_ALL_F, short_b, short_f, EDGES_B, EDGES_F,
                        backend_group, frontend_group)

TODAY = "2026-09-22"
N_EDGE_B = len(EDGES_B)
N_EDGE_F = len(EDGES_F)

CSS = """
:root{--ink:#1f2430;--sub:#5b6472;--line:#e3e7ee;--bg:#f6f7fa;--card:#ffffff;
--blue:#2563eb;--blue-bg:#eff6ff;--green:#059669;--green-bg:#ecfdf5;--orange:#d97706;--orange-bg:#fffbeb;
--purple:#7c3aed;--purple-bg:#f5f3ff;--red:#dc2626;--red-bg:#fef2f2;--teal:#0d9488;--teal-bg:#f0fdfa;}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg);line-height:1.75;font-size:15px}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px 80px}
header.hero{background:linear-gradient(135deg,#1e3a8a,#2563eb 55%,#0d9488);color:#fff;border-radius:18px;padding:44px 40px;margin-bottom:28px}
.hero h1{margin:0 0 10px;font-size:30px;letter-spacing:.5px}
.hero p{margin:6px 0;opacity:.92;font-size:15px}
.hero .meta{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}
.hero .chip{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:3px 14px;font-size:13px}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 24px;margin-bottom:30px}
nav.toc h2{margin:0 0 10px;font-size:17px}
nav.toc ol{margin:0;padding-left:22px;columns:2;column-gap:40px}
nav.toc li{margin:4px 0;break-inside:avoid}
nav.toc a{color:var(--blue);text-decoration:none}
nav.toc a:hover{text-decoration:underline}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 30px;margin-bottom:26px}
h2.sec{margin:0 0 4px;font-size:23px;border-bottom:2px solid var(--blue-bg);padding-bottom:10px}
h2.sec .no{display:inline-block;background:var(--blue);color:#fff;border-radius:8px;font-size:15px;padding:1px 10px;margin-right:10px;vertical-align:2px}
.secsub{color:var(--sub);margin:8px 0 18px;font-size:14px}
h3{font-size:18px;margin:26px 0 10px}
h4{font-size:15.5px;margin:18px 0 8px}
code{font-family:"SF Mono",ui-monospace,Consolas,Menlo,monospace;font-size:13px;background:#eef1f6;border-radius:5px;padding:1px 6px;color:#334155}
p{margin:8px 0}
a{color:var(--blue)}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
th{background:#f0f3f8;font-weight:600}
.warn{background:var(--orange-bg);border:1px solid #fde68a;border-radius:10px;padding:12px 16px;margin:12px 0;font-size:14px}
.tip{background:var(--green-bg);border:1px solid #a7f3d0;border-radius:10px;padding:12px 16px;margin:12px 0;font-size:14px}
kbd{background:#e8ebf2;border:1px solid #cbd5e1;border-bottom-width:2px;border-radius:5px;padding:1px 7px;font-size:12px}
.arch{display:flex;flex-direction:column;gap:0;align-items:center;margin:18px 0}
.arch .row{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;width:100%}
.nbox{border-radius:10px;padding:10px 16px;font-size:13.5px;text-align:center;border:2px solid;min-width:120px}
.nbox b{display:block;font-size:14px}
.nbox small{opacity:.85}
.nb-user{background:var(--purple-bg);border-color:var(--purple);color:var(--purple)}
.nb-web{background:var(--blue-bg);border-color:var(--blue);color:var(--blue)}
.nb-api{background:var(--teal-bg);border-color:var(--teal);color:var(--teal)}
.nb-worker{background:var(--orange-bg);border-color:var(--orange);color:var(--orange)}
.nb-store{background:var(--green-bg);border-color:var(--green);color:var(--green)}
.arch .arr{color:#94a3b8;font-size:16px;line-height:1.5;margin:2px 0}
.arch .lbl{font-size:12px;color:var(--sub);margin-top:-4px}
.chain{margin:14px 0}
.step{border:1px solid var(--line);border-left:5px solid var(--blue);border-radius:12px;background:#fbfcfe;margin:0;padding:0;overflow:hidden}
.stephead{display:flex;align-items:center;gap:10px;padding:10px 16px;background:#f2f5fa;flex-wrap:wrap}
.stepnum{background:var(--blue);color:#fff;font-weight:700;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:13px;flex:none}
.steptitle{font-weight:650;font-size:15px}
.actor{font-size:12px;border-radius:999px;padding:1px 11px;font-weight:600;flex:none}
.actor.front{background:var(--purple-bg);color:var(--purple)}
.actor.api{background:var(--teal-bg);color:var(--teal)}
.actor.worker{background:var(--orange-bg);color:var(--orange)}
.actor.db{background:var(--green-bg);color:var(--green)}
.actor.model{background:var(--red-bg);color:var(--red)}
.stepbody{padding:10px 18px 14px}
.refs{margin:6px 0}
.ref{font-size:13px;color:#475569;margin:2px 0}
.ref code{background:#e8edf5;color:#1d4ed8}
.steptext{font-size:14.5px}
.note{background:var(--green-bg);border-radius:8px;padding:8px 14px;margin-top:8px;font-size:13.5px}
.chain .arr{text-align:center;color:#94a3b8;font-size:15px;line-height:1.4;margin:4px 0}
.grouph{font-size:19px;border-left:5px solid var(--teal);padding-left:12px;margin-top:34px}
.grouph .cnt{font-size:13px;color:var(--sub);font-weight:400;margin-left:10px}
.dirdesc{font-size:13.5px;color:var(--sub);background:#f2f5fa;border-radius:8px;padding:6px 14px;margin:14px 0 8px}
details.filecard{border:1px solid var(--line);border-radius:10px;margin:7px 0;background:#fff}
details.filecard summary{cursor:pointer;padding:9px 14px;display:flex;align-items:baseline;gap:10px;list-style:none;flex-wrap:wrap}
details.filecard summary::-webkit-details-marker{display:none}
details.filecard.core{border-left:4px solid var(--orange);background:#fffdf7}
details.filecard.core .fname{color:#b45309}
.star{color:#d97706;font-size:14px}
.fname{font-weight:650;color:#0f172a;font-size:13.5px}
.fdesc{color:var(--sub);font-size:13px;flex:1;min-width:260px}
.chev{font-size:11px;color:#94a3b8;border:1px solid var(--line);border-radius:999px;padding:0 9px;flex:none}
.fpath{font-size:12px;color:#64748b;background:#f8fafc;border-bottom:1px solid var(--line);padding:6px 16px;font-family:ui-monospace,Consolas,monospace;word-break:break-all}
.mlist{list-style:none;margin:8px 0;padding:0 0 6px 4px}
.mlist li{padding:3px 0 3px 14px;border-left:2px solid #eef1f6;margin-left:10px;position:relative}
.mlist li:before{content:"▸";position:absolute;left:0;color:#b6c0cf;font-size:12px}
.mlist.sub{margin-top:3px}
.mhead{display:inline}
.mname{background:#eef2ff;color:#3730a3;font-weight:600}
.mln{color:#94a3b8;font-size:11.5px;margin:0 6px}
.mdoc{color:#475569;font-size:13px}
.mdoc.none{color:#b0b8c4;font-style:italic}
.badge{font-size:11px;border-radius:4px;padding:0 6px;margin-right:4px;font-weight:600}
.badge.fn{background:#dbeafe;color:#1d4ed8}
.badge.cls{background:#fce7f3;color:#be185d}
.nomethod{color:#94a3b8;font-size:13px;margin:6px 16px}
.mchips{font-size:12px;margin:2px 0 4px 8px;line-height:1.9}
.mchips .cc{background:#f0f7ff;color:#1d4ed8;padding:0 5px;font-size:11.5px}
.mchips .cf{color:#8a94a6;font-size:11px;margin-right:6px}
.mchips .cmore{color:#b45309;font-size:11px;background:#fff4dd;border-radius:4px;padding:0 5px}
.mchips.out{border-left:8px solid #dbeafe;padding-left:4px}
.apisech{font-size:12.5px;color:#8a94a6;margin:10px 0 2px 14px}
.mchips.in{border-left:8px solid #fde2e4;padding-left:4px}
/* 调用树 */
details.treebox{border:1px solid var(--line);border-radius:12px;margin:14px 0;background:#fff}
details.treebox summary{cursor:pointer;padding:10px 16px;display:flex;align-items:center;gap:12px;list-style:none;flex-wrap:wrap;background:#f2f5fa;border-radius:12px}
details.treebox summary::-webkit-details-marker{display:none}
.treecnt{font-size:12px;color:var(--sub);background:#e8edf5;border-radius:999px;padding:0 10px}
.treedesc{font-size:13px;color:var(--sub);padding:8px 18px 0}
ul.tree{list-style:none;margin:8px 18px 14px;padding-left:6px;font-size:13.5px}
ul.tree ul{list-style:none;border-left:1.5px dashed #c7d0dd;margin-left:9px;padding-left:14px}
ul.tree li{padding:2.5px 0;position:relative}
ul.tree li:before{content:"";position:absolute;left:-14px;top:12px;width:9px;height:1.5px;background:#c7d0dd}
.tn{font-family:"SF Mono",ui-monospace,Consolas,Menlo,monospace;font-weight:600;color:#1e293b;background:#f1f5f9;border-radius:4px;padding:0 5px;font-size:12.5px}
.tfb{font-size:11px;border-radius:4px;padding:0 6px;margin-left:6px}
.l-r{background:var(--teal-bg);color:var(--teal)}
.l-s{background:var(--blue-bg);color:var(--blue)}
.l-q{background:var(--purple-bg);color:var(--purple)}
.l-a{background:var(--orange-bg);color:var(--orange)}
.l-t{background:var(--green-bg);color:var(--green)}
.l-k{background:#fdf2ec;color:#b45309}
.l-m{background:var(--red-bg);color:var(--red)}
.l-o{background:#f1f5f9;color:#64748b}
.trep{color:#94a3b8;font-style:italic}
.tdup{color:#b0b8c4;font-size:12px;margin-left:6px}
.tnew{background:#fff1f2;color:#be123c;border-radius:4px;font-size:11px;padding:0 5px;font-weight:600}
.tmark{color:#b45309;font-weight:700}
.toolbar{position:sticky;top:0;z-index:50;background:rgba(246,247,250,.94);backdrop-filter:blur(4px);border-bottom:1px solid var(--line);padding:8px 0;margin-bottom:22px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.toolbar button{border:1px solid var(--blue);color:var(--blue);background:#fff;border-radius:8px;padding:4px 14px;font-size:13px;cursor:pointer}
.toolbar button:hover{background:var(--blue-bg)}
.toolbar .hint{font-size:12.5px;color:var(--sub)}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--sub);margin:4px 0 10px;align-items:center}
footer{color:#94a3b8;text-align:center;font-size:12.5px;margin-top:36px}
@media print{.toolbar{display:none}details.filecard,details.treebox{page-break-inside:avoid}}
@media (max-width:720px){nav.toc ol{columns:1}section{padding:18px 16px}header.hero{padding:28px 22px}}
"""

JS = """
document.addEventListener('DOMContentLoaded',function(){
  function btn(id,fn){var b=document.getElementById(id);if(b)b.addEventListener('click',fn);}
  btn('exp-all',function(){document.querySelectorAll('details.filecard').forEach(function(d){d.open=true});});
  btn('col-all',function(){document.querySelectorAll('details.filecard').forEach(function(d){d.open=false});});
  btn('exp-core',function(){document.querySelectorAll('details.filecard').forEach(function(d){d.open=d.classList.contains('core')});});
});
"""

ARCH_HTML = '''
<div class="arch">
 <div class="row"><div class="nbox nb-user"><b>👤 用户</b><small>浏览器</small></div></div>
 <div class="arr">▼ 打开页面 / 发消息</div>
 <div class="row"><div class="nbox nb-web"><b>web 前端</b><small>Vue 3 + Vite（5173）</small></div></div>
 <div class="arr">▼ 所有请求走 /api（HTTP + SSE）</div>
 <div class="row">
   <div class="nbox nb-api"><b>api 服务</b><small>FastAPI（server/main.py）</small></div>
   <div style="display:flex;align-items:center;color:#94a3b8;padding:0 4px">⇄</div>
   <div class="nbox nb-worker"><b>worker 服务</b><small>ARQ（server/worker_main.py）</small></div>
 </div>
 <div class="lbl">api 把任务投递到 Redis 队列；worker 领取执行，执行事件写回 Redis Stream</div>
 <div class="arr">▼ 读写</div>
 <div class="row">
   <div class="nbox nb-store"><b>PostgreSQL</b><small>业务数据·队列·Run·checkpoint</small></div>
   <div class="nbox nb-store"><b>Redis</b><small>ARQ 队列·事件流·缓存</small></div>
   <div class="nbox nb-store"><b>MinIO</b><small>附件·知识库原始文件</small></div>
   <div class="nbox nb-store"><b>Milvus</b><small>向量检索</small></div>
   <div class="nbox nb-store"><b>Neo4j</b><small>知识图谱</small></div>
 </div>
 <div class="arr">▼ worker 执行智能体时调用</div>
 <div class="row">
   <div class="nbox nb-store"><b>大模型 API</b><small>OpenAI 兼容等</small></div>
   <div class="nbox nb-store"><b>沙盒 sandbox-provisioner</b><small>隔离执行命令</small></div>
   <div class="nbox nb-store"><b>OCR/解析服务</b><small>MinerU / PaddleOCR</small></div>
 </div>
</div>
<p class="tip"><b>一句话总结：</b>用户在 Vue 页面上操作 → 前端把请求发给 FastAPI → API 先把事实写进 PostgreSQL，再把任务丢进 Redis 队列 → 独立的 worker 进程领取任务、调用大模型和工具执行智能体 → 执行过程的事件写进 Redis Stream → 前端通过 SSE 实时收到打字机效果的回复。这就是 Yuxi 的骨架，其余全部是这条主干上的细节。</p>
'''

CONCEPTS = '''
<table>
<tr><th style="width:130px">名词</th><th>小白解释</th></tr>
<tr><td><b>Agent 智能体</b></td><td>一个「会干活的角色」。由 <code>Agent</code> 表的一条记录（名字、图标、配置）+ 一个执行后端（backend）组成。默认的那个叫「智能助手」（ChatbotAgent）。</td></tr>
<tr><td><b>Backend 后端（智能体的）</b></td><td>智能体的「发动机型号」。内置两种：<code>ChatbotAgent</code>（主对话）和 <code>SubAgentBackend</code>（被主智能体调用的子智能体）。注册表在 <code>yuxi/agents/buildin/__init__.py</code>。</td></tr>
<tr><td><b>Thread / Conversation</b></td><td>一次会话（聊天窗口）。前端地址栏 <code>/agent/:thread_id</code> 里的那串 ID。所有消息、附件、项目绑定都挂在它上面。</td></tr>
<tr><td><b>Message</b></td><td>会话里的一条消息（用户发的、AI 回的、工具执行的）。</td></tr>
<tr><td><b>AgentRunRequest（请求）</b></td><td>用户发一条消息产生的「排队凭证」。先写进数据库，决定这条消息是立即执行、排队等待，还是被拒绝。</td></tr>
<tr><td><b>AgentRun（运行）</b></td><td>一次真正的执行任务。一条请求派发后变成一个 Run，交给 worker 执行。审批后「继续运行」会创建新的 Run（resume 类型）。</td></tr>
<tr><td><b>队列策略 queue_policy</b></td><td>线程里已有正在跑的 Run 时怎么办：<code>enqueue</code> 排队（默认）、<code>reject</code> 拒绝、<code>steer</code> 转向（接替当前运行）。</td></tr>
<tr><td><b>租约 Lease</b></td><td>worker 执行 Run 前「抢锁」。抢到的那个 worker 才能执行并定期续租（心跳）；worker 崩了租约过期，系统自动把 Run 收敛为失败，不会卡死。</td></tr>
<tr><td><b>ARQ</b></td><td>基于 Redis 的 Python 异步任务队列库。api 进程把任务投进 Redis，worker 进程取出来执行。</td></tr>
<tr><td><b>LangGraph</b></td><td>把「模型 ↔ 工具」的循环建成一张状态图的框架。Yuxi 的智能体循环（模型思考→调工具→看结果→继续）由它驱动，状态检查点(checkpoint)存在 PostgreSQL。</td></tr>
<tr><td><b>Middleware 中间件</b></td><td>包在模型外面的能力层，像洋葱：文件系统、Skills、长期记忆、子任务、摘要压缩、网络重试、Token 统计、工具审批……在 <code>yuxi/agents/middlewares/</code>。</td></tr>
<tr><td><b>Tool 工具</b></td><td>智能体能调用的函数：读/写/搜文件、联网搜索、OCR、查知识库、跑 MySQL……在 <code>yuxi/agents/toolkits/</code> 注册。</td></tr>
<tr><td><b>Skill</b></td><td>给智能体的「技能包」（一个含 SKILL.md 的目录），可以带脚本和提示词，运行时只读共享给智能体。</td></tr>
<tr><td><b>MCP</b></td><td>Model Context Protocol，接外部工具服务的标准协议。管理界面在「扩展中心」。</td></tr>
<tr><td><b>SubAgent 子智能体</b></td><td>主智能体用 <code>subagent_start</code> 工具派出去干活的子任务，有自己独立的 Run 与线程，共享同一个工作目录。</td></tr>
<tr><td><b>SSE</b></td><td>Server-Sent Events，服务器向浏览器单向推流的 HTTP 长连接。你看到的「打字机效果」就是它。</td></tr>
<tr><td><b>Workdir 工作目录</b></td><td>智能体的「硬盘」。每个项目(Project)对应磁盘上一个真实目录，文件是实时的，Run 结束后保留。安全模块 <code>yuxi/workspace/</code> 唯一拥有宿主路径访问。</td></tr>
<tr><td><b>Durable Task 持久任务</b></td><td>知识库解析、评估这类后台任务的可靠执行机制：先写 PostgreSQL（task_type + payload），worker 按租约执行，崩溃可恢复。</td></tr>
<tr><td><b>Docker Compose</b></td><td>本地开发/部署的事实来源：起 api、worker、web、postgres、redis、minio、milvus、neo4j 等一组容器。开发时先看 <code>docker-compose.yml</code>。</td></tr>
</table>
'''

DIRMAP = '''
<h3>后端 backend/</h3>
<table>
<tr><th style="width:280px">目录 / 文件</th><th>职责（一句话）</th></tr>
<tr><td><code>server/main.py</code></td><td>FastAPI 入口：建 app、挂路由、CORS、限流中间件</td></tr>
<tr><td><code>server/worker_main.py</code></td><td>ARQ worker 进程入口</td></tr>
<tr><td><code>server/routers/</code>（26 个）</td><td>全部 HTTP 路由：agent、auth、chat、knowledge、mcp、skill……路由很「薄」，只做参数校验和转发</td></tr>
<tr><td><code>server/utils/</code></td><td>lifespan 启动流程、认证依赖、访问日志</td></tr>
<tr><td><code>package/yuxi/services/</code>（43 个）</td><td><b>用例层</b>：一个业务动作一个函数（发消息、排队、执行 Run、知识库任务……）</td></tr>
<tr><td><code>package/yuxi/agents/</code></td><td>智能体定义：基类、内置智能体、中间件、工具箱、Skills、MCP、后端</td></tr>
<tr><td><code>package/yuxi/repositories/</code>（23 个）</td><td><b>数据访问层</b>：所有 SQL 查询都在这里，按业务对象分文件</td></tr>
<tr><td><code>package/yuxi/storage/</code></td><td>postgres / redis / minio / neo4j 四种存储的连接与客户端</td></tr>
<tr><td><code>package/yuxi/knowledge/</code></td><td>知识域：解析(parser)、分块(chunking)、向量库(implementations)、图谱(graphs)、评估(eval)</td></tr>
<tr><td><code>package/yuxi/models/</code></td><td>大模型适配：chat / embed / rerank 三类模型的加载调用</td></tr>
<tr><td><code>package/yuxi/workspace/</code></td><td>用户工作区：路径映射、安全文件原语、Workdir、预览</td></tr>
<tr><td><code>package/yuxi/config · utils · permissions</code></td><td>目录约定、通用工具（认证/日志/时间/SSE）、权限</td></tr>
<tr><td><code>test/</code></td><td>测试：unit / integration / e2e 三层</td></tr>
</table>
<h3>前端 web/src/</h3>
<table>
<tr><th style="width:280px">目录 / 文件</th><th>职责（一句话）</th></tr>
<tr><td><code>main.js · App.vue</code></td><td>应用入口与根组件</td></tr>
<tr><td><code>router/</code></td><td>路由表 + 登录/管理员守卫</td></tr>
<tr><td><code>apis/</code>（22 个）</td><td><b>唯一的后端请求出口</b>：base.js 统一封装，其余按业务分文件</td></tr>
<tr><td><code>stores/</code>（10 个）</td><td>Pinia 跨页面状态：用户、线程、配置、主题……</td></tr>
<tr><td><code>composables/</code>（12 个）</td><td>可组合逻辑：排队、Run SSE、流式渲染、审批、子任务</td></tr>
<tr><td><code>views/</code>（14 个）</td><td>页面级组件：AgentView（对话）、WorkspaceView、DashboardView……</td></tr>
<tr><td><code>components/</code>（约 130 个）</td><td>界面积木：AgentChatComponent 是最大的核心组件（5600+ 行）</td></tr>
<tr><td><code>utils/</code>（63 个）</td><td>纯函数工具：消息处理、Markdown、时间、断线恢复……</td></tr>
</table>
<div class="tip"><b>改代码先看这张表：</b>加接口 → <code>routers</code> + <code>apis</code>；改业务流程 → <code>services</code>；改智能体行为 → <code>agents</code>；改 SQL → <code>repositories</code>；改页面 → <code>views/components</code>。路由层永远不要直接写 SQL。</div>
'''

chain_a = "".join([
arrow(),
step(1, ("前端·输入", "front"), "用户点击发送，聊天组件收集输入",
     ["web/src/components/AgentChatComponent.vue → handleSendMessage() (约 L3299)",
      "web/src/components/MessageInputComponent.vue / AgentInputArea.vue（输入框、图片、@ 提及）"],
     "把用户输入的<b>文本、图片、附件、当前选择的模型、审批模式</b>都收集起来。如果这个会话还没有 thread_id，先调 <code>ensureActiveThread()</code>（单飞防重）→ chatThreadsStore.createThread → <code>POST /api/chat/thread</code> 创建一个新会话；第一条消息还会异步调 <code>agentApi.generateTitle()</code> 自动起会话标题。"),
step(2, ("前端·乐观更新", "front"), "先在界面上「骗」出这条消息（乐观插入）",
     ["AgentChatComponent.vue → insertOptimisticHumanMessage()",
      "web/src/composables/useAgentThreadState.js（每线程的运行状态）"],
     "不等服务器确认，先把你发的消息立刻显示在聊天区（这叫<b>乐观更新</b>，让界面显得快）。如果线程里已有正在运行的 Run，则把这条请求放进 <code>queuedRequests</code> 排队列表展示。"),
step(3, ("前端·HTTP", "front"), "调用 API：创建一次 Agent 运行",
     ["web/src/apis/agent_api.js → agentApi.createAgentRun()",
      "web/src/apis/base.js → apiPost()（统一加 Token、统一错误处理）"],
     "发出 <code>POST /api/agent/runs</code>，请求体包含 query、agent_slug、thread_id、request_id（前端生成的幂等 ID）、图片、模型覆盖 model_spec、审批模式、排队策略 queue_policy。"),
step(4, ("后端·API", "api"), "FastAPI 路由接住请求，先验身份再组装参数",
     ["backend/server/main.py（app 挂载全部 /api 路由）",
      "backend/server/routers/agent_router.py → create_agent_run()",
      "backend/server/utils/auth_middleware.py → get_current_user()（验 JWT / API Key）",
      "backend/package/yuxi/services/input_message_service.py → build_chat_input_message()"],
     "路由函数先通过 <code>get_required_user</code> 依赖完成认证（解析 Bearer Token 或 API Key 得到当前用户）；若带了 <code>resume</code> 参数则走「恢复运行」分支（见链路 F），否则把 query+图片封装成标准输入消息，交给用例层 <code>submit_agent_request()</code>。"),
step(5, ("后端·API", "api"), "提交用例：一个事务里写好「事实」，才谈执行",
     ["backend/package/yuxi/services/agent_request_service.py → submit_agent_request() (L72)",
      "→ _persist_request()：同一事务写 Message（用户消息）+ AgentRunRequest（排队凭证）",
      "backend/package/yuxi/services/workdir_service.py → resolve_conversation_workdir_binding()（解析工作目录）"],
     "这是整个系统最重要的设计：<b>先把「这条消息确实收到了」写进 PostgreSQL（同一事务：用户消息 + 请求记录），提交成功后才去投递执行任务</b>。这样即使队列丢消息，数据库里的事实还在，可恢复、可对账。同时做幂等（同 request_id 直接返回已有状态）。"),
step(6, ("后端·API", "api"), "排队判定：立即执行？排队？拒绝？",
     ["backend/package/yuxi/services/agent_request_queue_service.py → dispatch_ready_head() / _get_queue_state()",
      "backend/package/yuxi/services/agent_run_service.py → prepare_agent_run_creation_scope()（冻结配置快照）→ persist_agent_run_record()（写 AgentRun）→ enqueue_agent_run()（投递）"],
     "检查这个线程有没有正在跑的 Run：没有 → 创建 AgentRun（把模型、审批模式、工作目录<b>冻结成快照</b>存进 Run，之后改配置不影响本次运行）并投递；有 → 按 queue_policy 决定排队（状态 <code>queued</code>）、拒绝（<code>rejected</code>）或 steer 接替。接口把 request_id / 状态 / run_id 返回给前端。"),
step(7, ("前端·SSE①", "front"), "排队阶段：先订阅「请求事件流」",
     ["web/src/composables/useAgentRequestQueue.js → startRequestStream()",
      "GET /api/agent/requests/{request_id}/events → stream_request_events()（排队 SSE）"],
     "如果返回状态是 queued，前端先订阅<b>请求 SSE</b>，实时显示「排在第几位」；一旦后端把它派发成 Run（SSE 里收到 run_id），前端自动切换到<b>Run SSE</b>（下一步）。"),
step(8, ("后端·Worker", "worker"), "worker 领取任务：先抢租约，再干活",
     ["backend/server/worker_main.py → main()（worker 进程入口）",
      "backend/package/yuxi/services/run_worker.py → process_agent_run() (L843)",
      "→ mark_run_running()（抢占租约）· _heartbeat_lease()（后台心跳续租）",
      "→ _validate_run_workdir_binding() · prepare_and_record_run_execution()（固化执行清单）"],
     "ARQ worker 从 Redis 队列领到 run_id 后，先用带身份的 token 抢占 Run 租约——<b>抢不到说明别的 worker 已在执行，直接退出</b>（防止重复执行）。抢到后启动两个后台协程：心跳续租 + 监听取消信号；然后校验工作目录、固化执行清单（manifest），一切就绪才开始跑。"),
step(9, ("后端·Worker", "worker"), "智能体执行编排：找到「发动机」并装配",
     ["backend/package/yuxi/services/chat_service.py → stream_agent_chat() (L1004)",
      "→ _resolve_agent_runtime()（按 run 记录找到 Agent 定义 + 后端 + Context，用第 6 步冻结的快照）",
      "→ ConversationRepository.get_attachments()（把本线程附件信息塞进用户消息）",
      "→ 然后释放业务数据库连接（执行期间不再占用）"],
     "注意一个细节：智能体执行期间<b>不持有业务数据库连接</b>，模型调用可能持续几分钟，连接池不能被耗干；LangGraph 的状态检查点走独立的连接池。"),
step(10, ("后端·Worker", "worker"), "构图：模型 + 工具 + 提示词 + 中间件 = 一个智能体",
     ["backend/package/yuxi/agents/buildin/chatbot/graph.py → ChatbotAgent.get_graph()",
      "backend/package/yuxi/models/chat.py → load_chat_model()（按 provider/model 名加载真实模型客户端）",
      "backend/package/yuxi/agents/toolkits/service.py → resolve_configured_runtime_tools()（把勾选的工具变成实例）",
      "backend/package/yuxi/agents/base.py → BaseAgent._stream_input_with_state() → graph.astream_events()"],
     "以默认「智能助手」为例：<code>create_agent()</code>（LangChain）把四样东西组装成一张 LangGraph 执行图：<b>① 模型</b>（load_chat_model 按「供应商/模型名」加载）<b>② 工具</b>（用户勾选的）<b>③ 系统提示词</b>（build_prompt_with_context 拼装角色设定）<b>④ 中间件栈</b>（下一步）。然后逐事件地流式执行。"),
step(11, ("后端·Worker", "worker"), "中间件栈：智能体的「能力洋葱」",
     ["backend/package/yuxi/agents/buildin/chatbot/graph.py → _build_middlewares()",
      "backend/package/yuxi/agents/middlewares/（每个中间件一个文件）"],
     "从内到外依次是：<code>SteerMiddleware</code>（运行中接受转向指令）→ <b>文件系统</b>（读写工作区文件，超长输出会被裁剪）→ <b>Skills</b>（注入技能包说明）→ <b>Memory</b>（长期记忆）→ <b>SubAgent</b>（subagent_start/await 工具）→ <b>摘要压缩</b>（对话太长自动总结）→ TodoList（任务清单）→ <b>网络重试</b>（断网指数退避重试）→ 图片兼容 → <b>Token 统计</b> → <b>工具审批</b>（危险操作暂停等人批准）。"),
step(12, ("后端·Worker", "worker"), "Agent 循环：模型 ↔ 工具，直到给出最终回答",
     ["LangGraph 自动循环（模型节点 ⇄ 工具节点）",
      "工具实现：yuxi/agents/toolkits/buildin/tools.py（联网搜索、OCR、产物暴露、追问用户）",
      "yuxi/agents/toolkits/kbs/（查知识库 → Milvus 向量检索）",
      "yuxi/workspace/filesystem.py（文件读写，no-follow 防路径逃逸）",
      "yuxi/agents/backends/sandbox/（命令在隔离沙盒执行）"],
     "典型的一轮：模型输出文字 token（同时流给前端）→ 模型说「我要调 read_file 工具」→ LangGraph 执行工具 → 结果回给模型 → 模型继续……直到模型不再要工具，产出最终回答。若审批中间件判定该工具需要人工批准，会触发 <b>interrupt 中断</b>，等人在页面上点「批准/拒绝」（见链路 F）。"),
step(13, ("后端·Worker", "worker"), "事件管道：执行过程变成一条条事件流",
     ["run_worker.py → _consume_stream_with_cancel()（消费执行流）",
      "→ _iter_json_chunks() / ChunkedEventWriter.append+flush()（loading 类小块攒批发送）",
      "→ _map_chunk_to_run_event() → append_run_event() → <b>写入 Redis Stream</b>",
      "→ model_message_audit_service / tool_message_audit_service（模型与工具的审计单独记录）"],
     "每一个 token、每一次工具调用、每个阶段变化都被转换成事件（带序号 seq）写进 Redis Stream。审计消息不进普通聊天历史，单独存表，供调试面板查看。"),
step(14, ("前端·SSE②", "front"), "前端消费 Run SSE：打字机效果就是这么来的",
     ["GET /api/agent/runs/{run_id}/events → agent_run_service.stream_agent_run_events()（把 Redis Stream 转成 SSE）",
      "web/src/composables/useAgentRunStream.js → processRunSseResponse()（手写 SSE 解析）→ dispatchRunEventChunks()",
      "→ useAgentStreamHandler.js → AgentChatComponent 更新消息",
      "web/src/composables/useStreamSmoother.js（平滑打字机）· ToolCallingResult/ToolCallRenderer.vue（工具卡片渲染）"],
     "SSE 事件按 thread_id 路由到对应会话；断线时前端用 <code>Last-Event-ID</code>（事件序号）从断点续拉，页面刷新后也能恢复现场。工具调用显示成可展开的卡片，思考过程显示成「思考中」折叠块。"),
step(15, ("后端·收尾", "worker"), "终态落库 + 自动派发下一条排队消息",
     ["run_worker.py → _finish_run() → mark_run_terminal()（Run 状态写回 PostgreSQL：completed/failed/cancelled）",
      "→ _release_runtime_if_idle()（清理沙盒进程，但保留工作目录文件）",
      "→ agent_request_queue_service.dispatch_next_request()（FIFO 自动派发队头）",
      "前端收到 end 事件 → 线程状态复位，排队中的下一条消息自动开始"],
     "最终回答通过 <code>output_message_id</code> 绑定成可展示消息；阶段耗时从各时间点派生。worker 崩溃时，后台对账循环会发现过期租约，把 Run 幂等收敛为 <code>failed(worker_lease_expired)</code>——这是系统「不会卡死」的关键保险。"),
])

chain_b = "".join([
arrow(),
step(1, ("前端", "front"), "登录页提交表单",
     ["web/src/views/LoginView.vue", "web/src/stores/user.js（保存 Token 与用户信息）"],
     "用户输入账号（支持用户 ID / 手机号）和密码，前端调 <code>auth_api</code> 发起登录。"),
step(2, ("前端·HTTP", "front"), "POST /api/auth/token",
     ["web/src/apis/auth_api.js", "backend/server/main.py 的 LoginRateLimitMiddleware（进程内限流：60 秒最多 10 次）"],
     "登录接口有双重限流：main.py 里的中间件按 IP 内存限流 + login_rate_limit_service 的 Redis 滑动窗口（IP+账号）。"),
step(3, ("后端·API", "api"), "登录用例：查用户、验密码、防爆破",
     ["backend/server/routers/auth_router.py → login_for_access_token() (L221)",
      "backend/package/yuxi/repositories/user_repository.py → get_by_login_identifier()",
      "backend/package/yuxi/utils/auth_utils.py → AuthUtils.verify_password()（bcrypt 校验）",
      "失败 → user.increment_failed_login()（连续失败锁定账户）"],
     "防爆破三件套：通用错误信息（不暴露「用户不存在」）、失败计数锁定、限流。"),
step(4, ("后端·API", "api"), "签发 JWT",
     ["auth_utils.py → AuthUtils.create_access_token()（payload: sub=用户ID）"],
     "登录成功后签发 Bearer Token 返回前端，前端存进 user store（持久化到 localStorage）。"),
step(5, ("之后每个请求", "api"), "认证依赖链",
     ["server/utils/auth_middleware.py → get_current_user()（解析 JWT 或 X-API-Key → _verify_api_key()）",
      "→ get_required_user()（必须登录）→ get_admin_user()（管理员）→ get_superadmin_user()（超级管理员）"],
     "所有业务路由通过 FastAPI 的 <code>Depends()</code> 声明所需权限级别，后端权限检查永远是最终边界；前端路由守卫只管体验。"),
])

chain_c = "".join([
arrow(),
step(1, ("前端", "front"), "上传文档",
     ["web/src/components/FileUploadModal.vue → web/src/apis/knowledge_api.js（文件先传到 MinIO）"],
     "在知识库详情页上传 PDF/Word/图片等，文件本体进 MinIO 对象存储。"),
step(2, ("前端·HTTP", "front"), "提交入库请求",
     ["POST /api/knowledge/databases/{kb_id}/documents"],
     "把文件列表 + 解析参数（OCR 引擎、分块策略等）提交给后端。"),
step(3, ("后端·API", "api"), "路由校验后，提交持久任务",
     ["backend/server/routers/knowledge_router.py → add_documents() (L715)",
      "→ tasker.enqueue(task_type=knowledge_ingest, payload=...)（Durable Task 先写 PostgreSQL）"],
     "和聊天链路同样的哲学：<b>先把任务写进数据库，再投递</b>。接口立刻返回 task_id，进度去任务中心看。"),
step(4, ("后端·Worker", "worker"), "worker 领取任务（惰性加载 Handler）",
     ["backend/package/yuxi/services/task_registry.py → TaskDefinition.load_handler()",
      "backend/package/yuxi/services/task_service.py → TaskContext（带租约的进度/取消边界）",
      "backend/package/yuxi/services/task_queue_service.py（pending 任务由周期 publisher 补发）"],
     "worker 按 task_type 从注册表<b>惰性加载</b> Handler（避免启动加载全部领域代码），用任务租约保证不重复执行。"),
step(5, ("后端·Worker", "worker"), "入库 Handler：解析 → 分块 → 向量化 → 入库",
     ["backend/package/yuxi/services/knowledge_task_service.py → run_knowledge_ingest() (L35)",
      "→ knowledge/parser/unified.py（选 MinerU / PaddleOCR / RapidOCR / DeepSeek OCR 等解析器 → 提取文本）",
      "→ knowledge/chunking/ragflow_like/dispatcher.py（按预设分块：通用/书籍/法律/QA/语义…）",
      "→ models/embed.py（调用向量模型）→ knowledge/implementations/milvus.py（写入 Milvus）",
      "→ repositories/knowledge_file_repository.py（文件状态写回 PostgreSQL）"],
     "每个文件独立处理，失败只标记该文件为 failed，不影响整批。可选再走图谱构建（LLM 抽取实体关系 → Neo4j + Milvus 图索引）。"),
step(6, ("检索时", "worker"), "智能体「查资料」就是这么来的",
     ["智能体勾选知识库 → toolkits/kbs/ 的 query_kb 等工具 → MilvusKB 向量检索（→ 可选 rerank 重排）",
      "结果作为工具输出回到模型 → 模型引用知识库内容回答（前端显示引用来源卡片）"],
     "聊天时你看到的「知识库引用」，就是链路 A 第 12 步的工具调用走了一遍本链路建好的向量索引。"),
])

chain_d = "".join([
arrow(),
step(1, ("后端·Worker", "worker"), "主智能体决定派子任务",
     ["yuxi/agents/middlewares/subagent_task.py → YuxiSubAgentMiddleware（注册 subagent_start / subagent_await 工具）"],
     "主 Agent 的工具列表里有 <code>subagent_start</code>（派出子任务）和 <code>subagent_await</code>（等待结果）。模型像调普通工具一样调用它们。"),
step(2, ("后端·Worker", "worker"), "创建子 Run",
     ["yuxi/services/subagent_run_service.py → SubagentRunService.start() (L105)",
      "→ _create_run_record()（run_type=subagent，挂父子关系）→ _ensure_child_conversation() / _ensure_thread_relation()",
      "→ enqueue（复用与主链路完全相同的队列与 worker）"],
     "子任务不是「函数调用」，而是一个真正的 AgentRun：有自己的租约、心跳、事件流和终态，共享父 Run 的 runtime 和工作目录。"),
step(3, ("后端·Worker", "worker"), "子智能体执行（同链路 A 第 9-13 步）",
     ["yuxi/agents/buildin/subagent/graph.py → SubAgentBackend（受限工具集）",
      "yuxi/agents/presets/subagents/（预置角色：调研员、事实核查员等）"],
     "子智能体默认工具受限（不能无限套娃），预设角色决定其系统提示词。"),
step(4, ("前端", "front"), "页面独立订阅子 Run",
     ["web/src/composables/useSubagentRuns.js · web/src/components/SubagentThreadView.vue",
      "GET /api/agent/runs/{run_id}/events（thread_id 区分父子事件）"],
     "子任务的事件带着自己的 thread_id 写进同一条 Redis Stream，前端按 ID 分流，可以在页面上单独展开看子任务的完整过程。"),
])

chain_e = "".join([
arrow(),
step(1, ("API 进程", "api"), "uvicorn 启动 → lifespan 按顺序拉起组件",
     ["backend/server/main.py → app = FastAPI(lifespan=lifespan)",
      "backend/server/utils/lifespan.py → _startup()"],
     "顺序：安全密钥 → PostgreSQL 连接池 + <b>Schema 版本校验</b>（改表只由 storage-migrator 容器做，api 只校验）→ 系统配置入库 → 内置 MCP → 内置 Skills → 默认智能体 → 内置模型供应商 → 知识库运行时 → Redis → 沙盒 Provider → LangGraph checkpointer。任何一个必需组件失败，进程拒绝接流量（readiness 不通过）。"),
step(2, ("Worker 进程", "worker"), "ARQ worker 启动 → 注册任务与对账循环",
     ["backend/server/worker_main.py → yuxi/services/arq_worker.py → run_worker(WorkerSettings)",
      "run_worker.py → WorkerSettings.functions = [process_agent_run（Run 执行）, process_task（Durable Task 执行）]",
      "→ _reconcile_agent_run_leases_forever()（过期 Run 租约对账）",
      "→ _reconcile_durable_tasks_forever()（持久任务对账补发）"],
     "worker 一边领新任务，一边两个后台循环持续「打扫」：把失联的 Run 收敛为失败、把 pending 的 Durable Task 补发。"),
step(3, ("前端", "front"), "Vite dev server / 构建产物",
     ["web/src/main.js → createApp → 挂载 Pinia + Router + Ant Design Vue"],
     "开发环境 5173 端口热重载，生产构建后由 nginx 之类的静态服务提供。"),
])

chain_f = "".join([
arrow(),
step(1, ("后端·Worker", "worker"), "工具触发人工审批 / 追问",
     ["yuxi/agents/tool_approval.py → create_tool_approval_middleware()",
      "toolkits/buildin/tools.py → ask_user_question()（主动追问用户）"],
     "审批模式下，写文件、执行命令等操作会触发 LangGraph <b>interrupt</b>：智能体暂停，等待人类输入。"),
step(2, ("后端·收尾", "worker"), "Run 进入 interrupted，状态存进 checkpoint",
     ["run_worker.py 捕获 interrupt → Run 状态 interrupted（LangGraph checkpoint 已保存暂停点）"],
     "注意：interrupted 是「暂停」，不是失败——对话状态完整保存在 PostgreSQL 的 checkpoint 里。"),
step(3, ("前端", "front"), "弹出审批框，用户选择",
     ["web/src/components/HumanApprovalModal.vue · web/src/composables/useApproval.js"],
     "用户可以批准/拒绝工具调用，或回答智能体的追问。"),
step(4, ("前端·HTTP", "front"), "提交 resume 请求",
     ["POST /api/agent/runs（带 resume 载荷）→ agent_router.create_agent_run() 走 resume 分支",
      "→ agent_run_service.create_resume_run_view()（新建一个 run_type=resume 的 Run）"],
     "恢复<b>不重新排队</b>：直接创建新 Run，从 checkpoint 恢复智能体状态继续执行。"),
step(5, ("后端·Worker", "worker"), "worker 从断点继续",
     ["run_worker.py → stream_agent_resume()（chat_service.py L1293）→ LangGraph 从 checkpoint 恢复 → 后续同链路 A"],
     "对用户来说就是：点了「批准」，智能体接着刚才的进度继续干活。"),
])

STORAGE = '''
<table>
<tr><th style="width:130px">存储</th><th>存什么</th><th>关键代码</th></tr>
<tr><td><b>PostgreSQL</b></td><td>用户/部门、智能体定义、会话与消息、AgentRunRequest（队列）、AgentRun（运行+租约+attempt）、Durable Task、API Key、项目、定时任务、知识库元数据、模型/工具审计、<b>LangGraph checkpoint（智能体暂停恢复的存档）</b></td><td><code>storage/postgres/models_business.py · models_knowledge.py · manager.py</code></td></tr>
<tr><td><b>Redis</b></td><td>ARQ 任务队列、Run 事件 Stream（打字机效果的来源）、取消信号 key、模型与配置缓存</td><td><code>storage/redis/ · services/run_queue_service.py</code></td></tr>
<tr><td><b>MinIO</b></td><td>聊天附件、知识库原始文件、Office→PDF 预览缓存</td><td><code>storage/minio/ · services/attachment_service.py</code></td></tr>
<tr><td><b>Milvus</b></td><td>文档向量（检索）、图谱实体/关系向量（+etcd 协调）</td><td><code>knowledge/implementations/milvus.py · graphs/</code></td></tr>
<tr><td><b>Neo4j</b></td><td>知识图谱（实体-关系网络）</td><td><code>storage/neo4j/</code></td></tr>
<tr><td><b>沙盒</b></td><td>智能体执行命令/脚本的隔离环境（惰性创建，Run 结束销毁）</td><td><code>agents/backends/sandbox/</code></td></tr>
<tr><td><b>文件系统</b></td><td>每个用户的工作区（Workdir）：智能体写的文件、上传的产物——<b>是实时的事实源，Run 结束不删除</b></td><td><code>yuxi/workspace/</code></td></tr>
</table>
<h4>三套后台任务机制（不要混淆）</h4>
<table>
<tr><th>机制</th><th>用途</th><th>入口</th></tr>
<tr><td><b>AgentRun</b></td><td>智能体对话执行（含 resume / subagent）</td><td><code>process_agent_run</code></td></tr>
<tr><td><b>用户定时 Agent</b></td><td>定时触发智能体（调度锁防并发）</td><td><code>scheduled_agent_service</code> → 复用 AgentRun 链路</td></tr>
<tr><td><b>Durable Task</b></td><td>知识库解析/评估/图谱构建</td><td><code>task_registry</code> → 各领域 Handler</td></tr>
</table>
'''

FAQ = '''
<h3>想改 XXX，从哪个文件开始？</h3>
<table>
<tr><th>想做的事</th><th>先看这些文件</th></tr>
<tr><td>改智能体的人设/提示词</td><td><code>agents/buildin/chatbot/prompt.py</code>、<code>agents/presets/</code></td></tr>
<tr><td>给智能体加一个新工具</td><td><code>agents/toolkits/</code>（buildin/ 或 kbs/）+ <code>toolkits/registry.py</code> 注册</td></tr>
<tr><td>改排队/并发策略</td><td><code>services/agent_request_queue_service.py</code>、<code>run_worker.py 的 worker_max_jobs</code></td></tr>
<tr><td>加一个新 HTTP 接口</td><td><code>server/routers/新文件.py</code> + <code>server/routers/__init__.py</code> 注册 + 前端 <code>apis/</code> 加封装</td></tr>
<tr><td>改数据库表</td><td><code>storage/postgres/models_*.py</code> + <code>storage_migrations/</code> 加迁移（由 storage-migrator 执行）</td></tr>
<tr><td>支持新的大模型供应商</td><td><code>models/chat.py</code> + 管理页配置 Provider</td></tr>
<tr><td>改聊天界面交互</td><td><code>components/AgentChatComponent.vue</code>（注意 5600+ 行，先搜索函数名定位）</td></tr>
<tr><td>改知识库解析/分块</td><td><code>knowledge/parser/</code>、<code>knowledge/chunking/ragflow_like/parsers/</code></td></tr>
</table>
<h3>常见疑问</h3>
<p><b>Q：为什么回复是「打字机」效果？</b><br>A：worker 把每个 token 写成事件进 Redis Stream → SSE 接口转推 → 前端 useStreamSmoother 平滑展示。全链路见链路 A 第 13-14 步。</p>
<p><b>Q：为什么要有「先写数据库再投队列」两步？</b><br>A：保证「事实先于消息」。队列可能丢、worker 可能崩，但数据库里的记录永远可以对账恢复——这是本系统最重要的架构不变量。</p>
<p><b>Q：两个 worker 同时领到同一个 Run 会怎样？</b><br>A：只有抢到租约（mark_run_running）的那个会执行，另一个直接退出。租约靠心跳续期，过期会被对账循环收敛成失败。</p>
<p><b>Q：智能体写的文件存哪了？</b><br>A：每个项目一个 Workdir（宿主 <code>用户数据目录/projects/...</code>），Run 结束保留；智能体内部看到的路径是 <code>/home/gem/user-data/...</code>，由 <code>agents/backends/paths.py</code> 映射。</p>
<p><b>Q：我该按什么顺序读源码？</b><br>A：① 第 4 章链路 A 的 15 步按顺序点开文件看 → ② 第 5 章的调用树从入口函数往下钻 → ③ <code>agents/buildin/chatbot/graph.py</code> → ④ 打开 Docker Compose 对照容器再看一遍链路 E。</p>
'''

HOWTOREAD = '''
<div class="tip">
<b>本文档怎么用：</b>第 1-4 章从头读到尾，是建立全局认知的最短路径；<b>第 5 章是「A 文件的哪个方法调用 B 文件的哪个方法」的精确答案</b>（调用树 + 全量边）；第 6-7 章是<b>全量文件清单</b>——每个方法下方都列出了它「调用了谁（→ 调用）」和「被谁调用（← 被调）」。<b>★ 标记 = 核心链路文件</b>。支持 <kbd>Ctrl</kbd>+<kbd>F</kbd> 搜索。
</div>
<div class="legend">
<span><span class="star">★</span> 核心链路文件</span>
<span><code class="cc">方法()</code><span class="cf">@文件</span> 一条调用边</span>
<span><span class="tmark">≈</span> 静态推断（少数可能不准）</span>
<span><span class="tmark">⭢</span> FastAPI Depends 依赖</span>
<span><span class="tnew">new</span> 类实例化</span>
</div>
'''

def build():
    toc = '''
<nav class="toc" id="toc"><h2>📑 目录</h2><ol>
<li><a href="#s1">Yuxi 是什么？一张图看懂</a></li>
<li><a href="#s2">三分钟名词表（小白版）</a></li>
<li><a href="#s3">目录地图：每个目录是干嘛的</a></li>
<li><a href="#s4">核心调用链（6 条链路 · 38 步）</a>
 <ul><li><a href="#c-a">A. 一条聊天消息的一生（最核心）</a></li>
 <li><a href="#c-b">B. 登录与认证</a></li>
 <li><a href="#c-c">C. 知识库文档入库与检索</a></li>
 <li><a href="#c-d">D. SubAgent 子任务</a></li>
 <li><a href="#c-e">E. 服务启动</a></li>
 <li><a href="#c-f">F. 工具审批与中断恢复</a></li></ul></li>
<li><a href="#s5">方法级调用图：哪个方法调用哪个方法</a></li>
<li><a href="#s6">后端全量文件清单（每个方法 · 每条调用边）</a></li>
<li><a href="#s7">前端全量文件清单（每个函数 · 每条调用边）</a></li>
<li><a href="#s8">数据存储与三套后台任务</a></li>
<li><a href="#s9">新手实操指南：想改 XXX 从哪开始</a></li>
</ol></nav>'''

    hero = f'''
<header class="hero">
<h1>🗺️ Yuxi 代码调用逻辑分析报告</h1>
<p>面向小白的完整代码导览：架构全景 · 核心调用链 · <b>方法级调用图（A 文件的哪个方法调用 B 文件的哪个方法）</b> · 前后端全量清单</p>
<div class="meta">
<span class="chip">后端 Python · {n_b} 个文件 · {n_m_b} 个类/函数/方法 · {N_EDGE_B} 条调用边</span>
<span class="chip">前端 Vue 3 · {n_f} 个文件 · {n_m_f} 个函数 · {N_EDGE_F} 条调用边</span>
<span class="chip">生成日期 {TODAY}</span>
<span class="chip">分支 arena/01a0bce6-yuxi · commit 86c67dc</span>
</div>
</header>'''

    s1 = f'''<section id="s1"><h2 class="sec"><span class="no">1</span>Yuxi 是什么？一张图看懂</h2>
<p class="secsub">Yuxi 是一个面向 <b>RAG（检索增强生成）、知识图谱和多智能体工作流</b>的知识库平台。你可以把它理解成：一个可以自己搭「AI 员工」（智能体）的平台——这些 AI 员工能读你的知识库、能操作文件、能上网查资料、还能派出「实习生」（SubAgent）帮忙干活。</p>
{ARCH_HTML}
</section>'''

    s2 = f'''<section id="s2"><h2 class="sec"><span class="no">2</span>三分钟名词表（小白版）</h2>
<p class="secsub">读调用链之前，先把这几个词混个眼熟。不用背，后面遇到随时回来查。</p>
{CONCEPTS}
</section>'''

    s3 = f'''<section id="s3"><h2 class="sec"><span class="no">3</span>目录地图：每个目录是干嘛的</h2>
{DIRMAP}
</section>'''

    s4 = f'''<section id="s4"><h2 class="sec"><span class="no">4</span>核心调用链（逐步深挖）</h2>
<p class="secsub">每一步都标注了<b>确切的文件 → 方法</b>，可以边读边在编辑器里跳转对照。角色颜色：<span class="actor front">前端</span> <span class="actor api">API 进程</span> <span class="actor worker">Worker 进程</span> <span class="actor db">数据库</span>。每条链路的「方法 → 方法」完整展开见第 5 章调用树。</p>
{HOWTOREAD}
<h3 id="c-a">🔗 链路 A：一条聊天消息的一生 <span class="cnt" style="font-weight:400;font-size:13px;color:var(--sub)">（最核心，共 15 步）</span></h3>
<p>场景：你在 /agent 页面选好模型，输入「帮我总结这份文档」，按回车——接下来 15 步就是屏幕背后发生的一切。</p>
<div class="chain">{chain_a}</div>
<h3 id="c-b">🔗 链路 B：登录与认证（5 步）</h3>
<div class="chain">{chain_b}</div>
<h3 id="c-c">🔗 链路 C：知识库文档入库与检索（6 步）</h3>
<div class="chain">{chain_c}</div>
<h3 id="c-d">🔗 链路 D：SubAgent 子任务（4 步）</h3>
<div class="chain">{chain_d}</div>
<h3 id="c-e">🔗 链路 E：服务启动（3 步）</h3>
<div class="chain">{chain_e}</div>
<h3 id="c-f">🔗 链路 F：工具审批与中断恢复（5 步）</h3>
<div class="chain">{chain_f}</div>
</section>'''

    # ---------- 第 5 章：方法级调用树 ----------
    def T(title, desc, cf, caller):
        return render_tree(title, desc, cf, caller, FWD_ALL_B, short_b)

    trees_b = "".join([
    T("① 用户发消息：HTTP 入口", "从前端 POST /api/agent/runs 进入后端的第一站。注意 ⭢ 标记的 get_required_user / get_db 是 FastAPI 依赖（自动先执行认证）。",
      "backend/server/routers/agent_router.py", "create_agent_run"),
    T("② 提交请求：写库 + 排队判定", "整个系统最重要的用例：同一事务写用户消息和排队凭证，再决定立即派发还是排队。",
      "backend/package/yuxi/services/agent_request_service.py", "submit_agent_request"),
    T("③ worker 领取并执行 Run", "ARQ 任务的执行入口：抢租约 → 心跳 → 固化 manifest → 驱动智能体 → 终态落库。new 标记 = 类实例化。",
      "backend/package/yuxi/services/run_worker.py", "process_agent_run"),
    T("④ 智能体执行编排", "把上一步的执行流一步步转成事件；≈ 标记的 BaseAgent.stream_messages_with_state 是通过继承推断的调用。",
      "backend/package/yuxi/services/chat_service.py", "stream_agent_chat"),
    T("⑤ 组装智能体（模型+工具+中间件）", "ChatbotAgent.get_graph：模型加载 → 工具解析 → 提示词 → create_agent 组图。",
      "backend/package/yuxi/agents/buildin/chatbot/graph.py", "ChatbotAgent.get_graph"),
    T("⑥ Run SSE：打字机效果的来源", "把 Redis Stream 里的运行事件转成 HTTP SSE 推给前端。",
      "backend/package/yuxi/services/agent_run_service.py", "stream_agent_run_events"),
    T("⑦ 排队 SSE：排在第几位", "排队阶段的事件流，派发后前端切到 ⑥ 的 Run SSE。",
      "backend/package/yuxi/services/agent_request_queue_service.py", "stream_request_events"),
    T("⑧ 登录", "查用户 → 验密码（bcrypt）→ 计数锁定 → 签发 JWT。",
      "backend/server/routers/auth_router.py", "login_for_access_token"),
    T("⑨ 知识库文档入库", "Durable Task 的 Handler：下载文件 → 解析 → 分块 → 向量化 → 写 Milvus。",
      "backend/package/yuxi/services/knowledge_task_service.py", "run_knowledge_ingest"),
    T("⑩ 子智能体派出", "subagent_start 工具的后端：创建 run_type=subagent 的子 Run 并挂父子关系。",
      "backend/package/yuxi/services/subagent_run_service.py", "SubagentRunService.start"),
    ])

    trees_f = "".join([
    render_tree("⑪ 前端：发送消息", "AgentChatComponent.handleSendMessage：创建线程 → 乐观插入 → 调 agentApi.createAgentRun（对应后端 ①）。前端树只展开跨文件调用，组件内部调用需读源码。",
      "web/src/components/AgentChatComponent.vue", "handleSendMessage", FWD_ALL_F, short_f),
    render_tree("⑫ 前端：排队订阅", "useAgentRequestQueue.startRequestStream：订阅排队 SSE，拿到 run_id 后切换到 Run SSE。",
      "web/src/composables/useAgentRequestQueue.js", "startRequestStream", FWD_ALL_F, short_f),
    render_tree("⑬ 前端：Run SSE 消费", "useAgentRunStream.processRunSseResponse：手写的 SSE 解析器，逐事件回调。",
      "web/src/composables/useAgentRunStream.js", "processRunSseResponse", FWD_ALL_F, short_f),
    ])

    s5 = f'''<section id="s5"><h2 class="sec"><span class="no">5</span>方法级调用图：A 文件的哪个方法调用 B 文件的哪个方法</h2>
<p class="secsub">对全部源码做了<b>静态调用分析</b>：后端基于 Python AST（import 解析 + 实例类型推断 + FastAPI Depends 识别），前端基于 import 与 API 对象方法匹配。共提取 <b>{N_EDGE_B} 条后端调用边 + {N_EDGE_F} 条前端调用边</b>。</p>
<div class="warn"><b>怎么看这些树：</b>每行是一个「被调用到的方法」，缩进表示调用层级（父节点调用了子节点）；方法名右侧的彩色标签是它所在的<b>文件</b>（颜色对应分层：<span class="tfb l-r">路由</span> <span class="tfb l-s">服务</span> <span class="tfb l-q">仓库</span> <span class="tfb l-a">智能体</span> <span class="tfb l-t">存储</span> <span class="tfb l-k">知识</span> <span class="tfb l-m">模型</span> <span class="tfb l-o">其他</span>）。<span class="tmark">⭢</span> 是 FastAPI 依赖注入、<span class="tnew">new</span> 是实例化类、<span class="tmark">≈</span> 是静态推断（个别可能不准，以源码为准）、↻ 表示该方法在上文已展开过（防止树无限膨胀）。<b>全部出边/入边</b>（含同文件内部调用）在第 6-7 章的文件卡片里逐方法列出。</div>
<h3>后端：10 棵入口调用树（对应第 4 章链路）</h3>
{trees_b}
<h3>前端：3 棵核心调用树</h3>
{trees_f}
<div class="tip"><b>想查任意方法的完整调用关系？</b>去第 6-7 章按 <kbd>Ctrl</kbd>+<kbd>F</kbd> 搜方法名：每个方法下面都列出了「→ 调用」（它调了谁）和「← 被调」（谁调了它），跨文件边均带目标文件名。</div>
</section>'''

    catalog_b = render_catalog(INV_B, backend_group, DIR_DESCR_B, True, "b")
    s6 = f'''<section id="s6"><h2 class="sec"><span class="no">6</span>后端全量文件清单</h2>
<p class="secsub">共 <b>{n_b}</b> 个源码文件、<b>{n_m_b}</b> 个类/函数/方法（不含测试）。点开文件卡片：每个方法下方列出它的跨文件调用边（<b>→ 调用</b>）与反向边（<b>← 被调</b>）；类卡片显示「被实例化于」。方法说明优先取自源码 docstring。</p>
{catalog_b}
</section>'''

    catalog_f = render_catalog(INV_F, frontend_group, DIR_DESCR_F, False, "f")
    s7 = f'''<section id="s7"><h2 class="sec"><span class="no">7</span>前端全量文件清单</h2>
<p class="secsub">共 <b>{n_f}</b> 个源码文件、<b>{n_m_f}</b> 个函数。Vue 组件以模板为主，函数按行号区间近似归属；「→ 调用」里能看到它调了哪个 API 模块的哪个方法（如 agentApi.createAgentRun）。</p>
{catalog_f}
</section>'''

    s8 = f'''<section id="s8"><h2 class="sec"><span class="no">8</span>数据存储与三套后台任务</h2>{STORAGE}</section>'''
    s9 = f'''<section id="s9"><h2 class="sec"><span class="no">9</span>新手实操指南</h2>{FAQ}</section>'''

    toolbar = '''<div class="toolbar"><button id="exp-core">只展开 ★ 核心文件</button><button id="exp-all">展开全部</button><button id="col-all">全部收起</button><span class="hint">提示：清单默认折叠，点文件名展开；★ = 核心链路文件</span></div>'''

    doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Yuxi 代码调用逻辑分析报告</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{hero}
{toolbar}
{toc}
{s1}{s2}{s3}{s4}{s5}{s6}{s7}{s8}{s9}
<footer>基于仓库 GoLangCJava/Yuxi（分支 arena/01a0bce6-yuxi，commit 86c67dc）静态分析生成 · 调用边由 AST/import 分析提取，≈ 边为启发式推断 · 仅供学习参考</footer>
</div>
<script>{JS}</script>
</body>
</html>'''

    out = "/home/user/Yuxi/docs/代码调用逻辑分析报告.html"
    with open(out, "w", encoding="utf-8") as fp:
        fp.write(doc)
    print("written:", out, f"{os.path.getsize(out)/1024:.0f} KB")

if __name__ == "__main__":
    build()
