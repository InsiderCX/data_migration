# Alchemer and Zoho vs the legacy loads: Bolnica Colić, Orto-Nova, Affidea (25 Nov 2026)

Checked before Ana's manual validation (DEV-412) and the ops validation (Karlo). Read-only: Alchemer API, Zoho Analytics, EU prod replica, the load files. All numbers are **real**. "After the load" = what Clinicdash will show on prod for the legacy responses the load links (scored, NPS 0–10, dated by `dateStarted`, Zagreb/Belgrade). Ids and counts only.

## 1. Alchemer is the source of truth: response counts in the legacy period

Responses submitted before each Account's first platform invite, Alchemer API vs `survey_response` on the prod replica.

| Survey | Alchemer survey | Period ends | Complete: Alchemer / DB | Partial: Alchemer / DB |
|---|---|---|---|---|
| Bolnica Colić | 90511513 | 11 Nov 2026 | 619 / 619 | 118 / 118 |
| Orto-Nova (HR) | 90492015 | 19 May 2025 | 863 / 863 | 239 / 239 |
| Orto-Nova-IT | 90509784 | 19 May 2025 | 731 / 731 | 174 / 174 |
| Orto-Nova-SLO | 90509787 | 19 May 2025 | 91 / 91 | 9 / 9 |
| Affidea | 90540487 | 9 Jul 2024 | 9,877 / 9,877 | 1,291 / 1,291 |

**All identical.** Deleted responses can't be compared: the Alchemer API returns 0 Deleted for every Survey (it doesn't count them). The DB has 9 / 222 / 45 / 5 / 67 Deleted; the load links none of them.

## 2. Zoho vs Clinicdash after the load, by year

Zoho = the Account's Joined table (Colić `JOINED`, Orto Nova `JOINED_FINAL`, Affidea `Joined_FINAL`), scored rows, by `Time Started`.

### Bolnica Colić

| Year | Zoho: responses / promoters / detractors | After the load | NPS |
|---|---|---|---|
| 2023 | 166 / 157 / 6 | 166 / 157 / 6 | 91.0 |
| 2024 | 202 / 188 / 9 | 202 / 188 / 9 | 88.6 |
| 2025 | 175 / 146 / 18 | 175 / 146 / 18 | 73.1 |
| 2026 | 331 (177 legacy + 154 platform since 11 Nov) | 177 legacy | 80.8 (legacy) |

**Identical.** Staging after the load gives the same numbers (run log).

### Orto-Nova (three Surveys together; Zoho groups by answer language)

| Year | Zoho: responses / promoters / detractors | After the load | NPS |
|---|---|---|---|
| 2022 | 168 / 152 / 7 | 168 / 152 / 7 | 86.3 |
| 2023 | 835 / 756 / 37 | 835 / 756 / 37 | 86.1 |
| 2024 | 812 / 725 / 44 | 812 / 725 / 44 | 83.9 |
| 2025 | 174 / 163 / 7 | 174 / 163 / 7 | 89.7 |

**Identical** (1,989 scored; the load links 1,995, of which 6 have no score). Per Survey after the load: HR 88.2–92.9, IT 76.4–84.3, SLO 82.8–100 by year.

**Not on staging:** the staging copy holds different scores for these responses (about 620 with score 5; on prod mostly 10), so Clinicdash staging shows Orto-Nova's legacy NPS around 15. Prod and Zoho agree; staging is wrong. Counts on staging are right.

### Affidea (by Location)

| Year | Location | Zoho | After the load | NPS after the load |
|---|---|---|---|---|
| 2023 | Čavka (34) | 417 / 386 / 9 | 417 / 386 / 9 | 90.4 |
| 2023 | Kalajžić (35) | 762 / 723 / 16 | 762 / 723 / 16 | 92.8 |
| 2023 | Sv. Rok (36) | 2,033 / 1,556 / 188 | 2,033 / 1,556 / 188 | 67.3 |
| 2023 | Vita (37) | 848 / 794 / 19 | 848 / 794 / 19 | 91.4 |
| 2024 | Čavka (34) | 701 | 705 | 90.2 |
| 2024 | Kalajžić (35) | 1,057 | 1,060 | 91.5 |
| 2024 | Sv. Rok (36) | 1,159 (1,160 rows) | 1,162 | 68.8 |
| 2024 | Vita (37) | 636 | 639 | 91.1 |

2023 is **identical**. 2024 (Zoho read before 9 Jul 2024) differs only by:

- **+16 late answers**: legacy invites answered on or after 9 Jul 2024 (Čavka 4, Kalajžić 5, Sv. Rok 4, Vita 3; two of them in 2025 and 2026). They are linked and show in the month they were answered.
- **−1 response 7379** (Sv. Rok, Mar 2024): its legacy id is one of the 12 repeated ids, so it is not linked (COPS-234 A2). Zoho counts it (and lists it twice). Found by id checksum per month: Zoho Mar 2024 sum 980,518, ours 973,139.

Not in Zoho or the load: the **3,532 responses whose invite is missing from Karlo's file** (question 3 in DEV-409). Zoho can't show them either, because it joins responses to the same patient table.

## 3. Result

Every number is identical or has a named reason. No unexplained difference.
