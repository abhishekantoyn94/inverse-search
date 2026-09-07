import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JurisdictionLevel(str, enum.Enum):
    FEDERAL = "federal"
    STATE = "state"


class DocType(str, enum.Enum):
    CASE = "case"
    STATUTE = "statute"
    REGULATION = "regulation"
    SECONDARY = "secondary"
    DISCOVERY = "discovery"


class SourceType(str, enum.Enum):
    PRIMARY = "primary"
    QUASI_PRIMARY = "quasi_primary"
    SECONDARY = "secondary"
    DISCOVERY = "discovery"


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class SectionType(str, enum.Enum):
    PARAGRAPH = "paragraph"
    HOLDING = "holding"
    HEADNOTE = "headnote"
    STATUTE_SECTION = "statute_section"
    FOOTNOTE = "footnote"


class TreatmentType(str, enum.Enum):
    CITES = "cites"
    FOLLOWS = "follows"
    DISTINGUISHES = "distinguishes"
    APPROVES = "approves"
    CRITICISES = "criticises"
    OVERRULES = "overrules"
    DEPARTS_FROM = "departs_from"
    INTERPRETS = "interprets"
    APPLIES = "applies"
    NARROWS = "narrows"
    EXPANDS = "expands"


class ExtractedBy(str, enum.Enum):
    RULE = "rule"
    LLM = "llm"


class EntityType(str, enum.Enum):
    JUDGE = "judge"
    PARTY = "party"
    COURT = "court"


class PropositionRelation(str, enum.Enum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    DISTINGUISH = "distinguish"
    LIMIT = "limit"
    REVERSE = "reverse"


class ClaimType(str, enum.Enum):
    AUTHORITY = "authority"
    INFERENCE = "inference"
    ANALOGY = "analogy"
    SPECULATION = "speculation"
    UNRESOLVED = "unresolved"


class ChatRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    level: Mapped[JurisdictionLevel] = mapped_column(Enum(JurisdictionLevel))
    parent_jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"))

    courts: Mapped[list["Court"]] = relationship(back_populates="jurisdiction")


class Court(Base):
    __tablename__ = "courts"

    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"))
    courtlistener_id: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, comment="0=trial, increasing toward highest appellate")
    parent_court_id: Mapped[int | None] = mapped_column(ForeignKey("courts.id"))
    binding_scope: Mapped[dict] = mapped_column(JSON, default=dict)

    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="courts")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[DocType] = mapped_column(Enum(DocType))
    jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"))
    court_id: Mapped[int | None] = mapped_column(ForeignKey("courts.id"))
    title: Mapped[str] = mapped_column(Text)
    citation_string: Mapped[str | None] = mapped_column(String(255), index=True)
    date_decided_or_enacted: Mapped[date | None] = mapped_column(Date)
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_provider: Mapped[str] = mapped_column(String(64))
    license_note: Mapped[str | None] = mapped_column(Text)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus), default=IngestionStatus.PENDING
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sections: Mapped[list["DocumentSection"]] = relationship(back_populates="document")


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    section_type: Mapped[SectionType] = mapped_column(Enum(SectionType))
    sequence: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    locator: Mapped[str | None] = mapped_column(String(64), comment="e.g. page/paragraph/section no.")
    embedding_ref: Mapped[str | None] = mapped_column(
        String(128), index=True, comment="doc id in the OpenSearch index"
    )

    document: Mapped["Document"] = relationship(back_populates="sections")

    __table_args__ = (UniqueConstraint("document_id", "sequence"),)


class Citation(Base):
    """An edge in the authority graph: citing document/section -> cited document/section."""

    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    citing_section_id: Mapped[int | None] = mapped_column(ForeignKey("document_sections.id"))
    cited_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    cited_section_id: Mapped[int | None] = mapped_column(ForeignKey("document_sections.id"))
    citation_string_raw: Mapped[str] = mapped_column(String(255))
    treatment_type: Mapped[TreatmentType] = mapped_column(Enum(TreatmentType))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    extracted_by: Mapped[ExtractedBy] = mapped_column(Enum(ExtractedBy))
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StatuteVersion(Base):
    __tablename__ = "statute_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    statute_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    section_no: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    effective_start: Mapped[date | None] = mapped_column(Date)
    effective_end: Mapped[date | None] = mapped_column(Date)
    amendment_of: Mapped[int | None] = mapped_column(ForeignKey("statute_versions.id"))


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType))
    name: Mapped[str] = mapped_column(String(255), index=True)
    entity_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class DocumentEntity(Base):
    __tablename__ = "document_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(64), comment="e.g. plaintiff, defendant, author")


class Proposition(Base):
    __tablename__ = "propositions"

    id: Mapped[int] = mapped_column(primary_key=True)
    text_summary: Mapped[str] = mapped_column(Text)
    area_of_law: Mapped[str | None] = mapped_column(String(120))


class PropositionDocument(Base):
    __tablename__ = "proposition_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposition_id: Mapped[int] = mapped_column(ForeignKey("propositions.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    relation: Mapped[PropositionRelation] = mapped_column(Enum(PropositionRelation))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("orgs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("folders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResearchQuestion(Base):
    __tablename__ = "research_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("research_sessions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    modes: Mapped[list[str]] = mapped_column(JSON, default=list)
    jurisdiction_filter: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResearchAnswer(Base):
    __tablename__ = "research_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("research_questions.id"), index=True)
    structured_answer: Mapped[dict] = mapped_column(JSON, comment="matches research.schemas.StructuredAnswer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claims: Mapped[list["Claim"]] = relationship(back_populates="answer")


class Claim(Base):
    """Every substantive proposition in a StructuredAnswer, source-pointed for the
    Source Verification gate to check."""

    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("research_answers.id"), index=True)
    section_name: Mapped[str] = mapped_column(String(64))
    claim_text: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[ClaimType] = mapped_column(Enum(ClaimType))
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    source_section_id: Mapped[int | None] = mapped_column(ForeignKey("document_sections.id"))
    extract_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verified: Mapped[bool] = mapped_column(default=False)

    answer: Mapped["ResearchAnswer"] = relationship(back_populates="claims")


class ChatMessage(Base):
    """A conversational turn. `answer_id` is set only for assistant turns that were a
    full /research run; plain /chat follow-ups reference the session's latest answer
    for grounding but don't create a new one."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("research_sessions.id"), index=True)
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole))
    content: Mapped[str] = mapped_column(Text)
    answer_id: Mapped[int | None] = mapped_column(ForeignKey("research_answers.id"))
    web_results: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
