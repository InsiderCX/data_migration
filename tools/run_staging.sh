#!/usr/bin/env bash
# Run one Account's STAGING.md end to end on EU STAGING ONLY (refuses any other database). Writes to staging.
# Usage from the repo root: bash tools/run_staging.sh <account> <clinic csv file name in accounts/<account>/data/>
# Needs STG_DATABASE_URL in .env. Never point it at prod.
set -uo pipefail
REPO=/Users/anabelcar/Code/data_migration; A=$1; CLINIC=$2; ACC=$REPO/accounts/$A
STG="$(grep '^STG_DATABASE_URL=' $REPO/.env | cut -d= -f2-)"
case "$STG" in *insider-eu-stg*) ;; *) echo "REFUSING: STG_DATABASE_URL is not insider-eu-stg"; exit 9;; esac
P(){ psql "$STG" -X -v ON_ERROR_STOP=1 "$@"; }
LOAD=$(python3 -c "import json;print(json.load(open('$ACC/sql_config.json'))['load_file'])")
step(){ echo; echo "=== $1  ($(date '+%H:%M:%S'))"; }
fail(){ echo "STOPPED at: $1"; exit 1; }
step "0 target";  P -A -F ' | ' -c "SELECT current_database() AS db, current_setting('server_version') AS pg" || fail 0
[ "$(P -At -c 'select current_database()')" = "insider-eu-stg" ] || fail "0 not staging"
step "1 01_before_import.sql";  P -f $ACC/sql/01_before_import.sql 2>&1 | grep -vi "notice\|^$" || fail 1
[ "$(P -At -c "select to_regclass('public.stg_${A}_full')")" = "stg_${A}_full" ] || fail "1 staging table missing"
step "2 import $LOAD"; P -c "\\copy stg_${A}_full FROM '$ACC/data/$LOAD' CSV HEADER NULL ''" || fail 2
step "3 count check"; P -A -F ' | ' -c "SELECT count(*) AS total, count(*) FILTER (WHERE row_kind='platform') AS platform, count(*) FILTER (WHERE row_kind='legacy_invite') AS legacy_invite, count(*) FILTER (WHERE row_kind='legacy_visit') AS legacy_visit, count(*) FILTER (WHERE row_kind='legacy_raw') AS legacy_raw FROM stg_${A}_full" || fail 3
step "4 02_load.sql"; P -A -F ' | ' -f $ACC/sql/02_load.sql 2>&1 | grep -v "^BEGIN\|^COMMIT\|^ALTER\|^UPDATE\|^INSERT\|^SELECT\|^CREATE\|^DO$" ; [ ${PIPESTATUS[0]} = 0 ] || fail 4
step "5 03_validation.sql (one query at a time)"
python3 - "$ACC/sql/03_validation.sql" > /tmp/03_split_$A.txt <<'PY'
import sys
qs=[q.strip() for q in open(sys.argv[1]).read().split(";\n") if "SELECT" in q]
print("\n;;;\n".join(q+";" for q in qs))
PY
i=0; while IFS= read -r -d $'\0' q; do i=$((i+1)); echo "-- query $i"; P -A -F ' | ' -c "$q" || fail "5.$i"; done < <(python3 -c "import sys;print('\0'.join(x.strip() for x in open('/tmp/03_split_$A.txt').read().split(';;;') if x.strip()), end='\0')")
step "6 04 export + compare by value"; P --csv -f $ACC/sql/04_export_original_csv.sql > $ACC/out/stg_export_$(date +%F).csv || fail 6
$REPO/.venv/bin/python -I - "$ACC/out/stg_export_$(date +%F).csv" "$ACC/data/$CLINIC" <<'PY' || exit 1
import sys, pandas as pd
a = pd.read_csv(sys.argv[1], dtype=str, keep_default_na=False); b = pd.read_csv(sys.argv[2], dtype=str, encoding="utf-8-sig", keep_default_na=False)
print(f"export rows {len(a)} | original rows {len(b)} | identical values: {a.equals(b)}"); sys.exit(0 if a.equals(b) else 1)
PY
step "7 99_rollback.sql"; P -A -F ' | ' -f $ACC/sql/99_rollback.sql 2>&1 | grep -v "^BEGIN\|^COMMIT\|^DELETE\|^UPDATE\|^SELECT\|^CREATE\|^DO$"; [ ${PIPESTATUS[0]} = 0 ] || fail 7
step "8 reload: 01 + import + 02"
P -f $ACC/sql/01_before_import.sql >/dev/null 2>&1 || fail "8.01"
P -c "\\copy stg_${A}_full FROM '$ACC/data/$LOAD' CSV HEADER NULL ''" || fail "8.import"
P -A -F ' | ' -f $ACC/sql/02_load.sql 2>&1 | grep "_LEGACY_V1\|ERROR\|code |"; [ ${PIPESTATUS[0]} = 0 ] || fail "8.02"
echo; echo "DONE $A"
