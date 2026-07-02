# Stable by Design: Mantle Gas Fees under the SPCXx Tokenized-Equity Event

Reproducible onchain research for the **Mantle Research Challenge 2026 (Track 1)**.

On 12 June 2026, tokenized SpaceX (**SPCXx**) went live for 24/7 trading on Mantle the same day SpaceX completed the largest IPO in history. This repo uses that listing as a natural experiment to test a simple question: **when a real, high-demand asset lands on Mantle, do its fees and performance stay stable, and why?**

Every number in the paper is reconstructed from public onchain data (Mantle RPC) plus Nasdaq daily closes. Clone this repo, run one command, and you get the same figures and statistics.

## TL;DR findings

- **The fee barely moves.** Across the full population of SPCXx swaps, Mantle's total fee is statistically unrelated to both network demand and Ethereum gas (differenced OLS R² ≈ 0.02).
- **It is not "following Ethereum."** The L1 data fee is only ~2% of the total; the dominant L2 fee sits on a fixed 50 Gwei base with no priority-fee auction. Stability is structural, not pass-through.
- **Massive headroom.** Across a 13k+ block census, the network runs at ~0.2% of its 60M-gas block limit (~99.8% unused). One hot asset cannot move it.
- **The token tracks its parent.** SPCXx and SPCX co-move (daily price r ≈ 0.90) in the same range, though with several-percent day-to-day dispersion from thin liquidity. No tight-peg or convergence claim is made.

## Repository layout

```
scripts/
  common.py            RPC helpers + SPCX (Nasdaq) caching
  backfill_swaps.py    reconstruct every SPCXx swap from Merchant Moe LB Swap events
  backfill_network.py  hourly L1 gas + block-fullness + capacity samples
  capacity_report.py   census utilization / headroom (via eth_feeHistory)
  analyze.py           ADF -> first-difference -> OLS (Newey-West) + VIF, per RQ
  charts.py            all report figures
  make_docx.py         renders the report from the analysis outputs
  poll.sh              one command to refresh all datasets
  build_report.sh      one command to run analysis + figures
data/                  frozen CSV/JSON datasets (the census)
figures/               generated charts (PNG)
rencana-riset-*.md     research plan (methodology, Indonesian)
feasibility-findings.md  data-source validation log
```

## Reproduce it

```bash
pip install -r requirements.txt

# refresh the datasets from public RPC (idempotent, resumable)
bash scripts/poll.sh

# run the full statistical analysis + regenerate every figure
bash scripts/build_report.sh
```

`analyze.py` writes `data/analysis_results.json`; `capacity_report.py` writes `data/capacity_summary.json`; `charts.py` writes `figures/*.png`. The pipeline is deterministic from block numbers, so a fresh run on the same window reproduces the same results.

## Data dictionary (key columns)

`data/spcxx_swaps.csv` (one row per swap):
`block, ts_utc, txhash, side, spcxx_amount, usdt0_amount, price_usd, fee_l2_mnt, fee_l1_mnt, fee_total_mnt, gas_used, eff_gas_price_gwei, l1_gas_price_gwei`

`data/mantle_hourly.csv` (one row per hour):
`hour_utc, anchor_block, l1_gas_price_gwei, avg_gas_used, avg_gas_limit, utilization_pct, avg_tx_count, base_fee_gwei, n_blocks_sampled`

## Method, in one paragraph

Quantitative, observational, census-level study (the full population of swaps, not a sample). Swaps are decoded from Merchant Moe Liquidity Book `Swap` events (topic `0xad7d6f97…`; tokenX = SPCXx 18dp, tokenY = USDT0 6dp). Per-transaction fees are decomposed from receipts as `gasUsed × effectiveGasPrice` (L2) `+ l1Fee` (L1). Analysis: ADF stationarity, first-differencing to defeat spurious correlation, Pearson/Spearman correlations, and OLS with Newey–West (HAC) errors and VIF diagnostics. Capacity is a per-block census via `eth_feeHistory` gasUsedRatio.

## Honest limitations

- Short window and thin volume limit statistical power; a null can mean "not enough data," not "no effect."
- The listing and the CEX allocation-failure news overlap within ~24h and cannot be cleanly separated.
- Price tracking (RQ1) is reported at daily granularity only. Intraday premium/convergence is not claimed: matching 24/7 onchain UTC prices to Nasdaq hourly bars (US/Eastern, end-of-bar) misaligns during fast moves.

## Sources

Background facts verified against CoinDesk, CNBC, The Block, Chainwire; Mantle fee mechanism from Mantle Docs; RWA TVL from Mantle's Q1 2026 ecosystem report. Full paper (write-up, figures, methodology) linked from the accompanying submission.

---
*Data reconstructed from Mantle public RPC (chainId 5000) and Nasdaq daily closes. No API keys required.*
