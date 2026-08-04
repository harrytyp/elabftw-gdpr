#!/usr/bin/env python3
"""
eLabFTW DSGVO-Auskunft — Report-Generator.

Erzeugt aus dem Export-Ordner (gdpr_export.py) ein menschenlesbares Paket:
  report/                 HTML-Explorer (index.html + Entry-Seiten + Thumbnails)
  report/Auskunft_<uid>.pdf   Auskunftsschreiben (Art. 15(1)-Pflichtangaben + Mengen)
  gdpr_auskunft_<uid>.zip     alles zusammen (HTML + PDF + index.md + README)

Nutzung: .venv/bin/python gdpr_report.py [--out-dir DIR]
"""
import argparse
import html
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
THUMB_MAX = 400

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
.karten { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
.karte { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 10px 16px; min-width: 140px; }
.karte b { font-size: 22px; display: block; }
.entry { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }
.entry a { color: #16324f; font-weight: 600; text-decoration: none; }
.meta { color: #5a6570; font-size: 13px; }
.body { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; padding: 14px 18px; white-space: pre-wrap; font-size: 14px; line-height: 1.5; }
details { background: #fff; border: 1px solid #d8dde3; border-radius: 8px; margin: 6px 0; padding: 8px 14px; }
summary { cursor: pointer; font-weight: 600; }
.galerie { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.galerie a { border: 1px solid #d8dde3; border-radius: 6px; overflow: hidden; background: #fff; }
.galerie img { display: block; max-width: 180px; max-height: 140px; }
.datei { display: inline-block; background: #eef1f5; border-radius: 6px; padding: 6px 10px; margin: 4px; font-size: 13px; }
.hinweis { background: #fff7e0; border: 1px solid #e5cf8a; border-radius: 8px; padding: 12px 16px; margin: 12px 0; font-size: 14px; }
.zurueck { display: inline-block; margin-bottom: 12px; color: #16324f; }
td.klein { font-size: 13px; color: #5a6570; }
"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def fmt(ts) -> str:
    return str(ts)[:16] if ts else "—"


def read_json(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def resolve_status_category(ent: dict, etype: str, lookups: dict | None) -> tuple:
    if not lookups:
        return None, None
    lk = lookups.get(str(ent.get("team"))) or {}
    if etype == "experiments":
        return (lk.get("experiments_status", {}).get(str(ent.get("status"))),
                lk.get("experiments_categories", {}).get(str(ent.get("category"))))
    if etype == "items":
        return (lk.get("items_status", {}).get(str(ent.get("status"))),
                lk.get("items_types", {}).get(str(ent.get("category"))))
    if etype == "items_types":
        return (None, lk.get("items_categories", {}).get(str(ent.get("category"))))
    return None, None


def entry_meta(ent: dict, etype: str, lookups: dict | None = None) -> list:
    st_name, cat_name = resolve_status_category(ent, etype, lookups)
    status = ent.get("status") or ent.get("state") or "—"
    if st_name:
        status = f"{status} ({st_name})"
    category = ent.get("category") or "—"
    if cat_name:
        category = f"{category} ({cat_name})"
    m = [
        ("ID / elabid", f"{ent.get('id')} / {ent.get('elabid', '—')}"),
        ("Erstellt", fmt(ent.get("created_at"))),
        ("Geändert", fmt(ent.get("modified_at"))),
        ("Zuletzt geändert von", ent.get("lastchangeby") or "—"),
        ("Status", status),
        ("Kategorie", category),
        ("Gesperrt", f"von {ent.get('lockedby')} seit {fmt(ent.get('locked_at'))}" if ent.get("locked") else "nein"),
        ("Timestamped", fmt(ent.get("timestamped_at")) if ent.get("timestamped") else "nein"),
        ("Custom ID", ent.get("custom_id") or "—"),
        ("Bewertung", ent.get("rating") or "—"),
    ]
    return [(k, v) for k, v in m]


def make_thumb(src: Path, dst: Path) -> None:
    try:
        im = Image.open(src)
        im.thumbnail((THUMB_MAX, THUMB_MAX))
        im.convert("RGB").save(dst, "JPEG", quality=82)
    except Exception:
        shutil.copy(src, dst)


def sanitize(name: str) -> str:
    keep = "".join(c for c in name if c.isalnum() or c in "._- ")
    return keep.strip() or "file"


def up_filename(up: dict) -> str:
    """Dateiname im Export: uid-Originalname (real_name vor long_name)."""
    name = up.get("real_name") or up.get("long_name") or f"upload-{up.get('id')}"
    return f"{up.get('id')}-{sanitize(name)}"


def entity_page(out_dir: Path, report_dir: Path, assets_dir: Path, etype: str, ent: dict,
                lookups: dict | None = None) -> Path:
    eid = ent["id"]
    edir = out_dir / etype / str(eid)
    files_dir = out_dir / "files" / f"{etype}-{eid}"
    page = report_dir / "entries" / f"{etype}-{eid}.html"
    page.parent.mkdir(parents=True, exist_ok=True)

    comments = read_json(edir / "comments.json") or []
    revisions = read_json(edir / "revisions.json") or []
    steps = read_json(edir / "steps.json") or []
    tags = read_json(edir / "tags.json") or []
    uploads = read_json(edir / "uploads.json") or []
    req_actions = read_json(edir / "request_actions.json") or []

    rows = "".join(f"<tr><td class='klein'>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in entry_meta(ent, etype, lookups))
    tag_html = "".join(f"<span class='datei'>{esc(t.get('tag', t))}</span>" for t in tags)
    step_rows = ""
    for s in steps:
        done = "✔" if s.get("finished") else "☐"
        dl = f"<br><span class='meta'>Deadline: {fmt(s.get('deadline'))}</span>" if s.get("deadline") else ""
        step_rows += f"<tr><td>{done}</td><td>{esc(s.get('body'))}{dl}</td></tr>"
    comment_html = ""
    for c in comments:
        comment_html += (
            f"<div class='entry'><b>{esc(c.get('fullname', c.get('userid')))}</b> "
            f"<span class='meta'>{fmt(c.get('created_at'))}</span>"
            f"<p style='margin:6px 0 0'>{esc(c.get('comment'))}</p></div>"
        )
    rev_html = ""
    for r in revisions:
        rev_html += (
            f"<details><summary>Revision vom {fmt(r.get('created_at'))} "
            f"— {esc(r.get('userid'))}</summary>"
            f"<div class='body'>{esc(r.get('body'))}</div></details>"
        )
    gal = []
    files = []
    for u in uploads:
        uid = u["id"]
        fname = up_filename(u)
        fpath = files_dir / fname if files_dir.exists() else None
        if fpath and fpath.exists() and fpath.suffix.lower() in IMG_EXT:
            thumb = assets_dir / f"{etype}-{eid}-{uid}.img"
            make_thumb(fpath, thumb)
            gal.append(f"<a href='../assets/{etype}-{eid}-{uid}.img' target='_blank'><img src='../assets/{etype}-{eid}-{uid}.img' alt='{esc(u.get('real_name', fname))}'></a>")
        files.append(
            f"<span class='datei'><a href='../files/{etype}-{eid}/{esc(fname)}' download>{esc(u.get('real_name', fname))}</a>"
            f" <span class='meta'>({u.get('filesize', '?')} B, {fmt(u.get('created_at'))})</span></span>"
        )
    ra_html = "".join(
        f"<div class='entry'><b>{esc(r.get('action'))}</b> <span class='meta'>{fmt(r.get('created_at'))} "
        f"— von {esc(r.get('requester_userid'))}, Status {esc(r.get('state'))}</span></div>" for r in req_actions
    )
    gal_html = f"<div class='galerie'>{''.join(gal)}</div>" if gal else ""
    files_html = f"<div>{''.join(files)}</div>" if files else "<p class='meta'>keine Uploads</p>"

    body = ent.get("body") or ""
    page.write_text(f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{esc(ent.get('title', etype))} — {etype} {eid}</title>
<style>{CSS}</style></head><body><div class="wrap">
<a class="zurueck" href="../index.html">← Zurück zur Übersicht</a>
<header><h1>{esc(ent.get('title', '(ohne Titel)'))}</h1>
<p>{etype} #{eid} · elabid {esc(ent.get('elabid', '—'))} · zuletzt geändert {fmt(ent.get('modified_at'))}</p></header>
<h2>Metadaten</h2><table>{rows}</table>
<h2>Inhalt</h2><div class="body">{esc(body)}</div>
<h2>Tags</h2><p>{tag_html or '<span class=\'meta\'>—</span>'}</p>
<h2>Schritte</h2><table><tr><th></th><th>Schritt</th></tr>{step_rows}</table>
<h2>Kommentare ({len(comments)})</h2>{comment_html or '<p class=\'meta\'>keine</p>'}
<h2>Revisionen ({len(revisions)})</h2>{rev_html or '<p class=\'meta\'>keine</p>'}
<h2>Uploads ({len(uploads)})</h2>{gal_html}{files_html}
<h2>Request-Actions ({len(req_actions)})</h2>{ra_html or '<p class=\'meta\'>keine</p>'}
</div></body></html>""")
    return page


def pretty_body(raw) -> str:
    """Notification-body: JSON-String/Dict -> lesbarer Text."""
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
    elif isinstance(raw, list):
        return ", ".join(pretty_body(x) for x in raw) or "—"
    else:
        return str(raw) if raw else "—"
    parts = []
    if data.get("msg"):
        parts.append(str(data["msg"]))
    if data.get("actor"):
        parts.append(f"Akteur: {data['actor']}")
    ev = data.get("event")
    if isinstance(ev, dict):
        title = ev.get("experiment_title") or ev.get("item_title") or ev.get("title")
        if title:
            parts.append(f"Ereignis: {title}")
        elif ev.get("id"):
            parts.append(f"Ereignis-ID: {ev['id']}")
        if ev.get("start"):
            parts.append(f"{ev['start']} – {ev.get('end', '')}")
    if data.get("step_id"):
        parts.append(f"Schritt {data['step_id']} (Deadline {data.get('deadline', '—')})")
    if data.get("team"):
        parts.append(f"Team: {data['team']}")
    if data.get("userid"):
        parts.append(f"User: {data['userid']}")
    return " · ".join(parts) or "—"


def row_val(x):
    return x.get("name") if isinstance(x, dict) else x


def in_group(g, userid) -> bool:
    users = g.get("users") if isinstance(g, dict) else None
    if not isinstance(users, list):
        return True
    return any(str(u.get("userid")) == str(userid) for u in users)


def members_str(g) -> str:
    users = g.get("users") if isinstance(g, dict) else None
    if not isinstance(users, list):
        return "—"
    return ", ".join(str(u.get("fullname", u.get("userid"))) for u in users)


def build_html(out_dir: Path, report_dir: Path) -> None:
    assets_dir = report_dir / "assets"
    files_src = out_dir / "files"
    files_dst = report_dir / "files"
    assets_dir.mkdir(parents=True, exist_ok=True)
    if files_src.exists():
        shutil.copytree(files_src, files_dst, dirs_exist_ok=True)

    manifest = read_json(out_dir / "manifest.json") or {}
    lookups = manifest.get("lookups")
    user = manifest.get("user") or {}
    teams = user.get("teams") or []
    notifications = manifest.get("notifications") or []
    groups = manifest.get("groups") or []
    procurement = manifest.get("procurement") or []
    bookings = manifest.get("bookings") or []
    rors = manifest.get("rors") or []
    req_actions_u = manifest.get("request_actions_user") or []

    # Entry-Seiten
    entry_links = []
    counts = {}
    for etype in ("experiments", "items", "experiments_templates", "items_types"):
        ids = manifest.get("entities", {}).get(etype, [])
        counts[etype] = len(ids)
        for eid in ids:
            ent = read_json(out_dir / etype / str(eid) / "entity.json") or {"id": eid}
            page = entity_page(out_dir, report_dir, assets_dir, etype, ent, lookups)
            entry_links.append(
                f"<div class='entry'><a href='entries/{etype}-{eid}.html'>{esc(ent.get('title', '(ohne Titel)'))}</a>"
                f"<div class='meta'>{etype} #{eid} · {fmt(ent.get('modified_at'))}</div></div>"
            )
    entry_links.sort(key=lambda s: s.lower())

    team_rows = "".join(
        f"<tr><td>{esc(t.get('name'))}</td><td>{esc(t.get('id'))}</td>"
        f"<td>{'ja' if t.get('is_admin') else 'nein'}</td><td>{'ja' if t.get('is_owner') else 'nein'}</td>"
        f"<td>{'ja' if t.get('is_archived') else 'nein'}</td></tr>" for t in teams
    )
    notif_rows = "".join(
        f"<tr><td>{fmt(n.get('created_at'))}</td><td>{esc(n.get('category'))}</td>"
        f"<td>{esc(pretty_body(n.get('body')))}</td><td>{'ja' if n.get('is_ack') else 'nein'}</td></tr>" for n in notifications
    )
    uid = user.get("userid")
    my_groups = [g for g in groups if in_group(g, uid)]
    group_rows = "".join(
        f"<tr><td>{esc(row_val(g))}</td><td>{esc(g.get('id', '—'))}</td><td>{esc(members_str(g))}</td></tr>"
        for g in my_groups
    )
    proc_rows = "".join(
        f"<tr><td>{fmt(p.get('created_at'))}</td><td>{esc(p.get('requester_fullname', p.get('requester_userid', '—')))}</td>"
        f"<td>{p.get('entity_id', '—')}</td><td>{p.get('qty_ordered', '—')}</td><td>{esc(p.get('state'))}</td></tr>" for p in procurement
    )
    book_rows = "".join(
        f"<tr><td>{fmt(b.get('start'))} – {fmt(b.get('end'))}</td><td>{esc(b.get('title'))}</td>"
        f"<td>{esc(b.get('item_title', b.get('item')))}</td></tr>" for b in bookings
    )
    ra_rows = "".join(
        f"<tr><td>{fmt(r.get('created_at'))}</td><td>{esc(r.get('action'))}</td>"
        f"<td>{esc(r.get('state'))}</td><td>{esc(r.get('target_userid'))}</td></tr>" for r in req_actions_u
    )

    karten = "".join(
        f"<div class='karte'><b>{n}</b>{label}</div>"
        for label, n in [
            ("Experiments", counts["experiments"]), ("Items", counts["items"]),
            ("Templates", counts["experiments_templates"]), ("Items-Types", counts["items_types"]),
            ("Uploads", manifest.get("upload_files_downloaded", 0)), ("Notifications", len(notifications)),
            ("Bookings", len(bookings)), ("Gruppen", len(my_groups)), ("Procurement", len(procurement)),
        ]
    )

    (report_dir / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>DSGVO-Auskunft — {esc(user.get('fullname'))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>DSGVO-Auskunft (Art. 15) — {esc(user.get('fullname'))}</h1>
<p>E-Mail: {esc(user.get('email'))} · User-ID: {esc(user.get('userid'))} · erstellt: {fmt(user.get('created_at'))}</p>
<p>Letzter Login: {fmt(user.get('last_login'))} · Export erstellt: {fmt(manifest.get('exported_at'))}</p></header>

<div class="hinweis"><b>Hinweis:</b> Dieser Bericht enthält personenbezogene Daten und ist nur für den
Anfragenden bestimmt. Anteile Dritter müssen vor der Weitergabe geschwärzt werden (Art. 15(4) DSGVO).
Rohwerte wie Passwort-Hashes, MFA-Secrets oder Tokens sind bewusst nicht enthalten — diese werden nur
als Kategorie ausgewiesen (siehe PDF).</div>

<h2>Übersicht</h2><div class="karten">{karten}</div>

<h2>Konto &amp; Teams</h2>
<table><tr><th>Team</th><th>ID</th><th>Admin</th><th>Owner</th><th>Archiviert</th></tr>{team_rows}</table>

<h2>Notifications ({len(notifications)})</h2>
<table><tr><th>Datum</th><th>Kategorie</th><th>Inhalt</th><th>Gelesen</th></tr>{notif_rows}</table>

<h2>Gruppen ({len(my_groups)})</h2>
<table><tr><th>Gruppe</th><th>ID</th><th>Mitglieder</th></tr>{group_rows}</table>

<h2>Procurement-Requests ({len(procurement)})</h2>
<table><tr><th>Datum</th><th>Anfrager</th><th>Entry</th><th>Menge</th><th>Status</th></tr>{proc_rows}</table>

<h2>Bookings ({len(bookings)})</h2>
<table><tr><th>Zeitraum</th><th>Titel</th><th>Ressource</th></tr>{book_rows}</table>

<h2>Request-Actions ({len(req_actions_u)})</h2>
<table><tr><th>Datum</th><th>Aktion</th><th>Status</th><th>Ziel-User</th></tr>{ra_rows}</table>

<h2>Entries ({sum(counts.values())})</h2>{''.join(entry_links)}

<h2>Nur per DB/CLI abgedeckt (gdpr_cli.sql)</h2>
<ul>
<li>audit_logs, authfail, changelog (strukturiert), api_keys, exports, todolist, unfinished_steps, favtags, pins, sig_keys, edit_mode, lockout_devices</li>
</ul>
</div></body></html>""")


def build_pdf(out_dir: Path, pdf_path: Path) -> None:
    manifest = read_json(out_dir / "manifest.json") or {}
    user = manifest.get("user") or {}
    teams = user.get("teams") or []
    entities = manifest.get("entities", {})
    counts = {et: len(ids) for et, ids in entities.items()}

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"DSGVO-Auskunft {user.get('fullname')}")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#555555"))

    story = [
        Paragraph("DSGVO-Auskunft nach Art. 15 — Zusammenfassung", h1),
        Paragraph(
            f"<b>{esc(user.get('fullname'))}</b><br/>E-Mail: {esc(user.get('email'))} · "
            f"User-ID: {esc(user.get('userid'))}<br/>Account erstellt: {fmt(user.get('created_at'))} · "
            f"Letzter Login: {fmt(user.get('last_login'))} · Export: {fmt(manifest.get('exported_at'))}", body),
        Paragraph("1. Verarbeitete Datenkategorien", h2),
        Paragraph(
            "In eLabFTW werden zu Ihrer Person folgende Kategorien personenbezogener Daten verarbeitet: "
            "(a) Kontodaten (Name, E-Mail, Org-ID, Team-Zugehörigkeiten, Rollen, Login-Zeitpunkte), "
            "(b) von Ihnen erzeugte Inhalte (Experimente, Ressourcen, Vorlagen, Kommentare, Revisionen, "
            "Schritte, Tags, Verknüpfungen), (c) hochgeladene Dateien, (d) Buchungen, Benachrichtigungen, "
            "Gruppenmitgliedschaften, Bestellanfragen, Request-Actions, (e) Protokoll-/Sicherheitsdaten "
            "(Audit-Trail, Login-Versuche — nur als Kategorie, siehe Ziffer 4).", body),
        Paragraph("2. Umfang der Kopie", h2),
        Paragraph(
            "Die vollständigen Detaildaten liegen diesem Schreiben als HTML-Explorer und als "
            "maschinenlesbare Kopie (JSON/ELN) bei. Mengenübersicht:", body),
        Table([[k, str(v)] for k, v in [
            ("Experimente", counts["experiments"]), ("Ressourcen (Items)", counts["items"]),
            ("Vorlagen", counts["experiments_templates"]), ("Items-Types", counts["items_types"]),
            ("Upload-Dateien", manifest.get("upload_files_downloaded", 0)),
            ("Notifications", len(manifest.get("notifications") or [])),
            ("Bookings", len(manifest.get("bookings") or [])),
            ("Gruppen", len(manifest.get("groups") or [])),
            ("Procurement-Requests", len(manifest.get("procurement") or [])),
        ]], colWidths=[90 * mm, 60 * mm], style=TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f5")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])),
        Spacer(1, 6),
        Paragraph(
            "Teams/Rollen: " + ", ".join(f"{t.get('name')} (Admin: {t.get('is_admin')}, Owner: {t.get('is_owner')}, "
            f"archiviert: {t.get('is_archived')})" for t in teams), small),
        Paragraph("3. Zwecke, Empfänger, Speicherdauer", h2),
        Paragraph(
            "Zweck: elektronisches Laborbuch zur Dokumentation und Nachvollziehbarkeit der Forschungsarbeit. "
            "Empfänger: Teammitglieder gemäß Zugriffsrechten; Hosting-Betreiber im Rahmen des Betriebs (AV-Vertrag). "
            "Speicherdauer: Kontodaten bis zur Löschung/Archivierung des Accounts; Laborbuchinhalte entsprechend "
            "den Aufbewahrungspflichten (z.B. GxP, § 257 HGB); Audit-/Protokolldaten gemäß Löschkonzept des "
            "Betreibers; Backups rotieren nach dem Sicherungskonzept.", body),
        Paragraph("4. Nicht enthaltene Daten (nur als Kategorie)", h2),
        Paragraph(
            "Passwort-Hash, MFA-Secret, Reset-Token, API-Key-Hashes und Signaturschlüssel werden nur "
            "verschlüsselt/gehasht gespeichert und aus Sicherheitsgründen nicht ausgehändigt (Art. 32 DSGVO). "
            "Audit-Trail, fehlgeschlagene Login-Versuche, Todolist, Export-Historie, Favoriten/Pins und "
            "Sperrzustände sind per API nicht abrufbar und können auf Anfrage ergänzt werden (DB-Auszug). "
            "Anteile Dritter in geteilten Inhalten wurden ggf. geschwärzt (Art. 15(4) DSGVO).", body),
        Paragraph("5. Ihre Rechte", h2),
        Paragraph(
            "Berichtigung (Art. 16), Löschung (Art. 17 — vorbehaltlich gesetzlicher Aufbewahrungspflichten), "
            "Einschränkung (Art. 18), Datenübertragbarkeit (Art. 20), Widerspruch (Art. 21) sowie Beschwerde "
            "bei der zuständigen Aufsichtsbehörde. Die Auskunft erfolgte innerhalb der Frist des Art. 12(3) DSGVO.", body),
    ]
    doc.build(story)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(PROJECT_ROOT / "out"))
    ap.add_argument("--report-dir", default=str(PROJECT_ROOT / "report"))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    manifest = read_json(out_dir / "manifest.json")
    if not manifest:
        print(f"Kein Export in {out_dir} — zuerst gdpr_export.py ausführen")
        return 1
    user = manifest.get("user") or {}
    uid = user.get("userid") or manifest.get("target_userid", "x")

    report_dir = Path(args.report_dir)
    if report_dir.exists():
        shutil.rmtree(report_dir)
    report_dir.mkdir(parents=True)

    build_html(out_dir, report_dir)
    pdf_path = report_dir / f"Auskunft_User{uid}.pdf"
    build_pdf(out_dir, pdf_path)

    # ZIP: Report + Roh-Export (index.md, manifest) + README
    zip_path = PROJECT_ROOT / f"gdpr_auskunft_User{uid}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(report_dir.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(report_dir))
        for name in ("index.md", "manifest.json", "user.json", "README.md"):
            p = out_dir / name if (out_dir / name).exists() else PROJECT_ROOT / name
            if p.exists():
                z.write(p, f"rohdaten/{p.name}")

    print(f"HTML:   {report_dir}/index.html")
    print(f"PDF:    {pdf_path}")
    print(f"ZIP:    {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
