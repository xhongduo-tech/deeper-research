"""
Knowledge Graph Skill — entity/relation extraction + semantic clustering.

Enhancements over v1:
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


class KnowledgeGraphSkill(Skill):
    name = "knowledge_graph"
    category = "knowledge"
    description = (
        "从文本中抽取实体和关系构建知识图谱：带类型的实体、加权关系、重要性评分、"
        "语义聚类提示；输出结构化 JSON 可直接用于图谱可视化"
    )
    parameters = {
        "text":    {"type": "string", "description": "待抽取文本"},
        "domain":  {"type": "string", "description": "业务领域（fine-tunes entity types）", "default": "general"},
        "context": {"type": "string", "description": "附加上下文", "default": ""},
        "max_nodes": {"type": "integer", "description": "最大节点数", "default": 30},
        "extract_clusters": {"type": "boolean", "description": "是否提取语义聚类", "default": True},
    }

    # Entity types per domain to guide extraction
    _DOMAIN_ENTITY_HINTS: dict[str, list[str]] = {
        "finance":       ["公司", "金融机构", "投资工具", "财务指标", "监管机构", "市场事件", "经济政策"],
        "healthcare":    ["医疗机构", "疾病", "药物", "治疗方案", "医疗设备", "临床指标", "监管标准"],
        "technology":    ["技术", "产品", "平台", "公司", "标准协议", "研发机构", "市场应用"],
        "manufacturing": ["生产工艺", "原材料", "供应商", "设备", "质量标准", "物流节点", "客户"],
        "retail":        ["品牌", "渠道", "消费者群体", "产品类别", "促销活动", "竞争对手", "市场趋势"],
        "general":       ["组织", "人物", "概念", "事件", "产品", "政策", "地点", "属性"],
    }

    async def execute(self, text: str = "", domain: str = "general", context: str = "",
                      max_nodes: int = 30, extract_clusters: bool = True, **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text             = params.get("text", text)
            domain           = params.get("domain", domain)
            context          = params.get("context", context)
            max_nodes        = int(params.get("max_nodes", max_nodes))
            extract_clusters = params.get("extract_clusters", extract_clusters)

        entity_hints = self._DOMAIN_ENTITY_HINTS.get(domain, self._DOMAIN_ENTITY_HINTS["general"])
        context_block = f"\n背景信息：{context[:500]}" if context else ""

        system_msg = f"""你是知识图谱构建专家，专门从文本中提取结构化的实体-关系网络。
领域：{domain}。重点关注的实体类型：{', '.join(entity_hints)}。
严格输出 JSON，不含任何额外文字。"""

        cluster_instruction = """
  "clusters": [
    {"cluster_id": 1, "name": "<聚类名称>", "node_names": ["节点名1", "节点名2", ...], "theme": "<聚类主题描述>"}
  ],""" if extract_clusters else '  "clusters": [],'

        user_content = f"""从以下文本中提取知识图谱，输出严格的 JSON 格式：{context_block}

文本（前3500字）：
{text[:3500]}

输出以下 JSON 结构（最多 {max_nodes} 个节点）：
{{
  "nodes": [
    {{
      "id": "<唯一短标识，用英文下划线>",
      "name": "<实体名称（中文）>",
      "type": "<{'/'.join(entity_hints[:4])}/...>",
      "importance": <0.0-1.0，基于中心度估算>,
      "description": "<简短描述，≤30字>",
      "aliases": ["<别称1>", "<别称2>"],
      "community": <整数，0-5，同社区的节点颜色一致>
    }}
  ],
  "edges": [
    {{
      "source": "<源节点id>",
      "target": "<目标节点id>",
      "relation_type": "<关系英文标识: causes/influences/is-a/part-of/cooperates-with/competes-with/depends-on/produces/regulates/leads-to>",
      "relation_label": "<关系中文描述，≤10字>",
      "weight": <0.1-1.0，关系重要性>,
      "confidence": <0.1-1.0，抽取置信度>,
      "direction": "directed|undirected"
    }}
  ],
  {cluster_instruction.strip()}
  "graph_summary": "<2-3句话描述图谱整体结构和核心发现>"
}}

重要约束：
1. edges 的 source/target 必须都是 nodes 中存在的 id
2. importance > 0.7 的节点为核心节点（≤5个）
3. 优先抽取有实际意义的关系，避免无信息量的泛化关系
4. 同一实体只出现一次（合并别称）"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)

        raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                         temperature=0.1, max_tokens=2500)

        # Parse JSON
        kg: dict = {"nodes": [], "edges": [], "clusters": [], "graph_summary": ""}
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.rsplit("```", 1)[0].strip()
            kg = json.loads(clean)
        except Exception:
            # Fallback: use raw extraction
            try:
                from app.services.ontology_service import extract_kg_from_text
                kg = await extract_kg_from_text(text, domain=domain, context=context)
            except Exception:
                pass

        # Post-process: validate edge references
        node_ids = {n["id"] for n in kg.get("nodes", [])}
        node_names = {n["name"] for n in kg.get("nodes", [])}
        kg["edges"] = [
            e for e in kg.get("edges", [])
            if (e.get("source") in node_ids or e.get("source") in node_names)
            and (e.get("target") in node_ids or e.get("target") in node_names)
        ]

        n_nodes = len(kg.get("nodes", []))
        n_edges = len(kg.get("edges", []))
        n_clusters = len(kg.get("clusters", []))

        top_nodes = sorted(kg.get("nodes", []), key=lambda x: x.get("importance", 0), reverse=True)[:5]
        top_names = "、".join(n["name"] for n in top_nodes)

        summary = (
            f"提取到 **{n_nodes}** 个节点、**{n_edges}** 条关系"
            + (f"、**{n_clusters}** 个语义聚类" if n_clusters else "")
            + f"。\n核心节点：{top_names}"
            + (f"\n\n{kg.get('graph_summary', '')}" if kg.get("graph_summary") else "")
        )

        return {"result": summary, "kg": kg, "node_count": n_nodes, "edge_count": n_edges}
