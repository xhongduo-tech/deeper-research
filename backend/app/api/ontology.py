"""
Ontology API — knowledge graph construction and domain schema management.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ontology_service import (
    extract_kg_from_text,
    build_domain_schema,
    save_kg_to_db,
    save_domain_schema,
    get_graph_for_scope,
    expand_query_with_ontology,
    get_domain_schema,
)
from app.agents.ontology_agent import OntologyAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ontology", tags=["ontology"])


class ExtractKGRequest(BaseModel):
    text: str
    domain: str = "general"
    context: str = ""
    kb_id: Optional[int] = None
    report_id: Optional[int] = None
    save: bool = True


class BuildSchemaRequest(BaseModel):
    domain: str
    background_text: str = ""
    save: bool = True


class QueryExpandRequest(BaseModel):
    query: str
    kb_id: Optional[int] = None
    top_k: int = 5


@router.post("/extract")
async def extract_knowledge_graph(req: ExtractKGRequest, db: AsyncSession = Depends(get_db)):
    """Extract entities and relations from text, optionally persist to DB."""
    if len(req.text.strip()) < 20:
        raise HTTPException(status_code=400, detail="文本太短，至少需要20个字符")

    agent = OntologyAgent()
    kg = await agent.extract(req.text, domain=req.domain, context=req.context)

    node_count, edge_count = 0, 0
    if req.save and (kg.get("nodes") or kg.get("edges")):
        node_count, edge_count = await save_kg_to_db(
            db, kg, kb_id=req.kb_id, report_id=req.report_id, domain=req.domain
        )

    return {
        "kg": kg,
        "saved": req.save,
        "node_count": len(kg.get("nodes", [])),
        "edge_count": len(kg.get("edges", [])),
        "persisted_nodes": node_count,
        "persisted_edges": edge_count,
    }


@router.post("/extract-and-reason")
async def extract_and_reason(req: ExtractKGRequest, db: AsyncSession = Depends(get_db)):
    """Extract KG and perform semantic reasoning."""
    if len(req.text.strip()) < 20:
        raise HTTPException(status_code=400, detail="文本太短")

    agent = OntologyAgent()
    kg = await agent.extract(req.text, domain=req.domain, context=req.context)
    result = await agent.synthesize_and_reason(req.context or req.text[:50], kg, domain=req.domain)

    if req.save and kg.get("nodes"):
        await save_kg_to_db(db, kg, kb_id=req.kb_id, report_id=req.report_id, domain=req.domain)

    return result


@router.get("/graph")
async def get_knowledge_graph(
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
    limit: int = 150,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the stored knowledge graph for visualization."""
    graph = await get_graph_for_scope(db, kb_id=kb_id, report_id=report_id, limit_nodes=limit)
    return graph


@router.post("/schema/build")
async def build_schema(req: BuildSchemaRequest, db: AsyncSession = Depends(get_db)):
    """Build a comprehensive domain ontology schema."""
    if not req.domain.strip():
        raise HTTPException(status_code=400, detail="领域名称不能为空")

    schema = await build_domain_schema(req.domain, req.background_text)
    ds = None
    if req.save and schema:
        ds = await save_domain_schema(db, req.domain, schema)

    return {
        "domain": req.domain,
        "schema": schema,
        "saved": req.save,
        "schema_id": ds.id if ds else None,
    }


@router.get("/schema/{domain}")
async def get_schema(domain: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a stored domain schema."""
    ds = await get_domain_schema(db, domain)
    if not ds:
        raise HTTPException(status_code=404, detail=f"未找到领域 '{domain}' 的本体框架")

    import json
    return {
        "id": ds.id,
        "domain": ds.domain,
        "version": ds.version,
        "core_concepts": json.loads(ds.core_concepts) if ds.core_concepts else [],
        "relations": json.loads(ds.relations) if ds.relations else [],
        "business_rules": json.loads(ds.business_rules) if ds.business_rules else [],
        "kpi_taxonomy": json.loads(ds.kpi_taxonomy) if ds.kpi_taxonomy else {},
        "entity_taxonomy": json.loads(ds.entity_taxonomy) if ds.entity_taxonomy else {},
        "last_built_at": ds.last_built_at.isoformat() if ds.last_built_at else None,
    }


@router.get("/graph/data-kb")
async def get_data_kb_graph(db: AsyncSession = Depends(get_db)):
    """Return ontology nodes + edges linked to actual knowledge bases.

    Combines domain ontology schemas with KB coverage data to produce
    a graph where each domain node is connected to its corresponding KBs.
    """
    from app.models.knowledge_base import KnowledgeBase
    from app.models.ontology import OntologyNode, OntologyEdge
    from sqlalchemy import select

    # Load all corp-scope KBs (system KBs)
    kb_rows = (await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.scope == "corp")
    )).scalars().all()

    # Load ontology nodes (domains)
    node_rows = (await db.execute(
        select(OntologyNode).limit(200)
    )).scalars().all()

    # Build nodes: domain nodes + KB nodes
    nodes = []
    edges = []

    for node in node_rows:
        nodes.append({
            "id": f"ont_{node.id}",
            "label": node.name,
            "type": "ontology_domain",
            "domain": node.domain,
            "importance": node.importance or 0.5,
        })

    for kb in kb_rows:
        kb_node_id = f"kb_{kb.id}"
        nodes.append({
            "id": kb_node_id,
            "label": kb.name,
            "type": "knowledge_base",
            "kb_type": kb.kb_type,
            "doc_count": kb.doc_count or 0,
            "chunk_count": kb.chunk_count or 0,
        })
        # Link KB to matching ontology nodes by domain similarity
        for node in node_rows:
            if node.domain and kb.kb_type and (node.domain in kb.kb_type or kb.kb_type in node.domain):
                edges.append({
                    "source": f"ont_{node.id}",
                    "target": kb_node_id,
                    "relation": "covers",
                    "strength": 0.6,
                })

    return {"nodes": nodes, "edges": edges, "kb_count": len(kb_rows), "ontology_count": len(node_rows)}


@router.post("/query-expand")
async def query_expand(req: QueryExpandRequest, db: AsyncSession = Depends(get_db)):
    """Expand a search query using ontology relationships."""
    expanded = await expand_query_with_ontology(req.query, db, kb_id=req.kb_id, top_k=req.top_k)
    return {"original": req.query, "expanded": expanded}


@router.post("/extract-kb/{kb_id}")
async def extract_kg_from_kb(
    kb_id: int,
    domain: str = "general",
    max_chunks: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Extract KG from all chunks in a knowledge base, persist results."""
    from sqlalchemy import select
    from app.models.knowledge_base import KBChunk, KBDocument

    # Load top chunks from the KB (ordered by doc, chunk_index)
    q = (
        select(KBChunk)
        .where(KBChunk.kb_id == kb_id)
        .order_by(KBChunk.doc_id, KBChunk.chunk_index)
        .limit(max_chunks)
    )
    chunks = (await db.execute(q)).scalars().all()
    if not chunks:
        raise HTTPException(status_code=404, detail="知识库中没有文档内容，请先上传文档")

    combined_text = "\n\n".join(c.content for c in chunks if c.content)[:6000]

    agent = OntologyAgent()
    kg = await agent.extract(combined_text, domain=domain)
    node_count, edge_count = await save_kg_to_db(db, kg, kb_id=kb_id, domain=domain)

    return {
        "kb_id": kb_id,
        "chunks_processed": len(chunks),
        "kg": kg,
        "node_count": node_count,
        "edge_count": edge_count,
    }
