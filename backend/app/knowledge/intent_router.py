"""Intent Router — 将用户意图路由到正确的本体论领域.

识别场景:
  - research_report   深度研究报告（金融/行业/政策分析）
  - data_analysis     数据分析（Excel/CSV 数值推断）
  - code_diagnosis    代码诊断（工程代码审查/调试）
  - document_qa       文档问答（对已上传文档的问答）
  - template_filling  模板填充（按格式生成内容）
  - ppt_generation    PPT 生成
  - chat_assistant    普通对话
  - knowledge_graph   知识图谱构建/查询

每个场景挂载不同的本体约束，并选择对应的三角协调策略。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

ScenarioType = Literal[
    "research_report",
    "data_analysis",
    "code_diagnosis",
    "document_qa",
    "template_filling",
    "ppt_generation",
    "knowledge_graph",
    "chat_assistant",
]

# ── 关键词触发规则（轻量级，无需 LLM） ─────────────────────────────────────────

_KEYWORD_RULES: list[tuple[ScenarioType, list[str]]] = [
    ("data_analysis", [
        "分析数据", "excel", "csv", "数据分析", "统计", "不良率", "财务",
        "交叉分析", "同比", "环比", "sql", "查询表", "画图", "饼图", "柱状图",
        "趋势图", "数据透视", "data"
    ]),
    ("code_diagnosis", [
        "代码", "程序", "bug", "报错", "调试", "github", ".py", ".java",
        "函数", "类", "模块", "编译", "测试", "unit test", "traceback",
        "异常", "exception", "stack overflow", "debug", "repository"
    ]),
    ("template_filling", [
        "根据模板", "按模板", ".dotx", ".potx", "占位符", "填充模板",
        "模板格式", "参照格式", "仿照", "续写", "下一年度同类"
    ]),
    ("ppt_generation", [
        "ppt", "幻灯片", "演示文稿", "slides", "presentation",
        "制作ppt", "生成ppt", "汇报材料", ".pptx"
    ]),
    ("knowledge_graph", [
        "知识图谱", "关系图", "实体关系", "构建图", "知识网络",
        "neo4j", "图数据库", "实体抽取", "关系抽取"
    ]),
    ("document_qa", [
        "这份文档", "根据文件", "这个文件", "文档里", "报告里说", "上传的",
        "文件中", "原文", "请根据", "从文档"
    ]),
    ("research_report", [
        "研究报告", "分析报告", "行业分析", "市场分析", "政策分析",
        "深度研究", "白皮书", "调研", "综述", "全面分析", "评估"
    ]),
]

# 本体领域映射
_ONTOLOGY_DOMAIN: dict[ScenarioType, str] = {
    "research_report":  "business_research",
    "data_analysis":    "structured_data",
    "code_diagnosis":   "software_engineering",
    "document_qa":      "document_retrieval",
    "template_filling": "document_template",
    "ppt_generation":   "presentation",
    "knowledge_graph":  "graph_knowledge",
    "chat_assistant":   "general",
}


@dataclass
class RoutedIntent:
    scenario: ScenarioType
    ontology_domain: str
    confidence: float
    signals: list[str] = field(default_factory=list)   # 触发规则

    # 解析出的结构化参数
    has_file_input: bool = False
    has_structured_data: bool = False  # Excel/CSV
    has_code_input: bool = False
    has_template_input: bool = False
    output_format: str = "docx"        # docx/pptx/xlsx/html/md

    def uses_duckdb(self) -> bool:
        return self.has_structured_data or self.scenario == "data_analysis"

    def uses_polyglot(self) -> bool:
        return self.scenario == "code_diagnosis"

    def uses_vector_rag(self) -> bool:
        return self.scenario in ("research_report", "document_qa", "template_filling")

    def uses_ontology(self) -> bool:
        return self.scenario in ("research_report", "data_analysis", "knowledge_graph")


class IntentRouter:
    """基于规则 + LLM 后验的意图路由器."""

    @classmethod
    async def route(
        cls,
        brief: str,
        file_types: list[str] | None = None,
        output_format: str = "docx",
        use_llm: bool = False,
    ) -> RoutedIntent:
        """
        Args:
            brief:        用户指令文本
            file_types:   上传的文件扩展名列表（如 [".xlsx", ".docx"]）
            output_format: 目标输出格式
            use_llm:       是否调用 LLM 做精确分类（轻量模式下关闭）
        """
        file_types = [f.lower() for f in (file_types or [])]

        # 1) 关键词匹配
        scenario, signals, score = cls._keyword_match(brief, file_types)

        # 2) 文件类型强制覆盖
        has_structured = any(ext in (".xlsx", ".xls", ".csv", ".xlsb") for ext in file_types)
        has_code = any(ext in (".py", ".java", ".js", ".ts", ".go", ".sh", ".zip", ".tar.gz") for ext in file_types)
        has_template = any(ext in (".dotx", ".potx") for ext in file_types)

        if has_code and scenario not in ("data_analysis",):
            scenario = "code_diagnosis"
            signals.append("code_file_detected")
        if has_template:
            scenario = "template_filling"
            signals.append("template_file_detected")

        # 3) 输出格式推断
        if output_format in ("pptx", "ppt") or scenario == "ppt_generation":
            scenario = "ppt_generation"

        # 4) LLM 精确分类（可选）
        if use_llm and score < 0.6:
            scenario, score = await cls._llm_classify(brief, scenario)

        intent = RoutedIntent(
            scenario=scenario,
            ontology_domain=_ONTOLOGY_DOMAIN.get(scenario, "general"),
            confidence=score,
            signals=signals,
            has_file_input=bool(file_types),
            has_structured_data=has_structured,
            has_code_input=has_code,
            has_template_input=has_template,
            output_format=output_format,
        )
        logger.info("[IntentRouter] %s (conf=%.2f, signals=%s)", scenario, score, signals[:3])
        return intent

    @classmethod
    def _keyword_match(
        cls, brief: str, file_types: list[str]
    ) -> tuple[ScenarioType, list[str], float]:
        text = brief.lower()
        # 文件类型也加入匹配文本
        type_text = " ".join(file_types)
        combined = f"{text} {type_text}"

        best_scenario: ScenarioType = "chat_assistant"
        best_score = 0.0
        best_signals: list[str] = []

        for scenario, keywords in _KEYWORD_RULES:
            hits = [kw for kw in keywords if kw.lower() in combined]
            score = len(hits) / max(len(keywords), 1)
            if score > best_score:
                best_score = score
                best_scenario = scenario
                best_signals = hits[:5]

        # 如果文本很长且包含研究报告常见词汇，默认 research_report
        if best_score < 0.05 and len(brief) > 50:
            best_scenario = "research_report"
            best_score = 0.4
            best_signals = ["default_long_brief"]

        return best_scenario, best_signals, min(best_score * 2, 1.0)

    @staticmethod
    async def _llm_classify(brief: str, fallback: ScenarioType) -> tuple[ScenarioType, float]:
        from app.pipeline.llm_helpers import call_llm_json
        valid = list(_ONTOLOGY_DOMAIN.keys())
        system = f"""对用户指令进行场景分类。只输出 JSON: {{"scenario": "...", "confidence": 0.0-1.0}}
有效场景: {valid}"""
        try:
            resp = await call_llm_json(system, f"指令: {brief[:500]}")
            sc = resp.get("scenario", fallback)
            conf = float(resp.get("confidence", 0.5))
            if sc in _ONTOLOGY_DOMAIN:
                return sc, conf
        except Exception as exc:
            logger.debug("LLM classify failed: %s", exc)
        return fallback, 0.5
