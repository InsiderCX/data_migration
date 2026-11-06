# Arcadia legacy import

Import of the pre-platform history of **Arcadia** (EU, `insider-prod`), so Clinicdash shows Jun 2023 – 23 Apr 2025 like any other period, and the clinic's original file can be exported back exactly.

| | |
|---|---|
| Linear | [DEV-162](https://linear.app/insidercx/issue/DEV-162/upload-the-legacy-data) · plan: [`docs/plans/2026-11-03_videntis-arcadia-apolonija.md`](../../docs/plans/2026-11-03_videntis-arcadia-apolonija.md) |
| Load code | `ARCADIA_LEGACY_V1` |
| Account / Location / Survey | 45 / 78 / 27 on EU prod. Scripts resolve them from Alchemer survey **90534273** |
| Owner | Ana (ana@insidercx.com) |
| Status | **Loaded on EU staging 3 Nov 2026** (mock sending batch 13089), validated, export identical, rollback tested. Run log: [`runs/2026-11-03_staging.md`](runs/2026-11-03_staging.md). Next: ops SQL (05–08), ops sign-off |

All numbers below are **real**, read from the EU prod replica or the input files on 3 Nov 2026, unless marked estimated.

## 1. Inputs

| File | What it is | SHA-256 |
|---|---|---|
| `Pacijenti_Joined_Arcadia.csv` | 13,595 rows + header, 17 columns. 6,497 rows **with** `visit_date` are platform-era invites (`id` = `visit_msg.id`, uuid). 7,098 rows **without** `visit_date` are legacy rows with a numeric id | `2beffde7f71484f20278273dbc845ef607b5f2dc7bcc4e82abe008db4356c109` |
| `Survey_responses_Arcadia.csv` | Alchemer export joined with patient fields: 2,424 rows, but only **2,331 distinct responses**. 93 responses appear twice because their sguid matches two clinic rows (see §3) | `8066d05cae0541c70fe1f7da26f92d51b65cf0426f400d9355f8f19a55d1d0b7` |

Columns compared with SIE: the 15 base columns plus `sent_at` and `location` (filled only on platform rows). No `age`. `comment` is empty on every row.

Both files contain Patient PII. They live in `data/` (git-ignored).

## 2. Facts that shape the build

1. **Region:** EU only (no match on UK).
2. **Dates are day-first.** `Time Started` and `visit_date` are `DD/MM/YYYY HH:MM:SS`, Europe/Zagreb local. Checked against `survey_response."dateStarted"` for 5 response ids: all identical in Zagreb time.
3. **Legacy rows have a real `year_of_birth`** (7,085 of 7,098). Nothing to derive. No `language_code` on legacy rows: all get the HR template.
4. **Template:** SURVEY_INVITE 114 HR (the only one).
5. **Legacy period:** responses with numeric sguids run 29 Jun 2023 – Apr 2025. Platform's first invite: 24 Apr 2025. One legacy response started later (May 2026).
6. **Legacy id schemes:** `10xx` (4 digits), `10xxx`–`11xxx` (5 digits), `11` + sequence (6 digits, 111000–116819, Nov 2023 – Apr 2025).

## 3. Reused legacy ids (open item A1)

- **289 legacy ids appear on two clinic rows**, each time for a **different Patient** (different name and phone in all 289; same doctor in 58).
- All 289 are 5-digit ids in **10113–10467**. Their responses run from Jul 2023 to Apr 2025, while neighbouring ids cover a few months. This points to **two id schemes that collided** (an id reused for a second Patient), not to a copied row.
- **93 of the 289 have a response** (one response each). The survey export joined that response to both Patient rows, which is why it shows 186 rows.
- **Which Patient a response belongs to can't be read from the files.** The phone in the survey export comes from the join, so it can't decide. The dates of nearby rows separate only 2 of 93.

Without a decision, these 93 responses stay unlinked. Both Patient rows are still imported as visits.

## 4. Unlinked Survey Responses (1,092)

| Group | Count | Linkable? |
|---|---|---|
| Numeric sguid, id on exactly one clinic row | **979** | yes |
| Numeric sguid, id on two clinic rows (reused) | 93 | open item A1 |
| Numeric sguid, id not in the clinic file (`102`, two test-like) | 3 | no |
| Empty sguid (one dated 1 Jan 1970) | 15 | no |
| Test sguid | 2 | no |
| **Total** | **1,092** | **979 (+ up to 93)** |

## 5. Platform benchmarks (initial invites sent 24 Apr 2025 – 3 Nov 2026)

| Benchmark | Value |
|---|---|
| Initial invites sent / delivered | 6,536 / 5,765 |
| Delivery rate | 88.2% |
| Responses linked / response rate (over delivered) | 1,270 / 22.0% |
| Visit → send median | 26.2 h |
| Send → response median | 1.05 h |
| Most common send hour (Zagreb) | 16:00 |
| Reminders | none |
| Quarantine / age limit | 90 days / 18 |
| Sending | `INFOBIP_SMS_MAIN`, sender `Arcadia`; SMS status names as SIE |
| Baseline on prod: Patients / Patient Visits / Patient Tickets | 5,976 / 10,053 / 0 |

## 6. Estimation check (decision 7: Spearman ≥ 0.95)

Legacy id vs response start, all 1,072 responded legacy rows: **0.992, passes.**

| Id group | Responses | Spearman | Period |
|---|---|---|---|
| 4 digits `10…` | 33 | 0.590 (weak) | Jun – Aug 2023 |
| 5 digits `10…` (includes the reused ids) | 131 | 0.574 (weak) | Jul 2023 – Apr 2025 |
| 5 digits `11…` | 74 | 0.959 | Sep – Dec 2023 |
| 6 digits `11…` | 833 | 0.997 | Nov 2023 – Apr 2025 |

## 7. Open items

| # | Item | Who |
|---|---|---|
| A1 | 289 reused ids, 93 responses on them: which Patient each response belongs to | Ana decides (possibly the clinic knows the second scheme) |
| A2 | Send dates for non-responded rows in the weak `10…` groups (Jun 2023 onward) | Decide in step 2 |

## Step 2: load file (built 3 Nov 2026)

```bash
python3 -I scripts/1_build_load_file.py data/Pacijenti_Joined_Arcadia.csv data/db_unlinked_responses_2026-11-03.csv data/arcadia_full_v1.csv
```

| | |
|---|---|
| Load file | `data/arcadia_full_v1.csv`, SHA-256 `27c75d5da82a9132ba6758003859d4744da1515c96cf56227552651e757fa44b` |
| Row kinds | 13,595 rows: 6,497 platform / 5,255 legacy_invite / 1,843 legacy_visit |
| Responses linked (real) | 979 (the 93 on reused ids stay unlinked, decision 13) |
| Original columns | `raw_*`, values identical; 101 lines differ only in quoting |
| Year of birth | the file's real `year_of_birth` (7,085 rows) |

Responses come from the prod replica (`data/db_unlinked_responses_2026-11-03.csv`), not from the survey export, because the DB has linkable responses the export lacks.

**Legacy period, estimated** (sent, delivered and send dates are estimates; responses are real):

| Period | Sent (est.) | Delivered (est.) | Responses (real) | Response rate (est.) | Platform delivery / response rate (real) |
|---|---|---|---|---|---|
| 29 Jun 2023 – 4 Feb 2025 | 5,255 | 4,761 (90.5%) | 979 | 20.6% | 88.2% / 22.0% |

- Invite replay on platform data: recall 89.4% (−4.1%) with the age rule 18. Passes decision 7 (≥ 85%).
- Legacy rows without a phone are invites only when a real response proves it (decision 15).
- Median estimated invites per send day: 10 (busiest 83).
- The 578 rows on reused ids are flagged `sguid_reused`: they can get an invite, but the sguid is never put in the link table.
- Send-date method differs from SIE in two ways (check C10): dates are interpolated between isotonic block midpoints instead of steps, and id schemes with Spearman < 0.95 get the anchors' send-time quantiles by id rank. Weekend dates move to Monday.
