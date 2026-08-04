# GDPR: Legal framing of the disclosure (Art. 15)

Summary of the supervisory-authority and case-law line. **Not legal advice** —
for a real request with dispute potential, involve the data protection officer.

## Principle: disclosure ≠ data dump

The disclosure is a graduated transparency right:

1. Confirmation whether data is processed (if not: **negative disclosure**)
2. Mandatory information under Art. 15(1): purposes, categories, recipients,
   retention period, source, automated decision-making, third-country
   safeguards, rights notice
3. **A copy of the data concerning the requester in an intelligible form**
   (Art. 15(3))

Handing out "everything technically retrievable" makes two mistakes: leaking
third-party data (Art. 15(4)) and an unintelligible form (formal defect).

## Five filter questions before any export

1. **Does it concern the person?** Only data that makes them identifiable.
2. **Does it contain third-party data?** Redact or summarise (Art. 15(4)).
   Almost always the case in collaborative eLabFTW entries.
3. **Is it an intelligible piece of information (Art. 12(1), 15(3))?** A bcrypt
   hash or TOTP secret is not → state the category, keep the raw value (also
   a security requirement, Art. 32).
4. **Internal note without personal reference?** Not disclosable (CJEU C-141/12,
   C-372/12 "YS"): pure legal/professional assessment in memos is not covered.
5. **Is a copy of the document owed?** No — CJEU C-487/21 ("CRIF",
   04.05.2023): what is owed is a copy of the **data**; a structured, complete
   summary suffices. Raw SQL dumps are neither required nor correct
   (unintelligible + third-party data).

## What MUST be in the disclosure (including the uncomfortable bits)

- Account data + metadata (last login, roles, validity)
- Own content — **including professional content** (CJEU C-434/16 "Nowak":
  no de-minimis threshold; exam/work data is personal data)
- **Data about the person in other people's entries** (e.g. comments about
  them) — CJEU C-252/21 ("Meta"): disclosure also covers data from third
  sources
- Login timestamps/IPs, if stored (CJEU C-582/14 "Breyer": IPs are personal
  data) — the eLabFTW DB stores **no** IPs, only possibly webserver logs
- Audit-trail entries concerning the person — **but**: § 34 BDSG allows
  restrictions for log/protocol data (case-by-case), and third-party parts
  ("who changed what") must be redacted
- Notifications, export history, procurement requests, failed logins

## What is NOT handed out

- Third-party data (Art. 15(4)) — even inside "own" entries
- Password hash, MFA secret, reset token, API key hashes, signing private
  keys, device/session tokens
- Internal memos without personal reference (CJEU YS)
- Backups: state category + rotation, no obligation to search them
- Trade secrets/know-how: shape the form, never full refusal
  (DSK position paper No. 6)
- Irreversibly anonymised or deleted data → negative disclosure suffices

## Process

- **Verify identity (Art. 12(6)):** send the reply to the **registered email
  address of the account**, not to the request address.
- **Deadline:** 1 month from identity verification (Art. 12(3)); +2 months
  with justification for complex cases; Recital 63 allows asking for
  specification for very large inventories.
- **Self-service:** if the person still has account access, their own profile
  export is the DSK-preferred solution (Recital 63) — only the data they
  cannot see themselves (logs, account history) needs to be added.
- **Form:** readable document (PDF) + machine-readable for electronic requests
  (Art. 15(3) sentence 2) — the ELN/ZIP export is suitable.
- **Costs:** first copy free; further copies and manifestly excessive requests
  may be charged (Art. 12(5)) — burden of proof on the controller.
- **Document (Art. 5(2)):** what was checked, delivered, redacted and why.

## eLabFTW / lab notebook specifics

- **Timestamped PDFs** are signed and immutable — unproblematic for the
  disclosure (just provide them), relevant for erasure (Art. 17):
  retention obligations (GxP, § 257 HGB) can block deletion
  (Art. 17(3)(b)) — anonymisation as middle ground. The eLabFTW
  maintainer's position: [issue #3731](https://github.com/elabftw/elabftw/issues/3731).
- **SAML/LDAP:** the IdP processes data too — the disclosure may need to
  cover it as well.

## Sources

- DSK position paper No. 6 "Auskunftsrecht der betroffenen Person, Art. 15
  DS-GVO" (as of 17.12.2018):
  https://www.datenschutzkonferenz-online.de/media/kp/dsk_kpnr_6.pdf
- CJEU, 04.05.2023, C-487/21 (CRIF):
  https://dejure.org/dienste/vernetzung/rechtsprechung?Gericht=EuGH&Datum=04.05.2023&Aktenzeichen=C-487%2F21
- CJEU, 20.12.2017, C-434/16 (Nowak)
- CJEU, 17.07.2014, C-141/12 + C-372/12 (YS)
- CJEU, 04.07.2023, C-252/21 (Meta)
- CJEU, 19.10.2016, C-582/14 (Breyer)
- eLabFTW issue #3731 "Audit trail and GDPR":
  https://github.com/elabftw/elabftw/issues/3731
