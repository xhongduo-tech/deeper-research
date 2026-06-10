"""Knowledge Base and Document ORM models."""
import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    scope = Column(String(20), default="personal")   # personal | dept | team | corp
    kb_type = Column(String(40), default="general")  # general | policy | research | contract | finance | tech | meeting
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    doc_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    total_size = Column(Integer, default=0)          # bytes
    embed_model = Column(String(100), default="")    # embedding model used
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    documents = relationship("KBDocument", back_populates="kb", cascade="all, delete-orphan")
    chunks = relationship("KBChunk", back_populates="kb", cascade="all, delete-orphan")
    project = relationship("Project", back_populates="knowledge_bases")


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(400), nullable=False)
    file_type = Column(String(20), default="text")
    file_size = Column(Integer, default=0)
    content_preview = Column(Text, default="")      # first 500 chars for display
    chunk_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending | indexed | error
    error_msg = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    kb = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("KBChunk", back_populates="document", cascade="all, delete-orphan")


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    doc_id = Column(Integer, ForeignKey("kb_documents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, default=0)
    embedding_json = Column(Text, default="")       # JSON float array
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    kb = relationship("KnowledgeBase", back_populates="chunks")
    document = relationship("KBDocument", back_populates="chunks")

    def get_embedding(self) -> list[float] | None:
        if not self.embedding_json:
            return None
        try:
            return json.loads(self.embedding_json)
        except Exception:
            return None

    def set_embedding(self, vec: list[float]):
        self.embedding_json = json.dumps(vec)
