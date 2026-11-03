#!/usr/bin/env bash
# End-to-end test of one Account's rendered SQL on a throw-away local PostgreSQL 16 (never touches stg or prod).
# Flow: mock (prod-like, SIE already loaded) -> 01 -> import load file -> count -> 02 -> checks -> 03 -> 04 (export == original?)
#       -> 99 rollback (back to baseline) -> 01 + 02 again -> 01 must refuse (already loaded).
# Usage: bash tools/legacy_mock/run_mock_test.sh accounts/<account> <path to the original clinic csv>
# Needs: PostgreSQL 16 binaries (brew install postgresql@16, or PG_BIN=...), python with pandas (repo .venv if present).
set -euo pipefail
ACC_DIR="$(cd "$1" && pwd)"
ORIG="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -n "${PG_BIN:-}" ]; then B="$PG_BIN"
elif [ -x /usr/lib/postgresql/16/bin/initdb ]; then B=/usr/lib/postgresql/16/bin
elif command -v brew >/dev/null && [ -x "$(brew --prefix postgresql@16 2>/dev/null)/bin/initdb" ]; then B="$(brew --prefix postgresql@16)/bin"
else echo "PostgreSQL 16 not found: set PG_BIN or install it (brew install postgresql@16)" >&2; exit 1; fi
if [ -z "${PYTHON:-}" ]; then if [ -x "$REPO/.venv/bin/python" ]; then PYTHON="$REPO/.venv/bin/python"; else PYTHON=python3; fi; fi
SLUG=$("$PYTHON" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['slug'])" "$ACC_DIR/sql_config.json")
LOAD=$("$PYTHON" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['load_file'])" "$ACC_DIR/sql_config.json")
D=$(mktemp -d "/tmp/${SLUG}_legacy_test.XXXX")
PORT=$((5400 + RANDOM % 90))
"$B/initdb" -D "$D/data" -U postgres -A trust -E UTF8 >/dev/null
"$B/pg_ctl" -D "$D/data" -o "-k $D -p $PORT -c listen_addresses=" -l "$D/log" -w start >/dev/null
trap '"$B/pg_ctl" -D "$D/data" stop >/dev/null 2>&1; rm -rf "$D"' EXIT
P="$B/psql -h $D -p $PORT -U postgres -X -q -d t"
"$B/psql" -h "$D" -p "$PORT" -U postgres -X -q -d postgres -c "create database t"
cp -r "$ACC_DIR/sql" "$D/"
"$PYTHON" -I "$REPO/tools/legacy_mock/make_mock.py" "$ACC_DIR" "$D/mock.sql" "$D/exp.json"
cd "$D"
FAIL=0
check(){ if [ "$2" = "$3" ]; then echo "   ok   $1: $2"; else echo "   FAIL $1: got $2, expected $3"; FAIL=1; fi; }
snap(){ $P -At -c "select 'patients='||(select count(*) from patient)||' visits='||(select count(*) from patient_visit)||' msgs='||(select count(*) from visit_msg)||' batches='||(select count(*) from visit_msg_sending_batch)||' linked='||(select count(*) from survey_response where visit_msg_id is not null)||' map='||(select count(*) from legacy_invite_map)||' src='||(select count(*) from legacy_source_row)"; }
run(){ echo "== $1"; $P -v ON_ERROR_STOP=1 -f "sql/$1" 2>&1 | grep -E "ERROR|NOTICE: +Using|_LEGACY_V|^ *[0-9]+ *\|" | grep -v "does not exist, skipping" || true; }
X(){ "$PYTHON" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['expect'][sys.argv[2]])" "$ACC_DIR/sql_config.json" "$1"; }
E(){ "$PYTHON" -I -c "import json,sys; v=json.load(open(sys.argv[1]))[sys.argv[2]]; print('' if v is None else v)" exp.json "$1"; }

$P -v ON_ERROR_STOP=1 -f mock.sql >/dev/null
BASE=$(snap); echo "baseline:       $BASE"
run 01_before_import.sql
$P -c "\\copy stg_${SLUG}_full FROM '$ACC_DIR/data/$LOAD' CSV HEADER NULL ''"
check "staging rows" "$($P -At -c "select count(*) from stg_${SLUG}_full")" "$(X rows)"
run 02_load.sql
B_ID=$($P -At -c "select sending_batch_id from legacy_sending_batch where code like '%_LEGACY_V1'")
echo "== checks after 02"
check "legacy invites" "$($P -At -c "select count(*) from visit_msg where sending_batch_id = $B_ID")" "$(X legacy_invite)"
check "linked responses" "$($P -At -c "select count(*) from survey_response sr join visit_msg vm on vm.id = sr.visit_msg_id where vm.sending_batch_id = $B_ID")" "$(X linked)"
check "Deleted response linked" "$($P -At -c "select count(*) from survey_response where status = 'Deleted' and visit_msg_id is not null")" "0"
check "Deleted sguid in map" "$($P -At -c "select count(*) from legacy_invite_map where legacy_sguid = '$(E deleted_sguid)'")" "0"
if [ -n "$(E reused_sguid)" ]; then
  check "reused-id response linked" "$($P -At -c "select count(*) from survey_response where sguid = '$(E reused_sguid)' and visit_msg_id is not null")" "0"
fi
check "rows attached to the one Patient with their phone" "$($P -At -c "select count(*) from legacy_source_row r join patient p on p.id = r.patient_id where p.first_name = 'PHONE1'")" "$(E one_phone_rows)"
check "rows attached to a Patient whose phone is shared" "$($P -At -c "select count(*) from legacy_source_row r join patient p on p.id = r.patient_id where p.first_name = 'PHONE2'")" "0"
check "existing Patients changed" "$($P -At -c "select count(*) from patient where created < (select loaded_at from legacy_sending_batch where sending_batch_id = $B_ID) and updated >= (select loaded_at from legacy_sending_batch where sending_batch_id = $B_ID)")" "0"
check "visits without Patient" "$($P -At -c "select count(*) from legacy_source_row where row_kind in ('legacy_invite','legacy_visit') and patient_id is null")" "0"
check "SIE untouched" "$($P -At -c "select count(*) from legacy_sending_batch where code = 'SIE_LEGACY_V4'")" "1"
echo "== 03_validation.sql (each query must run)"
"$PYTHON" -I - <<'EOF'
qs = [q.strip() for q in open("sql/03_validation.sql").read().split(";\n") if "SELECT" in q and not q.strip().startswith("-- When")]
for i, q in enumerate(qs, 1):
    open(f"03_{i}.sql", "w").write(q + ";\n")
print(f"   {len(qs)} queries")
EOF
for f in 03_*.sql; do $P -v ON_ERROR_STOP=1 -f "$f" >/dev/null 2>err.txt && echo "   ok   $f" || { echo "   FAIL $f: $(head -1 err.txt)"; FAIL=1; }; done
$P --csv -v ON_ERROR_STOP=1 -f sql/04_export_original_csv.sql > export.csv
SAME=$("$PYTHON" -I - "$ORIG" <<'EOF'
import sys, pandas as pd
a = pd.read_csv("export.csv", dtype=str, keep_default_na=False)
b = pd.read_csv(sys.argv[1], dtype=str, encoding="utf-8-sig", keep_default_na=False)
print(a.equals(b))
EOF
)
check "04 export identical to the original (values)" "$SAME" "True"
run 99_rollback.sql
check "after rollback = baseline" "$(snap)" "$BASE"
run 01_before_import.sql
$P -c "\\copy stg_${SLUG}_full FROM '$ACC_DIR/data/$LOAD' CSV HEADER NULL ''"
run 02_load.sql
check "reload: linked responses" "$($P -At -c "select count(*) from survey_response sr join visit_msg vm on vm.id = sr.visit_msg_id join legacy_sending_batch l on l.sending_batch_id = vm.sending_batch_id where l.code like '%_LEGACY_V1'")" "$(X linked)"
echo "== 01 when already loaded (must refuse):"; { $P -f sql/01_before_import.sql 2>&1 || true; } | { grep -m1 ERROR || true; } | sed "s/^/   /"
echo; if [ $FAIL = 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; exit 1; fi
