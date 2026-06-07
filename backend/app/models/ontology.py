"""Ontology and Knowledge Graph ORM models."""
import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class OntologyNode(Base):
    """A concept/entity in the domain knowledge graph."""
    __tablename__ = "ontology_nodes"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True)
    report_id = Column(Integer, nullable=True)            # linked to a report if built during research
    name = Column(String(300), nullable=False)            # concept label
    node_type = Column(String(60), default="concept")    # concept | entity | event | process | attribute
    domain = Column(String(80), default="general")       # business domain
    description = Column(Text, default="")
    aliases = Column(Text, default="")                   # JSON list of alternative names
    properties = Column(Text, default="")                # JSON dict of attributes
    importance = Column(Float, default=0.5)              # 0-1 centrality score
    source_docs = Column(Text, default="")               # JSON list of source doc refs
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    out_edges = relationship(
        "OntologyEdge", foreign_keys="OntologyEdge.source_id",
        back_populates="source", cascade="all, delete-orphan"
    )
    in_edges = relationship(
        "OntologyEdge", foreign_keys="OntologyEdge.target_id",
        back_populates="target", cascade="all, delete-orphan"
    )

    def get_aliases(self) -> list[str]:
        try:
            return json.loads(self.aliases) if self.aliases else []
        except Exception:
            return []

    def get_properties(self) -> dict:
        try:
            return json.loads(self.properties) if self.properties else {}
        except Exception:
            return {}


class OntologyEdge(Base):
    """A directed relationship between two ontology nodes."""
    __tablename__ = "ontology_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("ontology_nodes.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("ontology_nodes.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(100), nullable=False)  # is-a | part-of | causes | influences | competes-with | etc.
    relation_label = Column(String(200), default="")     # human-readable label
    weight = Column(Float, default=1.0)                  # relation strength
    direction = Column(String(20), default="directed")   # directed | bidirectional
    evidence = Column(Text, default="")                  # supporting text excerpt
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source = relationship("OntologyNode", foreign_keys=[source_id], back_populates="out_edges")
    target = relationship("OntologyNode", foreign_keys=[target_id], back_populates="in_edges")


class DomainSchema(Base):
    """Persistent domain schema snapshot: structured business ontology for a domain."""
    __tablename__ = "domain_schemas"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(80), nullable=False, unique=True)   # finance | healthcare | etc.
    version = Column(String(20), default="1.0")
    core_concepts = Column(Text, default="")    # JSON list of main concept names
    relations = Column(Text, default="")        # JSON list of {from, relation, to}
    business_rules = Column(Text, default="")   # JSON list of domain rules
    kpi_taxonomy = Column(Text, default="")     # JSON: {category: [kpi_name...]}
    entity_taxonomy = Column(Text, default="")  # JSON: {type: [entity_name...]}
    last_built_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    built_by = Column(String(50), default="ontology_agent")


__all__ = ["OntologyNode", "OntologyEdge", "DomainSchema"]
