"""Backfill the full population of SPCXx/USDT0 swaps on Mantle (Merchant Moe LB)
since pool creation, with per-transaction fee decomposition (L2 vs L1).

Output: data/spcxx_swaps.csv  (one row per swap)
Re-runnable / incremental: resumes from the last block already in the CSV.
"""
import csv
import os
import datetime
from common import rpc, to_int, POOL, latest_block

SWAP_TOPIC = "0xad7d6f97abf51ce18e17a38f4d70e975be9c0708474987bb3e26ad21bd93ca70"
CREATE_BLOCK = 96575448           # pool creation (2026-06-12 16:20 UTC)
SPCXX_DEC = 18                    # tokenX
USDT0_DEC = 6                     # tokenY
MASK = (1 << 128) - 1
CHUNK = 10000
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "spcxx_swaps.csv")
FIELDS = ["block", "ts_utc", "txhash", "side", "spcxx_amount", "usdt0_amount",
          "price_usd", "fee_l2_mnt", "fee_l1_mnt", "fee_total_mnt", "gas_used",
          "eff_gas_price_gwei", "l1_gas_price_gwei"]

_block_ts = {}


def block_ts(num):
    if num not in _block_ts:
        b = rpc("eth_getBlockByNumber", [hex(num), False])
        _block_ts[num] = to_int(b["timestamp"])
    return _block_ts[num]


def decode_swap(log):
    """Return (side, spcxx_amt, usdt0_amt, price)."""
    d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, len(d), 64)]
    a_in, a_out = w[1], w[2]
    in_x, in_y = a_in & MASK, a_in >> 128      # X=SPCXx, Y=USDT0
    out_x, out_y = a_out & MASK, a_out >> 128
    if in_x > 0:        # SPCXx sold into pool -> user SELL
        spcxx, usdt0, side = in_x / 10**SPCXX_DEC, out_y / 10**USDT0_DEC, "SELL"
    else:               # USDT0 in -> user BUY SPCXx
        usdt0, spcxx, side = in_y / 10**USDT0_DEC, out_x / 10**SPCXX_DEC, "BUY"
    price = usdt0 / spcxx if spcxx else 0.0
    return side, spcxx, usdt0, price


def tx_fee(txhash):
    """Decompose total fee into L2 execution + L1 data (in MNT)."""
    rc = rpc("eth_getTransactionReceipt", [txhash])
    gas_used = to_int(rc["gasUsed"])
    eff = to_int(rc.get("effectiveGasPrice", "0x0"))
    l1 = to_int(rc.get("l1Fee", "0x0"))
    l1_gp = to_int(rc.get("l1GasPrice", "0x0"))
    l2_fee = gas_used * eff
    return (l2_fee / 1e18, l1 / 1e18, (l2_fee + l1) / 1e18,
            gas_used, eff / 1e9, l1_gp / 1e9)


def last_block_in_csv():
    if not os.path.exists(OUT):
        return None
    last = None
    with open(OUT) as f:
        for row in csv.DictReader(f):
            last = int(row["block"])
    return last


def main():
    resume = last_block_in_csv()
    start = (resume + 1) if resume else CREATE_BLOCK
    tip = latest_block()
    print(f"backfill swaps: blocks {start}..{tip}  (resume={resume})")

    new_exists = os.path.exists(OUT)
    f = open(OUT, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if not new_exists:
        w.writeheader()

    total = 0
    b = start
    while b <= tip:
        hi = min(b + CHUNK - 1, tip)
        logs = rpc("eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(hi),
                                    "address": POOL, "topics": [SWAP_TOPIC]}])
        for l in logs:
            blk = to_int(l["blockNumber"])
            side, spcxx, usdt0, price = decode_swap(l)
            l2, l1, tot, gu, egp, l1gp = tx_fee(l["transactionHash"])
            ts = datetime.datetime.fromtimestamp(block_ts(blk), datetime.UTC)
            w.writerow({
                "block": blk, "ts_utc": ts.isoformat(), "txhash": l["transactionHash"],
                "side": side, "spcxx_amount": f"{spcxx:.8f}", "usdt0_amount": f"{usdt0:.6f}",
                "price_usd": f"{price:.4f}", "fee_l2_mnt": f"{l2:.10f}",
                "fee_l1_mnt": f"{l1:.10f}", "fee_total_mnt": f"{tot:.10f}",
                "gas_used": gu, "eff_gas_price_gwei": f"{egp:.4f}",
                "l1_gas_price_gwei": f"{l1gp:.6f}"})
            total += 1
        if logs:
            print(f"  blocks {b}..{hi}: +{len(logs)} swaps (running {total})")
        b = hi + 1
    f.close()
    print(f"done. wrote {total} new swap rows to {OUT}")


if __name__ == "__main__":
    main()
