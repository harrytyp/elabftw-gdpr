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

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
THUMBNAIL_MAX = 400

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


def format_ts(value) -> str:
    return str(value)[:16] if value else "-"


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
        ("ID / elabid", f"{entity.get('id')} / {entity.get('elabid', '-')}"),
        ("Created", format_ts(entity.get("created_at"))),
        ("Modified", format_ts(entity.get("modified_at"))),
        ("Last changed by", entity.get("lastchangeby") or "-"),
        ("Status", status),
        ("Category", category),
        ("Locked", f"by {entity.get('lockedby')} since {format_ts(entity.get('locked_at'))}"
                   if entity.get("locked") else "no"),
        ("Timestamped", format_ts(entity.get("timestamped_at")) if entity.get("timestamped") else "no"),
        ("Custom ID", entity.get("custom_id") or "-"),
        ("Rating", entity.get("rating") or "-"),
    ]


def make_thumbnail(source: Path, target: Path) -> None:
    try:
        image = Image.open(source)
        image.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX))
        image.convert("RGB").save(target, "JPEG", quality=82)
    except Exception:
        shutil.copy(source, target)


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

    meta_rows = "".join(
        f"<tr><td class='klein'>{escape(k)}</td><td>{escape(v)}</td></tr>"
        for k, v in entity_metadata(entity, entity_type, lookups)
    )
    tags_html = "".join(f"<span class='file'>{escape(t.get('tag', t))}</span>" for t in tags)

    step_rows = ""
    for step in steps:
        done = "✔" if step.get("finished") else "☐"
        deadline = (f"<br><span class='meta'>Deadline: {format_ts(step.get('deadline'))}</span>"
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
            f"<details><summary>Revision from {format_ts(revision.get('created_at'))} "
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
<html lang="en"><head><meta charset="utf-8">
<title>{escape(entity.get('title', entity_type))} - {entity_type} {eid}</title>
<style>{CSS}</style></head><body><div class="wrap">
<a class="back" href="../index.html">← Back to overview</a>
<header><h1>{escape(entity.get('title', '(no title)'))}</h1>
<p>{entity_type} #{eid} · elabid {escape(entity.get('elabid', '-'))} · modified {format_ts(entity.get('modified_at'))}</p></header>
<h2>Metadata</h2><table>{meta_rows}</table>
<h2>Content</h2><div class="body">{escape(body)}</div>
<h2>Tags</h2><p>{tags_html or "<span class='meta'>-</span>"}</p>
<h2>Steps</h2><table><tr><th></th><th>Step</th></tr>{step_rows}</table>
<h2>Comments ({len(comments)})</h2>{comments_html or "<p class='meta'>none</p>"}
<h2>Revisions ({len(revisions)})</h2>{revisions_html or "<p class='meta'>none</p>"}
<h2>Uploads ({len(uploads)})</h2>{gallery_html}{files_html}
<h2>Request actions ({len(request_actions)})</h2>{request_actions_html or "<p class='meta'>none</p>"}
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
    my_groups = [g for g in groups if user_in_group(g, uid)]
    team_rows = "".join(
        f"<tr><td>{escape(t.get('name'))}</td><td>{escape(t.get('id'))}</td>"
        f"<td>{'yes' if t.get('is_admin') else 'no'}</td><td>{'yes' if t.get('is_owner') else 'no'}</td>"
        f"<td>{'yes' if t.get('is_archived') else 'no'}</td></tr>" for t in teams
    )
    notification_rows = "".join(
        f"<tr><td>{format_ts(n.get('created_at'))}</td><td>{escape(n.get('category'))}</td>"
        f"<td>{escape(pretty_notification_body(n.get('body')))}</td>"
        f"<td>{'yes' if n.get('is_ack') else 'no'}</td></tr>" for n in notifications
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

    cards = "".join(
        f"<div class='card'><b>{n}</b>{label}</div>"
        for label, n in [
            ("Experiments", counts["experiments"]),
            ("Items", counts["items"]),
            ("Templates", counts["experiments_templates"]),
            ("Item types", counts["items_types"]),
            ("Uploads", uploads_total),
            ("Notifications", len(notifications)),
            ("Bookings", len(bookings)),
            ("Groups", len(my_groups)),
            ("Procurement", len(procurement)),
        ]
    )

    # DB appendix rows (pipeline B)
    appendix_sections = ""
    if db_appendix:
        def _rows(name, cols):
            return "".join(
                "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row[:cols]) + "</tr>"
                for row in db_appendix.get(name, [])
            )
        appendix_sections = f"""
<h2>DB appendix (audit trail, logins, changelog, keys)</h2>
<p><b>Source:</b> direct database export (no API key). Includes all uploads
(active {uploads_active or '?'}, archived {uploads_archived or '?'}) and records
that are not reachable via the API.</p>
<h3>Audit trail ({len(db_appendix.get('audit_logs', []))})</h3>
<table><tr><th>Date</th><th>Category</th><th>Requester</th><th>Target</th><th>Body (truncated)</th></tr>{_rows('audit_logs', 5)}</table>
<h3>Failed logins ({len(db_appendix.get('authfail', []))})</h3>
<table><tr><th>Attempt time</th></tr>{_rows('authfail', 1)}</table>
<h3>Changelog ({len(db_appendix.get('changelog', []))})</h3>
<table><tr><th>Type</th><th>Date</th><th>Target</th><th>Content</th></tr>{_rows('changelog', 4)}</table>
<h3>API keys ({len(db_appendix.get('api_keys', []))})</h3>
<table><tr><th>ID</th><th>Name</th><th>Created</th><th>Last used</th><th>Write</th></tr>{_rows('api_keys', 5)}</table>
<h3>Exports ({len(db_appendix.get('exports', []))})</h3>
<table><tr><th>ID</th><th>Date</th><th>State</th><th>Format</th></tr>{_rows('exports', 4)}</table>
<h3>Todolist ({len(db_appendix.get('todolist', []))})</h3>
<table><tr><th>ID</th><th>Created</th><th>Body</th></tr>{_rows('todolist', 3)}</table>
<h3>Sig keys ({len(db_appendix.get('sig_keys', []))}) / Favorites ({len(db_appendix.get('favtags', []))})</h3>
<table><tr><th>Sig key ID</th><th>Created</th><th>State</th></tr>{_rows('sig_keys', 3)}</table>
"""

    # API-mode limitation banner (pipeline A stays transparent)
    limitation_note = ""
    if not is_db:
        limitation_note = f"""
<div class="notice notice-error"><b>API-Limitation:</b> This report was created
from the API only (1-click). The following data is NOT included and must be added
via <code>gdpr_cli.sql</code> or the DB pipeline
(<code>elab-gdpr-db --users {escape(user.get('userid', ''))}</code>):
audit_logs, authfail, changelog, api_keys, exports, todolist, sig_keys, favtags,
and archived uploads (state=2, {uploads_archived or 'n/a'} additional files).
See LIMITATIONS.md in this package.</div>
"""

    (report_dir / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>GDPR disclosure - {escape(user.get('fullname'))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>GDPR data subject access request (Art. 15) - {escape(user.get('fullname'))}</h1>
<p>Email: {escape(user.get('email'))} · User ID: {escape(user.get('userid'))} · created: {format_ts(user.get('created_at'))}</p>
<p>Last login: {format_ts(user.get('last_login'))} · Export created: {format_ts(manifest.get('exported_at'))}</p></header>

<div class="notice"><b>Notice:</b> This report contains personal data and is intended
for the data subject only. Third-party content (co-authors, reviewer comments, names in
audit logs) must be redacted before sharing (Art. 15(4) GDPR). Raw values such as password
hashes, MFA secrets or tokens are deliberately not included - they are only listed as
categories (see PDF).</div>

{limitation_note}

<h2>Overview</h2><div class="cards">{cards}</div>

<h2>Account &amp; teams</h2>
<table><tr><th>Team</th><th>ID</th><th>Admin</th><th>Owner</th><th>Archived</th></tr>{team_rows}</table>

<h2>Notifications ({len(notifications)})</h2>
<table><tr><th>Date</th><th>Category</th><th>Content</th><th>Read</th></tr>{notification_rows}</table>

<h2>Groups ({len(my_groups)})</h2>
<table><tr><th>Group</th><th>ID</th><th>Members</th></tr>{group_rows}</table>

<h2>Procurement requests ({len(procurement)})</h2>
<table><tr><th>Date</th><th>Requester</th><th>Entry</th><th>Quantity</th><th>State</th></tr>{procurement_rows}</table>

<h2>Bookings ({len(bookings)})</h2>
<table><tr><th>Period</th><th>Title</th><th>Resource</th></tr>{booking_rows}</table>

<h2>Request actions ({len(request_actions_user)})</h2>
<table><tr><th>Date</th><th>Action</th><th>State</th><th>Target user</th></tr>{request_action_rows}</table>

<h2>Entries ({sum(counts.values())})</h2>{''.join(entry_links)}

<h2>DB/CLI only (gdpr_cli.sql)</h2>
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
    uploads_total = manifest.get("uploads_total",
                                 manifest.get("upload_files_downloaded", 0))
    uploads_archived = manifest.get("uploads_archived")

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"GDPR disclosure {user.get('fullname')}")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=11,
                           textColor=colors.HexColor("#555555"))

    story = [
        Paragraph("GDPR data subject access request (Art. 15) - Summary", h1),
        Paragraph(
            f"<b>{escape(user.get('fullname'))}</b><br/>Email: {escape(user.get('email'))} · "
            f"User ID: {escape(user.get('userid'))}<br/>Account created: {format_ts(user.get('created_at'))} · "
            f"Last login: {format_ts(user.get('last_login'))} · Export: {format_ts(manifest.get('exported_at'))}",
            body),
        Paragraph("1. Categories of personal data processed", h2),
        Paragraph(
            "eLabFTW processes the following categories of personal data about you: "
            "(a) account data (name, email, organisation ID, team memberships, roles, login timestamps), "
            "(b) content you created (experiments, resources, templates, comments, revisions, steps, tags, links), "
            "(c) uploaded files, (d) bookings, notifications, group memberships, procurement requests, "
            "request actions, (e) log/security data (audit trail, login attempts - categories only, see 4).",
            body),
        Paragraph("2. Scope of the copy", h2),
        Paragraph(
            "The full detail data is attached to this letter as an HTML explorer and as a machine-readable "
            "copy (JSON/ELN). Counts:", body),
        Table([[k, str(v)] for k, v in [
            ("Experiments", counts["experiments"]),
            ("Items (resources)", counts["items"]),
            ("Templates", counts["experiments_templates"]),
            ("Item types", counts["items_types"]),
            ("Upload files", uploads_total),
            ("Notifications", len(manifest.get("notifications") or [])),
            ("Bookings", len(manifest.get("bookings") or [])),
            ("Groups", len(manifest.get("groups") or [])),
            ("Procurement requests", len(manifest.get("procurement") or [])),
        ]], colWidths=[90 * mm, 60 * mm], style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f5")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])),
        Spacer(1, 6),
        Paragraph(
            "Teams/roles: " + ", ".join(
                f"{t.get('name')} (admin: {t.get('is_admin')}, owner: {t.get('is_owner')}, "
                f"archived: {t.get('is_archived')})" for t in teams), small),
        Paragraph("3. Purposes, recipients, retention", h2),
        Paragraph(
            "Purpose: electronic lab notebook for documenting and tracing research work. "
            "Recipients: team members according to access rights; hosting operator for operations "
            "(data processing agreement). Retention: account data until account deletion/archiving; "
            "lab notebook content according to legal retention obligations (e.g. GxP, German Commercial "
            "Code § 257 HGB); audit/log data per the operator's retention schedule; backups rotate "
            "according to the backup policy.", body),
        Paragraph("4. Data not included (categories only)", h2),
        Paragraph(
            "Password hashes, MFA secrets, reset tokens, API key hashes and signing keys are stored "
            "hashed/encrypted only and are not handed out for security reasons (Art. 32 GDPR). "
            + ("The audit trail, failed login attempts, changelog, todolist, export history and "
               "favourites are included in this package (direct database export). "
               if is_db else
               "Audit trail, failed login attempts, todolist, export history, favourites/pins and lock "
               "states are not retrievable via the API and can be supplied on request (database extract). ")
            + f"Archived uploads: {uploads_archived or 0} files are only listed as metadata "
            + ("(included in this package). " if is_db else "(not downloaded with the API). ")
            + "Third-party portions of shared content may have been redacted (Art. 15(4) GDPR).", body),
        Paragraph("5. Your rights", h2),
        Paragraph(
            "Rectification (Art. 16), erasure (Art. 17 - subject to legal retention obligations), "
            "restriction (Art. 18), data portability (Art. 20), objection (Art. 21) and the right to "
            "lodge a complaint with the supervisory authority. This disclosure was provided within the "
            "time limit of Art. 12(3) GDPR.", body),
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

def build_report_for_user(user_dir: Path) -> int:
    """Build HTML + PDF + ZIP for one user folder (must contain manifest.json)."""
    manifest = read_json(user_dir / "manifest.json")
    if not manifest:
        print(f"No export found in {user_dir} - run the export first")
        return 1
    user = manifest.get("user") or {}
    uid = user.get("userid") or manifest.get("target_userid", "x")

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
            f"# Limitations of this API export\n\n"
            f"This package was created with the 1-click API pipeline "
            f"(elab-gdpr, sysadmin API key). The following data is NOT included "
            f"and must be added for a complete Art. 15 disclosure:\n\n"
            f"- audit_logs, authfail, changelog, api_keys, exports, todolist,\n"
            f"  sig_keys, favtags (DB-only, {db_counts})\n"
            f"- archived uploads (state=2, {archived} files - metadata only here)\n\n"
            f"Run the DB pipeline instead for everything in one go:\n\n"
            f"    elab-gdpr-db --users {uid} --with-files\n\n"
            f"Generated: {manifest.get('exported_at', '')}\n", encoding="utf-8")

    zip_path = user_dir / f"gdpr_disclosure_User{uid}.zip"
    build_zip(user_dir, zip_path)

    print(f"HTML: {user_dir / 'index.html'}")
    print(f"PDF:  {pdf_path}")
    print(f"ZIP:  {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    return 0


def build_reports(base_dir: Path, user_filter: list[int] | None = None) -> dict:
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

    results = {}
    for user_dir in user_dirs:
        print(f"\n===== Report for {user_dir.name} =====")
        results[user_dir.name] = build_report_for_user(user_dir)
    ok = sum(1 for v in results.values() if v == 0)
    print(f"\nBuilt {ok}/{len(results)} reports")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="eLabFTW GDPR Art. 15 report generator (HTML + PDF + ZIP)")
    parser.add_argument("--out-dir", default=str(OUTPUT_DIR),
                        help="base directory containing per-user export folders")
    parser.add_argument("--user", default=None,
                        help="comma-separated user IDs to build reports for "
                             "(default: all exported users)")
    args = parser.parse_args()

    user_filter = None
    if args.user:
        user_filter = [int(x) for x in args.user.replace(" ", "").split(",") if x]
    results = build_reports(Path(args.out_dir), user_filter)
    if not results:
        return 1
    return 0 if all(v == 0 for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
