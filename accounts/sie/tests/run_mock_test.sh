#!/usr/bin/env bash
# End-to-end test of the v4 scripts on a throw-away local PostgreSQL 16 (never touches stg or prod).
# Flow: mock (stg-like) -> 01 -> import CSV -> 02 -> 03 -> 04 (export == original?) -> 05 (every ops query runs)
#       -> 08 ops lists + ops workbook -> 99 rollback (back to baseline) -> 02 again -> 00 cleanup (back to baseline)
#       -> 01 guard with leftovers.
# Usage (from anywhere): bash accounts/sie/tests/run_mock_test.sh <path to Pacijenti_JOINED_Stomatologija_i_estetika.csv>
# Needs: PostgreSQL 16 binaries, python3 with pandas + openpyxl, and data/sie_full_v4.csv + data/Joined.csv.
#   Linux as root: /usr/lib/postgresql/16/bin, creates user postgres (original setup).
#   macOS / non-root: `brew install postgresql@16`; the server runs as the current user.
#   Overrides: PG_BIN=<dir with initdb/pg_ctl/psql>, PYTHON=<python with pandas> (default: repo .venv if present).
set -euo pipefail
ORIG="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
if [ -n "${PG_BIN:-}" ]; then B="$PG_BIN"
elif [ -x /usr/lib/postgresql/16/bin/initdb ]; then B=/usr/lib/postgresql/16/bin
elif command -v brew >/dev/null && [ -x "$(brew --prefix postgresql@16 2>/dev/null)/bin/initdb" ]; then B="$(brew --prefix postgresql@16)/bin"
else echo "PostgreSQL 16 not found: set PG_BIN or install it (brew install postgresql@16)" >&2; exit 1; fi
if [ -z "${PYTHON:-}" ]; then if [ -x "$REPO/.venv/bin/python" ]; then PYTHON="$REPO/.venv/bin/python"; else PYTHON=python3; fi; fi
export PATH="$B:$PATH"
D=$(mktemp -d /tmp/sie_v4_test.XXXX)
if [ "$(id -u)" = 0 ]; then
  id postgres >/dev/null 2>&1 || useradd -m postgres
  chown postgres "$D"
  as_pg(){ su postgres -c "$1"; }
else
  as_pg(){ sh -c "$1"; }
fi
as_pg "$B/initdb -D $D/data -U postgres -A trust -E UTF8 >/dev/null && $B/pg_ctl -D $D/data -o '-k $D -p 5499 -c listen_addresses=' -l $D/log -w start >/dev/null"
trap 'as_pg "$B/pg_ctl -D $D/data stop" >/dev/null 2>&1; rm -rf "$D"' EXIT
sleep 2
P="psql -h $D -p 5499 -U postgres -X -q -d t"
psql -h "$D" -p 5499 -U postgres -X -q -d postgres -c "create database t"
cp -r "$ROOT/sql" "$ROOT/data" "$D/"; if [ "$(id -u)" = 0 ]; then chown -R postgres "$D"; fi
"$PYTHON" "$ROOT/tests/make_mock.py" "$ROOT/data/sie_full_v4.csv" "$D/mock.sql" "$D/stg.sql"
cd "$D"
snap(){ $P -At -c "select 'patients='||(select count(*) from patient)||' visits='||(select count(*) from patient_visit)||' msgs='||(select count(*) from visit_msg)||' batches='||(select count(*) from visit_msg_sending_batch)||' linked='||(select count(*) from survey_response where visit_msg_id is not null)||' tickets='||(select count(*) from patient_ticket)"; }
run(){ echo "== $1"; $P -f "sql/$1" 2>&1 | grep -E "ERROR|NOTICE: +Using|SIE_LEGACY|^ *[0-9]+ *\|" | grep -v "does not exist, skipping" || true; }

$P -v ON_ERROR_STOP=1 -f mock.sql >/dev/null
BASE=$(snap); echo "baseline:        $BASE"
run 01_before_import.sql
$P -f stg.sql
$P -c "select count(*) total, count(*) filter (where row_kind='platform') platform, count(*) filter (where row_kind='legacy_invite') legacy_invite, count(*) filter (where row_kind='legacy_visit') legacy_visit from stg_sie_full"
run 02_load.sql
echo "== 03_validation.sql"; $P -f sql/03_validation.sql 2>&1 | grep -E "ERROR|^ " | grep -v -- "---"
$P --csv -f sql/04_export_original_csv.sql > export.csv
"$PYTHON" - "$ORIG" <<'EOF'
import sys, pandas as pd
a = pd.read_csv("export.csv", dtype=str, keep_default_na=False)
b = pd.read_csv(sys.argv[1], dtype=str, encoding="utf-8-sig", keep_default_na=False)
print("== 04 export identical to original file:", a.equals(b), f"({len(a)} rows)")
EOF
echo "== 05_ops_exports.sql (each query must run)"; $P -f sql/05_ops_exports.sql 2>&1 | grep -cE "^\(\d+ rows?\)|^\([0-9]+ row" | sed 's/^/   result sets: /'; $P -f sql/05_ops_exports.sql 2>&1 | grep ERROR || echo "   no errors"
echo "== 08_ops_lists.sql + 3_build_ops_workbook.py"
"$PYTHON" - <<'EOF'
# split 08 into its two queries (invites.csv, responses.csv), the way a person runs them one at a time
parts = [q.strip() for q in open("sql/08_ops_lists.sql").read().split(";\n") if "SELECT" in q]
assert len(parts) == 2, len(parts)
for name, q in zip(("08_invites", "08_responses"), parts):
    open(name + ".sql", "w").write(q + ";\n")
EOF
$P --csv -v ON_ERROR_STOP=1 -f 08_invites.sql > invites.csv
$P --csv -v ON_ERROR_STOP=1 -f 08_responses.sql > responses.csv
"$PYTHON" - <<'EOF'
import pandas as pd
i = pd.read_csv("invites.csv", dtype=str, keep_default_na=False)
r = pd.read_csv("responses.csv", dtype=str, keep_default_na=False)
l = i[i.source == "legacy"]
print(f"   invites.csv {len(i)} rows, responses.csv {len(r)} rows")
print(f"   legacy sent {len(l)} / delivered {l.status.str.startswith('DELIVERED').sum()} / responses {(l.responded == 'yes').sum()}   (expect 2692 / 2592 / 480)")
EOF
"$PYTHON" "$ROOT/scripts/3_build_ops_workbook.py" invites.csv responses.csv ops.xlsx --bi "$ROOT/data/Joined.csv" --source "mock test" 2>&1 | sed 's/^/   /'
run 99_rollback.sql;       echo "after rollback:  $(snap)  (baseline: $BASE)"
run 02_load.sql
run 00_cleanup_all.sql;    echo "after cleanup:   $(snap)  (baseline: $BASE)"
run 01_before_import.sql
$P -c "insert into visit_msg_sending_batch(account_id,trigger,processed_visits,processed_patients,created_messages,quarantine_blocked,ignored_visits) values (36,'legacy_import',0,0,0,0,'[]')" >/dev/null
echo "== 01 with leftovers (must refuse):"; $P -f sql/01_before_import.sql 2>&1 | grep -m1 ERROR
