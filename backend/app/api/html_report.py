"""HTML Report API — generates self-contained HTML files from research content."""
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from html.parser import HTMLParser

from app.services.html_generator import generate_html_report
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/html", tags=["html"])


class HtmlGenerateRequest(BaseModel):
    prompt: str
    content: str = ""
    title: str = "DataAgent 报告"
    template_style: str = "report"   # dashboard | report | minimal | vivid
    template_logic: str = ""
    processing_direction: str = "自动定义"
    skills: list[str] = []
    project_id: int | None = None
    tags: Optional[list[str]] = None
    kb_ids: list[int] = []
    include_system_kb: bool = False


class HtmlAnalyzeRequest(BaseModel):
    title: str = "参考网页"
    html: str
    template_logic: str = ""


class _HtmlStructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.headings: list[tuple[str, str]] = []
        self.links: list[str] = []
        self.tables = 0
        self.forms = 0
        self.scripts = 0
        self.current_tag = ""
        self._title_open = False
        self._heading_tag = ""
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == "title":
            self._title_open = True
        if tag in ("h1", "h2", "h3", "h4"):
            self._heading_tag = tag
            self._buf = []
        if tag == "a":
            text = dict(attrs).get("href")
            if text:
                self.links.append(text[:120])
        if tag == "table":
            self.tables += 1
        if tag == "form":
            self.forms += 1
        if tag == "script":
            self.scripts += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._title_open = False
        if tag == self._heading_tag:
            text = " ".join("".join(self._buf).split())
            if text:
                self.headings.append((tag, text[:160]))
            self._heading_tag = ""
            self._buf = []

    def handle_data(self, data):
        if self._title_open:
            self.title += data.strip()
        if self._heading_tag:
            self._buf.append(data)


@router.post("/generate")
async def generate_html(req: HtmlGenerateRequest):
    """Generate a self-contained HTML report from prompt + optional content."""
    rag_context = ""
    if req.kb_ids or req.include_system_kb:
        from app.services.rag_service import search_kb
        from app.database import async_session
        async with async_session() as db:
            kb_ids = list(req.kb_ids)
            if req.include_system_kb:
                from app.models.knowledge_base import KnowledgeBase
                from sqlalchemy import select
                system_kb_ids = (await db.execute(
                    select(KnowledgeBase.id).where(KnowledgeBase.scope == "corp")
                )).scalars().all()
                for kb_id in system_kb_ids:
                    if kb_id not in kb_ids:
                        kb_ids.append(kb_id)
            if kb_ids:
                try:
                    results = await search_kb(db, kb_ids=kb_ids, query=req.prompt, top_k=6, score_threshold=0.15)
                    if results:
                        snippets = []
                        for r in results:
                            content = r.get("content", "")
                            source = r.get("source", "未知来源")
                            if content:
                                snippets.append(f"【{source}】{content[:400]}")
                        rag_context = "\n\n".join(snippets)
                except Exception:
                    pass

    messages = [
        {
            "role": "system",
            "content": (
                "你是专业项目管理网页架构师。输出必须是可用于 HTML 页面生成的 Markdown，"
                "围绕项目控制、依赖关系、里程碑、风险、资源、看板、路线图或结构化汇报组织内容。"
                "不要写成普通营销页或长文报告。必须包含图表/矩阵/看板/时间线等模块的数据口径。"
                "若读取或分析用户上传的结构化数据，必须走 Python 或 SQL 的可审计计算路径，不得凭空估算。"
                "涉及加总、占比、差异、趋势、排序、聚合等计算时，必须声明应由智能体工具/Python/SQL 执行并保留口径。"
                "需要生成图片、图表或复杂图示时，必须按最高质量标准设计：专业构图、清晰层级、准确图形语义、"
                "高分辨率输出、无低质占位图、无装饰性假图，优先使用可审计数据驱动的图表或结构化矢量图。"
                "对于项目视图页面，除 Markdown 正文外，必须提供一个 fenced JSON 代码块，字段名为 project_view_spec，"
                "用于确定性渲染真实图示，而不是只用文字描述。"
            ),
        },
    ]
    if req.template_logic.strip():
        messages.append({
            "role": "system",
            "content": "当前用户选择的项目视图模板逻辑如下，必须严格遵循内容结构、信息优先级和表达方式：\n\n" + req.template_logic[:4000],
        })
    if req.processing_direction.strip() or req.skills:
        messages.append({
            "role": "system",
            "content": (
                "当前用户在网页输入框中选择的处理方向/网页技能如下，必须作为生成策略使用：\n"
                f"- 处理方向：{req.processing_direction or '自动定义'}\n"
                f"- 启用 skills：{', '.join(req.skills[:12]) if req.skills else 'web-project-view-general'}\n"
                "这些 skills 代表页面的信息架构和判断重点，不是装饰标签。"
            ),
        })
    if rag_context:
        messages.append({
            "role": "system",
            "content": "以下是从知识库中检索到的相关上下文，请优先依据这些内容回答：\n\n" + rag_context[:10000],
        })
    source_block = f"\n\n【用户提供的素材】\n{req.content[:12000]}" if req.content.strip() else ""
    messages.append({
        "role": "user",
        "content": (
            "请根据以下需求生成项目视图网页内容（Markdown格式，700-1400字）。"
            "必须给出：页面目标、核心图表/视图、关键数据口径、汇报口径、风险/动作闭环。"
            "如果页面包含图像/图示，请明确图示类型、数据字段、视觉编码、质量要求和生成工具路径；"
            "如果素材含表格/数字，请只给出经 Python/SQL 或智能体工具计算后的口径，不要手算猜测。"
            "\n\n请在正文前输出一个 JSON 代码块，格式如下："
            "\n```json\n{\"project_view_spec\":{\"type\":\"gantt_pert|kanban_burndown|risk_matrix|fishbone|timeline|resource_gantt|mind_map|dashboard\",\"title\":\"页面标题\",\"summary\":\"一句话结论\",\"metrics\":[{\"label\":\"整体进度\",\"value\":\"62%\",\"trend\":\"+8%\",\"progress\":62}],\"tasks\":[{\"name\":\"任务\",\"owner\":\"负责人\",\"status\":\"进行中\",\"start\":10,\"duration\":20,\"progress\":60,\"risk\":\"风险\"}],\"risks\":[{\"id\":\"R1\",\"name\":\"风险\",\"probability\":3,\"impact\":3,\"owner\":\"负责人\",\"action\":\"应对动作\"}],\"actions\":[{\"name\":\"动作\",\"owner\":\"负责人\",\"due\":\"时间\",\"status\":\"状态\"}]}}\n```"
            "\nJSON 后继续输出 Markdown 正文。JSON 不要编造真实数据，缺失时用合理占位并标注口径。"
            f"\n\n【用户需求】\n{req.prompt}{source_block}"
        ),
    })
    router_svc = get_model_router()
    model, base_url, api_key = router_svc.route_for_chat(agent_type="nova", messages=messages)
    try:
        final_content = await chat(
            messages, model=model, base_url=base_url, api_key=api_key,
            temperature=0.35, max_tokens=2200
        )
    except Exception as exc:
        logger.warning("[html_generate] LLM unavailable, using deterministic fallback: %s", exc)
        final_content = (
            f"## 页面目标\n"
            f"- 围绕「{req.prompt or req.title}」生成项目视图网页。\n"
            "- 页面用于项目管理、进度汇报、风险识别和行动闭环，不作为普通展示页。\n\n"
            "## 核心视图\n"
            "- 以所选模板为主视图，突出任务、时间、依赖、资源、风险或结构关系。\n"
            "- 顶部放置总体状态、关键节点、当前风险和下一动作。\n\n"
            "## 关键数据口径\n"
            "- 进度：按任务完成率、里程碑达成率、延期天数统计。\n"
            "- 风险：按影响程度、发生概率、责任人和截止时间分级。\n"
            "- 资源：按角色/人员占用率、冲突时段和调配建议呈现。\n\n"
            "## 汇报口径\n"
            "- 已完成什么、当前卡在哪里、风险影响什么、需要谁在什么时候决策。\n"
            "- 对领导/客户汇报时优先展示结果、证据、风险和请求事项。\n\n"
            "## 风险与行动闭环\n"
            "- 每个风险必须有触发信号、缓解措施、责任人和截止时间。\n"
            "- 每个下一步动作必须能落到负责人和时间节点。"
        )
        if req.content.strip():
            final_content += f"\n\n## 用户素材摘要\n{req.content[:4000]}"

    html = generate_html_report(
        title=req.title,
        content=final_content,
        template_style=req.template_style,
        subtitle=req.prompt[:80] if req.prompt else "",
        tags=req.tags,
    )

    return {
        "html": html,
        "title": req.title,
        "template_style": req.template_style,
        "char_count": len(html),
    }


@router.post("/analyze")
async def analyze_html(req: HtmlAnalyzeRequest):
    """Extract reusable project-view structure from an uploaded HTML page."""
    parser = _HtmlStructureParser()
    parser.feed(req.html[:300000])
    plain = " ".join(replace.strip() for replace in req.html.replace("<", " <").replace(">", "> ").split())
    plain = plain[:12000]
    heading_md = "\n".join(f"- {tag.upper()}: {text}" for tag, text in parser.headings[:30]) or "- 未发现明确标题层级"
    messages = [
        {
            "role": "system",
            "content": (
                "你是网页结构解析与项目汇报模板提取专家。"
                "从上传 HTML 中抽取可复用的网页结构、数据可视化看板、思维导图/逻辑结构、汇报口径。"
                "只提炼结构和表达方式，不照搬具体敏感数据。"
            ),
        }
    ]
    if req.template_logic.strip():
        messages.append({
            "role": "system",
            "content": "用户当前选中的项目视图模板规则，解析结果需要服务于该模板：\n\n" + req.template_logic[:3000],
        })
    messages.append({
        "role": "user",
        "content": (
            f"文件标题：{req.title}\n"
            f"浏览器标题：{parser.title or '未识别'}\n"
            f"标题层级：\n{heading_md}\n"
            f"表格数量：{parser.tables}，表单数量：{parser.forms}，脚本数量：{parser.scripts}，链接数量：{len(parser.links)}\n\n"
            f"HTML 文本摘录：\n{plain}\n\n"
            "请输出 Markdown，必须包含以下小节：\n"
            "## 网页结构骨架\n## 数据可视化看板\n## 思维导图与逻辑结构\n## 汇报口径\n## 可复用模板规则\n## 生成新页面时的注意事项"
        ),
    })
    router_svc = get_model_router()
    model, base_url, api_key = router_svc.route_for_chat(agent_type="nova", messages=messages)
    try:
        analysis = await chat(messages, model=model, base_url=base_url, api_key=api_key, temperature=0.25, max_tokens=1800)
    except Exception as exc:
        logger.warning("[html_analyze] LLM unavailable, using deterministic fallback: %s", exc)
        analysis = (
            "## 网页结构骨架\n"
            f"- 浏览器标题：{parser.title or req.title}\n"
            f"- 标题层级：\n{heading_md}\n"
            f"- 页面信号：表格 {parser.tables} 个，表单 {parser.forms} 个，脚本 {parser.scripts} 个，链接 {len(parser.links)} 个。\n\n"
            "## 数据可视化看板\n"
            "- 根据表格、标题和脚本信号，优先抽取 KPI 卡片、趋势图、风险/进度矩阵和明细表。\n"
            "- 若原页面已有表格，生成新页面时应保留其字段口径，并转换为管理看板模块。\n\n"
            "## 思维导图与逻辑结构\n"
            "- 以 H1 作为中心主题，H2/H3 作为一级和二级分支。\n"
            "- 对每个分支补充目标、证据、风险和行动项，形成可汇报的树状结构。\n\n"
            "## 汇报口径\n"
            "- 先讲总体状态，再讲阶段进展、关键风险、资源/依赖和下一步决策。\n"
            "- 面向领导或客户时减少过程描述，突出节点、责任人、影响和需要拍板的事项。\n\n"
            "## 可复用模板规则\n"
            "- 复用标题层级、模块顺序、指标口径和表格字段，不照搬具体敏感数据。\n"
            "- 新页面必须按所选项目视图模板重构为图表、矩阵、看板或时间线。\n\n"
            "## 生成新页面时的注意事项\n"
            "- 标注数据来源和指标定义。\n"
            "- 对风险、延期、资源冲突给出责任人、截止时间和升级路径。"
        )
    return {"title": parser.title or req.title, "analysis": analysis}
