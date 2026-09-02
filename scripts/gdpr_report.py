"""eLabFTW GDPR Art. 15 report generator - HTML explorer + PDF + ZIP.

Turns one per-user raw export folder under ``output/`` into a
human-readable disclosure package in the same folder:

  output/UserX/index.html                    HTML explorer
  output/UserX/Disclosure_UserX.pdf          Art. 15 disclosure letter
  output/UserX/gdpr_disclosure_UserX.zip     complete package

Usage:
  gdpr_report.py [--out-dir DIR] [--user 75]
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Allow running this file directly (python scripts/gdpr_report.py) while the
# package imports (scripts.i18n) still resolve. Harmless when imported as a
# module - the root is already on sys.path then.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

from scripts.i18n import (LOCALE_TO_LANG, needs_ttf_font, normalize_lang, t, tt)

OUTPUT_DIR = PROJECT_ROOT / "output"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
THUMBNAIL_MAX = 400

# Report language, set per run (default "en"). Filled by main()/build_reports.
REPORT_LANG = "en"
# TTF fallback font for scripts outside cp1252 (PL/CZ/...). Resolved lazily.
_TTF_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    # Linux (reportlab recommends DejaVu; common on debian/ubuntu)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_BASE_FONT = "Helvetica"
_BASE_FONT_BOLD = "Helvetica-Bold"


def _resolve_fonts(lang: str) -> None:
    """Register a TTF pair when the language needs non-cp1252 glyphs.

    Falls back to Helvetica (WinAnsi) for en/de/fr/es/it/pt/nl and whenever
    no TTF is found, so the report still builds everywhere.
    """
    global _BASE_FONT, _BASE_FONT_BOLD
    if not needs_ttf_font(lang):
        return
    import os
    regular = bold = None
    for cand in _TTF_CANDIDATES:
        if os.path.exists(cand):
            if "Bold" in cand or "bold" in cand:
                bold = bold or cand
            else:
                regular = regular or cand
    if regular and bold:
        try:
            pdfmetrics.registerFont(TTFont("GDPRReport", regular))
            pdfmetrics.registerFont(TTFont("GDPRReport-Bold", bold))
            _BASE_FONT = "GDPRReport"
            _BASE_FONT_BOLD = "GDPRReport-Bold"
        except Exception:
            _BASE_FONT = "Helvetica"
            _BASE_FONT_BOLD = "Helvetica-Bold"
    else:
        # only one of the pair found: keep Helvetica rather than a broken mix
        _BASE_FONT = "Helvetica"
        _BASE_FONT_BOLD = "Helvetica-Bold"


def redact_names(text: str, names: list[str]) -> str:
    """Replace other users' names/emails with '[redacted]' (third parties only).

    Local fallback - gdpr_db_full.py has the same helper; both stay in sync.
    """
    if not text:
        return text
    for nm in names:
        nm = (nm or "").strip()
        if len(nm) < 3:
            continue
        text = text.replace(nm, "[redacted]")
    return text

CSS = """
body { font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f5f6f8; color: #1a1d21; }
.wrap { max-width: 1000px; margin: 0 auto; padding: 24px; }
header { background: #16324f; color: #fff; padding: 20px 24px; border-radius: 8px; margin-bottom: 20px; }
header h1 { margin: 0 0 6px; font-size: 22px; }
header p { margin: 2px 0; color: #c8d4e0; font-size: 14px; }
h2 { font-size: 18px; margin: 28px 0 10px; border-bottom: 2px solid #d8dde3; padding-bottom: 4px; }
table { border-collapse: collapse; width: 100%; background: #fff; font-size: 14px; }
th, td { border: 1px solid #d8dde3; padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: #eef1f5; }
.cards { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
.card { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 10px 16px; min-width: 140px; }
.card b { font-size: 22px; display: block; }
.entry { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }
.entry a { color: #16324f; font-weight: 600; text-decoration: none; }
.meta { color: #5a6570; font-size: 13px; }
.body { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px 18px; white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
details { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; margin: 6px 0; padding: 8px 14px; }
summary { cursor: pointer; font-weight: 600; }
.gallery { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.gallery a { border: 1px solid #d8dde3; border-radius: 6px; overflow: hidden; background: #fff; }
.gallery img { display: block; max-width: 180px; max-height: 140px; }
.file { display: inline-block; background: #eef1f5; border-radius: 6px; padding: 6px 10px; margin: 4px; font-size: 13px; }
.notice { background: #fff7e0; border: 1px solid #e5cf8a; border-radius: 8px; padding: 12px 16px; margin: 12px 0; font-size: 14px; }
.notice-error { background: #fdecea; border-color: #e5b4ad; color: #8b2e24; }
.back { display: inline-block; margin-bottom: 12px; color: #16324f; }
td.klein { font-size: 13px; color: #5a6570; }
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def escape(value) -> str:
    """HTML-escape arbitrary values (also for None)."""
    return html.escape(str(value if value is not None else ""), quote=True)


def _date_fmt(lang: str) -> str:
    """Date format for a report language (used by format_ts)."""
    return {
        "de": "%d.%m.%Y %H:%M",
        "fr": "%d/%m/%Y %H:%M",
        "es": "%d/%m/%Y %H:%M",
        "it": "%d/%m/%Y %H:%M",
        "pt": "%d/%m/%Y %H:%M",
        "nl": "%d-%m-%Y %H:%M",
        "pl": "%d.%m.%Y %H:%M",
    }.get(lang, "%Y-%m-%d %H:%M")


def format_ts(value, lang: str | None = None) -> str:
    """Render a timestamp in the report language's date format.

    The raw value is a string from the API/DB (e.g. ``2026-08-20 09:30:00``
    or ISO). We reformat only when it parses cleanly; otherwise the original
    string is returned unchanged (never mangled).
    """
    if not value:
        return "-"
    text = str(value)
    candidate = text.replace("T", " ")[:16]
    for src_fmt, dst_fmt in (
        ("%Y-%m-%d %H:%M", _date_fmt(lang or REPORT_LANG)),
        ("%Y-%m-%d", "%d.%m.%Y" if (lang or REPORT_LANG) == "de" else "%Y-%m-%d"),
    ):
        try:
            from datetime import datetime
            parsed = datetime.strptime(candidate, src_fmt)
            return parsed.strftime(dst_fmt)
        except ValueError:
            continue
    return text[:16]


def read_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def sanitize_filename(name: str) -> str:
    """Filesystem-safe file name (keeps letters, digits, . _ - space)."""
    keep = "".join(c for c in name if c.isalnum() or c in "._- ")
    return keep.strip() or "file"


def upload_filename(upload: dict) -> str:
    """Export file name: uid-OriginalName (real_name preferred over long_name)."""
    name = upload.get("real_name") or upload.get("long_name") or f"upload-{upload.get('id')}"
    return f"{upload.get('id')}-{sanitize_filename(name)}"


def pretty_notification_body(raw) -> str:
    """Render a notification body (JSON string/dict) as readable text."""
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
    elif isinstance(raw, list):
        return ", ".join(pretty_notification_body(x) for x in raw) or "-"
    else:
        return str(raw) if raw else "-"
    parts = []
    if data.get("msg"):
        parts.append(str(data["msg"]))
    if data.get("actor"):
        parts.append(f"Actor: {data['actor']}")
    event = data.get("event")
    if isinstance(event, dict):
        title = event.get("experiment_title") or event.get("item_title") or event.get("title")
        if title:
            parts.append(f"Event: {title}")
        elif event.get("id"):
            parts.append(f"Event ID: {event['id']}")
        if event.get("start"):
            parts.append(f"{event['start']} - {event.get('end', '')}")
    if data.get("step_id"):
        parts.append(f"Step {data['step_id']} (deadline {data.get('deadline', '-')})")
    if data.get("team"):
        parts.append(f"Team: {data['team']}")
    if data.get("userid"):
        parts.append(f"User: {data['userid']}")
    return " · ".join(parts) or "-"


def user_in_group(group, userid) -> bool:
    members = group.get("users") if isinstance(group, dict) else None
    if not isinstance(members, list):
        return True  # no member list -> cannot verify, keep
    return any(str(m.get("userid")) == str(userid) for m in members)


def group_members(group) -> str:
    members = group.get("users") if isinstance(group, dict) else None
    if not isinstance(members, list):
        return "-"
    return ", ".join(str(m.get("fullname", m.get("userid"))) for m in members)


def resolve_status_category(entity: dict, entity_type: str, lookups: dict | None) -> tuple:
    """Map status/category IDs to their display names via team lookups."""
    if not lookups:
        return None, None
    team_lookups = lookups.get(str(entity.get("team"))) or {}
    if entity_type == "experiments":
        return (team_lookups.get("experiments_status", {}).get(str(entity.get("status"))),
                team_lookups.get("experiments_categories", {}).get(str(entity.get("category"))))
    if entity_type == "items":
        return (team_lookups.get("items_status", {}).get(str(entity.get("status"))),
                team_lookups.get("items_types", {}).get(str(entity.get("category"))))
    if entity_type == "items_types":
        return (None, team_lookups.get("items_categories", {}).get(str(entity.get("category"))))
    return None, None


def entity_metadata(entity: dict, entity_type: str, lookups: dict | None = None) -> list:
    """Human-readable key/value metadata rows for an entity."""
    status_name, category_name = resolve_status_category(entity, entity_type, lookups)
    status = entity.get("status") or entity.get("state") or "-"
    if status_name:
        status = f"{status} ({status_name})"
    category = entity.get("category") or "-"
    if category_name:
        category = f"{category} ({category_name})"
    return [
        (t(REPORT_LANG, "meta_id_elabid"),
         f"{entity.get('id')} / {entity.get('elabid', '-')}"),
        (t(REPORT_LANG, "meta_created"), format_ts(entity.get("created_at"))),
        (t(REPORT_LANG, "meta_modified"), format_ts(entity.get("modified_at"))),
        (t(REPORT_LANG, "meta_last_changed_by"), entity.get("lastchangeby") or "-"),
        (t(REPORT_LANG, "meta_status"), status),
        (t(REPORT_LANG, "meta_category"), category),
        (t(REPORT_LANG, "meta_locked"),
         t(REPORT_LANG, "meta_locked_by_since",
           who=entity.get("lockedby") or "-",
           when=format_ts(entity.get("locked_at")))
         if entity.get("locked") else t(REPORT_LANG, "no")),
        (t(REPORT_LANG, "meta_timestamped"),
         format_ts(entity.get("timestamped_at")) if entity.get("timestamped")
         else t(REPORT_LANG, "no")),
        (t(REPORT_LANG, "meta_custom_id"), entity.get("custom_id") or "-"),
        (t(REPORT_LANG, "meta_rating"), entity.get("rating") or "-"),
    ]


def make_thumbnail(source: Path, target: Path) -> None:
    try:
        image = Image.open(source)
        image.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX))
        image.convert("RGB").save(target, "JPEG", quality=82)
    except Exception:
        shutil.copy(source, target)


class _AcroFormField(Flowable):
    """A labelled AcroForm text field usable inside a Platypus story.

    Renders a bold label line, then an interactive single-line text field
    (AcroForm) that the operator can click and type into in any PDF reader.
    Uses ``relative=True`` so coordinates are taken from the flowable's own
    position (ReportLab >= 3.6; works on 4.x and 5.x).
    """

    def __init__(self, label: str, field_name: str,
                 label_width: float = 68 * mm,
                 width: float = 130 * mm,
                 height: float = 5.6 * mm,
                 font_size: int = 9):
        super().__init__()
        self.label = label
        self.field_name = field_name
        self.label_width = label_width
        self.width = width
        self.height = height
        self.font_size = font_size

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # bold label on the left
        c.saveState()
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(0, self.height - 3, self.label)
        c.restoreState()
        # interactive AcroForm field on the right (relative to this flowable)
        c.acroForm.textfield(
            name=self.field_name,
            x=self.label_width,
            y=0,
            width=self.width - self.label_width,
            height=self.height - 0.5 * mm,
            borderWidth=0.4,
            borderColor=colors.HexColor("#666666"),
            fillColor=colors.HexColor("#fbfbfb"),
            fontName="Helvetica",
            fontSize=self.font_size,
            forceBorder=True,
            relative=True,
        )


# ---------------------------------------------------------------------------
# HTML explorer
# ---------------------------------------------------------------------------

def build_entity_page(out_dir: Path, report_dir: Path, assets_dir: Path,
                      entity_type: str, entity: dict, lookups: dict | None) -> Path:
    eid = entity["id"]
    entity_dir = out_dir / entity_type / str(eid)
    files_dir = out_dir / "files" / f"{entity_type}-{eid}"
    page = report_dir / "entries" / f"{entity_type}-{eid}.html"
    page.parent.mkdir(parents=True, exist_ok=True)

    comments = read_json(entity_dir / "comments.json") or []
    revisions = read_json(entity_dir / "revisions.json") or []
    steps = read_json(entity_dir / "steps.json") or []
    tags = read_json(entity_dir / "tags.json") or []
    uploads = read_json(entity_dir / "uploads.json") or []
    request_actions = read_json(entity_dir / "request_actions.json") or []
    lang = REPORT_LANG

    meta_rows = "".join(
        f"<tr><td class='klein'>{escape(k)}</td><td>{escape(v)}</td></tr>"
        for k, v in entity_metadata(entity, entity_type, lookups)
    )
    tags_html = "".join(f"<span class='file'>{escape(t.get('tag', t))}</span>" for t in tags)

    step_rows = ""
    for step in steps:
        done = "✔" if step.get("finished") else "☐"
        deadline = (f"<br><span class='meta'>{tt(lang, 'deadline')}: {format_ts(step.get('deadline'))}</span>"
                    if step.get("deadline") else "")
        step_rows += f"<tr><td>{done}</td><td>{escape(step.get('body'))}{deadline}</td></tr>"

    comments_html = ""
    for comment in comments:
        comments_html += (
            f"<div class='entry'><b>{escape(comment.get('fullname', comment.get('userid')))}</b> "
            f"<span class='meta'>{format_ts(comment.get('created_at'))}</span>"
            f"<p style='margin:6px 0 0'>{escape(comment.get('comment'))}</p></div>"
        )

    revisions_html = ""
    for revision in revisions:
        revisions_html += (
            f"<details><summary>{tt(lang, 'revision_from')} {format_ts(revision.get('created_at'))} "
            f"- {escape(revision.get('userid'))}</summary>"
            f"<div class='body'>{escape(revision.get('body'))}</div></details>"
        )

    gallery = []
    file_links = []
    for upload in uploads:
        uid = upload["id"]
        fname = upload_filename(upload)
        fpath = files_dir / fname if files_dir.exists() else None
        if fpath and fpath.exists() and fpath.suffix.lower() in IMAGE_EXTENSIONS:
            thumb = assets_dir / f"{entity_type}-{eid}-{uid}.img"
            make_thumbnail(fpath, thumb)
            gallery.append(
                f"<a href='../assets/{entity_type}-{eid}-{uid}.img' target='_blank'>"
                f"<img src='../assets/{entity_type}-{eid}-{uid}.img' "
                f"alt='{escape(upload.get('real_name', fname))}'></a>"
            )
        file_links.append(
            f"<span class='file'><a href='../files/{entity_type}-{eid}/{escape(fname)}' "
            f"download>{escape(upload.get('real_name', fname))}</a> "
            f"<span class='meta'>({upload.get('filesize', '?')} B, "
            f"{format_ts(upload.get('created_at'))})</span></span>"
        )
    gallery_html = f"<div class='gallery'>{''.join(gallery)}</div>" if gallery else ""
    files_html = (f"<div>{''.join(file_links)}</div>" if file_links
                  else "<p class='meta'>no uploads</p>")

    request_actions_html = "".join(
        f"<div class='entry'><b>{escape(r.get('action'))}</b> "
        f"<span class='meta'>{format_ts(r.get('created_at'))} - by "
        f"{escape(r.get('requester_userid'))}, state {escape(r.get('state'))}</span></div>"
        for r in request_actions
    )

    body = entity.get("body") or ""
    page.write_text(f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8">
<title>{escape(entity.get('title', tt(lang, 'no_title')))} - {entity_type} {eid}</title>
<style>{CSS}</style></head><body><div class="wrap">
<a class="back" href="../index.html">{tt(lang, 'back_to_overview')}</a>
<header><h1>{escape(entity.get('title', tt(lang, 'no_title')))}</h1>
<p>{entity_type} #{eid} · elabid {escape(entity.get('elabid', '-'))} · {t(REPORT_LANG, 'meta_modified').lower()} {format_ts(entity.get('modified_at'))}</p></header>
<h2>{tt(lang, 'metadata')}</h2><table>{meta_rows}</table>
<h2>{tt(lang, 'content')}</h2><div class="body">{escape(body)}</div>
<h2>{tt(lang, 'tags')}</h2><p>{tags_html or "<span class='meta'>-</span>"}</p>
<h2>{tt(lang, 'steps')}</h2><table><tr><th></th><th>{tt(lang, 'step')}</th></tr>{step_rows}</table>
<h2>{tt(lang, 'comments')} ({len(comments)})</h2>{comments_html or f"<p class='meta'>{tt(lang, 'none')}</p>"}
<h2>{tt(lang, 'revisions')} ({len(revisions)})</h2>{revisions_html or f"<p class='meta'>{tt(lang, 'none')}</p>"}
<h2>{tt(lang, 'uploads')} ({len(uploads)})</h2>{gallery_html}{files_html}
<h2>{tt(lang, 'request_actions')} ({len(request_actions)})</h2>{request_actions_html or f"<p class='meta'>{tt(lang, 'none')}</p>"}
</div></body></html>""")
    return page


def build_html_report(out_dir: Path, report_dir: Path) -> None:
    assets_dir = report_dir / "assets"
    files_source = out_dir / "files"
    files_dest = report_dir / "files"
    assets_dir.mkdir(parents=True, exist_ok=True)
    # raw export and report share one folder per user - files are already there
    if files_source.exists() and files_source.resolve() != files_dest.resolve():
        shutil.copytree(files_source, files_dest, dirs_exist_ok=True)

    manifest = read_json(out_dir / "manifest.json") or {}
    lookups = manifest.get("lookups")
    user = manifest.get("user") or {}
    teams = manifest.get("teams") or user.get("teams") or []
    notifications = manifest.get("notifications") or []
    groups = manifest.get("groups") or []
    procurement = manifest.get("procurement") or []
    bookings = manifest.get("bookings") or []
    request_actions_user = manifest.get("request_actions_user") or []
    is_db = manifest.get("source") == "db"
    db_appendix = read_json(out_dir / "db_appendix.json") if is_db else None
    uploads_total = manifest.get("uploads_total",
                                 manifest.get("upload_files_downloaded", 0))
    uploads_active = manifest.get("uploads_active")
    uploads_archived = manifest.get("uploads_archived")

    # In DB mode the top-level sections (notifications, groups, procurement,
    # bookings, request actions) live in db_appendix.json - the manifest only
    # has counts. Fill them so the summary cards/tables are not empty.
    if is_db and db_appendix:
        appx = db_appendix
        if not notifications and appx.get("notifications"):
            notifications = [dict(zip(("id", "created_at", "category", "is_ack",
                                       "body"), r)) for r in appx["notifications"]]
        if not groups and appx.get("team_groups"):
            groups = [{"id": r[0], "name": f"Group {r[0]}"} for r in appx["team_groups"]]
        if not procurement and appx.get("procurement"):
            procurement = [dict(zip(("id", "created_at", "entity_id", "qty_ordered",
                                     "qty_received", "state", "team"), r))
                           for r in appx["procurement"]]
        if not bookings and appx.get("bookings"):
            bookings = [dict(zip(("id", "title", "start", "end", "team",
                                  "experiment", "item", "created_at"), r))
                        for r in appx["bookings"]]
        if not request_actions_user and appx.get("request_actions"):
            request_actions_user = [
                dict(zip(("t", "action", "created_at", "state", "entity_id",
                          "requester_userid", "target_userid"), r))
                for r in appx["request_actions"]]

    # Entity pages + overview links
    entry_links = []
    counts = {}
    for entity_type in ("experiments", "items", "experiments_templates", "items_types"):
        ids = manifest.get("entities", {}).get(entity_type, [])
        counts[entity_type] = len(ids)
        for eid in ids:
            entity = read_json(out_dir / entity_type / str(eid) / "entity.json") or {"id": eid}
            build_entity_page(out_dir, report_dir, assets_dir, entity_type, entity, lookups)
            entry_links.append(
                f"<div class='entry'><a href='entries/{entity_type}-{eid}.html'>"
                f"{escape(entity.get('title', '(no title)'))}</a>"
                f"<div class='meta'>{entity_type} #{eid} · "
                f"{format_ts(entity.get('modified_at'))}</div></div>"
            )
    entry_links.sort(key=str.lower)

    uid = user.get("userid")
    lang = REPORT_LANG
    y, n = tt(lang, "yes"), tt(lang, "no")
    my_groups = [g for g in groups if user_in_group(g, uid)]
    team_rows = "".join(
        f"<tr><td>{escape(t.get('name'))}</td><td>{escape(t.get('id'))}</td>"
        f"<td>{y if t.get('is_admin') else n}</td><td>{y if t.get('is_owner') else n}</td>"
        f"<td>{y if t.get('is_archived') else n}</td></tr>" for t in teams
    )
    notification_rows = "".join(
        f"<tr><td>{format_ts(n.get('created_at'))}</td><td>{escape(n.get('category'))}</td>"
        f"<td>{escape(pretty_notification_body(n.get('body')))}</td>"
        f"<td>{y if n.get('is_ack') else n}</td></tr>" for n in notifications
    )
    group_rows = "".join(
        f"<tr><td>{escape(g.get('name') if isinstance(g, dict) else g)}</td>"
        f"<td>{escape(g.get('id', '-'))}</td><td>{escape(group_members(g))}</td></tr>"
        for g in my_groups
    )
    procurement_rows = "".join(
        f"<tr><td>{format_ts(p.get('created_at'))}</td>"
        f"<td>{escape(p.get('requester_fullname', p.get('requester_userid', '-')))}</td>"
        f"<td>{p.get('entity_id', '-')}</td><td>{p.get('qty_ordered', '-')}</td>"
        f"<td>{escape(p.get('state'))}</td></tr>" for p in procurement
    )
    booking_rows = "".join(
        f"<tr><td>{format_ts(b.get('start'))} - {format_ts(b.get('end'))}</td>"
        f"<td>{escape(b.get('title'))}</td>"
        f"<td>{escape(b.get('item_title', b.get('item')))}</td></tr>" for b in bookings
    )
    request_action_rows = "".join(
        f"<tr><td>{format_ts(r.get('created_at'))}</td><td>{escape(r.get('action'))}</td>"
        f"<td>{escape(r.get('state'))}</td><td>{escape(r.get('target_userid'))}</td></tr>"
        for r in request_actions_user
    )

    # cards (summary)
    cards = "".join(
        f"<div class='card'><b>{n}</b>{label}</div>"
        for label, n in [
            (tt(lang, "card_experiments"), counts["experiments"]),
            (tt(lang, "card_items"), counts["items"]),
            (tt(lang, "card_templates"), counts["experiments_templates"]),
            (tt(lang, "card_item_types"), counts["items_types"]),
            (tt(lang, "card_uploads"), uploads_total),
            (tt(lang, "card_notifications"), len(notifications)),
            (tt(lang, "card_bookings"), len(bookings)),
            (tt(lang, "card_groups"), len(my_groups)),
            (tt(lang, "card_procurement"), len(procurement)),
        ]
    )

    # DB appendix rows (pipeline B)
    appendix_sections = ""
    if db_appendix:
        lang = REPORT_LANG
        # appendix strings are static HTML (no user data) -> t(), not tt()
        def A(key: str, **fmt) -> str:
            return t(lang, key, **fmt)
        def _rows(name, cols):
            return "".join(
                "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row[:cols]) + "</tr>"
                for row in db_appendix.get(name, [])
            )
        # redacted variant: masks other users' IDs and flags comment columns
        def _redact_rows(name, cols, comment_idx):
            out = []
            me_uid = user.get("userid")
            for row in db_appendix.get(name, []):
                cells = list(row[:cols])
                # column 2 is the author userid -> mask it (third party)
                if len(cells) > 2:
                    try:
                        uid = int(cells[2])
                        if uid != me_uid:
                            cells[2] = f"[user {uid}]"
                    except (ValueError, TypeError):
                        cells[2] = "[unknown user]"
                out.append("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in cells) + "</tr>")
            return "".join(out)
        appendix_sections = f"""
<h2>{A('appendix_title')}</h2>
<p><b>{A('appendix_source_label')}</b>{A('appendix_source_text', active=uploads_active or '?', archived=uploads_archived or '?')}</p>
<h3>{A('appx_audit_trail')} ({len(db_appendix.get('audit_logs', []))})</h3>
<table><tr><th>{A('col_date')}</th><th>{A('col_category')}</th><th>{A('col_requester')}</th><th>{A('col_target')}</th><th>{A('col_body')}</th></tr>{_rows('audit_logs', 5)}</table>
<h3>{A('appx_failed_logins')} ({len(db_appendix.get('authfail', []))})</h3>
<table><tr><th>{A('col_attempt_time')}</th></tr>{_rows('authfail', 1)}</table>
<h3>{A('appx_changelog')} ({len(db_appendix.get('changelog', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_date')}</th><th>{A('col_target')}</th><th>{A('col_content')}</th></tr>{_rows('changelog', 4)}</table>
<h3>{A('appx_api_keys')} ({len(db_appendix.get('api_keys', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_name')}</th><th>{A('col_created')}</th><th>{A('col_last_used')}</th><th>{A('col_write')}</th></tr>{_rows('api_keys', 5)}</table>
<h3>{A('appx_exports')} ({len(db_appendix.get('exports', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_date')}</th><th>{A('col_state')}</th><th>{A('col_format')}</th></tr>{_rows('exports', 4)}</table>
<h3>{A('appx_todolist')} ({len(db_appendix.get('todolist', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_created')}</th><th>{A('col_body_full')}</th></tr>{_rows('todolist', 3)}</table>
<h3>{A('appx_sig_keys')} ({len(db_appendix.get('sig_keys', []))}) / {A('appx_favorites')} ({len(db_appendix.get('favtags', []))})</h3>
<table><tr><th>{A('col_sig_key_id')}</th><th>{A('col_created')}</th><th>{A('col_state')}</th></tr>{_rows('sig_keys', 3)}</table>
<h3>{A('appx_pins')} ({len(db_appendix.get('pins', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_entity_id')}</th></tr>{_rows('pins', 2)}</table>
<h3>{A('appx_team_groups')} ({len(db_appendix.get('team_groups', []))})</h3>
<table><tr><th>{A('col_group_id')}</th></tr>{_rows('team_groups', 1)}</table>
<h3>{A('appx_storage_history')} ({len(db_appendix.get('storage_history', []))})</h3>
<table><tr><th>{A('col_date')}</th><th>{A('col_storage_unit')}</th><th>{A('col_old_parent')}</th><th>{A('col_new_parent')}</th></tr>{_rows('storage_history', 4)}</table>
<h3>{A('appx_compounds')} ({len(db_appendix.get('compounds', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_name')}</th><th>{A('col_iupac')}</th><th>{A('col_cas')}</th><th>{A('col_created')}</th></tr>{_rows('compounds', 5)}</table>
<h3>{A('appx_request_actions')} ({len(db_appendix.get('request_actions', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_action')}</th><th>{A('col_date')}</th><th>{A('col_state')}</th><th>{A('col_entity')}</th></tr>{_rows('request_actions', 5)}</table>
<h3>{A('appx_procurement')} ({len(db_appendix.get('procurement', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_date')}</th><th>{A('col_entity')}</th><th>{A('col_qty')}</th><th>{A('col_state')}</th></tr>{_rows('procurement', 5)}</table>
<h3>{A('appx_notifications')} ({len(db_appendix.get('notifications', []))})</h3>
<table><tr><th>{A('col_id')}</th><th>{A('col_date')}</th><th>{A('col_category')}</th><th>{A('col_read')}</th><th>{A('col_body_full')}</th></tr>{_rows('notifications', 5)}</table>
<h3>{A('appx_entity_links')} ({len(db_appendix.get('links', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_item')}</th><th>{A('col_link')}</th></tr>{_rows('links', 3)}</table>
<h3>{A('appx_storage_assignments')} ({len(db_appendix.get('storage_assignments', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_item')}</th><th>{A('col_storage')}</th><th>{A('col_qty')}</th><th>{A('col_unit')}</th><th>{A('col_date')}</th></tr>{_rows('storage_assignments', 6)}</table>
<h3>{A('appx_compound_links')} ({len(db_appendix.get('compound_links', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_entity')}</th><th>{A('col_compound')}</th><th>{A('col_date')}</th></tr>{_rows('compound_links', 4)}</table>
<h3>{A('appx_template_steps')} ({len(db_appendix.get('template_steps', []))})</h3>
<table><tr><th>{A('col_type')}</th><th>{A('col_template')}</th><th>{A('col_step')}</th><th>{A('col_finished')}</th></tr>{_rows('template_steps', 4)}</table>
<h3>{A('appx_third_party_comments')} ({len(db_appendix.get('third_party_mentions', []))})</h3>
<p class="notice notice-error"><b>{A('redact_before_sending')}</b> {A('appx_redact_notice')}</p>
<table><tr><th>{A('col_type')}</th><th>{A('col_entity')}</th><th>{A('col_user')}</th><th>{A('col_date')}</th><th>{A('col_comment')}</th></tr>{_redact_rows('third_party_mentions', 5, 4)}</table>
<h3>{A('appx_your_comments')} ({len(db_appendix.get('comments_on_other_entries', []))})</h3>
<p>{A('appx_your_comments_notice')}</p>
<table><tr><th>{A('col_type')}</th><th>{A('col_entry')}</th><th>{A('col_user')}</th><th>{A('col_date')}</th><th>{A('col_comment')}</th></tr>{_redact_rows('comments_on_other_entries', 5, 4)}</table>
<h3>{A('appx_name_mentions')} ({len(db_appendix.get('name_mentions', []))})</h3>
<p class="notice notice-error"><b>{A('redact_before_sending')}</b> {A('appx_name_mentions_notice')}</p>
<table><tr><th>{A('col_type')}</th><th>{A('col_entry')}</th><th>{A('col_user')}</th><th>{A('col_date')}</th><th>{A('col_comment')}</th></tr>{_redact_rows('name_mentions', 5, 4)}</table>
"""

    # API-mode limitation banner (pipeline A stays transparent)
    limitation_note = ""
    if not is_db:
        limitation_note = (
            f"<div class=\"notice notice-error\"><b>{tt(lang, 'limitation_title')}</b> "
            f"{t(lang, 'limitation_body', uid=escape(user.get('userid', '')), archived=uploads_archived or 'n/a')}</div>"
        )

    (report_dir / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="{lang}"><head><meta charset="utf-8">
<title>{tt(lang, 'page_title', name=escape(user.get('fullname')))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>{tt(lang, 'doc_title', name=escape(user.get('fullname')))}</h1>
<p>{t(lang, 'subtitle_email_user', email=escape(user.get('email')), uid=escape(user.get('userid')), created=format_ts(user.get('created_at')))}</p>
<p>{t(lang, 'subtitle_last_login', last_login=format_ts(user.get('last_login')), exported=format_ts(manifest.get('exported_at')))}</p></header>

<div class="notice"><b>{tt(lang, 'notice_title')}</b> {t(lang, 'notice_body')}</div>

{limitation_note}

<h2>{tt(lang, 'overview')}</h2><div class="cards">{cards}</div>

<h2>{tt(lang, 'account_teams')}</h2>
<table><tr><th>{tt(lang, 'team')}</th><th>{tt(lang, 'id')}</th><th>{tt(lang, 'admin')}</th><th>{tt(lang, 'owner')}</th><th>{tt(lang, 'archived')}</th></tr>{team_rows}</table>

<h2>{tt(lang, 'notifications')} ({len(notifications)})</h2>
<table><tr><th>{tt(lang, 'date')}</th><th>{tt(lang, 'category')}</th><th>{tt(lang, 'content')}</th><th>{tt(lang, 'read')}</th></tr>{notification_rows}</table>

<h2>{tt(lang, 'groups')} ({len(my_groups)})</h2>
<table><tr><th>{tt(lang, 'group')}</th><th>{tt(lang, 'id')}</th><th>{tt(lang, 'members')}</th></tr>{group_rows}</table>

<h2>{tt(lang, 'procurement_requests')} ({len(procurement)})</h2>
<table><tr><th>{tt(lang, 'date')}</th><th>{tt(lang, 'requester')}</th><th>{tt(lang, 'entry')}</th><th>{tt(lang, 'quantity')}</th><th>{tt(lang, 'state')}</th></tr>{procurement_rows}</table>

<h2>{tt(lang, 'bookings')} ({len(bookings)})</h2>
<table><tr><th>{tt(lang, 'period')}</th><th>{tt(lang, 'title')}</th><th>{tt(lang, 'resource')}</th></tr>{booking_rows}</table>

<h2>{tt(lang, 'request_actions')} ({len(request_actions_user)})</h2>
<table><tr><th>{tt(lang, 'date')}</th><th>{tt(lang, 'action')}</th><th>{tt(lang, 'state')}</th><th>{tt(lang, 'target_user')}</th></tr>{request_action_rows}</table>

<h2>{tt(lang, 'entries')} ({sum(counts.values())})</h2>{''.join(entry_links)}

<h2>{tt(lang, 'db_cli_only')}</h2>
<ul>
<li>audit_logs, authfail, changelog (structured), api_keys, exports, todolist, unfinished_steps, favtags, pins, sig_keys, edit_mode, lockout_devices</li>
</ul>

{appendix_sections}
</div></body></html>""")


# ---------------------------------------------------------------------------
# PDF disclosure letter
# ---------------------------------------------------------------------------

def build_pdf_report(out_dir: Path, pdf_path: Path) -> None:
    manifest = read_json(out_dir / "manifest.json") or {}
    user = manifest.get("user") or {}
    teams = manifest.get("teams") or user.get("teams") or []
    entities = manifest.get("entities", {})
    counts = {et: len(ids) for et, ids in entities.items()}
    is_db = manifest.get("source") == "db"
    db_appendix = (read_json(out_dir / "db_appendix.json") or {}) if is_db else {}
    uploads_total = manifest.get("uploads_total",
                                 manifest.get("upload_files_downloaded", 0))
    uploads_archived = manifest.get("uploads_archived")
    subject_name = user.get("fullname") or \
        f"{user.get('firstname', '')} {user.get('lastname', '')}".strip() or \
        f"User {user.get('userid', '')}"

    _resolve_fonts(REPORT_LANG)
    lang = REPORT_LANG
    FONT = _BASE_FONT
    FONT_BOLD = _BASE_FONT_BOLD

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"GDPR disclosure {user.get('fullname')}")
    h1 = ParagraphStyle("h1", fontName=FONT_BOLD, fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=12, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", fontName=FONT, fontSize=8, leading=11,
                           textColor=colors.HexColor("#555555"))

    # Counts table rows (both pipelines)
    count_rows = [
        (t(lang, "pdf_count_experiments"), counts["experiments"]),
        (t(lang, "pdf_count_items"), counts["items"]),
        (t(lang, "pdf_count_templates"), counts["experiments_templates"]),
        (t(lang, "pdf_count_item_types"), counts["items_types"]),
        (t(lang, "pdf_count_upload_files"), uploads_total),
        (t(lang, "pdf_count_notifications"),
         len(db_appendix.get("notifications") or manifest.get("notifications") or [])),
        (t(lang, "pdf_count_bookings"),
         len(db_appendix.get("bookings") or manifest.get("bookings") or [])),
        (t(lang, "pdf_count_groups"),
         len(db_appendix.get("team_groups") or manifest.get("groups") or [])),
        (t(lang, "pdf_count_procurement"),
         len(db_appendix.get("procurement") or manifest.get("procurement") or [])),
    ]
    story = [
        Paragraph(t(lang, "pdf_title"), h1),
        Paragraph(
            f"<b>{escape(subject_name)}</b><br/>"
            f"{t(lang, 'pdf_recipient_line', email=escape(user.get('email')), uid=escape(user.get('userid')), created=format_ts(user.get('created_at')), last_login=format_ts(user.get('last_login')), exported=format_ts(manifest.get('exported_at')))}",
            body),
        # Controller identity (Art. 4(7) GDPR): interactive form fields the
        # operator fills in while reviewing the letter (click + type).
        Paragraph(t(lang, "pdf_controller_label"), body),
        Spacer(1, 2 * mm),
        _AcroFormField(t(lang, "pdf_controller_name"), "controller_name"),
        Spacer(1, 1.5 * mm),
        _AcroFormField(t(lang, "pdf_controller_address"), "controller_address"),
        Spacer(1, 1.5 * mm),
        _AcroFormField(t(lang, "pdf_controller_contact"), "controller_contact"),
        Spacer(1, 1.5 * mm),
        _AcroFormField(t(lang, "pdf_controller_dpo"), "controller_dpo"),
        Spacer(1, 3 * mm),
        Paragraph(t(lang, "pdf_s1"), h2),
        Paragraph(t(lang, "pdf_s1_body"), body),
        Paragraph(t(lang, "pdf_s2"), h2),
        Paragraph(t(lang, "pdf_s2_body"), body),
        Table([[k, str(v)] for k, v in count_rows],
              colWidths=[90 * mm, 60 * mm], style=TableStyle([
                  ("FONTNAME", (0, 0), (-1, -1), FONT),
                  ("FONTSIZE", (0, 0), (-1, -1), 9),
                  ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                  ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f5")),
                  ("TOPPADDING", (0, 0), (-1, -1), 3),
                  ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
              ])),
        Spacer(1, 6),
        Paragraph(
            t(lang, "pdf_teams_roles", teams=", ".join(
                t(lang, "pdf_team_item",
                  name=team.get("name"),
                  admin=t(lang, "yes") if team.get("is_admin") else t(lang, "no"),
                  owner=t(lang, "yes") if team.get("is_owner") else t(lang, "no"),
                  archived=t(lang, "yes") if team.get("is_archived") else t(lang, "no"))
                for team in teams)), small),
        Paragraph(t(lang, "pdf_s3"), h2),
        Paragraph(t(lang, "pdf_s3_body"), body),
        Paragraph(t(lang, "pdf_s4"), h2),
        Paragraph(
            t(lang, "pdf_s4_body",
              db_scope=(t(lang, "pdf_s4_db_scope") if is_db
                        else t(lang, "pdf_s4_api_scope")),
              archived_line=(
                  t(lang, "pdf_s4_archived_line",
                    count=uploads_archived or 0)
                  + (t(lang, "pdf_s4_archived_db") if is_db
                     else t(lang, "pdf_s4_archived_api")))),
            body),
        Paragraph(t(lang, "pdf_s5"), h2),
        Paragraph(t(lang, "pdf_s5_body"), body),
    ]
    doc.build(story)


# ---------------------------------------------------------------------------
# ZIP archive
# ---------------------------------------------------------------------------

def build_zip(report_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(report_dir.rglob("*")):
            if path.is_file() and path != zip_path:
                archive.write(path, path.relative_to(report_dir))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_report_for_user(user_dir: Path, lang_arg: str | None = None) -> int:
    """Build HTML + PDF + ZIP for one user folder (must contain manifest.json).

    ``lang_arg`` is the raw --lang value ("en", "de", "auto", ...); resolved
    per user against the manifest's user.lang when "auto".
    """
    global REPORT_LANG
    manifest = read_json(user_dir / "manifest.json")
    if not manifest:
        print(f"No export found in {user_dir} - run the export first")
        return 1
    user = manifest.get("user") or {}
    uid = user.get("userid") or manifest.get("target_userid", "x")

    # Resolve report language: explicit --lang wins; "auto" reads the data
    # subject's eLabFTW UI language from the manifest.
    REPORT_LANG = normalize_lang(lang_arg or "en", user.get("lang"))
    lang = REPORT_LANG

    # clean only generated artifacts, keep the raw JSON export
    for name in ("index.html", "entries", "assets"):
        path = user_dir / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for pattern in ("Disclosure_User*.pdf", "gdpr_disclosure_User*.zip"):
        for path in user_dir.glob(pattern):
            path.unlink()

    build_html_report(user_dir, user_dir)
    pdf_path = user_dir / f"Disclosure_User{uid}.pdf"
    build_pdf_report(user_dir, pdf_path)

    # Pipeline A (API) is transparent: write LIMITATIONS.md so the recipient
    # sees exactly which DB-only data is missing from this package.
    if manifest.get("source") != "db":
        db_counts = "unknown (DB export not run)"
        try:
            import json as _json
            appx = _json.loads((user_dir / "db_appendix.json").read_text(
                encoding="utf-8")) if (user_dir / "db_appendix.json").exists() else None
            if appx:
                db_counts = ", ".join(f"{k} {len(v)}" for k, v in appx.items())
        except Exception:
            pass
        archived = manifest.get("uploads_archived", "n/a")
        (user_dir / "LIMITATIONS.md").write_text(
            t(lang, "limitations_md",
              db_counts=db_counts, archived=archived,
              uid=uid, exported=manifest.get("exported_at", "")),
            encoding="utf-8")

    zip_path = user_dir / f"gdpr_disclosure_User{uid}.zip"
    build_zip(user_dir, zip_path)

    print(t(lang, "cli_html", path=user_dir / "index.html"))
    print(t(lang, "cli_pdf", path=pdf_path))
    print(t(lang, "cli_zip", path=zip_path, size=zip_path.stat().st_size // 1024))
    return 0


def build_reports(base_dir: Path, user_filter: list[int] | None = None,
                  lang_arg: str | None = None) -> dict:
    """Build reports for all user folders with an export (or a subset).

    Returns {user_dir_name: 0|1} (1 = report built successfully).
    """
    if (base_dir / "manifest.json").exists():
        user_dirs = [base_dir]
    else:
        user_dirs = sorted(d for d in base_dir.glob("User*")
                           if (d / "manifest.json").exists())
    if user_filter:
        user_dirs = [d for d in user_dirs
                     if d.name.removeprefix("User").isdigit()
                     and int(d.name.removeprefix("User")) in user_filter]
    if not user_dirs:
        print(f"No exports found under {base_dir} - run the export first")
        return {}

    # default language for CLI progress lines (auto resolves per user later)
    cli_lang = normalize_lang(lang_arg or "en")
    results = {}
    for user_dir in user_dirs:
        print(f"\n{t(cli_lang, 'cli_report_for', name=user_dir.name)}")
        results[user_dir.name] = build_report_for_user(user_dir, lang_arg)
    ok = sum(1 for v in results.values() if v == 0)
    print(f"\n{t(cli_lang, 'cli_built', ok=ok, total=len(results))}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="eLabFTW GDPR Art. 15 report generator (HTML + PDF + ZIP)")
    parser.add_argument("--out-dir", default=str(OUTPUT_DIR),
                        help="base directory containing per-user export folders")
    parser.add_argument("--user", default=None,
                        help="comma-separated user IDs to build reports for "
                             "(default: all exported users)")
    parser.add_argument("--lang", default="en",
                        help="report language: en, de, fr, ... or 'auto' to "
                             "read the user's eLabFTW language (default: en)")
    args = parser.parse_args()

    user_filter = None
    if args.user:
        user_filter = [int(x) for x in args.user.replace(" ", "").split(",") if x]
    results = build_reports(Path(args.out_dir), user_filter, args.lang)
    if not results:
        return 1
    return 0 if all(v == 0 for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
