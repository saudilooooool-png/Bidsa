"""RFP draft builder.

Generates a structured Arabic proposal skeleton from the tender's warehouse
record plus the most relevant snippets of the organization's knowledge base.
Deterministic template by default; polished by the LLM when OPENAI_API_KEY is
configured. Drafts are stored in bid_proposals (org-scoped).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_subscription
from app.core.config import get_settings
from app.core.plans import entitlements
from app.db.session import get_session
from app.models.lookup import Activity, Agency, Region
from app.models.saas import BidProposal, KnowledgeChunk
from app.models.tender import Tender
from app.services.textproc import tokenize

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])
settings = get_settings()


async def _relevant_chunks(session: AsyncSession, org_id, tender_text: str, k: int = 4) -> list[str]:
    """Score org chunks by token overlap with the tender text (no AI needed)."""
    tender_tokens = set(tokenize(tender_text))
    if not tender_tokens:
        return []
    rows = (await session.execute(
        select(KnowledgeChunk.content)
        .where(KnowledgeChunk.organization_id == org_id).limit(400)
    )).scalars().all()
    scored = sorted(
        ((len(tender_tokens & set(tokenize(c))), c) for c in rows),
        key=lambda x: x[0], reverse=True,
    )
    return [c for score, c in scored[:k] if score > 0]


def _template(company: str, tender: dict, snippets: list[str]) -> str:
    experience = "\n\n".join(f"— {s[:600]}" for s in snippets) if snippets else \
        "(أضف سابقة الأعمال ذات الصلة هنا — لم تُرفع مستندات مطابقة بعد)"
    award = f"{tender['award_sar']:,.0f} ريال" if tender.get("award_sar") else "غير معلن"
    return f"""# عرض فني مبدئي — {tender['title']}

**مقدم من:** {company}
**المنافسة:** {tender['reference_number']} — {tender['agency'] or 'الجهة الحكومية'}
**النشاط:** {tender['activity'] or '—'} · **المنطقة:** {tender['region'] or '—'}
**مرجع القيمة (ترسيات مشابهة):** {award}

## 1. فهم نطاق العمل
تدرك {company} أن هذه المنافسة تستهدف: {tender['title']}. وسنلتزم بتحقيق
متطلبات كراسة الشروط كاملة مع الجودة والجدولة المطلوبتين.
(راجع هذا القسم بعد قراءة كراسة الشروط وأضف تفاصيل النطاق.)

## 2. المنهجية المقترحة
1. مرحلة التخطيط والتعبئة — حصر المتطلبات وتشكيل فريق العمل.
2. مرحلة التنفيذ — وفق خطة زمنية تفصيلية تُرفق بالعرض النهائي.
3. مرحلة الضبط والجودة — مؤشرات أداء ومراجعات دورية مع الجهة.
4. مرحلة التسليم والإغلاق — توثيق كامل ونقل معرفة.

## 3. خبرات {company} ذات الصلة
{experience}

## 4. الفريق المقترح
(أدرج هيكل الفريق: مدير المشروع، الكوادر الفنية، نسب الإشغال.)

## 5. الجدول الزمني المبدئي
(قسّم مدة العقد إلى مراحل بموجب متطلبات الكراسة.)

## 6. الالتزام بالمحتوى المحلي
تلتزم {company} بمتطلبات المحتوى المحلي وقوائم الإلزام حيثما وردت في الكراسة.

---
*مسودة أولية أنشأتها منصة بيدسا اعتمادًا على بيانات المنافسة ومستندات الشركة —
راجعها وأكملها قبل التقديم.*"""


class GenerateIn(BaseModel):
    tender_id: uuid.UUID


@router.post("/generate", status_code=201)
async def generate(
    body: GenerateIn,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    plan = entitlements(auth.org.plan)
    if plan.proposals_per_month is not None:
        now = datetime.now(timezone.utc)
        used = (await session.execute(
            select(func.count(BidProposal.id)).where(
                BidProposal.organization_id == auth.org.id,
                extract("year", BidProposal.created_at) == now.year,
                extract("month", BidProposal.created_at) == now.month,
            )
        )).scalar_one()
        if used >= plan.proposals_per_month:
            raise HTTPException(
                402, f"استهلكت حصة المسودات الشهرية ({plan.proposals_per_month}). رقِّ الخطة للمزيد.")

    row = (await session.execute(
        select(Tender, Agency.name_ar, Activity.name_ar, Region.name_ar)
        .outerjoin(Agency, Agency.id == Tender.agency_id)
        .outerjoin(Activity, Activity.id == Tender.activity_id)
        .outerjoin(Region, Region.id == Tender.region_id)
        .where(Tender.id == body.tender_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "tender not found")
    tender, agency, activity, region = row
    tender_info = {
        "reference_number": tender.reference_number, "title": tender.title,
        "agency": agency, "activity": activity, "region": region,
        "award_sar": tender.win_amount_halalas / 100 if tender.win_amount_halalas else None,
    }

    snippets = await _relevant_chunks(
        session, auth.org.id, f"{tender.title} {activity or ''}")
    content = _template(auth.org.name, tender_info, snippets)
    model_used = "template_v1"

    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content":
                           "حسّن مسودة العرض الفني التالية بالعربية الفصحى المهنية، "
                           "مع الإبقاء على البنية والعناوين كما هي:\n\n" + content}],
                temperature=0.2, max_tokens=2500,
            )
            content = resp.choices[0].message.content or content
            model_used = settings.OPENAI_MODEL
        except Exception:  # noqa: BLE001 — LLM polish is best-effort
            pass

    proposal = BidProposal(
        organization_id=auth.org.id, tender_id=tender.id,
        created_by=auth.user.id, status="draft",
        proposal_content=content, ai_model=model_used,
    )
    # one draft per (org, tender): replace an existing one
    existing = (await session.execute(
        select(BidProposal).where(
            BidProposal.organization_id == auth.org.id,
            BidProposal.tender_id == tender.id)
    )).scalar_one_or_none()
    if existing:
        existing.proposal_content = content
        existing.ai_model = model_used
        existing.status = "draft"
        proposal = existing
    else:
        session.add(proposal)
    await session.commit()
    return {"id": str(proposal.id), "tender_title": tender.title, "model": model_used}


@router.get("")
async def list_proposals(
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(BidProposal, Tender.title, Tender.reference_number)
        .join(Tender, Tender.id == BidProposal.tender_id)
        .where(BidProposal.organization_id == auth.org.id)
        .order_by(BidProposal.created_at.desc())
    )).all()
    return [
        {"id": str(p.id), "status": p.status, "tender_title": t,
         "reference_number": ref, "model": p.ai_model,
         "created_at": p.created_at.isoformat()}
        for p, t, ref in rows
    ]


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: uuid.UUID,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    row = (await session.execute(
        select(BidProposal, Tender.title, Tender.reference_number)
        .join(Tender, Tender.id == BidProposal.tender_id)
        .where(BidProposal.id == proposal_id,
               BidProposal.organization_id == auth.org.id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "proposal not found")
    p, title, ref = row
    return {"id": str(p.id), "status": p.status, "tender_title": title,
            "reference_number": ref, "model": p.ai_model,
            "content": p.proposal_content, "created_at": p.created_at.isoformat()}
