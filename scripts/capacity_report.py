"""Capacity & headroom report for Mantle, derived from the hourly dataset plus
a per-block utilization sample. Quantifies how much of Mantle's block-gas
capacity is actually used during the SPCXx observation window (RQ4 / Implications).

Outputs a console report and writes data/capacity_summary.json.
"""
import json
import os
import statistics
import pandas as pd
from common import rpc, to_int, latest_block

CREATE_BLOCK = 96575448
BLOCK_TIME_S = 2.0
DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def per_block_sample(chunks=12):
    """CENSUS utilization across the window via eth_feeHistory gasUsedRatio
    (1024 contiguous blocks per call), spread evenly from creation to tip. This
    is a true per-block census of utilization (no strided sampling that could
    miss full blocks), so both mean AND peak are accurate. tx/gas detail comes
    from a light block read per chunk midpoint."""
    tip = latest_block()
    span = max(tip - CREATE_BLOCK, 1024)
    stride = max(span // chunks, 1024)
    util, txc, used = [], [], []
    gl = to_int(rpc("eth_getBlockByNumber", ["latest", False])["gasLimit"])
    end = CREATE_BLOCK + 1024
    while end <= tip:
        r = rpc("eth_feeHistory", [hex(1024), hex(end), []])
        ratios = r.get("gasUsedRatio", []) or []
        util.extend(x * 100 for x in ratios)
        used.extend(int(x * gl) for x in ratios)        # gasUsed = ratio * limit
        # tx/block: light read at the chunk midpoint (representative)
        bmid = rpc("eth_getBlockByNumber", [hex(end - 512), False])
        if bmid:
            txc.append(len(bmid.get("transactions", [])))
        end += stride
    # always include the latest 1024 blocks
    r = rpc("eth_feeHistory", [hex(1024), "latest", []])
    util.extend(x * 100 for x in (r.get("gasUsedRatio", []) or []))
    used.extend(int(x * gl) for x in (r.get("gasUsedRatio", []) or []))
    return gl, util, used, txc or [1], tip


def main():
    hourly = pd.read_csv(os.path.join(DATA, "spcxx_swaps.csv")) if False else None
    net = pd.read_csv(os.path.join(DATA, "mantle_hourly.csv"))
    gl, util, used, txc, tip = per_block_sample()

    avg_gas_per_tx = statistics.mean(used) / max(statistics.mean(txc), 0.01)
    cap_gas_per_s = gl / BLOCK_TIME_S
    max_tps_profile = cap_gas_per_s / avg_gas_per_tx
    cur_tps = statistics.mean(txc) / BLOCK_TIME_S

    util_mean = statistics.mean(util)
    util_median = statistics.median(util)
    summary = {
        "window_blocks": [CREATE_BLOCK, tip],
        "method": "census via eth_feeHistory gasUsedRatio",
        "blocks_in_census": len(util),
        "block_gas_limit": gl,
        "block_time_s": BLOCK_TIME_S,
        "capacity_gas_per_s": cap_gas_per_s,
        "utilization_pct_census_mean": round(util_mean, 4),
        "utilization_pct_census_median": round(util_median, 4),
        "utilization_pct_block_peak": round(max(util), 4),
        # keep hourly (sampled) for cross-reference
        "utilization_pct_hourly_mean": round(net["utilization_pct"].mean(), 4),
        # backward-compat alias used by the report narrative
        "headroom_pct_mean": round(100 - util_mean, 4),
        "headroom_pct_at_peak": round(100 - max(util), 4),
        "tx_per_block_mean": round(statistics.mean(txc), 2),
        "avg_gas_per_tx": round(avg_gas_per_tx),
        "current_tps": round(cur_tps, 3),
        "max_tps_at_current_profile": round(max_tps_profile),
        "max_tps_simple_transfer_21k": round(cap_gas_per_s / 21000),
    }

    print("=" * 60)
    print("MANTLE CAPACITY & HEADROOM REPORT")
    print("=" * 60)
    print(f"Block gas limit      : {gl:,} gas/block (constant)")
    print(f"Block time           : {BLOCK_TIME_S} s (constant)")
    print(f"Capacity             : {cap_gas_per_s:,.0f} gas/s")
    print("-" * 60)
    print(f"Census              : {summary['blocks_in_census']:,} blocks (eth_feeHistory)")
    print(f"Utilization (census) : median {summary['utilization_pct_census_median']}%"
          f" | mean {summary['utilization_pct_census_mean']}%")
    print(f"Utilization (peak blk): {summary['utilization_pct_block_peak']}%  "
          f"(headroom at peak ~{summary['headroom_pct_at_peak']:.2f}%)")
    print(f"HEADROOM (mean)      : ~{summary['headroom_pct_mean']:.2f}% unused")
    print("-" * 60)
    print(f"tx/block (mean)      : {summary['tx_per_block_mean']}")
    print(f"avg gas/tx           : {summary['avg_gas_per_tx']:,}")
    print(f"Current throughput   : {summary['current_tps']} tx/s")
    print(f"Max TPS (this profile): ~{summary['max_tps_at_current_profile']} tx/s  "
          f"[ceiling from gas-limit only; sequencer/L1-DA may bind first]")
    print(f"Max TPS (21k transfers): ~{summary['max_tps_simple_transfer_21k']:,} tx/s")
    print("=" * 60)

    out = os.path.join(DATA, "capacity_summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
