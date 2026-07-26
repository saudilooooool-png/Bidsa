"""AI enrichment ("Analyst" agent) — fills the schema's AI output columns.

Produces ai_summary, mandatory_requirements, local_content_requirements and
risk_flags for a tender using an LLM. Degrades gracefully (no-op) when no
OpenAI key is configured, so the pipeline never hard-fails on missing AI.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.tender import Tender

logger = get_logger(__name__)
settings = get_settings()

_PROMPT = """أنت محلل مناقصات حكومية. حلّل المنافسة التالية وأعد JSON فقط بالشكل:
{{
  "summary": "ملخص تنفيذي موجز بالعربية",
  "mandatory_requirements": ["متطلب 1", "متطلب 2"],
  "local_content_requirements": ["التزام المحتوى المحلي إن وجد"],
  "risk_flags": [{{"code": "short_deadline", "severity": "high", "note": "..."}}]
}}

المنافسة:
العنوان: {title}
الجهة: {agency}
النشاط: {activity}
النوع: {ttype}
الوصف: {description}
"""


class TenderEnricher:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def enrich(self, tender: Tender) -> bool:
        if not self.enabled:
            return False
        prompt = _PROMPT.format(
            title=tender.title,
            agency=tender.agency_id or "غير محدد",
            activity=tender.activity_id or "غير محدد",
            ttype=tender.type_id or "غير محدد",
            description=(tender.description or "")[:1500],
        )
        try:
            resp = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=700,
            )
            data = json.loads(resp.choices[0].message.content)
        except Exception as exc:  # noqa: BLE001
            logger.error("enrich_failed", ref=tender.reference_number, error=str(exc))
            return False

        tender.ai_summary = data.get("summary")
        tender.mandatory_requirements = data.get("mandatory_requirements")
        tender.local_content_requirements = data.get("local_content_requirements")
        tender.risk_flags = data.get("risk_flags")
        tender.ai_model = settings.OPENAI_MODEL
        tender.ai_processed_at = datetime.now(timezone.utc)
        return True
