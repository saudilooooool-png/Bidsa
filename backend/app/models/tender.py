"""Core procurement models: tenders, awards, winners, bids."""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.services.lifecycle import LIFECYCLE_VALUES

# Reuse the ENUM created by the SQL migration; do not re-emit the CREATE TYPE.
tender_lifecycle_enum = ENUM(*LIFECYCLE_VALUES, name="tender_lifecycle", create_type=False)


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())

    # Identity & taxonomy
    reference_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tender_number: Mapped[str | None] = mapped_column(Text)   # agency-side number
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    details_url: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id", ondelete="SET NULL"))
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"))
    type_id: Mapped[int | None] = mapped_column(ForeignKey("tender_types.id", ondelete="SET NULL"))
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id", ondelete="SET NULL"))
    tender_category_hint: Mapped[str | None] = mapped_column(Text)

    # Official status & lifecycle
    status_text: Mapped[str | None] = mapped_column(Text)
    status_id: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lifecycle_snapshot: Mapped[str | None] = mapped_column(tender_lifecycle_enum)
    lifecycle_basis: Mapped[str | None] = mapped_column(Text)

    # Money (exact integer halalas) & bidding
    win_amount_halalas: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(3), default="SAR")
    bids_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_winners: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Provenance / freshness / evidence
    component_details: Mapped[dict | None] = mapped_column(JSONB)
    freshness: Mapped[dict | None] = mapped_column(JSONB)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    provenance: Mapped[dict | None] = mapped_column(JSONB)
    raw_path: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(Text)
    source_snapshot_id: Mapped[str | None] = mapped_column(Text)

    # AI / multi-agent outputs
    ai_summary: Mapped[str | None] = mapped_column(Text)
    mandatory_requirements: Mapped[dict | None] = mapped_column(JSONB)
    local_content_requirements: Mapped[dict | None] = mapped_column(JSONB)
    risk_flags: Mapped[list | None] = mapped_column(JSONB)
    ai_model: Mapped[str | None] = mapped_column(Text)
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # RAG embedding + generated full-text vector (DB-managed, read-only here)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    award: Mapped["Award | None"] = relationship(back_populates="tender", uselist=False, cascade="all, delete-orphan")
    bids: Mapped[list["TenderBid"]] = relationship(back_populates="tender", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("win_amount_halalas IS NULL OR win_amount_halalas >= 0", name="ck_tender_win_nonneg"),
        CheckConstraint("bids_count >= 0", name="ck_tender_bids_nonneg"),
    )


class Award(Base):
    __tablename__ = "awards"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), unique=True, nullable=False)
    win_amount_halalas: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(3), default="SAR")
    award_state: Mapped[str | None] = mapped_column(Text)
    award_mode: Mapped[str | None] = mapped_column(Text)
    award_completeness: Mapped[str | None] = mapped_column(Text)
    award_announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    money_consistency: Mapped[dict | None] = mapped_column(JSONB)
    award_groups: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tender: Mapped["Tender"] = relationship(back_populates="award")
    winners: Mapped[list["AwardWinner"]] = relationship(back_populates="award", cascade="all, delete-orphan")


class AwardWinner(Base):
    __tablename__ = "award_winners"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    award_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("awards.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    award_halalas: Mapped[int | None] = mapped_column(BigInteger)
    group_ref: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[dict | None] = mapped_column(JSONB)

    award: Mapped["Award"] = relationship(back_populates="winners")


class TenderBid(Base):
    __tablename__ = "tender_bids"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    bid_halalas: Mapped[int | None] = mapped_column(BigInteger)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw: Mapped[dict | None] = mapped_column(JSONB)

    tender: Mapped["Tender"] = relationship(back_populates="bids")
