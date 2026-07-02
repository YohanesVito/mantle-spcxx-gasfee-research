"""Backfill hourly Mantle network series for RQ3 (L1 gas pass-through) and
RQ4 (block fullness), by sampling blocks across the observation window.

Mantle block time is a constant 2.000s, so hour h maps deterministically to
block = anchor_block + h*1800. For each hour we sample K blocks and record:
  - l1_gas_price_gwei : Ethereum L1 gas as seen by Mantle (from a tx receipt)
  - avg_gas_used      : mean block gasUsed   (fullness)
  - avg_tx_count      : mean transactions/block (fullness)
  - base_fee_gwei     : L2 base fee (expected constant 50)

Output: data/mantle_hourly.csv  (incremental / resumable)
"""
import csv
import os
import datetime
from common import rpc, to_int, latest_block, block_timestamp

CREATE_BLOCK = 96575448
BLOCKS_PER_HOUR = 1800          # 3600s / 2s
SAMPLES_PER_HOUR = 6            # blocks sampled per hour for fullness
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "mantle_hourly.csv")
FIELDS = ["hour_utc", "anchor_block", "l1_gas_price_gwei", "avg_gas_used",
          "avg_gas_limit", "utilization_pct", "avg_tx_count", "base_fee_gwei",
          "n_blocks_sampled"]


def l1_gas_from_block(block_num, search=8):
    """Find l1GasPrice (Gwei) from a user tx receipt in block_num or nearby."""
    for off in range(search):
        for bn in (block_num + off, block_num - off):
            b = rpc("eth_getBlockByNumber", [hex(bn), True])
            if not b:
                continue
            for tx in b.get("transactions", []):
                if to_int(tx.get("gasPrice", "0x0")) > 0:
                    rc = rpc("eth_getTransactionReceipt", [tx["hash"]])
                    l1gp = to_int(rc.get("l1GasPrice", "0x0"))
                    if l1gp > 0:
                        return l1gp / 1e9
    return None


def sample_hour(anchor):
    """Sample SAMPLES_PER_HOUR blocks within the hour for fullness/capacity metrics."""
    gas_used, gas_limit, tx_count, base_fee, n = 0, 0, 0, None, 0
    stride = BLOCKS_PER_HOUR // SAMPLES_PER_HOUR
    for i in range(SAMPLES_PER_HOUR):
        bn = anchor + i * stride
        b = rpc("eth_getBlockByNumber", [hex(bn), False])
        if not b:
            continue
        gas_used += to_int(b["gasUsed"])
        gas_limit += to_int(b["gasLimit"])
        tx_count += len(b.get("transactions", []))
        if base_fee is None and b.get("baseFeePerGas"):
            base_fee = to_int(b["baseFeePerGas"]) / 1e9
        n += 1
    if n == 0:
        return None
    return gas_used / n, gas_limit / n, tx_count / n, base_fee, n


def last_hour_in_csv():
    if not os.path.exists(OUT):
        return None
    last = None
    with open(OUT) as f:
        for row in csv.DictReader(f):
            last = row["hour_utc"]
    return last


def main():
    anchor_ts = block_timestamp(CREATE_BLOCK)
    # start hour aligned to the top of the creation hour
    start_dt = datetime.datetime.fromtimestamp(anchor_ts, datetime.UTC).replace(
        minute=0, second=0, microsecond=0)
    tip = latest_block()
    tip_ts = block_timestamp(tip)
    end_dt = datetime.datetime.fromtimestamp(tip_ts, datetime.UTC).replace(
        minute=0, second=0, microsecond=0)

    resume = last_hour_in_csv()
    new = not os.path.exists(OUT)
    f = open(OUT, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()

    h = start_dt
    written = 0
    while h <= end_dt:
        iso = h.isoformat()
        if resume and iso <= resume:
            h += datetime.timedelta(hours=1)
            continue
        # block for this hour (deterministic; 2s block time)
        anchor = CREATE_BLOCK + round((h.timestamp() - anchor_ts) / 2)
        if anchor < CREATE_BLOCK:
            anchor = CREATE_BLOCK
        if anchor > tip:
            break
        s = sample_hour(anchor)
        if not s:
            h += datetime.timedelta(hours=1)
            continue
        avg_gas, avg_limit, avg_tx, base_fee, n = s
        util = (avg_gas / avg_limit * 100) if avg_limit else 0.0
        l1gp = l1_gas_from_block(anchor)
        w.writerow({
            "hour_utc": iso, "anchor_block": anchor,
            "l1_gas_price_gwei": f"{l1gp:.6f}" if l1gp is not None else "",
            "avg_gas_used": f"{avg_gas:.0f}", "avg_gas_limit": f"{avg_limit:.0f}",
            "utilization_pct": f"{util:.4f}", "avg_tx_count": f"{avg_tx:.2f}",
            "base_fee_gwei": f"{base_fee:.2f}" if base_fee else "",
            "n_blocks_sampled": n})
        written += 1
        if written % 12 == 0:
            print(f"  {iso}  l1gas={l1gp} gwei  avgGasUsed={avg_gas:.0f}  avgTx={avg_tx:.1f}")
        h += datetime.timedelta(hours=1)
    f.close()
    print(f"done. wrote {written} hourly rows to {OUT}")


if __name__ == "__main__":
    main()
