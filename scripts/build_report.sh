#!/usr/bin/env bash
# One-command final analysis: runs the full stats pipeline + regenerates all
# figures from whatever data is currently collected. Safe to run anytime.
#
#   bash scripts/build_report.sh
#
set -e
cd "$(dirname "$0")"

echo "=== Building report artifacts — $(date -u '+%Y-%m-%d %H:%M UTC') ==="
echo "[1/2] statistical analysis -> data/analysis_results.json"
python3 analyze.py
echo
echo "[2/2] figures -> figures/*.png"
python3 charts.py
echo
echo "Done. Drop the numbers from analysis_results.json + figures/ into the report (section 7)."
