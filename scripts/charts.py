"""Generate all report figures from the datasets. Re-run anytime; figures
regenerate from current CSVs into figures/. No data dependency beyond the CSVs.

  python3 charts.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
FIG = os.path.join(os.path.dirname(__file__), "..", "figures")
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.3, "figure.autolayout": True})


def load():
    sw = pd.read_csv(os.path.join(DATA, "spcxx_swaps.csv"), parse_dates=["ts_utc"])
    sw = sw[sw.usdt0_amount > 1].copy()
    net = pd.read_csv(os.path.join(DATA, "mantle_hourly.csv"), parse_dates=["hour_utc"])
    sw["hour"] = sw.ts_utc.dt.floor("h")
    agg = sw.groupby("hour").agg(
        trades=("price_usd", "size"), volume=("usdt0_amount", "sum"),
        vwap=("price_usd", "mean"), fee_total=("fee_total_mnt", "mean"),
        fee_l1=("fee_l1_mnt", "mean"), fee_l2=("fee_l2_mnt", "mean")).reset_index()
    m = pd.merge(agg, net.rename(columns={"hour_utc": "hour"}), on="hour", how="left")
    return sw, net, m


def fig_price(sw):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(sw.ts_utc, sw.price_usd, ".", ms=4, alpha=0.5, label="SPCXx swap price")
    try:
        from common import load_spcx
        spcx = load_spcx()
        if spcx is not None and not spcx.empty:
            idx = pd.to_datetime(spcx["date"]).dt.tz_localize("UTC")
            ax.step(idx, spcx["close"], where="post", color="crimson", lw=1.5,
                    label="SPCX Nasdaq close")
    except Exception:
        pass
    ax.set_title("RQ1 — SPCXx on-chain price vs SPCX Nasdaq")
    ax.set_ylabel("USD"); ax.legend()
    fig.savefig(os.path.join(FIG, "fig1_price.png")); plt.close(fig)


def fig_fee_decomp(m):
    d = m[m.fee_total.notna()]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(d.hour, d.fee_l2, width=0.03, label="L2 execution fee", color="#2a6")
    ax.bar(d.hour, d.fee_l1, width=0.03, bottom=d.fee_l2, label="L1 data fee", color="#e74")
    ax.set_title("RQ3 — Hourly mean fee decomposition (L2 dominates)")
    ax.set_ylabel("MNT"); ax.legend()
    fig.savefig(os.path.join(FIG, "fig2_fee_decomp.png")); plt.close(fig)


def fig_fee_scatter(m):
    d = m[m.fee_total.notna()]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].scatter(d.volume, d.fee_total, s=18, alpha=0.6)
    axes[0].set_xlabel("SPCXx volume (USDT0)"); axes[0].set_ylabel("mean total fee (MNT)")
    axes[0].set_title("Fee vs internal demand")
    axes[1].scatter(d.l1_gas_price_gwei, d.fee_total, s=18, alpha=0.6, color="#e74")
    axes[1].set_xlabel("ETH L1 gas (Gwei)"); axes[1].set_ylabel("mean total fee (MNT)")
    axes[1].set_title("Fee vs L1 gas pass-through")
    fig.suptitle("RQ3 — Total fee is weakly related to both drivers")
    fig.savefig(os.path.join(FIG, "fig3_fee_scatter.png")); plt.close(fig)


def fig_utilization(net):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 4))
    a1.plot(net.hour_utc, net.utilization_pct, lw=1)
    a1.set_title("RQ4 — Block-gas utilization over time")
    a1.set_ylabel("% of 60M gas limit")
    a2.hist(net.utilization_pct.dropna(), bins=25, color="#48a")
    a2.set_title(f"Utilization distribution (mean {net.utilization_pct.mean():.2f}%)")
    a2.set_xlabel("% utilization")
    fig.suptitle("Mantle runs at ~0.2% of capacity (~99.8% headroom)")
    fig.savefig(os.path.join(FIG, "fig4_utilization.png")); plt.close(fig)


def fig_premium(sw):
    """SPCXx DAILY premium/discount vs SPCX (robust granularity). Shows tracking
    with dispersion; no tight-peg or convergence claim (thin liquidity)."""
    from common import load_spcx
    spcx = load_spcx()
    if spcx is None or spcx.empty:
        return
    spcx["date"] = pd.to_datetime(spcx["date"]).dt.date
    on = sw.copy()
    on["date"] = on.ts_utc.dt.date
    daily = on.groupby("date").apply(
        lambda g: np.average(g.price_usd, weights=g.usdt0_amount)).rename("vwap").reset_index()
    mer = pd.merge(daily, spcx[["date", "close"]], on="date", how="inner").sort_values("date")
    if mer.empty:
        return
    mer["premium_pct"] = (mer.vwap / mer.close - 1) * 100
    x = pd.to_datetime(mer.date)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axhline(0, color="grey", lw=1)
    ax.vlines(x, 0, mer.premium_pct, color="#a63", alpha=0.35, lw=1)
    ax.plot(x, mer.premium_pct, "o", ms=6, color="#a63")
    ax.set_title("RQ1 — SPCXx daily premium/discount vs SPCX Nasdaq")
    ax.set_ylabel("premium %")
    ax.text(0.02, 0.96, f"tracks with dispersion (thin liquidity); "
            f"median |premium| {mer.premium_pct.abs().median():.1f}%",
            transform=ax.transAxes, va="top", fontsize=9, color="#666")
    fig.savefig(os.path.join(FIG, "fig6_premium.png")); plt.close(fig)


def fig_volume(m):
    d = m[m.trades.notna()]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(d.hour, d.volume, width=0.03, color="#86c")
    ax.set_title("SPCXx hourly trading volume (demand proxy)")
    ax.set_ylabel("USDT0")
    fig.savefig(os.path.join(FIG, "fig5_volume.png")); plt.close(fig)


def main():
    sw, net, m = load()
    fig_price(sw); fig_fee_decomp(m); fig_fee_scatter(m); fig_utilization(net)
    fig_volume(m); fig_premium(sw)
    files = sorted(f for f in os.listdir(FIG) if f.endswith(".png"))
    print("generated figures in figures/:")
    for f in files:
        print("  -", f)


if __name__ == "__main__":
    main()
