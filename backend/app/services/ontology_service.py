"""
Ontology Service — knowledge graph construction and semantic reasoning.

Builds domain ontologies from text corpora, maintains entity-relation graphs,
and provides ontology-aware query expansion for enhanced RAG retrieval.
"""
import json
import logging
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology import OntologyNode, OntologyEdge, DomainSchema
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Extraction helpers
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_EXTRACT = """你是知识图谱构建专家。从给定文本中提取结构化知识，以JSON返回。
严格遵循输出格式，不要添加额外说明。确保节点名称简洁（≤20字），关系类型使用英文关键词。"""

NODE_TYPES = ["concept", "entity", "event", "process", "attribute", "metric", "policy", "product"]

RELATION_TYPES = {
    "is-a": "上下位关系（A是B的子类）",
    "part-of": "整体-部分关系",
    "causes": "因果关系（A导致B）",
    "influences": "影响关系（A影响B）",
    "competes-with": "竞争关系",
    "cooperates-with": "合作关系",
    "depends-on": "依赖关系",
    "produces": "生产/产出关系",
    "regulates": "监管/规制关系",
    "measures": "度量关系（A衡量B）",
    "belongs-to": "归属关系",
    "preceded-by": "前置关系",
    "associated-with": "关联关系",
}


async def extract_kg_from_text(
    text: str, domain: str = "general", context: str = ""
) -> dict:
    """
    Extract entities and relations from text using LLM.
    Returns {"nodes": [...], "edges": [...]}
    """
    relation_guide = "\n".join(f"  - {k}: {v}" for k, v in RELATION_TYPES.items())
    node_type_guide = ", ".join(NODE_TYPES)

    prompt = f"""从以下文本中提取知识图谱。领域：{domain}。
额外上下文：{context or '无'}

文本：
{text[:3000]}

请返回如下JSON格式（仅JSON，无其他内容）：
{{
  "nodes": [
    {{
      "name": "节点名称",
      "node_type": "concept|entity|event|process|attribute|metric|policy|product",
      "description": "简短描述（≤50字）",
      "aliases": ["别名1", "别名2"],
      "importance": 0.8
    }}
  ],
  "edges": [
    {{
      "source": "源节点名称",
      "target": "目标节点名称",
      "relation_type": "causes|influences|is-a|part-of|...",
      "relation_label": "中文关系描述",
      "weight": 0.9,
      "evidence": "支撑该关系的文本片段"
    }}
  ]
}}

节点类型说明：{node_type_guide}
关系类型说明：
{relation_guide}

提取要求：
1. 节点数量：5-20个，优先选重要概念
2. 边数量：5-25条，必须连接已提取的节点
3. importance在0-1之间，核心概念靠近1
4. 避免提取过于泛化的节点（如"系统"、"方法"等）"""

    messages = [
        {"role": "system", "content": SYSTEM_EXTRACT},
        {"role": "user", "content": prompt},
    ]
    router = get_model_router()
    model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
    raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                     temperature=0.1, max_tokens=2000)

    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"[ontology] KG extraction parse error: {e}\nRaw: {raw[:300]}")
        return {"nodes": [], "edges": []}


async def build_domain_schema(domain: str, background_text: str = "") -> dict:
    """Build a structured domain schema using LLM domain knowledge."""
    messages = [
        {
            "role": "system",
            "content": "你是领域知识建模专家。构建结构化的领域本体框架，以JSON格式输出。",
        },
        {
            "role": "user",
            "content": f"""为"{domain}"领域构建本体框架。
背景参考：{background_text[:1000] if background_text else '无'}

返回JSON（仅JSON）：
{{
  "core_concepts": ["概念1", "概念2", ...],
  "relations": [
    {{"from": "概念A", "relation": "influences", "to": "概念B"}},
    ...
  ],
  "business_rules": [
    "规则1描述",
    ...
  ],
  "kpi_taxonomy": {{
    "财务类": ["营收", "净利润", "ROE"],
    "运营类": ["客户数", "转化率"],
    ...
  }},
  "entity_taxonomy": {{
    "机构": ["监管机构", "上市公司"],
    "产品": ["金融产品", "实物商品"],
    ...
  }}
}}

要求：core_concepts 10-20个，relations 15-30条，kpi_taxonomy 3-5类各3-8项。""",
        },
    ]
    router = get_model_router()
    model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
    raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                     temperature=0.2, max_tokens=2500)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"[ontology] Domain schema parse error: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────────────
# DB persistence
# ──────────────────────────────────────────────────────────────────────────────

async def save_kg_to_db(
    db: AsyncSession,
    kg: dict,
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
    domain: str = "general",
) -> tuple[int, int]:
    """Persist extracted KG nodes and edges. Returns (node_count, edge_count)."""
    nodes_data = kg.get("nodes", [])
    edges_data = kg.get("edges", [])

    # Upsert nodes by name (within same kb/report scope)
    name_to_id: dict[str, int] = {}
    for nd in nodes_data:
        name = (nd.get("name") or "").strip()
        if not name:
            continue
        existing = (
            await db.execute(
                select(OntologyNode).where(
                    OntologyNode.name == name,
                    OntologyNode.kb_id == kb_id,
                    OntologyNode.report_id == report_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.importance = max(existing.importance, nd.get("importance", 0.5))
            existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            await db.flush()
            name_to_id[name] = existing.id
        else:
            node = OntologyNode(
                kb_id=kb_id,
                report_id=report_id,
                name=name,
                node_type=nd.get("node_type", "concept"),
                domain=domain,
                description=nd.get("description", ""),
                aliases=json.dumps(nd.get("aliases", []), ensure_ascii=False),
                importance=nd.get("importance", 0.5),
            )
            db.add(node)
            await db.flush()
            name_to_id[name] = node.id

    # Insert edges
    edge_count = 0
    for ed in edges_data:
        src_name = (ed.get("source") or "").strip()
        tgt_name = (ed.get("target") or "").strip()
        rel = (ed.get("relation_type") or "associated-with").strip()
        if src_name not in name_to_id or tgt_name not in name_to_id:
            continue
        edge = OntologyEdge(
            source_id=name_to_id[src_name],
            target_id=name_to_id[tgt_name],
            relation_type=rel,
            relation_label=ed.get("relation_label", rel),
            weight=ed.get("weight", 1.0),
            evidence=ed.get("evidence", ""),
            confidence=ed.get("confidence", 0.8),
        )
        db.add(edge)
        edge_count += 1

    await db.commit()
    return len(name_to_id), edge_count


async def save_domain_schema(db: AsyncSession, domain: str, schema: dict) -> DomainSchema:
    """Upsert domain schema in DB."""
    existing = (
        await db.execute(select(DomainSchema).where(DomainSchema.domain == domain))
    ).scalar_one_or_none()

    if existing:
        existing.core_concepts = json.dumps(schema.get("core_concepts", []), ensure_ascii=False)
        existing.relations = json.dumps(schema.get("relations", []), ensure_ascii=False)
        existing.business_rules = json.dumps(schema.get("business_rules", []), ensure_ascii=False)
        existing.kpi_taxonomy = json.dumps(schema.get("kpi_taxonomy", {}), ensure_ascii=False)
        existing.entity_taxonomy = json.dumps(schema.get("entity_taxonomy", {}), ensure_ascii=False)
        existing.last_built_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        await db.commit()
        return existing

    ds = DomainSchema(
        domain=domain,
        core_concepts=json.dumps(schema.get("core_concepts", []), ensure_ascii=False),
        relations=json.dumps(schema.get("relations", []), ensure_ascii=False),
        business_rules=json.dumps(schema.get("business_rules", []), ensure_ascii=False),
        kpi_taxonomy=json.dumps(schema.get("kpi_taxonomy", {}), ensure_ascii=False),
        entity_taxonomy=json.dumps(schema.get("entity_taxonomy", {}), ensure_ascii=False),
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return ds


# ──────────────────────────────────────────────────────────────────────────────
# Query / retrieval
# ──────────────────────────────────────────────────────────────────────────────

async def get_graph_for_scope(
    db: AsyncSession,
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
    limit_nodes: int = 150,
) -> dict:
    """Return graph dict {nodes:[...], edges:[...]} for frontend visualization."""
    q = select(OntologyNode).order_by(OntologyNode.importance.desc()).limit(limit_nodes)
    if kb_id is not None:
        q = q.where(OntologyNode.kb_id == kb_id)
    if report_id is not None:
        q = q.where(OntologyNode.report_id == report_id)

    nodes = (await db.execute(q)).scalars().all()
    node_ids = {n.id for n in nodes}

    edges_q = select(OntologyEdge).where(
        OntologyEdge.source_id.in_(node_ids),
        OntologyEdge.target_id.in_(node_ids),
    )
    edges = (await db.execute(edges_q)).scalars().all()

    return {
        "nodes": [
            {
                "id": n.id,
                "name": n.name,
                "node_type": n.node_type,
                "domain": n.domain,
                "description": n.description,
                "importance": n.importance,
                "aliases": n.get_aliases(),
            }
            for n in nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": e.source_id,
                "target": e.target_id,
                "relation_type": e.relation_type,
                "relation_label": e.relation_label,
                "weight": e.weight,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }


async def expand_query_with_ontology(
    query: str, db: AsyncSession, kb_id: Optional[int] = None, top_k: int = 5
) -> list[str]:
    """
    Ontology-aware query expansion: find related concepts and return expanded
    search terms to enrich RAG retrieval.
    """
    nodes_q = select(OntologyNode).where(OntologyNode.name.ilike(f"%{query[:30]}%"))
    if kb_id:
        nodes_q = nodes_q.where(OntologyNode.kb_id == kb_id)
    nodes_q = nodes_q.limit(3)
    seed_nodes = (await db.execute(nodes_q)).scalars().all()

    if not seed_nodes:
        return []

    expanded = []
    for node in seed_nodes:
        # Follow out-edges
        out_q = select(OntologyEdge, OntologyNode).join(
            OntologyNode, OntologyEdge.target_id == OntologyNode.id
        ).where(OntologyEdge.source_id == node.id).limit(top_k)
        rows = (await db.execute(out_q)).all()
        for _, target_node in rows:
            expanded.append(target_node.name)

        # Follow in-edges
        in_q = select(OntologyEdge, OntologyNode).join(
            OntologyNode, OntologyEdge.source_id == OntologyNode.id
        ).where(OntologyEdge.target_id == node.id).limit(top_k)
        rows = (await db.execute(in_q)).all()
        for _, src_node in rows:
            expanded.append(src_node.name)

    return list(dict.fromkeys(expanded))[:top_k]  # deduplicate, keep order


async def get_domain_schema(db: AsyncSession, domain: str) -> Optional[DomainSchema]:
    return (
        await db.execute(select(DomainSchema).where(DomainSchema.domain == domain))
    ).scalar_one_or_none()
