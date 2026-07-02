#!/usr/bin/env bash
# Daily forward-poll for the SPCXx/Mantle research datasets.
# Run once a day until ~1 July 2026. Both backfills are incremental/resumable,
# so this only appends new data since the last run.
#
#   bash scripts/poll.sh
#
set -e
cd "$(dirname "$0")"

echo "=== SPCXx/Mantle daily poll — $(date -u '+%Y-%m-%d %H:%M UTC') ==="

echo "[1/2] swaps..."
python3 backfill_swaps.py

echo "[2/2] network hourly..."
python3 backfill_network.py

echo "[+] caching SPCX Nasdaq baseline (daily + hourly)..."
python3 -c "from common import load_spcx, load_spcx_hourly; d=load_spcx(); h=load_spcx_hourly(); print('    SPCX daily:', 0 if d is None else len(d), '| hourly:', 0 if h is None else len(h))"

echo "[+] refreshing capacity report..."
python3 capacity_report.py >/dev/null && echo "    data/capacity_summary.json updated"

echo
echo "=== Dataset status ==="
python3 - <<'PY'
import pandas as pd, os
base=os.path.join(os.path.dirname(__file__) if "__file__" in dir() else ".","..","data")
sw=pd.read_csv(os.path.join(base,"spcxx_swaps.csv"), parse_dates=["ts_utc"])
net=pd.read_csv(os.path.join(base,"mantle_hourly.csv"), parse_dates=["hour_utc"])
print(f"  swaps:   {len(sw):4d} rows | {sw.ts_utc.min()} -> {sw.ts_utc.max()}")
print(f"  hourly:  {len(net):4d} rows | {net.hour_utc.min()} -> {net.hour_utc.max()}")
PY
echo "Done. Run again tomorrow."
