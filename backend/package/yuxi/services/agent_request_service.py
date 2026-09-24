"""统一的 AgentRun 消息提交应用服务。

Web Chat、Agent Call 和评估入口只在路由/适配层处理各自的输入输出协议，
实际的 AgentRunRequest 入队、Conversation 绑定和提交后派发都从这里进入。
Resume 与 Subagent 保留各自的特殊生命周期，不经过本服务。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.agents.buildin import AgentBackendNotFoundError, get_agent_backend
from yuxi.repositories.agent_repository import AgentRepository
from yuxi.repositories.agent_run_repository import AgentRunRepository
from yuxi.repositories.agent_run_request_repository import AgentRunRequestRepository
from yuxi.repositories.conversation_repository import ConversationRepository
from yuxi.repositories.project_repository import ProjectRepository
from yuxi.services.agent_request_queue_service import (
    DELIVERY_STATUS_QUEUED,
    DELIVERY_STATUS_REJECTED,
    REQUEST_STATUS_QUEUED,
    REQUEST_STATUS_REJECTED,
    DispatchResult,
    dispatch_ready_head,
    get_thread_conversation,
    is_steerable_message_run,
    queue_conflict,
    request_view,
    validate_queue_policy,
)
from yuxi.services.agent_run_service import create_agent_run_input_message, enqueue_agent_run, resolve_agent_run_config
from yuxi.services.input_message_service import AgentRunInputMessage
from yuxi.services.project_service import create_implicit_project
from yuxi.services.workdir_service import WorkdirBinding, resolve_conversation_workdir_binding
from yuxi.storage.postgres.models_business import AgentRunRequest, User
from yuxi.utils.datetime_utils import utc_now_naive
from yuxi.workspace.paths import ensure_bound_user_workdir


@dataclass(frozen=True)
class RunOrigin:
    """描述一次 Run 请求的入口来源与传输通道。"""

    source: str
    channel: str
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRequestInput:
    """普通 Agent 请求的入口输入。"""

    agent_slug: str
    thread_id: str
    request_id: str
    input_message: AgentRunInputMessage
    origin: RunOrigin
    request_metadata: dict[str, Any] = field(default_factory=dict)
    model_spec: str | None = None
    tool_approval_mode: str | None = None
    queue_policy: str = "enqueue"
    create_conversation: bool = False
    conversation_title: str | None = None
    conversation_project_id: str | None = None


async def submit_agent_request(
    *,
    request_input: AgentRequestInput,
    current_user: User,
    db: AsyncSession,
) -> dict[str, Any]:
    """校验作用域、写入 Request 并在提交后投递消息型 AgentRun。

    ``create_conversation`` 仅用于没有显式 Thread 的外部入口；普通 Web Chat
    必须复用已经创建的 Conversation。不同入口的协议适配不应绕过这里。

    不变量：PG 先持久化 Message/AgentRunRequest 并提交 owning transaction，
    之后才调用 enqueue_agent_run 把投递交给 ARQ；Redis 不持有最终业务状态。
    """

    # ───────── 1. Origin 信任边界校验 ─────────
    # source/channel 是后续审计、限流、配额分组的关键字段，必须 fail-closed。
    # 用 422（语义错误）而非 400：JSON 语法没问题，但字段语义不合法。
    # 长度上限 32 是反 DoS 保护——防止恶意客户端把超长字符串塞进 PG/审计日志。
    origin = request_input.origin
    if not origin.source.strip() or not origin.channel.strip():
        raise HTTPException(status_code=422, detail="Run origin source/channel 不能为空")
    if len(origin.source) > 32:
        raise HTTPException(status_code=422, detail="Run origin source 不能超过 32 个字符")
    if len(origin.channel) > 32:
        raise HTTPException(status_code=422, detail="Run origin channel 不能超过 32 个字符")

    # external_id 规范化：把 None/"" 统一成 None。
    # 这是幂等键归一化——同一 external_id 的不同写法（空串 vs None）必须被视为同一请求，
    # 否则前端""传值抖动会导致幂等检查走偏。
    external_id = str(origin.external_id).strip() if origin.external_id is not None else None
    if external_id == "":
        external_id = None

    # origin_metadata 排除 source/channel/external_id 三个独立字段，
    # 防止"同一信息存两份导致不一致"——它们已经作为 origin 的独立字段存在。
    origin_metadata = {
        key: value for key, value in origin.metadata.items() if key not in {"source", "channel", "external_id"}
    }

    # ───────── 2. Agent 可见性（权限最终边界） ─────────
    # AGENTS.md 不变量：「权限在后端依赖与 repository 可见性查询处最终执行」。
    # 路由层的 Depends(get_required_user) 只做凭据校验，真正的「能不能用这个 Agent」
    # 在这里通过 get_visible_by_slug(user=current_user) 下推到 SQL 层完成。
    # kind="main" 限定主智能体（SubAgent 预设走另一条路径，不在这里）。
    agent_repo = AgentRepository(db)
    agent_item = await agent_repo.get_visible_by_slug(
        slug=request_input.agent_slug,
        user=current_user,
        kind="main",
    )
    # 用 404 而非 403：不暴露「这个智能体存在但你没权限」的信息——安全考虑。
    if not agent_item:
        raise HTTPException(status_code=404, detail="智能体不存在")

    # ───────── 3. 幂等三段查（Request 表 → Run 表 → scope 校验） ─────────
    # 前端为每条消息生成 uuid 作为 request_id，重复提交（网络重试、双击、断网自动重连）
    # 必须能识别出来。这里分三段：
    #   ① 查 AgentRunRequest 表（"请求已落库"）
    #   ② 如果没有 Request 行，再查 AgentRun 表（"Run 已派发"，兜底异常状态）
    #   ③ 命中后做 scope 校验，确保不是冒用别人的 request_id
    existing_request = await AgentRunRequestRepository(db).get_by_request_id(request_input.request_id)
    existing_run = (
        None if existing_request else await AgentRunRepository(db).get_run_by_request_id(request_input.request_id)
    )

    # ─── 3a. 既有 Run 兜底分支 ───
    # 数据库出现 Run 但没有 Request 行——异常状态（旧版数据迁移、写入中断等），
    # 但仍要幂等返回，让前端能继续订阅 SSE，而不是创建第二条 Run。
    if existing_run and not existing_request:
        # 三道身份校验防冒用：uid / agent_slug+run_type / thread_id 必须全匹配。
        # 任一不匹配返回 409（Conflict）明确告诉客户端"这个 id 不是你的"。
        if existing_run.uid != str(current_user.uid):
            raise HTTPException(status_code=409, detail="request_id 冲突")
        if existing_run.agent_slug != agent_item.slug or existing_run.run_type != "chat":
            raise HTTPException(status_code=409, detail="request_id 冲突")
        if request_input.thread_id and existing_run.conversation_thread_id != request_input.thread_id:
            raise HTTPException(status_code=409, detail="request_id 冲突")
        # 返回结构里 request_events_url=None：已经过了排队段，前端直接连 Run SSE。
        # 用 dict 而非 dataclass：不同分支返回字段集略有差异，强类型反而碍事。
        return {
            "request_id": request_input.request_id,
            "status": existing_run.status,
            "queue_policy": request_input.queue_policy,
            "queue_position": 0,
            "message_id": existing_run.input_message_id,
            "run_id": existing_run.id,
            "stream_url": f"/api/agent/runs/{existing_run.id}/events",
            "request_events_url": None,
            "thread_id": existing_run.conversation_thread_id,
        }

    # ─── 3b. 既有 Request 重放分支 ───
    # 请求排队了但还没轮到派发。返回 request_view（含 request_events_url）
    # 让前端连 Request SSE 等待 run_created 事件。
    if existing_request:
        # 用规范化后的 external_id 重建 request_input，再做 scope 校验，
        # 防止有人用同一个 request_id 但改了 agent/thread/uid（攻击或前端 bug）。
        normalized_input = replace(request_input, origin=replace(origin, external_id=external_id))
        _validate_request_scope(existing_request, request_input=normalized_input, uid=str(current_user.uid))
        # 二次校验 Conversation 仍然属于当前用户、未删除、agent 仍匹配。
        # 这是因为 Request 可能来自很久以前，期间 Conversation 状态可能变了。
        conversation = await ConversationRepository(db).get_conversation_by_thread_id(
            existing_request.conversation_thread_id
        )
        if (
            conversation is None
            or conversation.uid != str(current_user.uid)
            or conversation.status == "deleted"
            or conversation.agent_id != request_input.agent_slug
        ):
            raise HTTPException(status_code=404, detail="对话线程不存在")
        # Project 也要校验 active——可能被软删除了。
        project = await ProjectRepository(db).get_for_user(conversation.project_id, str(current_user.uid))
        if project is None or project.status != "active":
            raise HTTPException(status_code=404, detail="Project 不存在或不可访问")
        return await request_view(repo=AgentRunRequestRepository(db), request=existing_request)

    # ───────── 4. 加载 Agent 后端 ─────────
    # backend_id 是 Agent 的执行后端标识（ChatbotAgent/Subagent/自定义 backend 等），
    # get_agent_backend 是 yuxi.agents.buildin 的工厂函数。
    # 失败转 404——后端配置错也算「智能体不可用」，对前端语义一致。
    try:
        agent_backend = get_agent_backend(agent_item.backend_id)
    except AgentBackendNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ───────── 5. Conversation 加载与隐式创建 ─────────
    # Web Chat 必有显式线程（前端先调 threadApi.createThread 建好），
    # 所以 conversation 应非空。隐式创建分支只给外部入口（channel/CLI）用——
    # AGENTS.md：「『可以』『也可以』『类似这样』『例如』当作简单方向，不是设计更大机制、
    # 配置项或兼容层的许可」，隐式创建不是默认行为，是外部入口的必要兼容。
    conversation_repo = ConversationRepository(db)
    project = None
    conversation = await conversation_repo.get_conversation_by_thread_id(request_input.thread_id)
    if not conversation:
        if not request_input.create_conversation:
            # 没传 create_conversation=True 就拒绝——普通 Web Chat 走这里就是 bug。
            raise HTTPException(status_code=404, detail="对话线程不存在")
        try:
            # 嵌套事务（SAVEPOINT）：嵌套事务里的失败可以单独回滚，不影响外层事务。
            # 关键用途在下面的 except IntegrityError 分支——并发兜底。
            async with db.begin_nested():
                project = None
                if request_input.conversation_project_id:
                    # lock_active_for_user 用 SELECT ... FOR UPDATE 加行锁校验，
                    # 防止并发修改，且校验 active 状态。
                    project = await ProjectRepository(db).lock_active_for_user(
                        request_input.conversation_project_id,
                        str(current_user.uid),
                    )
                    if project is None:
                        raise HTTPException(status_code=404, detail="Project 不存在或不可访问")
                else:
                    # 没指定 Project 就建一个默认的——每个 Conversation 必须有 Project 归属。
                    project = await create_implicit_project(
                        uid=str(current_user.uid),
                        db=db,
                    )
                conversation = await conversation_repo.add_conversation(
                    uid=str(current_user.uid),
                    agent_id=agent_item.slug,
                    title=request_input.conversation_title,
                    thread_id=request_input.thread_id,
                    metadata={
                        **origin_metadata,
                        "source": origin.source,
                        "channel": origin.channel,
                    },
                    project_id=project.id,
                )
        except IntegrityError:
            # 并发兜底：两个请求同时建同一 thread，PG 唯一约束触发 IntegrityError。
            # 优雅处理：回滚 SAVEPOINT（自动）→ 重新读现有 conversation → 让胜者的继续用。
            # 这避免了用悲观 lock 损害并发度，是分布式并发处理的常见模式。
            conversation = await conversation_repo.get_conversation_by_thread_id(request_input.thread_id)
            if not conversation:
                raise

    # ───────── 6. Metadata 合并与字段优先级 ─────────
    # 客户端可控的 metadata 不能盖过系统权威字段——这是信任边界上的「字段优先级」。
    # 优先级：origin.channel（权威）> 客户端传的 metadata。
    # origin_metadata 里已排除 source/channel/external_id，所以循环里再防一次
    # source/channel 被覆盖（双保险）。setdefault 保证只在客户端没传时才补。
    request_metadata = dict(request_input.request_metadata or {})
    request_metadata["channel"] = origin.channel
    for key, value in origin_metadata.items():
        if key in {"source", "channel"}:
            continue
        request_metadata.setdefault(key, value)

    # binding_project：只有 conversation 是新创建且 project 也是新创建（同一事务）时
    # 才传非空。否则传 None——避免锁住无关 project 影响并发。
    binding_project = project if project is not None and str(project.id) == str(conversation.project_id) else None

    # ───────── 7. Workdir 绑定（沙盒路径归属确认） ─────────
    # AGENTS.md 不变量：「沙盒虚拟路径、对象 URL 和宿主机路径不可混用；
    # 所有用户路径必须在 owning filesystem boundary 校验」。
    # 这一步决定本会话的文件工作区在哪——uid + thread 对应哪条 workdir 路径，
    # 是 managed（系统托管的 UserWorkspace）还是 unmanaged（外部挂载）。
    workdir_binding = await resolve_conversation_workdir_binding(
        conversation=conversation,
        uid=str(current_user.uid),
        db=db,
        project=binding_project,
    )

    # 用 replace 重建 request_input：把规范化后的 origin 和合并后的 metadata 灌回去。
    # dataclass 的不变更新——原对象不变，避免后续读到不一致状态。
    request_input = replace(
        request_input,
        origin=replace(origin, external_id=external_id, metadata=origin_metadata),
        request_metadata=request_metadata,
    )

    # ───────── 8. 核心落库：Message + AgentRunRequest + 可能的 AgentRun ─────────
    # _persist_request 在同一事务里写：
    #   - Message（用户消息，delivery_status="queued" 或 "rejected"）
    #   - AgentRunRequest（status="queued" 或 "rejected"）
    #   - 若是 FIFO 队头且无活跃 Run：写 AgentRun(pending) + RunOrigin
    # 返回 (request, dispatch)——dispatch 可能为 None（只排队，未立即派发）。
    request, dispatch = await _persist_request(
        db=db,
        request_input=request_input,
        current_user=current_user,
        agent_item=agent_item,
        agent_backend=agent_backend,
        workdir_binding=workdir_binding,
    )
    # 生成响应视图（request_view 把 Request 行变成 JSON-ready dict）。
    response = await request_view(repo=AgentRunRequestRepository(db), request=request)

    # ───────── 9. ★ 事务提交（AGENTS.md「PG 先于 ARQ」硬执行点） ─────────
    # 这一步必须先于 enqueue_agent_run。
    # 反例 1：先 enqueue 再 commit——worker 拉到 job 时 PG 里还没这条 Run（事务未提交可见），
    #         _get_run(run_id) 返回 None，Run 永远不会被处理。
    # 反例 2：enqueue 失败但 commit 成功——这没问题，reconciliation 循环会扫描 PG 中
    #         pending 但没投递的 Run，重新 enqueue（自愈）。
    # 任一步抛异常 → 整个事务回滚，PG 里不会留下半条 Request 或半条 Run。
    await db.commit()

    # ───────── 10. 事务后副作用（无法回滚的操作必须在 commit 后） ─────────
    # materialize_managed=True 时，物化 UserWorkspace 的 Workdir 字节（文件系统上创建目录）。
    # 放事务内：commit 失败会留下孤儿目录（PG 没记录但目录已建）。
    # 放事务后：commit 成功了再建目录；下次请求 materialize_managed 看到已存在就跳过。
    if workdir_binding.materialize_managed:
        ensure_bound_user_workdir(workdir_binding.uid, workdir_binding.workdir_path)

    # ───────── 11. ★ 投递 ARQ（commit 之后） ─────────
    # 只有 dispatch 非空（即本次创建了 Run）才投递。
    # enqueue_agent_run 往 Redis 队列推 process_agent_run job，载荷只含 run_id。
    # AGENTS.md：「Redis 不拥有最终业务状态」——Redis 重启后 recover_pending_dispatches
    # 会扫描 PG 中 pending 但无活跃 lease 的 Run 重新 enqueue，系统自愈。
    if dispatch is not None:
        await enqueue_agent_run(dispatch.run_id)
    return response


async def _persist_request(
    *,
    db: AsyncSession,
    request_input: AgentRequestInput,
    current_user: User,
    agent_item: Any,
    agent_backend: Any,
    workdir_binding: WorkdirBinding | None = None,
) -> tuple[AgentRunRequest, DispatchResult | None]:
    """保存请求并返回本事务实际派发的队头，供提交后投递。

    不变量：只有 ready FIFO 队头才会在此事务内创建 AgentRun；非队头返回
    ``dispatched=None`` 由外层仅落盘 Request。Request 与 Run 是不同状态模型。
    """
    # ───────── A. 把 request_input 拆成本地变量（避免后续重复属性访问） ─────────
    request_id = request_input.request_id
    uid = current_user.uid
    agent_slug = request_input.agent_slug
    thread_id = request_input.thread_id
    source, channel = request_input.origin.source, request_input.origin.channel
    external_id = request_input.origin.external_id
    origin_metadata = request_input.origin.metadata
    input_message = request_input.input_message
    model_spec, tool_approval_mode = request_input.model_spec, request_input.tool_approval_mode
    meta = request_input.request_metadata

    # ───────── B. queue_policy 信任边界校验 ─────────
    # queue_policy 来自外部输入，必须显式校验后才能用于派发决策。
    # 三种合法值：enqueue（默认排队）/ reject（已有活跃 Run 时拒绝）/ steer（接替当前 Run）。
    # steer 仅限 chat/channel 主会话入口用——SubAgent/外部调用不允许接替别人的 Run。
    policy = validate_queue_policy(request_input.queue_policy)
    if policy == "steer" and source not in {"chat", "channel"}:
        raise HTTPException(status_code=422, detail="queue_policy 'steer' 仅支持主会话 Chat/Channel")
    meta = meta or {}
    uid_str = str(uid)
    repo = AgentRunRequestRepository(db)

    # ───────── C. 嵌套幂等闭包（被两处调用） ─────────
    # 这个闭包是双段幂等检查的核心，会在「抢锁前」「抢锁后」各跑一次。
    # 闭包内会做 Workdir 绑定作用域安全校验 + scope 校验，任一不匹配 fail-closed。
    async def existing_request(binding: WorkdirBinding | None = None) -> AgentRunRequest | None:
        """幂等：相同 request_id 已存在时返回既有 request/run 视图，不存在返回 None。"""
        # 作用域安全：传入的 Workdir 绑定必须与请求 uid/thread 匹配。
        # 防止有人构造一个属于别人的 binding 传进来冒充别的用户的请求。
        if binding is not None and (binding.uid != uid_str or binding.thread_id != thread_id):
            raise RuntimeError("传入的 Workdir 绑定与请求作用域不一致")
        existing = await repo.get_by_request_id(request_id)
        if not existing:
            return None
        # scope 校验：request_id 已存在时，重新提交的请求作用域必须与原请求严格一致。
        # 防止有人用同一个 request_id 但改了 agent/thread/uid（攻击或前端 bug）。
        _validate_request_scope(existing, request_input=request_input, uid=uid_str)
        return existing

    # ───────── D. 抢锁前第一次幂等检查 ─────────
    # 目的：99% 的重复请求在此命中，直接返回，避免无谓地抢 Conversation 锁。
    # 这一步是性能优化，没有抢锁后的检查那么严格（race 可能漏），但够过滤大部分重复。
    if result := await existing_request(workdir_binding):
        return result, None

    # ───────── E. 抢 Conversation 行锁（FIFO 串行的硬约束） ─────────
    # AGENTS.md 不变量：「同一用户、Agent、线程的普通请求按 FIFO 串行派发」。
    # 实现方式：lock=True 即 SELECT ... FOR UPDATE，把 Conversation 行锁住。
    # 这样同一 (uid, agent_slug, thread_id) 的并发请求会被 PG 串行化，
    # 第一个抢到锁的请求完成 _persist_request（含队头判断与可能的 Run 创建）后，
    # 第二个请求才能进入，看到的是第一个请求已经写好的状态——FIFO 自然成立。
    conversation = await get_thread_conversation(
        db=db,
        uid=uid_str,
        agent_slug=agent_slug,
        thread_id=thread_id,
        lock=True,
    )

    # ───────── F. Workdir 绑定二次确认 ─────────
    # 外层可能没传 binding（subagent 等场景），这里按 conversation 现查。
    # 如果传了，必须与 conversation 严格对齐——uid/conversation_id/thread_id/project_id
    # 四个字段全匹配。任一不匹配说明运行时配置错乱，fail-closed。
    # AGENTS.md：「沙盒虚拟路径、对象 URL 和宿主机路径不可混用」——这是这条不变量的实现点。
    if workdir_binding is None:
        workdir_binding = await resolve_conversation_workdir_binding(
            conversation=conversation,
            uid=uid_str,
            db=db,
        )
    elif (
        workdir_binding.uid != uid_str
        or workdir_binding.conversation_id != conversation.id
        or workdir_binding.thread_id != conversation.thread_id
        or workdir_binding.project_id != conversation.project_id
    ):
        raise RuntimeError("传入的 Workdir 绑定与 Conversation 不一致")

    # ───────── G. 抢锁后第二次幂等检查（防止并发穿越） ─────────
    # 关键设计：第一次检查与抢锁之间有时间窗口，另一个并发请求可能已在这段时间内
    # 完成写入并释放锁。本请求拿到锁后再查一次，确保不重复创建。
    # 这是「double-checked locking」模式在 PG 上的应用。
    if result := await existing_request(workdir_binding):
        return result, None

    # ───────── H. 线程状态查询（FIFO 队头 + 活跃 Run + 中断态 Run） ─────────
    existing_requests = await repo.list_queued(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )
    # existing_head：当前线程的 FIFO 队头。只有队头才有机会在本事务内被派发为新 Run；
    # 非队头（即 existing_head != 本请求的 request_id）只能排队等待。
    existing_head = existing_requests[0] if existing_requests else None
    # active_run：当前线程是否有正在执行的 Run。有则不能立即派发新 Run（除非 steer）。
    active_run = await AgentRunRepository(db).get_active_run_by_thread_for_user(
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
        uid=uid_str,
    )
    # latest_run：线程最近一次 chat/resume Run，用于检查 interrupted 态。
    latest_run = await AgentRunRepository(db).get_latest_chat_or_resume_run(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    )

    # ───────── I. 时序保护：interrupted / steer 校验 ─────────
    # interrupted：Run 正在等待用户回答问题或审批工具，此时禁止入队新请求，
    # 否则会破坏 LangGraph 的 human-in-the-loop 时序——用户的回答不知道对应哪个 Run。
    if latest_run is not None and latest_run.status == "interrupted":
        raise queue_conflict("run_interrupted", "线程正在等待用户回答或审批")

    # steer 三个前置校验：
    # 1. active_run 必须可被 steer——某些 Run（如评估/外部调用）不允许接替。
    if policy == "steer" and active_run is not None and not await is_steerable_message_run(db=db, run=active_run):
        raise queue_conflict("run_not_steerable", "当前运行不支持引导")
    # 2. 同一线程至多一个 pending steer——避免多个 steer 互相打架。
    if policy == "steer" and await repo.get_pending_steer(
        uid=uid_str,
        agent_slug=agent_slug,
        conversation_thread_id=thread_id,
    ):
        raise queue_conflict("steer_already_pending", "线程已有等待执行的引导请求")

    # ───────── J. 决定本请求的命运：立即派发 / 排队 / 拒绝 ─────────
    # reject 语义：不能立即成为并派发 FIFO 队头就拒绝，不入队等待。
    # 即「要么立即跑，要么不跑」——用于交互式 UI 防止消息堆积。
    reject_without_immediate_dispatch = policy == "reject" and (active_run is not None or existing_head is not None)
    if reject_without_immediate_dispatch:
        # 拒绝：状态置为 REJECTED，不写 input_payload（不会被派发）。
        request_status = REQUEST_STATUS_REJECTED
        delivery_status = DELIVERY_STATUS_REJECTED
        input_payload = {}
    else:
        # 排队：状态置为 QUEUED，写入 input_payload（model_spec + tool_approval_mode）
        # 供后续 worker 加载 Run 时使用。
        request_status = REQUEST_STATUS_QUEUED
        delivery_status = DELIVERY_STATUS_QUEUED
        # 模型解析优先级：请求显式指定 > 会话默认 > Agent 默认配置。
        conversation_model_spec = (conversation.extra_metadata or {}).get("model_spec")
        requested_model_spec = (
            model_spec if isinstance(model_spec, str) and model_spec.strip() else conversation_model_spec
        )
        # resolve_agent_run_config 把 model_spec 字符串解析成后端可用的配置对象，
        # 同时校验 tool_approval_mode 合法性。
        resolved_model_spec, resolved_tool_approval_mode = await resolve_agent_run_config(
            requested_model_spec, tool_approval_mode, agent_item, agent_backend, db
        )
        input_payload = {
            "model_spec": resolved_model_spec,
            "tool_approval_mode": resolved_tool_approval_mode,
        }

    # ───────── K. 构造 input_message 的 metadata（request_id + source + 附加上下文） ─────────
    # _build_message_metadata 把 request_id/source/raw_message/attachment_file_ids 等组装到
    # Message.extra_metadata，供 worker 加载 Run 时重建上下文使用。
    run_input_message = input_message.with_metadata(
        _build_message_metadata(request_id=request_id, source=source, input_message=input_message, meta=meta)
    )

    # ───────── L. 原子落盘（savepoint）：附件绑定 + Message + AgentRunRequest ─────────
    # 用嵌套事务保证三步原子：要么全写成功，要么全回滚到抢锁后的状态。
    # 如果不用 savepoint 直接抛 IntegrityError，会回滚整个外层事务（含锁），
    # 而我们要在 except 分支里重新走幂等检查，所以需要 savepoint 局部回滚。
    try:
        async with db.begin_nested():
            attachment_file_ids = _normalize_attachment_file_ids(meta.get("attachment_file_ids"))

            # 附件信任边界：attachment_file_ids 来自外部输入，必须经 repository 绑定校验
            # 归属与可用性——确认这些文件确实属于本会话/用户、未被其他请求绑定、未被删除。
            # reject 时不绑定（反正不会被派发）。
            if not reject_without_immediate_dispatch and attachment_file_ids:
                bound_attachments = await ConversationRepository(db).bind_attachments_to_request(
                    conversation.id,
                    request_id,
                    attachment_file_ids,
                )
                bound_ids = {str(item.get("file_id")) for item in bound_attachments}
                missing_ids = [file_id for file_id in attachment_file_ids if file_id not in bound_ids]
                if missing_ids:
                    # 422：客户端传了不合法的附件 id——可能是 bug，也可能是攻击。
                    raise HTTPException(
                        status_code=422,
                        detail=f"附件不存在、已被使用或已被删除: {', '.join(missing_ids)}",
                    )

            # 写入用户消息（Message）：delivery_status 标记是 queued 还是 rejected。
            # 后续 worker 执行 Run 时会读取这条消息作为输入。
            persisted_message = await create_agent_run_input_message(
                db=db,
                conversation_id=conversation.id,
                request_id=request_id,
                input_message=run_input_message,
                delivery_status=delivery_status,
            )

            # 写入 AgentRunRequest：把前面所有字段（origin/metadata/policy/payload）固化到 PG。
            # input_message_id 双向绑定 Message ↔ Request——彼此能找到对方。
            persisted_request = await repo.create(
                request_id=request_id,
                uid=uid_str,
                agent_slug=agent_slug,
                conversation_thread_id=thread_id,
                source=source,
                channel=channel,
                external_id=external_id,
                origin_metadata=origin_metadata,
                queue_policy=policy,
                input_message_id=persisted_message.id,
                input_payload=input_payload,
                status=request_status,
            )
    except IntegrityError:
        # 并发兜底：request_id 唯一约束被并发请求抢占了——说明两份并发请求用了同一 request_id。
        # 回滚 SAVEPOINT 后重新走幂等路径返回既有视图。
        # 这是「乐观并发控制」模式：先尝试写，撞了再回退到读路径，比全程悲观锁并发度高。
        if result := await existing_request(workdir_binding):
            return result, None
        raise

    # ───────── M. 派发队头（dispatch_ready_head） ─────────
    # dispatched=None 表示本请求只排队，未立即创建 Run；
    # dispatched 非 None 表示当前线程的队头被派发为 Run——可能是本请求，也可能是别人。
    dispatched = None
    if not reject_without_immediate_dispatch:
        # 非 reject 路径：把解析后的 model_spec 写回 conversation.extra_metadata，
        # 让下次请求默认沿用（用户选择一次后，后续消息保持同一模型）。
        if policy != "reject":
            await ConversationRepository(db).set_model_spec(conversation, resolved_model_spec)

        # ★ FIFO 队头派发核心调用 ★
        # dispatch_ready_head 会：
        # 1. 查询当前 (uid, agent_slug, thread_id) 的 FIFO 队头
        # 2. 若队头无活跃 Run：创建 AgentRun(pending) + RunOrigin
        # 3. 返回 DispatchResult(request_id, run_id, ...) 或 None
        # expected_request_id：reject 路径下限定只有本请求成为队头才派发，
        #                       避免在 reject 模式下意外派发其他排队的请求。
        dispatched = await dispatch_ready_head(
            db=db,
            uid=uid_str,
            agent_slug=agent_slug,
            thread_id=thread_id,
            workdir_binding=workdir_binding,
            expected_request_id=request_id if policy == "reject" else None,
        )

        # 分支 1：本请求恰好成为队头并被派发——返回 run_id 供外层在 commit 后 enqueue。
        # 这是「立即派发」成功路径。
        if dispatched and dispatched.request_id == request_id:
            # reject 模式下成功派发也要写回 model_spec（前面 reject 分支跳过了 set_model_spec）。
            if policy == "reject":
                await ConversationRepository(db).set_model_spec(conversation, resolved_model_spec)
            return persisted_request, dispatched

        # 分支 2：reject 模式下未抢到队头——本请求不会被执行。
        # 就地把状态改为 REJECTED 并 flush 落盘，让客户端收到 REJECTED 状态。
        # flush 只同步 ORM 状态到 PG，不提交事务——真正 commit 在外层。
        if policy == "reject":
            persisted_request.status = REQUEST_STATUS_REJECTED
            persisted_request.input_payload = {}
            persisted_request.updated_at = utc_now_naive()
            persisted_message.delivery_status = DELIVERY_STATUS_REJECTED
            await db.flush()

    # 返回 (request, dispatch)——dispatch 可能为 None（仅排队）或非 None（已派发）。
    # 外层 submit_agent_request 拿到 dispatch 后会在 commit 后调 enqueue_agent_run。
    return persisted_request, dispatched


def _validate_request_scope(request: AgentRunRequest, *, request_input: AgentRequestInput, uid: str) -> None:
    """相同 ID 只允许重放同一不可变请求作用域。"""
    origin = request_input.origin
    expected_scope = (
        str(uid),
        request_input.agent_slug,
        request_input.thread_id,
        origin.source,
        origin.channel,
        origin.external_id,
    )
    actual_scope = (
        request.uid,
        request.agent_slug,
        request.conversation_thread_id,
        request.source,
        request.channel,
        request.external_id,
    )
    if actual_scope != expected_scope:
        raise queue_conflict("request_id_conflict", "request_id 已用于其他请求作用域")


def _build_message_metadata(
    *, request_id: str, source: str, input_message: AgentRunInputMessage, meta: dict
) -> dict[str, Any]:
    """构建 Message.extra_metadata：request_id + source + raw_message + 附加上下文。"""
    metadata: dict[str, Any] = {"request_id": request_id}
    if source:
        metadata["source"] = source
    if channel := meta.get("channel"):
        metadata["channel"] = channel
    if raw_message := input_message.raw_message():
        metadata["raw_message"] = raw_message
    if attachment_file_ids := meta.get("attachment_file_ids"):
        metadata["attachment_file_ids"] = attachment_file_ids
    if isinstance(meta.get("agent_invocation_meta"), dict):
        metadata["agent_invocation_meta"] = meta["agent_invocation_meta"]
    if meta.get("tool_approval_mode") is not None:
        metadata["tool_approval_mode"] = meta["tool_approval_mode"]
    return metadata


def _normalize_attachment_file_ids(value: object) -> list[str]:
    """规范化请求附件 ID，保持原始顺序并去重。"""
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for file_id in value:
        current = str(file_id).strip()
        if current and current not in seen:
            seen.add(current)
            normalized.append(current)
    return normalized
