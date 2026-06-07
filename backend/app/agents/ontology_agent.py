"""
Ontology Agent — domain knowledge graph construction and semantic enrichment.

Builds structured ontologies from research findings and document corpora,
enabling semantic reasoning, concept hierarchy navigation, and ontology-aware
query expansion for enhanced RAG retrieval.
"""
import logging
from typing import Optional

from app.models.research import SubTask, ResearchFinding
from app.services.ontology_service import (
    extract_kg_from_text,
    build_domain_schema,
    save_kg_to_db,
    save_domain_schema,
)
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)


class OntologyAgent:
    """
    Builds and maintains domain knowledge graphs from research text.

    Three operating modes:
    1. extract_from_text — extract entities/relations from a single text
    2. build_domain_schema — construct comprehensive domain ontology
    3. synthesize_ontology — merge multiple KG extractions into coherent graph
    """

    AGENT_TYPE = "ontology_agent"

    async def extract(
        self,
        text: str,
        domain: str = "general",
        context: str = "",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Extract knowledge graph from text and return structured KG."""
        if on_progress:
            await on_progress("ontology_agent", "抽取实体与关系...", 20)

        kg = await extract_kg_from_text(text, domain=domain, context=context)

        if on_progress:
            await on_progress("ontology_agent", "验证知识图谱结构...", 70)

        # Quality check: ensure edges reference valid nodes
        node_names = {n["name"] for n in kg.get("nodes", [])}
        valid_edges = [
            e for e in kg.get("edges", [])
            if e.get("source") in node_names and e.get("target") in node_names
        ]
        kg["edges"] = valid_edges

        if on_progress:
            await on_progress("ontology_agent", f"知识图谱构建完成: {len(kg.get('nodes',[]))}节点 {len(valid_edges)}关系", 100)

        return kg

    async def build_domain(
        self,
        domain: str,
        background_text: str = "",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Build comprehensive domain ontology schema."""
        if on_progress:
            await on_progress("ontology_agent", f"构建{domain}领域本体框架...", 30)

        schema = await build_domain_schema(domain, background_text)

        if on_progress:
            await on_progress("ontology_agent", "领域本体框架构建完成", 100)

        return schema

    async def synthesize_and_reason(
        self,
        topic: str,
        kg: dict,
        domain: str = "general",
        on_progress: Optional[callable] = None,
    ) -> dict:
        """
        Perform semantic reasoning over the extracted KG:
        - Infer implicit relations
        - Identify concept hierarchies
        - Generate ontology-grounded insights
        """
        if on_progress:
            await on_progress("ontology_agent", "语义推理与洞察生成...", 40)

        nodes_summary = "\n".join(
            f"  - {n['name']} ({n.get('node_type','concept')}): {n.get('description','')}"
            for n in kg.get("nodes", [])[:20]
        )
        edges_summary = "\n".join(
            f"  - {e['source']} --[{e.get('relation_label', e.get('relation_type',''))}]--> {e['target']}"
            for e in kg.get("edges", [])[:20]
        )

        messages = [
            {
                "role": "system",
                "content": "你是知识图谱推理专家，基于已有的知识图谱进行深度语义推理，发现隐含关联和深层逻辑。",
            },
            {
                "role": "user",
                "content": f"""基于以下知识图谱对"{topic}"进行语义推理。

已提取节点：
{nodes_summary or '（无节点数据）'}

已提取关系：
{edges_summary or '（无关系数据）'}

请分析：
1. **核心概念链** — 从主题出发，最重要的3-5条概念链路（A→B→C格式）
2. **隐含关联** — 图谱中未直接连接但实际相关的概念对（2-4对）
3. **概念层次** — 该领域的顶层→中层→底层概念层级
4. **知识缺口** — 图谱中明显缺失的关键节点或关系
5. **推理洞察** — 基于图谱结构得出的2-3条非显而易见的业务洞察""",
            },
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
        reasoning = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.3, max_tokens=1500)

        if on_progress:
            await on_progress("ontology_agent", "本体推理完成", 100)

        return {
            "kg": kg,
            "reasoning": reasoning,
            "topic": topic,
            "domain": domain,
            "node_count": len(kg.get("nodes", [])),
            "edge_count": len(kg.get("edges", [])),
        }

    async def run_for_subtask(self, task: SubTask) -> ResearchFinding:
        """Adapter to run as part of the multi-agent pipeline."""
        kg = await self.extract(task.query, domain="general")
        result = await self.synthesize_and_reason(task.query, kg)

        content_parts = [f"## 知识图谱分析：{task.query}\n"]
        content_parts.append(f"**提取节点数**：{result['node_count']}  **关系数**：{result['edge_count']}\n")

        if result.get("reasoning"):
            content_parts.append(result["reasoning"])

        return ResearchFinding(
            sub_task_id=task.id,
            content="\n".join(content_parts),
            source_type="ontology_analysis",
            confidence=0.80,
            key_data=[
                f"nodes: {result['node_count']}",
                f"edges: {result['edge_count']}",
                f"domain: {result['domain']}",
            ],
        )
