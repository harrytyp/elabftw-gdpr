"""Lightweight i18n for the GDPR report output (HTML + PDF).

Language is selected per run via ``--lang`` (default ``en``). The special
value ``auto`` reads the data subject's eLabFTW UI language from the
manifest (``user.lang``, e.g. ``de_DE``) and maps it onto the supported
codes below; anything unknown falls back to English.

Only the *report UI* is translated - the underlying data (entity titles,
comments, audit-log bodies, status/category names from eLabFTW, upload
file names) is user content and is deliberately NOT translated.

Adding a language later means: add its dict to ``STRINGS`` and (for scripts
outside cp1252 such as Polish or Czech) make sure a TTF font is registered
for the PDF. No code changes needed.
"""

from __future__ import annotations

import html

# eLabFTW locales (users.lang) -> report language code. Anything not listed
# (or missing) falls back to "en".
LOCALE_TO_LANG = {
    "de_DE": "de",
    "de": "de",
    "en_GB": "en",
    "en_US": "en",
    "fr_FR": "fr",
    "fr": "fr",
    "es_ES": "es",
    "es": "es",
    "it_IT": "it",
    "it": "it",
    "pt_PT": "pt",
    "pt_BR": "pt",
    "nl_BE": "nl",
    "nl_NL": "nl",
    "nl": "nl",
    "pl_PL": "pl",
    "pl": "pl",
}

# ---------------------------------------------------------------------------
# Strings
#
# en is the default and the fallback: every key used via t() MUST exist in
# the "en" dict. Other languages only need to override what is translated.
# ---------------------------------------------------------------------------

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # --- generic -----------------------------------------------------
        "yes": "yes",
        "no": "no",
        "none": "none",
        "no_uploads": "no uploads",
        "back_to_overview": "← Back to overview",
        "no_title": "(no title)",

        # --- html <lang> attribute and <title> --------------------------
        "html_lang": "en",

        # --- entity page headings ---------------------------------------
        "metadata": "Metadata",
        "content": "Content",
        "tags": "Tags",
        "steps": "Steps",
        "comments": "Comments",
        "revisions": "Revisions",
        "uploads": "Uploads",
        "request_actions": "Request actions",
        "step": "Step",
        "deadline": "Deadline",
        "revision_from": "Revision from",
        "upload_file": "Upload file",

        # --- metadata rows (entity_metadata) -----------------------------
        "meta_id_elabid": "ID / elabid",
        "meta_created": "Created",
        "meta_modified": "Modified",
        "meta_last_changed_by": "Last changed by",
        "meta_status": "Status",
        "meta_category": "Category",
        "meta_locked": "Locked",
        "meta_locked_by_since": "by {who} since {when}",
        "meta_timestamped": "Timestamped",
        "meta_custom_id": "Custom ID",
        "meta_rating": "Rating",

        # --- overview / index ---------------------------------------------
        "page_title": "GDPR disclosure - {name}",
        "doc_title": "GDPR data subject access request (Art. 15) - {name}",
        "subtitle_email_user": "Email: {email} · User ID: {uid} · created: {created}",
        "subtitle_last_login": "Last login: {last_login} · Export created: {exported}",
        "notice_title": "Notice:",
        "notice_body": (
            "This report contains personal data and is intended for the data "
            "subject only. Third-party content (co-authors, reviewer comments, "
            "names in audit logs) must be redacted before sharing (Art. 15(4) "
            "GDPR). Raw values such as password hashes, MFA secrets or tokens "
            "are deliberately not included - they are only listed as "
            "categories (see PDF)."
        ),
        "limitation_title": "API-Limitation:",
        "limitation_body": (
            "This report was created from the API only (1-click). The following "
            "data is NOT included and must be added via "
            "<code>scripts/gdpr_cli.sql</code> or the DB pipeline "
            "(<code>elab-gdpr-db --users {uid}</code>): audit_logs, authfail, "
            "changelog, api_keys, exports, todolist, sig_keys, favtags, and "
            "archived uploads (state=2, {archived} additional files). See "
            "LIMITATIONS.md in this package."
        ),
        "overview": "Overview",
        "account_teams": "Account & teams",
        "team": "Team",
        "id": "ID",
        "admin": "Admin",
        "owner": "Owner",
        "archived": "Archived",
        "notifications": "Notifications",
        "date": "Date",
        "category": "Category",
        "content": "Content",
        "read": "Read",
        "groups": "Groups",
        "group": "Group",
        "members": "Members",
        "procurement_requests": "Procurement requests",
        "requester": "Requester",
        "entry": "Entry",
        "quantity": "Quantity",
        "state": "State",
        "bookings": "Bookings",
        "period": "Period",
        "title": "Title",
        "resource": "Resource",
        "request_actions": "Request actions",
        "action": "Action",
        "target_user": "Target user",
        "entries": "Entries",
        "db_cli_only": "DB/CLI only (scripts/gdpr_cli.sql)",

        # --- summary cards -----------------------------------------------
        "card_experiments": "Experiments",
        "card_items": "Items",
        "card_templates": "Templates",
        "card_item_types": "Item types",
        "card_uploads": "Uploads",
        "card_notifications": "Notifications",
        "card_bookings": "Bookings",
        "card_groups": "Groups",
        "card_procurement": "Procurement",

        # --- DB appendix --------------------------------------------------
        "appendix_title": "DB appendix (audit trail, logins, changelog, keys)",
        "appendix_source_label": "Source:",
        "appendix_source_text": (
            " direct database export (no API key). Includes all uploads "
            "(active {active}, archived {archived}) and records that are not "
            "reachable via the API."
        ),
        "appx_audit_trail": "Audit trail",
        "appx_failed_logins": "Failed logins",
        "appx_changelog": "Changelog",
        "appx_api_keys": "API keys",
        "appx_exports": "Exports",
        "appx_todolist": "Todolist",
        "appx_sig_keys": "Sig keys",
        "appx_favorites": "Favorites",
        "appx_pins": "Pins",
        "appx_team_groups": "Team groups",
        "appx_storage_history": "Storage history",
        "appx_compounds": "Compounds",
        "appx_request_actions": "Request actions",
        "appx_procurement": "Procurement",
        "appx_notifications": "Notifications",
        "appx_entity_links": "Entity links",
        "appx_storage_assignments": "Storage assignments",
        "appx_compound_links": "Compound links",
        "appx_template_steps": "Template/type steps",
        "appx_third_party_comments": "Third-party comments on your entries",
        "appx_your_comments": "Your comments on other entries",
        "appx_name_mentions": "Name mentions in other users' comments",
        # generic col headers for appendix tables
        "col_date": "Date",
        "col_category": "Category",
        "col_requester": "Requester",
        "col_target": "Target",
        "col_body": "Body (truncated)",
        "col_attempt_time": "Attempt time",
        "col_type": "Type",
        "col_content": "Content",
        "col_id": "ID",
        "col_name": "Name",
        "col_created": "Created",
        "col_last_used": "Last used",
        "col_write": "Write",
        "col_state": "State",
        "col_format": "Format",
        "col_body_full": "Body",
        "col_sig_key_id": "Sig key ID",
        "col_entity_id": "Entity ID",
        "col_group_id": "Group ID",
        "col_storage_unit": "Storage unit",
        "col_old_parent": "Old parent",
        "col_new_parent": "New parent",
        "col_iupac": "IUPAC",
        "col_cas": "CAS",
        "col_action": "Action",
        "col_entity": "Entity",
        "col_qty": "Qty",
        "col_read": "Read",
        "col_item": "Item",
        "col_link": "Link",
        "col_storage": "Storage",
        "col_unit": "Unit",
        "col_compound": "Compound",
        "col_template": "Template",
        "col_step": "Step",
        "col_finished": "Finished",
        "col_user": "User",
        "col_comment": "Comment",
        "col_entry": "Entry",
        # appendix special notices
        "redact_before_sending": "Redact before sending (Art. 15(4)):",
        "appx_redact_notice": (
            "these are comments by OTHER users on your entries - they may "
            "contain third-party personal data."
        ),
        "appx_your_comments_notice": (
            "Your own statements on entries that belong to other users - only "
            "the comment itself is included, not the foreign entry's content."
        ),
        "appx_name_mentions_notice": (
            "comments by others that mention your name/email. Only the "
            "matching comment is shown, with other users' names redacted."
        ),
        "sig_fav_header": "Sig keys / Favorites",
        "fav_header": "Favorites",

        # --- PDF letter ----------------------------------------------------
        "pdf_title": "GDPR data subject access request (Art. 15) - Summary",
        "pdf_recipient_line": (
            "Email: {email} · User ID: {uid}<br/>Account created: {created} · "
            "Last login: {last_login} · Export: {exported}"
        ),
        "pdf_s1": "1. Categories of personal data processed",
        "pdf_s1_body": (
            "eLabFTW processes the following categories of personal data about "
            "you: (a) account data (name, email, internal organisation ID if "
            "set, team memberships, roles, login timestamps), (b) content you "
            "created (experiments, resources, templates, comments, revisions, "
            "steps, tags, links), (c) uploaded files, (d) bookings, "
            "notifications, group memberships, procurement requests, request "
            "actions, (e) log/security data (audit trail, login attempts - "
            "categories only, see 4)."
        ),
        "pdf_s2": "2. Scope of the copy",
        "pdf_s2_body": (
            "The full detail data is attached to this letter: (1) this "
            "summary letter (PDF), (2) an HTML explorer of all records "
            "(index.html), (3) the machine-readable raw data (JSON files) and "
            "(4) a ZIP archive containing the complete package. Overview of "
            "the data:"
        ),
        "pdf_count_experiments": "Experiments",
        "pdf_count_items": "Items (resources)",
        "pdf_count_templates": "Templates",
        "pdf_count_item_types": "Item types",
        "pdf_count_upload_files": "Upload files",
        "pdf_count_notifications": "Notifications",
        "pdf_count_bookings": "Bookings",
        "pdf_count_groups": "Groups",
        "pdf_count_procurement": "Procurement requests",
        "pdf_teams_roles": "Teams/roles: {teams}",
        "pdf_team_item": "{name} (admin: {admin}, owner: {owner}, archived: {archived})",
        "pdf_s3": "3. Purposes, recipients, retention",
        "pdf_s3_body": (
            "Purpose: electronic lab notebook for documenting and tracing "
            "research work. Recipients: other users with whom you share "
            "entries (the concrete recipients are visible from the shared "
            "entries in the annex); the hosting operator for operations "
            "(Art. 28 GDPR, data processing agreement). Retention: account "
            "data until account deletion/archiving; lab notebook content "
            "according to legal retention obligations (e.g. GxP, where "
            "applicable the retention periods of the German Commercial Code "
            "§ 257 HGB); audit/log data per the operator's retention "
            "schedule; backups rotate according to the backup policy. Source "
            "of the data: information you provided and content you created "
            "while using the service, plus system-generated records (login "
            "timestamps, audit trail, upload history) (Art. 15(1)(g) GDPR). "
            "Automated decision-making: no automated decision-making, "
            "including profiling, takes place (Art. 22 GDPR). Transfers: no "
            "transfer to third countries or international organisations takes "
            "place; recipients within the EEA only (Art. 15(1)(f) GDPR)."
        ),
        "pdf_s4": "4. Data not included (categories only)",
        "pdf_s4_body": (
            "The full detail data is contained in the annex (HTML explorer, "
            "JSON files, ZIP package). The following technical security values "
            "are deliberately NOT included: password hashes, MFA secrets, "
            "reset tokens, API key hashes and signing keys - they are stored "
            "hashed/encrypted only, cannot be used by you to exercise your "
            "rights, and are not handed out for security reasons (Art. 32 "
            "GDPR). "
            "{db_scope}"
            "{archived_line}"
            "Third-party portions of shared content may have been redacted "
            "(Art. 15(4) GDPR); if portions are redacted, we will name them "
            "on request."
        ),
        "pdf_s4_db_scope": (
            "The audit trail, failed login attempts, changelog, todolist, "
            "export history and favourites are included in this package "
            "(direct database export). "
        ),
        "pdf_s4_api_scope": (
            "Audit trail, failed login attempts, todolist, export history, "
            "favourites/pins and lock states are not retrievable via the API "
            "and can be supplied on request (database extract). "
        ),
        "pdf_s4_archived_db": "(included in this package). ",
        "pdf_s4_archived_api": "(not downloaded with the API). ",
        "pdf_s4_archived_line": "Archived uploads: {count} files are only listed as metadata ",
        "pdf_s5": "5. Your rights",
        "pdf_s5_body": (
            "Rectification (Art. 16), erasure (Art. 17 - subject to legal "
            "retention obligations), restriction (Art. 18), data portability "
            "(Art. 20), objection (Art. 21) and the right to lodge a "
            "complaint with a supervisory authority. This disclosure was "
            "provided within the time limit of Art. 12(3) GDPR from receipt "
            "of your request."
        ),
        "pdf_controller_label": "Controller under Art. 4(7) GDPR:",
        "pdf_controller_name": "Name / institution",
        "pdf_controller_address": "Address",
        "pdf_controller_contact": "Contact (e-mail / phone)",
        "pdf_controller_dpo": "Data protection officer",

        # --- LIMITATIONS.md ----------------------------------------------
        "limitations_md": (
            "# Limitations of this API export\n\n"
            "This package was created with the 1-click API pipeline "
            "(elab-gdpr, sysadmin API key). The following data is NOT "
            "included and must be added for a complete Art. 15 disclosure:\n\n"
            "- audit_logs, authfail, changelog, api_keys, exports, todolist,\n"
            "  sig_keys, favtags (DB-only, {db_counts})\n"
            "- archived uploads (state=2, {archived} files - metadata only "
            "here)\n\n"
            "Run the DB pipeline instead for everything in one go:\n\n"
            "    elab-gdpr-db --users {uid} --with-files\n\n"
            "Generated: {exported}\n"
        ),

        # --- CLI progress strings ------------------------------------------
        "cli_no_export": "No export found in {dir} - run the export first",
        "cli_built": "Built {ok}/{total} reports",
        "cli_report_for": "===== Report for {name} =====",
        "cli_html": "HTML: {path}",
        "cli_pdf": "PDF:  {path}",
        "cli_zip": "ZIP:  {path} ({size} KB)",
    },
    # German - full translation of the report UI (HTML + PDF + CLI).
    "de": {
        # --- generic -----------------------------------------------------
        "yes": "ja",
        "no": "nein",
        "none": "keine",
        "no_uploads": "keine Uploads",
        "back_to_overview": "← Zurück zur Übersicht",
        "no_title": "(kein Titel)",

        # --- html <lang> attribute ---------------------------------------
        "html_lang": "de",

        # --- entity page headings ---------------------------------------
        "metadata": "Metadaten",
        "content": "Inhalt",
        "tags": "Tags",
        "steps": "Schritte",
        "comments": "Kommentare",
        "revisions": "Versionen",
        "uploads": "Uploads",
        "request_actions": "Anfrage-Aktionen",
        "step": "Schritt",
        "deadline": "Frist",
        "revision_from": "Version vom",
        "upload_file": "Upload-Datei",

        # --- metadata rows ------------------------------------------------
        "meta_id_elabid": "ID / elabid",
        "meta_created": "Erstellt",
        "meta_modified": "Geändert",
        "meta_last_changed_by": "Zuletzt geändert von",
        "meta_status": "Status",
        "meta_category": "Kategorie",
        "meta_locked": "Gesperrt",
        "meta_locked_by_since": "von {who} seit {when}",
        "meta_timestamped": "Zeitgestempelt",
        "meta_custom_id": "Eigene ID",
        "meta_rating": "Bewertung",

        # --- overview / index ---------------------------------------------
        "page_title": "DSGVO-Auskunft - {name}",
        "doc_title": "DSGVO-Auskunftsersuchen (Art. 15) - {name}",
        "subtitle_email_user": "E-Mail: {email} · Benutzer-ID: {uid} · erstellt: {created}",
        "subtitle_last_login": "Letzter Login: {last_login} · Export erstellt: {exported}",
        "notice_title": "Hinweis:",
        "notice_body": (
            "Dieser Bericht enthält personenbezogene Daten und ist ausschließlich "
            "für die betroffene Person bestimmt. Inhalte Dritter (Koautoren, "
            "Reviewer-Kommentare, Namen in Audit-Logs) müssen vor der Weitergabe "
            "geschwärzt werden (Art. 15 Abs. 4 DSGVO). Rohwerte wie "
            "Passwort-Hashes, MFA-Geheimnisse oder Tokens sind bewusst nicht "
            "enthalten - sie werden nur als Kategorien aufgeführt (siehe PDF)."
        ),
        "limitation_title": "API-Einschränkung:",
        "limitation_body": (
            "Dieser Bericht wurde nur über die API erstellt (1-Klick). Die "
            "folgenden Daten sind NICHT enthalten und müssen über "
            "<code>scripts/gdpr_cli.sql</code> oder die DB-Pipeline "
            "(<code>elab-gdpr-db --users {uid}</code>) ergänzt werden: "
            "audit_logs, authfail, changelog, api_keys, exports, todolist, "
            "sig_keys, favtags sowie archivierte Uploads (state=2, {archived} "
            "weitere Dateien). Siehe LIMITATIONS.md in diesem Paket."
        ),
        "overview": "Übersicht",
        "account_teams": "Konto & Teams",
        "team": "Team",
        "id": "ID",
        "admin": "Admin",
        "owner": "Besitzer",
        "archived": "Archiviert",
        "notifications": "Benachrichtigungen",
        "date": "Datum",
        "category": "Kategorie",
        "content": "Inhalt",
        "read": "Gelesen",
        "groups": "Gruppen",
        "group": "Gruppe",
        "members": "Mitglieder",
        "procurement_requests": "Beschaffungsanträge",
        "requester": "Antragsteller",
        "entry": "Eintrag",
        "quantity": "Menge",
        "state": "Status",
        "bookings": "Buchungen",
        "period": "Zeitraum",
        "title": "Titel",
        "resource": "Ressource",
        "request_actions": "Anfrage-Aktionen",
        "action": "Aktion",
        "target_user": "Zielbenutzer",
        "entries": "Einträge",
        "db_cli_only": "Nur DB/CLI (scripts/gdpr_cli.sql)",

        # --- summary cards -----------------------------------------------
        "card_experiments": "Experimente",
        "card_items": "Ressourcen (Items)",
        "card_templates": "Vorlagen",
        "card_item_types": "Ressourcentypen",
        "card_uploads": "Uploads",
        "card_notifications": "Benachrichtigungen",
        "card_bookings": "Buchungen",
        "card_groups": "Gruppen",
        "card_procurement": "Beschaffung",

        # --- DB appendix --------------------------------------------------
        "appendix_title": "DB-Anhang (Audit-Trail, Logins, Changelog, Schlüssel)",
        "appendix_source_label": "Quelle:",
        "appendix_source_text": (
            " direkter Datenbankexport (ohne API-Key). Enthält alle Uploads "
            "(aktiv {active}, archiviert {archived}) und Datensätze, die über "
            "die API nicht erreichbar sind."
        ),
        "appx_audit_trail": "Audit-Trail",
        "appx_failed_logins": "Fehlgeschlagene Logins",
        "appx_changelog": "Changelog",
        "appx_api_keys": "API-Schlüssel",
        "appx_exports": "Exporte",
        "appx_todolist": "Aufgabenliste",
        "appx_sig_keys": "Signaturschlüssel",
        "appx_favorites": "Favoriten",
        "appx_pins": "Pins",
        "appx_team_groups": "Team-Gruppen",
        "appx_storage_history": "Lagerhistorie",
        "appx_compounds": "Verbindungen (Compounds)",
        "appx_request_actions": "Anfrage-Aktionen",
        "appx_procurement": "Beschaffung",
        "appx_notifications": "Benachrichtigungen",
        "appx_entity_links": "Verknüpfungen",
        "appx_storage_assignments": "Lagerzuordnungen",
        "appx_compound_links": "Compound-Verknüpfungen",
        "appx_template_steps": "Vorlagen-/Typschritte",
        "appx_third_party_comments": "Kommentare Dritter zu Ihren Einträgen",
        "appx_your_comments": "Ihre Kommentare zu fremden Einträgen",
        "appx_name_mentions": "Namensnennungen in Kommentaren anderer Nutzer",
        # generic col headers for appendix tables
        "col_date": "Datum",
        "col_category": "Kategorie",
        "col_requester": "Anfragesteller",
        "col_target": "Ziel",
        "col_body": "Inhalt (gekürzt)",
        "col_attempt_time": "Versuch (Zeitpunkt)",
        "col_type": "Typ",
        "col_content": "Inhalt",
        "col_id": "ID",
        "col_name": "Name",
        "col_created": "Erstellt",
        "col_last_used": "Zuletzt verwendet",
        "col_write": "Schreiben",
        "col_state": "Status",
        "col_format": "Format",
        "col_body_full": "Inhalt",
        "col_sig_key_id": "Signaturschlüssel-ID",
        "col_entity_id": "Entitäts-ID",
        "col_group_id": "Gruppen-ID",
        "col_storage_unit": "Lagereinheit",
        "col_old_parent": "Alter Standort",
        "col_new_parent": "Neuer Standort",
        "col_iupac": "IUPAC",
        "col_cas": "CAS",
        "col_action": "Aktion",
        "col_entity": "Entität",
        "col_qty": "Menge",
        "col_read": "Gelesen",
        "col_item": "Objekt",
        "col_link": "Verknüpfung",
        "col_storage": "Lager",
        "col_unit": "Einheit",
        "col_compound": "Compound",
        "col_template": "Vorlage",
        "col_step": "Schritt",
        "col_finished": "Erledigt",
        "col_user": "Benutzer",
        "col_comment": "Kommentar",
        "col_entry": "Eintrag",
        # appendix special notices
        "redact_before_sending": "Vor dem Versenden schwärzen (Art. 15 Abs. 4 DSGVO):",
        "appx_redact_notice": (
            "Dies sind Kommentare ANDERER Nutzer zu Ihren Einträgen - sie können "
            "personenbezogene Daten Dritter enthalten."
        ),
        "appx_your_comments_notice": (
            "Ihre eigenen Aussagen zu Einträgen anderer Nutzer - nur der Kommentar "
            "selbst ist enthalten, nicht der Inhalt des fremden Eintrags."
        ),
        "appx_name_mentions_notice": (
            "Kommentare anderer, die Ihren Namen/Ihre E-Mail erwähnen. Nur der "
            "passende Kommentar wird angezeigt, Namen anderer Nutzer sind geschwärzt."
        ),
        "sig_fav_header": "Signaturschlüssel / Favoriten",
        "fav_header": "Favoriten",

        # --- PDF letter ----------------------------------------------------
        "pdf_title": "DSGVO-Auskunftsersuchen (Art. 15) - Zusammenfassung",
        "pdf_recipient_line": (
            "E-Mail: {email} · Benutzer-ID: {uid}<br/>Konto erstellt: {created} · "
            "Letzter Login: {last_login} · Export: {exported}"
        ),
        "pdf_s1": "1. Kategorien der verarbeiteten personenbezogenen Daten",
        "pdf_s1_body": (
            "eLabFTW verarbeitet die folgenden Kategorien personenbezogener Daten "
            "über Sie: (a) Kontodaten (Name, E-Mail, ggf. interne "
            "Organisationskennung, Teammitgliedschaften, Rollen, "
            "Login-Zeitpunkte), (b) von Ihnen erstellte Inhalte (Experimente, "
            "Ressourcen, Vorlagen, Kommentare, Versionen, Schritte, Tags, "
            "Verknüpfungen), (c) hochgeladene Dateien, (d) Buchungen, "
            "Benachrichtigungen, Gruppenmitgliedschaften, Beschaffungsanträge, "
            "Anfrage-Aktionen, (e) Log-/Sicherheitsdaten (Audit-Trail, "
            "Login-Versuche - nur Kategorien, siehe 4)."
        ),
        "pdf_s2": "2. Umfang der Kopie",
        "pdf_s2_body": (
            "Die vollständigen Detaildaten sind diesem Schreiben beigefügt: "
            "(1) dieses zusammenfassende Schreiben (PDF), (2) ein HTML-Explorer "
            "aller Einträge (index.html), (3) die maschinenlesbaren Rohdaten "
            "(JSON-Dateien) sowie (4) ein ZIP-Archiv mit dem vollständigen "
            "Paket. Überblick über die Daten:"
        ),
        "pdf_count_experiments": "Experimente",
        "pdf_count_items": "Ressourcen (Items)",
        "pdf_count_templates": "Vorlagen",
        "pdf_count_item_types": "Ressourcentypen",
        "pdf_count_upload_files": "Upload-Dateien",
        "pdf_count_notifications": "Benachrichtigungen",
        "pdf_count_bookings": "Buchungen",
        "pdf_count_groups": "Gruppen",
        "pdf_count_procurement": "Beschaffungsanträge",
        "pdf_teams_roles": "Teams/Rollen: {teams}",
        "pdf_team_item": "{name} (Admin: {admin}, Besitzer: {owner}, archiviert: {archived})",
        "pdf_s3": "3. Zwecke, Empfänger, Speicherdauer",
        "pdf_s3_body": (
            "Zweck: elektronisches Laborbuch zur Dokumentation und Nachvollziehbarkeit "
            "der Forschung. Empfänger: andere Nutzer, mit denen Sie Einträge teilen "
            "(die konkreten Empfänger sind aus den geteilten Einträgen im Anhang "
            "ersichtlich); der Hosting-Betreiber für den Betrieb "
            "(Auftragsverarbeitung, Art. 28 DSGVO). Speicherdauer: Kontodaten bis "
            "zur Kontolöschung/-archivierung; Laborbuchinhalte gemäß gesetzlicher "
            "Aufbewahrungspflichten (z.B. GxP, soweit anwendbar die "
            "Aufbewahrungsfristen des Handelsgesetzbuchs § 257 HGB); Audit-/Logdaten "
            "gemäß den Aufbewahrungsfristen des Betreibers; Backups rotieren gemäß "
            "der Backup-Richtlinie. Datenquelle: die von Ihnen bereitgestellten "
            "Informationen und die von Ihnen bei der Nutzung erstellten Inhalte "
            "sowie systemgenerierte Aufzeichnungen (Login-Zeitpunkte, Audit-Trail, "
            "Upload-Historie) (Art. 15 Abs. 1 lit. g DSGVO). Automatisierte "
            "Entscheidungsfindung: Es findet keine automatisierte "
            "Entscheidungsfindung einschließlich Profiling statt (Art. 22 DSGVO). "
            "Übermittlung: Es findet keine Übermittlung in Drittländer oder an "
            "internationale Organisationen statt; Empfänger nur innerhalb des EWR "
            "(Art. 15 Abs. 1 lit. f DSGVO)."
        ),
        "pdf_s4": "4. Nicht enthaltene Daten (nur Kategorien)",
        "pdf_s4_body": (
            "Die vollständigen Detaildaten sind im Anhang enthalten (HTML-Explorer, "
            "JSON-Dateien, ZIP-Paket). Die folgenden technischen Sicherheitswerte "
            "sind bewusst NICHT enthalten: Passwort-Hashes, MFA-Geheimnisse, "
            "Reset-Tokens, API-Key-Hashes und Signaturschlüssel - sie werden nur "
            "gehasht/verschlüsselt gespeichert, sind für die Ausübung Ihrer Rechte "
            "nicht erforderlich und werden aus Sicherheitsgründen nicht ausgehändigt "
            "(Art. 32 DSGVO). "
            "{db_scope}"
            "{archived_line}"
            "Anteile Dritter an geteilten Inhalten wurden möglicherweise geschwärzt "
            "(Art. 15 Abs. 4 DSGVO); geschwärzte Anteile benennen wir auf Anfrage."
        ),
        "pdf_s4_db_scope": (
            "Audit-Trail, fehlgeschlagene Login-Versuche, Changelog, Aufgabenliste, "
            "Export-Historie und Favoriten sind in diesem Paket enthalten (direkter "
            "Datenbankexport). "
        ),
        "pdf_s4_api_scope": (
            "Audit-Trail, fehlgeschlagene Login-Versuche, Aufgabenliste, "
            "Export-Historie, Favoriten/Pins und Sperrzustände sind über die API "
            "nicht abrufbar und können auf Anfrage zur Verfügung gestellt werden "
            "(Datenbankextrakt). "
        ),
        "pdf_s4_archived_db": "(im Paket enthalten). ",
        "pdf_s4_archived_api": "(mit der API nicht heruntergeladen). ",
        "pdf_s4_archived_line": "Archivierte Uploads: {count} Dateien sind nur als Metadaten gelistet ",
        "pdf_s5": "5. Ihre Rechte",
        "pdf_s5_body": (
            "Berichtigung (Art. 16), Löschung (Art. 17 - vorbehaltlich gesetzlicher "
            "Aufbewahrungspflichten), Einschränkung der Verarbeitung (Art. 18), "
            "Datenübertragbarkeit (Art. 20), Widerspruch (Art. 21) sowie das Recht "
            "auf Beschwerde bei einer Aufsichtsbehörde. Diese Auskunft wurde "
            "innerhalb der Frist des Art. 12 Abs. 3 DSGVO nach Eingang Ihres "
            "Antrags erteilt."
        ),
        "pdf_controller_label": "Verantwortlicher im Sinne des Art. 4 Nr. 7 DSGVO:",
        "pdf_controller_name": "Name / Einrichtung",
        "pdf_controller_address": "Anschrift",
        "pdf_controller_contact": "Kontakt (E-Mail / Telefon)",
        "pdf_controller_dpo": "Datenschutzbeauftragte/r",

        # --- LIMITATIONS.md ----------------------------------------------
        "limitations_md": (
            "# Einschränkungen dieses API-Exports\n\n"
            "Dieses Paket wurde mit der 1-Klick-API-Pipeline (elab-gdpr, "
            "Sysadmin-API-Key) erstellt. Die folgenden Daten sind NICHT enthalten "
            "und müssen für eine vollständige Auskunft nach Art. 15 ergänzt werden:\n\n"
            "- audit_logs, authfail, changelog, api_keys, exports, todolist,\n"
            "  sig_keys, favtags (nur DB, {db_counts})\n"
            "- archivierte Uploads (state=2, {archived} Dateien - hier nur Metadaten)\n\n"
            "Führen Sie stattdessen die DB-Pipeline aus, um alles in einem Schritt "
            "zu erhalten:\n\n"
            "    elab-gdpr-db --users {uid} --with-files\n\n"
            "Erstellt: {exported}\n"
        ),

        # --- CLI progress strings ------------------------------------------
        "cli_no_export": "Kein Export in {dir} gefunden - zuerst den Export ausführen",
        "cli_built": "{ok}/{total} Berichte erstellt",
        "cli_report_for": "===== Bericht für {name} =====",
        "cli_html": "HTML: {path}",
        "cli_pdf": "PDF:  {path}",
        "cli_zip": "ZIP:  {path} ({size} KB)",
    },
    # Other languages - empty for now, English fallback via t().
    "fr": {},
    "es": {},
    "it": {},
    "pl": {},
}


def _lookup(lang: str, key: str) -> str:
    table = STRINGS.get(lang) or {}
    if key in table and table[key]:
        return table[key]
    return STRINGS["en"].get(key, key)


def t(lang: str, key: str, **fmt) -> str:
    """Translate ``key`` into ``lang`` (English fallback) and format.

    ``{placeholders}`` in the English string are replaced from kwargs. If a
    translated variant is missing, the English string is used for formatting
    too, so translations must use the same placeholders as the English entry.
    """
    value = _lookup(lang, key)
    if fmt:
        try:
            value = value.format(**fmt)
        except (KeyError, IndexError, ValueError):
            # Be safe: formatting a translated string that lacks a
            # placeholder must not crash the report.
            pass
    return value


def tt(lang: str, key: str, **fmt) -> str:
    """Like t() but HTML-escapes the formatted result (for attributes/text)."""
    return html.escape(t(lang, key, **fmt), quote=True)


def normalize_lang(lang: str | None, user_lang: str | None = None) -> str:
    """Resolve a --lang value to a supported code.

    - ``auto``: use the data subject's eLabFTW locale (``user.lang``),
      mapped via LOCALE_TO_LANG; fall back to "en".
    - anything else: lowercased, must be a known language code; fallback "en".
    """
    if not lang:
        return "en"
    lang = lang.strip().lower()
    if lang == "auto":
        if user_lang:
            mapped = LOCALE_TO_LANG.get(user_lang) or LOCALE_TO_LANG.get(
                user_lang.lower())
            if mapped:
                return mapped
        return "en"
    if lang in STRINGS:
        return lang
    # allow e.g. "de_DE" as a --lang value directly
    return LOCALE_TO_LANG.get(lang, "en")


def needs_ttf_font(lang: str) -> bool:
    """True when the report language needs a non-cp1252 font for the PDF.

    Helvetica (WinAnsi) covers German/French/Spanish/Italian/Portuguese/
    Dutch (ä ö ü ß é è à ç ñ …). Polish/Czech/etc. need a TTF fallback.
    """
    return lang not in {"en", "de", "fr", "es", "it", "pt", "nl"}
