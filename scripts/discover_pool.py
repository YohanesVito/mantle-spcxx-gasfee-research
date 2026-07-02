"""Discovery: identify pool type, tokens, decimals, Swap event signature,
and the pool creation block. Run once before building the backfill."""
import sys
from collections import Counter
from common import rpc, eth_call, to_int, erc20_decimals, erc20_symbol, \
    block_timestamp, latest_block, POOL

# Candidate token-accessor selectors (different DEX standards)
SELECTORS = {
    "token0()": "0x0dfe1681",
    "token1()": "0xd21220a7",
    "getTokenX()": "0x6c4a4f9b",  # Merchant Moe Liquidity Book
    "getTokenY()": "0xd5a9efc5",
}


def try_call(sel):
    try:
        raw = eth_call(POOL, SELECTORS[sel])
        if raw and raw != "0x" and int(raw, 16) != 0:
            return "0x" + raw[-40:]
    except Exception:
        return None
    return None


def find_creation_block():
    """Binary search for first block whose timestamp >= pool creation (~2026-06-12 16:20 UTC)."""
    lo, hi = 90_000_000, latest_block()
    target_ts = 1781281208  # from Dexscreener pairCreatedAt
    # narrow by timestamp
    while lo < hi:
        mid = (lo + hi) // 2
        ts = block_timestamp(mid)
        if ts < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def main():
    print("== Pool token discovery ==")
    tokens = {}
    for sel in SELECTORS:
        addr = try_call(sel)
        if addr:
            tokens[sel] = addr
            print(f"  {sel} -> {addr}")
    if not tokens:
        print("  No standard token accessor responded; pool may be a custom/router contract.")

    seen = {}
    for sel, addr in tokens.items():
        if addr in seen:
            continue
        try:
            sym = erc20_symbol(addr)
            dec = erc20_decimals(addr)
            seen[addr] = (sym, dec)
            print(f"    {addr}  symbol={sym}  decimals={dec}")
        except Exception as e:
            print(f"    {addr}  (failed token meta: {e})")

    print("\n== Creation block ==")
    cblk = find_creation_block()
    print(f"  creation block ~ {cblk}  ts={block_timestamp(cblk)}")

    print("\n== Event signature scan (recent 9000 blocks) ==")
    tip = latest_block()
    logs = rpc("eth_getLogs", [{
        "fromBlock": hex(tip - 9000), "toBlock": "latest", "address": POOL
    }])
    print(f"  logs: {len(logs)}")
    topic_counts = Counter(l["topics"][0] for l in logs if l.get("topics"))
    for topic, cnt in topic_counts.most_common():
        print(f"    {topic}  x{cnt}")
    # dump one log with the most-common non-transfer topic for manual decode
    if logs:
        sample = logs[-1]
        print("\n  sample log:")
        print("    topics:", sample["topics"])
        print("    data:", sample["data"][:200], "..." if len(sample["data"]) > 200 else "")
        print("    tx:", sample["transactionHash"], "block", to_int(sample["blockNumber"]))


if __name__ == "__main__":
    main()
