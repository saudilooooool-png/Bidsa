"""Text extraction, Arabic-aware tokenization, and chunking for the KB pipeline."""
from __future__ import annotations

import re
from collections import Counter
from io import BytesIO

# Minimal Arabic + English stopword set for keyword profiling.
STOPWORDS = {
    # Arabic function words
    "في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "التي",
    "الذي", "او", "أو", "ثم", "قد", "لا", "ما", "لم", "لن", "ان", "أن", "إن",
    "كل", "بعض", "غير", "بين", "بعد", "قبل", "حتى", "اذا", "إذا", "كما", "لدى",
    "عند", "منذ", "خلال", "حول", "دون", "ضمن", "وفق", "حسب", "نحن", "هو", "هي",
    "تم", "يتم", "وقد", "ومن", "وفي", "الخ", "الرقم", "رقم", "بشكل", "وذلك",
    # generic business words that match everything
    "شركة", "شركه", "مؤسسة", "مؤسسه", "المحدودة", "المحدوده", "خدمات", "أعمال",
    "اعمال", "مشروع", "مشاريع", "عامة", "عامه", "قسم", "ادارة", "إدارة", "العام",
    "السعودية", "السعوديه", "المملكة", "المملكه", "الرياض",
    # English
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "our",
    "company", "ltd", "llc", "co", "of", "in", "to", "we", "a", "an", "on",
}

_DIACRITICS = re.compile(r"[ً-ٰٟـ]")
_TOKEN = re.compile(r"[\wء-ي]{3,}")


def normalize_ar(text: str) -> str:
    text = _DIACRITICS.sub("", text)
    return (text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                .replace("ة", "ه").replace("ى", "ي"))


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalize_ar(text.lower()))
            if t not in STOPWORDS and not t.isdigit()]


def top_keywords(text: str, k: int = 15) -> list[str]:
    counts = Counter(tokenize(text))
    return [w for w, _ in counts.most_common(k)]


def chunk_text(text: str, target: int = 1500) -> list[str]:
    """Split on paragraph boundaries into ~target-char chunks."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if buf and len(buf) + len(p) > target:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
        # hard-split pathological paragraphs
        while len(buf) > 2 * target:
            chunks.append(buf[:target].strip())
            buf = buf[target:]
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from .txt/.md/.pdf uploads. Raises ValueError otherwise."""
    lower = filename.lower()
    if lower.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise ValueError("PDF support requires the pypdf package") from exc
        reader = PdfReader(BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n\n".join(pages).strip()
        if not text:
            raise ValueError(
                "تعذر استخراج نص من هذا الـPDF (يبدو ممسوحًا ضوئيًا). "
                "ارفع نسخة نصية أو ملف txt.")
        return text
    raise ValueError("صيغة غير مدعومة — المسموح: .txt / .md / .pdf")
