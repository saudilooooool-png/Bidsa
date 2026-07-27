"""Company knowledge base: file upload + tender matching.

Matching works with zero AI keys: it builds a keyword profile from the
organization's uploaded documents and runs it through Postgres full-text
search over the tender warehouse (title/description tsvector), ranked by
ts_rank. When embeddings are backfilled later, a pgvector path can slot in
beside this without changing the API shape.
"""
from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_subscription
from app.db.session import get_session
from app.models.lookup import Agency
from app.models.saas import KnowledgeChunk, KnowledgeDocument
from app.models.tender import Tender
from app.services.textproc import chunk_text, extract_text, tokenize

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_DOCS_PER_ORG = 50


@router.get("/documents")
async def list_documents(
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(KnowledgeDocument, func.count(KnowledgeChunk.id))
        .outerjoin(KnowledgeChunk, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.organization_id == auth.org.id)
        .group_by(KnowledgeDocument.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )).all()
    return [
        {"id": str(d.id), "title": d.title, "doc_type": d.doc_type,
         "filename": d.source_filename, "chunks": n,
         "created_at": d.created_at.isoformat()}
        for d, n in rows
    ]


@router.post("/upload", status_code=201)
async def upload(
    file: UploadFile,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "الحد الأقصى لحجم الملف 8MB.")
    doc_count = (await session.execute(
        select(func.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.organization_id == auth.org.id)
    )).scalar_one()
    if doc_count >= MAX_DOCS_PER_ORG:
        raise HTTPException(402, f"وصلت حد المستندات ({MAX_DOCS_PER_ORG}).")

    try:
        content = extract_text(file.filename or "file", data)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    doc = KnowledgeDocument(
        organization_id=auth.org.id,
        uploaded_by=auth.user.id,
        title=(file.filename or "مستند").rsplit(".", 1)[0][:200],
        doc_type="company_profile",
        source_filename=file.filename,
        mime_type=file.content_type,
    )
    session.add(doc)
    await session.flush()
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        session.add(KnowledgeChunk(
            document_id=doc.id, organization_id=auth.org.id,
            chunk_index=i, content=chunk, token_count=len(chunk.split()),
        ))
    await session.commit()
    return {"id": str(doc.id), "title": doc.title, "chunks": len(chunks)}


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    doc = (await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == auth.org.id)
    )).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "document not found")
    await session.delete(doc)
    await session.commit()
    return {"ok": True}


async def org_keyword_profile(session: AsyncSession, org_id, k: int = 15) -> list[str]:
    contents = (await session.execute(
        select(KnowledgeChunk.content)
        .where(KnowledgeChunk.organization_id == org_id).limit(400)
    )).scalars().all()
    counts: Counter[str] = Counter()
    for c in contents:
        counts.update(tokenize(c))
    return [w for w, _ in counts.most_common(k)]


@router.post("/match")
async def match_tenders(
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
):
    """Rank warehouse tenders against the org's document keyword profile."""
    keywords = await org_keyword_profile(session, auth.org.id)
    if not keywords:
        raise HTTPException(
            422, "ارفع ملفًا واحدًا على الأقل عن نشاط شركتك قبل تشغيل المطابقة.")

    # sanitize into a to_tsquery OR-expression on the simple config
    safe = [k.replace("'", "") for k in keywords if k.isalnum() or not set("&|!()") & set(k)]
    ts_query = " | ".join(safe[:15])
    rows = (await session.execute(
        select(
            Tender.id, Tender.reference_number, Tender.title,
            Agency.name_ar, Tender.deadline, Tender.win_amount_halalas,
            Tender.lifecycle_snapshot, Tender.details_url,
            func.ts_rank(Tender.search_vector,
                         func.to_tsquery("simple", ts_query)).label("rank"),
        )
        .outerjoin(Agency, Agency.id == Tender.agency_id)
        .where(Tender.search_vector.op("@@")(func.to_tsquery("simple", ts_query)))
        .order_by(text("rank DESC"), Tender.deadline.desc().nullslast())
        .limit(min(limit, 50))
    )).all()
    return {
        "profile_keywords": keywords,
        "matches": [
            {
                "tender_id": str(r[0]), "reference_number": r[1], "title": r[2],
                "agency": r[3],
                "deadline": r[4].isoformat() if r[4] else None,
                "award_sar": round(r[5] / 100, 2) if r[5] is not None else None,
                "lifecycle": r[6], "details_url": r[7],
                "score": round(float(r[8]), 4),
            }
            for r in rows
        ],
    }
