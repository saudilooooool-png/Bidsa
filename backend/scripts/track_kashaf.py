"""Track the upstream Kashaf / etimad-plus-viewer data pipeline over time.

The public repo `badroneai/etimad-plus-viewer` only mirrors + publishes data that
a private "Kashaf" pipeline pushes into it (a github-actions bot commits
`data: publish run_<id>_1` every few hours). Its `data/manifest.json` exposes the
snapshot id, generation time, the official-periodic source time, and coverage
facets — everything we need to learn their cadence and compare their coverage to
our own live fetch.

This script (stdlib only — runs on a plain GitHub runner with no pip installs):
  1. fetches their manifest.json,
  2. appends a new row to db/reports/kashaf_tracker.jsonl IF the snapshot changed,
  3. regenerates db/reports/kashaf_tracker.md (latest state + observed cadence).

Run locally or via .github/workflows/track-kashaf.yml (scheduled).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_URL = (
    "https://raw.githubusercontent.com/badroneai/etimad-plus-viewer/main/data/manifest.json"
)
UA = "bidsa-kashaf-tracker/1.0 (+https://github.com/saudilooooool-png/Bidsa)"


def _fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https URL
        return json.loads(resp.read().decode("utf-8"))


def _summarize(manifest: dict, *, fetched_at: str) -> dict:
    src = manifest.get("source_times", {}) or {}
    facets = manifest.get("facets", {}) or {}
    comp = (manifest.get("completeness", {}) or {}).get("phase0Awarded", {}) or {}
    snap = manifest.get("snapshot_id", "")
    run_id = None
    if snap.startswith("run_"):
        digits = snap[4:].split("_", 1)[0]
        run_id = int(digits) if digits.isdigit() else None
    return {
        "fetched_at": fetched_at,
        "snapshot_id": snap,
        "run_id": run_id,
        "generated_at": manifest.get("generated_at"),
        "as_of": manifest.get("as_of"),
        "official_periodic": src.get("officialPeriodic"),
        "phase0_awarded": src.get("phase0Awarded"),
        "facets_grand": facets.get("grand"),
        "facets_active": facets.get("active"),
        "facets_soon": facets.get("soon"),
        "awarded_source_records": comp.get("sourceRecords"),
        "official_universe_complete": (
            manifest.get("completeness", {}) or {}).get("officialUniverseComplete"),
    }


def _load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _cadence_hours(rows: list[dict]) -> list[float]:
    """Hours between consecutive DISTINCT generated_at values (chronological)."""
    times = sorted(
        {r["generated_at"] for r in rows if r.get("generated_at")},
        key=lambda s: _parse_iso(s) or datetime.min.replace(tzinfo=timezone.utc),
    )
    deltas = []
    for a, b in zip(times, times[1:]):
        da, db = _parse_iso(a), _parse_iso(b)
        if da and db:
            deltas.append(round((db - da).total_seconds() / 3600, 2))
    return deltas


def _render_md(rows: list[dict]) -> str:
    latest = rows[-1] if rows else {}
    deltas = _cadence_hours(rows)
    distinct = sorted(
        {r["snapshot_id"] for r in rows if r.get("snapshot_id")})
    lines = [
        "# متتبّع Kashaf (badroneai/etimad-plus-viewer)",
        "",
        "يرصد لقطات خط أنابيب Kashaf: المعرّف، زمن التوليد، زمن المصدر الرسمي الدوري،",
        "وعدّادات التغطية — لقياس وتيرتهم ومقارنة تغطيتهم بجلبنا الحي.",
        "",
        "## الحالة الحالية",
        "",
        f"- **آخر فحص:** {latest.get('fetched_at', '—')}",
        f"- **snapshot_id:** `{latest.get('snapshot_id', '—')}`",
        f"- **generated_at:** {latest.get('generated_at', '—')}",
        f"- **آخر مصدر رسمي دوري:** {latest.get('official_periodic', '—')}",
        f"- **التغطية:** grand {latest.get('facets_grand', '—')} · "
        f"active {latest.get('facets_active', '—')} · soon {latest.get('facets_soon', '—')}",
        f"- **الترسيات التاريخية (baseline):** {latest.get('awarded_source_records', '—')} "
        f"(الكون الرسمي مكتمل؟ {latest.get('official_universe_complete', '—')})",
        f"- **عدد اللقطات المرصودة:** {len(distinct)}",
        "",
        "## الوتيرة المرصودة (ساعات بين كل توليد متمايز)",
        "",
    ]
    if deltas:
        lines += [
            f"- عيّنات: {len(deltas)}",
            f"- الأدنى / الوسيط / الأعلى: {min(deltas)}h / "
            f"{round(statistics.median(deltas), 2)}h / {max(deltas)}h",
            f"- المتوسط: {round(statistics.mean(deltas), 2)}h",
        ]
    else:
        lines.append("- لا تكفي النقاط بعد لحساب الوتيرة (نحتاج توليدين متمايزين على الأقل).")
    lines += ["", "## آخر اللقطات", "",
              "| fetched_at | snapshot_id | generated_at | official_periodic | active | soon |",
              "|---|---|---|---|---|---|"]
    for r in rows[-15:]:
        lines.append(
            f"| {r.get('fetched_at','—')} | `{r.get('snapshot_id','—')}` | "
            f"{r.get('generated_at','—')} | {r.get('official_periodic','—')} | "
            f"{r.get('facets_active','—')} | {r.get('facets_soon','—')} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="db/reports")
    ap.add_argument("--now", help="override fetched_at timestamp (ISO); default = current UTC")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "kashaf_tracker.jsonl"
    md = out_dir / "kashaf_tracker.md"

    fetched_at = args.now or datetime.now(timezone.utc).isoformat()
    try:
        manifest = _fetch(MANIFEST_URL)
    except Exception as exc:  # noqa: BLE001 - network/parse; report and exit non-fatally
        sys.stderr.write(f"fetch failed: {exc}\n")
        return 0  # don't fail the scheduled run on a transient network hiccup

    summary = _summarize(manifest, fetched_at=fetched_at)
    rows = _load_rows(jsonl)
    last_snap = rows[-1]["snapshot_id"] if rows else None

    if summary["snapshot_id"] and summary["snapshot_id"] != last_snap:
        rows.append(summary)
        with jsonl.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
        print(f"NEW snapshot recorded: {summary['snapshot_id']} "
              f"(generated_at {summary['generated_at']})")
    else:
        print(f"No change (still {summary['snapshot_id']}).")

    md.write_text(_render_md(rows), encoding="utf-8")
    print(f"wrote {md} ({len(rows)} rows total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
