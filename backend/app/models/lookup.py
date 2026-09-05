"""Public reference/lookup tables (shared across tenants)."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_en: Mapped[str | None] = mapped_column(Text)


class Agency(Base):
    __tablename__ = "agencies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    external_code: Mapped[str | None] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)


class TenderType(Base):
    __tablename__ = "tender_types"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cr_number: Mapped[str | None] = mapped_column(Text, unique=True)
    name_ar: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text)
    # normalized dedupe key (hamza/teh-marbuta variants collapse to one row)
    name_key: Mapped[str | None] = mapped_column(Text, unique=True)
    # Nationality enrichment (absent from the historical corpus; filled from an
    # external/authoritative source — see services/company_nationality.py).
    nationality: Mapped[str | None] = mapped_column(Text)       # ISO-ish country label, e.g. "SA", "TR", "US"
    is_local: Mapped[bool | None] = mapped_column(Boolean)      # True=Saudi, False=foreign, NULL=unknown
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
