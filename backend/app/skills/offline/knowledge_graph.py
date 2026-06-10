"""Knowledge Graph Skill — SOTA-enhanced entity/relation extraction + semantic clustering.

Enhancements:
  - Chain-of-Thought: reason about entity relationships before extraction
  - Self-critique: checks graph completeness, relation validity, entity coverage
  - Adversarial review: challenges weak relations, spots missing entities
  - Quality score (0-100) per graph
  - Structured JSON output with auto-repair
  - Confidence scoring per entity and relation

Reference patterns:
  - Structured JSON output with typed entities and weighted relations
  - Importance scoring via centrality estimation (degree + domain weight)
  - Semantic cluster detection (groups related nodes)
  - Bidirectional relation labeling with confidence
  - Community detection hint (for visualization coloring)
  - Optional: ontology alignment (maps entities to domain schema concepts)
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class KnowledgeGraphSkill(Skill):
    name = "knowledge_graph"
    category = "knowledge"
    description = (
        "SOTA知识图谱构建：从文本中抽取实体和关系构建知识图谱，"
        "含CoT推理、自评、红队挑战和质量评分。"
        "输出带类型的实体、加权关系、重要性评分、语义聚类；可直接用于图谱可视化"
    )
    parameters = {
        "text":    {"type": "string", "description": "待抽取文本"},
        "domain":  {"type": "string", "description": "业务领域（fine-tunes entity types）", "default": "general"},
        "context": {"type": "string", "description": "附加上下文", "default": ""},
        "max_nodes": {"type": "integer", "description": "最大节点数", "default": 30},
        "extract_clusters": {"type": "boolean", "description": "是否提取语义聚类", "default": True},
        "enable_critique": {
            "type": "boolean",
            "description": "启用图谱质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    _DOMAIN_ENTITY_HINTS: dict[str, list[str]] = {
        "finance":       ["公司", "金融机构", "投资工具", "财务指标", "监管机构", "市场事件", "经济政策"],
        "healthcare":    ["医疗机构", "疾病", "药物", "治疗方案", "医疗设备", "临床指标", "监管标准"],
        "technology":    ["技术", "产品", "平台", "公司", "标准协议", "研发机构", "市场应用"],
        "manufacturing": ["生产工艺", "原材料", "供应商", "设备", "质量标准", "物流节点", "客户"],
        "retail":        ["品牌", "渠道", "消费者群体", "产品类别", "促销活动", "竞争对手", "市场趋势"],
        "general":       ["组织", "人物", "概念", "事件", "产品", "政策", "地点", "属性"],
    }

    KG_SCHEMA = {
        "nodes": [
            {
                "id": "",
                "name": "",
                "type": "",
                "importance": 0.5,
                "description": "",
                "aliases": [""],
                "community": 0,
                "confidence": 0.9,
            }
        ],
        "edges": [
            {
                "source": "",
                "target": "",
                "relation_type": "",
                "relation_label": "",
                "weight": 0.5,
                "confidence": 0.8,
                "direction": "directed|undirected",
            }
        ],
        "clusters": [
            {
                "cluster_id": 1,
                "name": "",
                "node_names": [""],
                "theme": "",
                "confidence": 0.8,
            }
        ],
        "graph_summary": "",
        "extraction_quality": 8.0,
    }

    async def execute(self, text: str = "", domain: str = "general", context: str = "",
                      max_nodes: int = 30, extract_clusters: bool = True,
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text             = params.get("text", text)
            domain           = params.get("domain", domain)
            context          = params.get("context", context)
            max_nodes        = int(params.get("max_nodes", max_nodes))
            extract_clusters = params.get("extract_clusters", extract_clusters)
            enable_critique  = params.get("enable_critique", enable_critique)
            enable_adversarial = params.get("enable_adversarial", enable_adversarial)

        entity_hints = self._DOMAIN_ENTITY_HINTS.get(domain, self._DOMAIN_ENTITY_HINTS["general"])
        context_block = f"\n背景信息：{context[:500]}" if context else ""

        # ── Phase 1: CoT Reasoning ────────────────────────────────────────────
        system_msg = f"""你是知识图谱构建专家，专门从文本中提取结构化的实体-关系网络。
领域：{domain}。重点关注的实体类型：{', '.join(entity_hints)}。"""

        cot_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"""在进行知识图谱抽取前，请先逐步思考：

1. 文本中涉及哪些核心实体？它们属于什么类型？
2. 这些实体之间存在哪些关键关系？
3. 哪些实体是最重要的（中心节点）？
4. 是否存在语义上可聚类的实体群组？
5. 文本中哪些信息可能被遗漏了？

文本（前2000字）：
{text[:2000]}
{context_block}

请输出你的思考过程。"""},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=1000)

        # ── Phase 2: Structured extraction ────────────────────────────────────
        cluster_instruction = (
            '  "clusters": [{"cluster_id": 1, "name": "", "node_names": [""], "theme": "", "confidence": 0.8}],'
            if extract_clusters else '  "clusters": [],'
        )

        schema_desc = f"""输出严格JSON，包含：
- nodes: 实体节点（每条含id, name, type, importance 0-1, description, aliases, community 0-5, confidence）
- edges: 关系边（每条含source, target, relation_type, relation_label, weight 0.1-1, confidence 0.1-1, direction）
- {cluster_instruction}
- graph_summary: 2-3句话描述图谱整体结构和核心发现
- extraction_quality: 1-10分自评

重要约束：
1. edges 的 source/target 必须都是 nodes 中存在的 id
2. importance > 0.7 的节点为核心节点（≤5个）
3. 优先抽取有实际意义的关系，避免无信息量的泛化关系
4. 同一实体只出现一次（合并别称）
5. 每个节点和关系都标注置信度"""

        user_content = f"""{reasoning[:400]}

从以下文本中提取知识图谱，输出严格的 JSON 格式：{context_block}

文本（前3500字）：
{text[:3500]}

输出以下 JSON 结构（最多 {max_nodes} 个节点）：
{schema_desc}"""

        structured = await structured_generate(
            system=system_msg + " 严格输出 JSON，不含任何额外文字。",
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.KG_SCHEMA,
            temperature=0.1,
            max_tokens=2500,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}

        if not analysis:
            # Fallback
            try:
                from app.services.ontology_service import extract_kg_from_text
                analysis = await extract_kg_from_text(text, domain=domain, context=context)
            except Exception:
                analysis = {"nodes": [], "edges": [], "clusters": [], "graph_summary": ""}

        # Post-process: validate edge references
        node_ids = {n["id"] for n in analysis.get("nodes", [])}
        node_names = {n["name"] for n in analysis.get("nodes", [])}
        analysis["edges"] = [
            e for e in analysis.get("edges", [])
            if (e.get("source") in node_ids or e.get("source") in node_names)
            and (e.get("target") in node_ids or e.get("target") in node_names)
        ]

        n_nodes = len(analysis.get("nodes", []))
        n_edges = len(analysis.get("edges", []))
        n_clusters = len(analysis.get("clusters", []))

        top_nodes = sorted(analysis.get("nodes", []), key=lambda x: x.get("importance", 0), reverse=True)[:5]
        top_names = "、".join(n["name"] for n in top_nodes)

        summary = (
            f"提取到 **{n_nodes}** 个节点、**{n_edges}** 条关系"
            + (f"、**{n_clusters}** 个语义聚类" if n_clusters else "")
            + f"。\n核心节点：{top_names}"
            + (f"\n\n{analysis.get('graph_summary', '')}" if analysis.get("graph_summary") else "")
        )

        result = {
            "result": summary,
            "kg": analysis,
            "node_count": n_nodes,
            "edge_count": n_edges,
            "reasoning": reasoning,
        }

        # ── Phase 3: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and analysis:
            try:
                critique = await self_critique(
                    draft=summary[:3000],
                    topic=f"知识图谱 - {domain}",
                    dimensions=["data_grounding", "specificity", "logical_rigor"],
                )
                quality_score = round(critique["overall_score"] * 10)
                result["quality_score"] = quality_score
                result["critique"] = critique
            except Exception:
                pass

        # ── Phase 4: Adversarial review ───────────────────────────────────────
        if enable_adversarial and analysis:
            try:
                adversarial = await adversarial_review(
                    output=summary[:3000],
                    topic=f"知识图谱 - {domain}",
                )
                result["adversarial"] = adversarial
            except Exception:
                pass

        return result
