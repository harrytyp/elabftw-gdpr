# DSGVO: Rechtliche Einordnung der Auskunft (Art. 15)

Zusammenfassung der Behörden-/Rechtsprechungslinie. **Keine Rechtsberatung** —
bei einem echten Begehren mit Streitpotenzial den Datenschutzbeauftragten
einbeziehen.

## Grundsatz: Auskunft ≠ Daten-Dump

Die Auskunft ist ein abgestuftes Transparenzrecht:

1. Bestätigung, ob Daten verarbeitet werden (ggf. **Negativauskunft**)
2. Pflichtangaben nach Art. 15(1): Zwecke, Kategorien, Empfänger, Speicherdauer,
   Herkunft, automatisierte Entscheidungen, Drittland-Garantien, Rechte-Hinweise
3. **Kopie der den Anfragenden betreffenden Daten in verständlicher Form** (Art. 15(3))

Wer „alles was technisch geht" rausgibt, macht zwei Fehler: Drittdaten-Leak
(Art. 15(4)) und unverständliche Form (Formfehler).

## Fünf Filterfragen vor jedem Export

1. **Betrifft es die Person?** Nur Daten, die sie identifizierbar machen.
2. **Stecken Daten Dritter drin?** Schwärzen oder Zusammenfassung (Art. 15(4)).
   In kollaborativen eLabFTW-Entries fast immer der Fall.
3. **Ist es eine verständliche Information (Art. 12(1), 15(3))?** Ein bcrypt-Hash
   oder TOTP-Secret ist das nicht → Kategorie nennen, Rohwert behalten
   (zugleich Sicherheitsgebot, Art. 32).
4. **Interne Notiz ohne Personenbezug?** Nicht auskunftspflichtig (EuGH C-141/12,
   C-372/12 „YS"): reine Rechts-/Fachbewertung in Vermerken fällt nicht darunter.
5. **Kopie des Dokuments geschuldet?** Nein — EuGH C-487/21 („CRIF",
   04.05.2023): geschuldet ist die Kopie der **Daten**; eine strukturierte,
   vollständige Zusammenfassung genügt. Roh-SQL-Dumps sind weder nötig noch
   richtig (unverständlich + Drittdaten).

## Was MUSS in die Auskunft (auch die unbequemen Punkte)

- Stammdaten + Account-Metadaten (letzter Login, Rollen, Gültigkeit)
- Eigene Inhalte — **auch berufliche** (EuGH C-434/16 „Nowak": keine
  Bagatellgrenze; Prüfungs-/Arbeitsdaten sind personenbezogen)
- **Daten über die Person in fremden Entries** (Kommentare anderer über sie) —
  EuGH C-252/21 („Meta"): Auskunft umfasst auch Daten aus Drittquellen
- Login-Zeitpunkte/-IPs, falls gespeichert (EuGH C-582/14 „Breyer": IPs sind
  personenbezogen) — in der eLabFTW-DB liegen **keine** IPs, nur ggf. in
  Webserver-Logs
- Audit-Trail-Einträge, die die Person betreffen — **aber**: § 34 BDSG erlaubt
  Einschränkungen bei Protokollierungsdaten (Einzelfallprüfung), und
  Dritt-Anteile („wer hat was geändert") sind zu schwärzen
- Notifications, Export-Historie, Bestellanfragen, fehlgeschlagene Logins

## Was NICHT rausgegeben wird

- Daten Dritter (Art. 15(4)) — auch nicht in „eigenen" Entries
- Passwort-Hash, MFA-Secret, Reset-Token, API-Key-Hashes, Signatur-Privatkeys,
  Geräte-/Session-Tokens
- Interne Vermerke ohne Personenbezug (EuGH YS)
- Backups: Kategorie + Rotationsdauer nennen, keine Durchsuchungspflicht
- Geschäftsgeheimnisse/Know-how: prägen die Form, nie die komplette Verweigerung
  (DSK-Kurzpapier Nr. 6)
- Unumkehrbar anonymisierte oder gelöschte Daten → Negativauskunft genügt

## Prozess

- **Identität prüfen (Art. 12(6)):** Antwort an die **registrierte E-Mail-Adresse
  des Accounts**, nicht an die Anfrage-Adresse.
- **Frist:** 1 Monat ab Identitätsklärung (Art. 12(3)); bei großem Umfang +2
  Monate mit Begründung; ErwGr. 63 erlaubt, bei sehr großen Beständen eine
  Präzisierung zu verlangen.
- **Selbstbedienung:** Hat die Person noch Account-Zugriff, ist der eigene
  Profil-Export die von der DSK bevorzugte Lösung (ErwGr. 63) — es werden nur
  die Daten ergänzt, die sie selbst nicht sieht (Logs, Stammdaten-Historie).
- **Form:** lesbares Dokument (PDF) + maschinenlesbar bei elektronischer
  Anfrage (Art. 15(3) S. 2) — ELN/ZIP-Export ist dafür geeignet.
- **Kosten:** erste Kopie gratis; weitere Kopien und offenkundig exzessive
  Anträge dürfen kosten (Art. 12(5)) — Beweislast beim Verantwortlichen.
- **Dokumentieren (Art. 5(2)):** was geprüft, geliefert, geschwärzt wurde und
  warum.

## Sonderfall eLabFTW / Laborbuch

- **Timestamped PDFs** sind signiert und unveränderlich — für die Auskunft
  unproblematisch (liefern), für die Löschung (Art. 17) relevant:
  Aufbewahrungspflichten (GxP, § 257 HGB) können die Löschung verhindern
  (Art. 17(3)(b)) — Anonymisierung als Mittelweg. Die Position des eLabFTW-
  Entwicklers dazu: [Issue #3731](https://github.com/elabftw/elabftw/issues/3731).
- **SAML/LDAP:** der IdP verarbeitet ebenfalls Daten — die Auskunft muss ggf.
  auch dorthin.

## Quellen

- DSK Kurzpapier Nr. 6 „Auskunftsrecht der betroffenen Person, Art. 15 DS-GVO"
  (Stand 17.12.2018): https://www.datenschutzkonferenz-online.de/media/kp/dsk_kpnr_6.pdf
- EuGH, 04.05.2023, C-487/21 (CRIF): https://dejure.org/dienste/vernetzung/rechtsprechung?Gericht=EuGH&Datum=04.05.2023&Aktenzeichen=C-487%2F21
- EuGH, 20.12.2017, C-434/16 (Nowak)
- EuGH, 17.07.2014, C-141/12 + C-372/12 (YS)
- EuGH, 04.07.2023, C-252/21 (Meta)
- EuGH, 19.10.2016, C-582/14 (Breyer)
- eLabFTW Issue #3731 „Audit trail and GDPR": https://github.com/elabftw/elabftw/issues/3731
