"""Tender-alert email digests.

For each org with saved searches, find new open tenders matching each search
since it was last notified, and email the org's members a single Arabic digest.
Skipped silently when SMTP is not configured (SMTP_HOST empty).
"""
from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.saas import Organization, SavedSearch, User
from app.services.feed import matches_for_search

logger = get_logger(__name__)
settings = get_settings()


def _sar_compact(halalas: int | None) -> str:
    if halalas is None:
        return "غير معلن"
    v = halalas / 100
    if v >= 1e6:
        return f"{v/1e6:.1f} مليون ريال"
    if v >= 1e3:
        return f"{v/1e3:.0f} ألف ريال"
    return f"{v:.0f} ريال"


def render_digest(company: str, blocks: list[tuple[str, list[dict]]]) -> str:
    base = settings.PUBLIC_APP_URL.rstrip("/")
    parts = [
        "<div dir='rtl' style='font-family:system-ui,Segoe UI,sans-serif;color:#0b0b0b'>",
        f"<h2>منافسات جديدة تطابق تنبيهاتك — {company}</h2>",
    ]
    for name, matches in blocks:
        parts.append(f"<h3 style='margin-top:20px'>🔔 {name} — {len(matches)} منافسة جديدة</h3>")
        parts.append("<ul style='padding-inline-start:18px'>")
        for m in matches:
            days = f" · تبقّى {m['days_left']} يومًا" if m.get("days_left") is not None else ""
            agency = f" — {m['agency']}" if m.get("agency") else ""
            url = m.get("details_url") or f"{base}/tenders"
            parts.append(
                f"<li style='margin-bottom:8px'>"
                f"<a href='{url}' style='color:#2a78d6;text-decoration:none'>{m['title']}</a>"
                f"{agency}<br><span style='color:#52514e;font-size:13px'>"
                f"{m.get('activity') or ''}{days}</span></li>"
            )
        parts.append("</ul>")
    parts.append(
        f"<p style='margin-top:24px'><a href='{base}/tenders' "
        f"style='background:#2a78d6;color:#fff;padding:8px 16px;border-radius:6px;"
        f"text-decoration:none'>تصفّح كل المنافسات المفتوحة</a></p>")
    parts.append("<hr style='border:none;border-top:1px solid #e1e0d9;margin-top:24px'>")
    parts.append("<p style='color:#898781;font-size:12px'>بيدسا — استخبارات المشتريات الحكومية.</p>")
    parts.append("</div>")
    return "".join(parts)


def _send(to_addrs: list[str], subject: str, html: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(to_addrs)
    msg.set_content("منافسات جديدة تطابق تنبيهاتك — افتح البريد بصيغة HTML لعرضها.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def run_digests(session: AsyncSession) -> dict:
    """Build and send one digest per org with matching new tenders."""
    if not settings.SMTP_HOST:
        logger.info("digest_skipped_no_smtp")
        return {"orgs_notified": 0, "emails_sent": 0, "reason": "smtp_not_configured"}

    now = datetime.now(timezone.utc)
    searches = (await session.execute(
        select(SavedSearch).where(SavedSearch.notify_email.is_(True))
    )).scalars().all()

    by_org: dict = {}
    for s in searches:
        matches = await matches_for_search(
            session, keywords=s.keywords, activity_id=s.activity_id,
            region_id=s.region_id, since=s.last_notified_at)
        if matches:
            by_org.setdefault(s.organization_id, []).append((s.name, matches))
        s.last_notified_at = now

    orgs_notified = emails_sent = 0
    for org_id, blocks in by_org.items():
        org = (await session.execute(
            select(Organization).where(Organization.id == org_id))).scalar_one()
        recipients = (await session.execute(
            select(User.email).where(User.organization_id == org_id, User.is_active.is_(True))
        )).scalars().all()
        if not recipients:
            continue
        html = render_digest(org.name, blocks)
        total = sum(len(m) for _, m in blocks)
        try:
            _send(list(recipients), f"بيدسا · {total} منافسة جديدة تطابق تنبيهاتك", html)
            orgs_notified += 1
            emails_sent += len(recipients)
        except Exception as exc:  # noqa: BLE001 - one org's SMTP failure mustn't stop the rest
            logger.error("digest_send_failed", org=str(org_id), error=str(exc))

    await session.commit()
    logger.info("digest_run_done", orgs_notified=orgs_notified, emails_sent=emails_sent)
    return {"orgs_notified": orgs_notified, "emails_sent": emails_sent}
