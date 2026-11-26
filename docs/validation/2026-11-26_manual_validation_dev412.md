# Manual validation on staging: Bolnica Colić, Orto-Nova, Affidea (26 Nov 2026)

DEV-412, done 26 Nov 2026. Ana checked Clinicdash staging and Zoho. Claude compared Zoho (`queryData` on the Joined tables), the EU prod replica, EU staging (one read-only query, with Ana's permission) and the load files, by response id. Ids and counts only. All numbers are **real** unless marked estimated. Ops sign-off: COPS-383.

## Bolnica Colić

| Where | Responses | Why |
|---|---|---|
| Clinicdash staging | 720 | Legacy responses the load links |
| Zoho, all time | 874 | 720 legacy + 154 platform answers from 11–22 Nov 2026 (114 Complete, 40 Partial), newer than the staging copy (28 Sep 2026) |
| Zoho, Feb 2023 – Apr 2026 | **720** | Same as staging (Ana) |

## Orto-Nova

- Zoho `JOINED_FINAL`, Oct 2023: 88 responses, 79 promoters, 5 detractors (NPS 84.1). The load: the same.
- Legacy NPS on production after the load: **85.5** (1,989 scored: 1,796 promoters, 95 detractors). Staging still shows about 15 (staging copy's scores).

## Affidea

**Zoho vs the load, day by day.** Zoho `Joined_FINAL` (distinct Response ID per day, by `Time Started`) vs the prod replica's `"dateStarted"` (Zagreb) of the responses the load links, 1 May 2023 – 8 Jul 2024: **356 of 357 days identical**. The only difference is 11 Mar 2024 (Zoho 21, load 20), response 7379 (repeated legacy id, not linked, COPS-234 A2). The 16 answers after 8 Jul 2024 are the known late answers.

**Nov 2023 per Location** (Zoho = the load): Čavka 109 / 102 / 2, Kalajžić 197 / 185 / 6, Sv. Rok 324 / 246 / 39, Vita 236 / 221 / 6 (responses / promoters / detractors).

**2 Apr 2024.** 85 live responses in the database. Zoho 30, the load 30: the same Response IDs. The other 55 have no invite in Karlo's file (part of the 3,532). On staging all 30 start on 2 Apr.

**Message performance is not comparable with Zoho.** It dates legacy answers by `visit_msg.sent_at`, which is **estimated** for legacy invites, and "Completed" counts `Complete` only. 2 Apr 2024: General dashboard 30; Message performance Responses 29 (response 8072 has an estimated send on 1 Apr), Completed 25 (4 Partial). Over the legacy period 982 of 7,628 responses fall on another day than their estimated send. Per day, Completed differs from the start-date count by a median of 2 (max 25); 38 of 364 days are equal.

| Month | Started (General dashboard = Zoho) | Message performance Responses | Message performance Completed |
|---|---|---|---|
| 2023-11 | 866 | 872 | 797 |
| 2024-01 | 691 | 689 | 588 |
| 2024-03 | 512 | 504 | 420 |
| 2024-04 | 549 | 547 | 473 |
| 2024-06 | 598 | 597 | 495 |

**A Zoho view export is not the Zoho table.** Ana's export for Apr 2024 had 541 responses. The `Joined_FINAL` table has 549. The 8 missing (Response IDs 8092, 8360, 8498, 8590, 8676, 8677, 8733, 8861) are normal rows (April dates, matched, scored, Location set). The old dashboard's 1,036 for Mar–Apr 2024 (table: 1,062) is the same effect. Chart filters can't be read with the Zamera token (error 8540).

**Kalajžić, Apr 2024: staging 169, production and Zoho 168.** Response 8060 (sguid 1042996, Partial) is the same row (`survey_response.id` 20341) on both. On staging `"dateStarted"` is 2 Apr 2024 15:43; on production and in Zoho it is 4 Nov 2026 20:00. The response was reopened after the staging copy (28 Sep 2026). Staging-only; nothing to fix.

## Result

Every difference between Zoho and Clinicdash has a named reason. Compare legacy data on the General dashboard or NPS Trends, never on Message performance.
