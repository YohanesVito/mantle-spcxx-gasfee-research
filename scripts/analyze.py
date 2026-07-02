"""Final analysis pipeline for the SPCXx / Mantle gas-fee study.

Runs the complete statistical analysis for RQ1-RQ4 on whatever data is present
in data/. Designed to be re-run as the dataset grows; produces a console report
and writes data/analysis_results.json. Guards against thin-sample failures.

  python3 analyze.py
"""
import json
import os
import warnings
import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
DATA = os.path.join(os.path.dirname(__file__), "..", "data")


# ---------- load & prep ----------
def load():
    sw = pd.read_csv(os.path.join(DATA, "spcxx_swaps.csv"), parse_dates=["ts_utc"])
    sw = sw[sw.usdt0_amount > 1].copy()                 # drop dust trades
    net = pd.read_csv(os.path.join(DATA, "mantle_hourly.csv"), parse_dates=["hour_utc"])
    sw["hour"] = sw.ts_utc.dt.floor("h")
    agg = sw.groupby("hour").agg(
        trades=("price_usd", "size"), volume=("usdt0_amount", "sum"),
        vwap=("price_usd", "mean"), fee_total=("fee_total_mnt", "mean"),
        fee_l1=("fee_l1_mnt", "mean"), fee_l2=("fee_l2_mnt", "mean"),
        eff_gas=("eff_gas_price_gwei", "mean")).reset_index()
    net = net.rename(columns={"hour_utc": "hour"})
    m = pd.merge(agg, net, on="hour", how="left").sort_values("hour").reset_index(drop=True)
    return sw, net, m


# ---------- helpers ----------
def adf(series, name):
    from statsmodels.tsa.stattools import adfuller
    s = series.dropna()
    if len(s) < 12 or s.nunique() < 3:
        return {"var": name, "n": len(s), "stationary": None, "note": "insufficient/constant"}
    stat, p, *_ = adfuller(s, autolag="AIC")
    return {"var": name, "n": len(s), "adf_stat": round(stat, 3), "pvalue": round(p, 4),
            "stationary": bool(p < 0.05)}


def corr_pair(df, a, b):
    from scipy.stats import pearsonr, spearmanr
    d = df[[a, b]].dropna()
    if len(d) < 5:
        return {"n": len(d), "pearson": None, "spearman": None}
    return {"n": len(d),
            "pearson": round(pearsonr(d[a], d[b])[0], 3),
            "pearson_p": round(pearsonr(d[a], d[b])[1], 4),
            "spearman": round(spearmanr(d[a], d[b])[0], 3)}


# ---------- RQ1: price convergence ----------
def rq1(sw):
    """Tracking of SPCXx vs SPCX at DAILY granularity (robust).

    NOTE: an earlier hourly-alignment version was dropped. yfinance intraday bars
    are timestamped at the bar START in US/Eastern with the price at the bar END,
    which — matched against 24/7 on-chain UTC-hourly VWAP — misaligned by up to an
    hour and manufactured spurious multi-percent premiums during fast Nasdaq moves.
    We therefore report only what is defensible: daily co-movement and daily
    premium dispersion. We do NOT claim a tight peg or a statistically robust
    convergence trend — thin on-chain liquidity makes both unreliable here."""
    from common import load_spcx
    out = {"note": "SPCXx daily on-chain VWAP vs SPCX Nasdaq daily close. "
                   "Reports co-movement + dispersion only; intraday premium and "
                   "convergence significance intentionally NOT claimed (see limitations)."}
    try:
        spcx = load_spcx()
        if spcx is None or spcx.empty:
            return {**out, "error": "no SPCX data"}
        spcx["date"] = pd.to_datetime(spcx["date"]).dt.date
        on = sw.copy()
        on["date"] = on.ts_utc.dt.date
        daily = on.groupby("date").apply(
            lambda g: np.average(g.price_usd, weights=g.usdt0_amount)).rename("onchain_vwap").reset_index()
        mer = pd.merge(daily, spcx[["date", "close"]], on="date", how="inner")
        if mer.empty:
            return {**out, "error": "no overlapping days"}
        mer["premium_pct"] = (mer.onchain_vwap / mer.close - 1) * 100
        # correlation of the two daily price levels = co-movement (robust)
        corr = mer[["onchain_vwap", "close"]].corr().iloc[0, 1] if len(mer) > 2 else None
        return {**out,
                "matched_days": int(len(mer)),
                "price_comovement_r": round(corr, 3) if corr is not None else None,
                "mean_abs_premium_pct": round(mer.premium_pct.abs().mean(), 2),
                "median_abs_premium_pct": round(mer.premium_pct.abs().median(), 2),
                "premium_range_pct": [round(mer.premium_pct.min(), 2), round(mer.premium_pct.max(), 2)],
                "onchain_price_range": [round(mer.onchain_vwap.min(), 2), round(mer.onchain_vwap.max(), 2)],
                "nasdaq_price_range": [round(mer.close.min(), 2), round(mer.close.max(), 2)]}
    except Exception as e:
        return {**out, "error": str(e)}


# ---------- RQ2: event-window volatility ----------
def rq2(sw):
    # event cluster 12-13 June; compare hourly return volatility pre vs post midpoint
    s = sw.sort_values("ts_utc").copy()
    s["hour"] = s.ts_utc.dt.floor("h")
    hourly = s.groupby("hour").apply(
        lambda g: np.average(g.price_usd, weights=g.usdt0_amount)).rename("p").reset_index()
    hourly["ret"] = np.log(hourly.p).diff()
    cut = pd.Timestamp("2026-06-13 12:00", tz="UTC")
    pre = hourly[hourly.hour < cut].ret.dropna()
    post = hourly[hourly.hour >= cut].ret.dropna()
    out = {"cut": str(cut), "n_pre": len(pre), "n_post": len(post),
           "vol_pre": round(pre.std(), 5) if len(pre) > 2 else None,
           "vol_post": round(post.std(), 5) if len(post) > 2 else None}
    if len(pre) > 2 and len(post) > 2:
        from scipy.stats import levene
        out["levene_p"] = round(levene(pre, post)[1], 4)
    return out


# ---------- RQ3: fee drivers ----------
def rq3(m):
    cols = ["fee_total", "fee_l1", "volume", "l1_gas_price_gwei", "eff_gas"]
    stationarity = [adf(m[c], c) for c in cols if c in m]
    # first-difference everything for regression
    d = m[cols].diff().dropna()
    corrs = {
        "fee_total~l1_gas": corr_pair(m, "fee_total", "l1_gas_price_gwei"),
        "fee_total~volume": corr_pair(m, "fee_total", "volume"),
        "fee_l1~l1_gas": corr_pair(m, "fee_l1", "l1_gas_price_gwei"),
        "d_fee_total~d_l1_gas": corr_pair(d, "fee_total", "l1_gas_price_gwei"),
        "d_fee_total~d_volume": corr_pair(d, "fee_total", "volume"),
    }
    reg = {"note": "OLS d_fee_total ~ d_l1_gas + d_volume, Newey-West HAC SE"}
    try:
        import statsmodels.api as sm
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        dd = m[["fee_total", "l1_gas_price_gwei", "volume"]].diff().dropna()
        if len(dd) >= 10:
            y = dd["fee_total"]
            X = sm.add_constant(dd[["l1_gas_price_gwei", "volume"]])
            fit = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
            reg["n"] = int(len(dd))
            reg["r2"] = round(fit.rsquared, 3)
            reg["coef"] = {k: round(v, 8) for k, v in fit.params.items()}
            reg["pvalues"] = {k: round(v, 4) for k, v in fit.pvalues.items()}
            vif_X = X.drop(columns="const")
            reg["vif"] = {vif_X.columns[i]: round(variance_inflation_factor(vif_X.values, i), 2)
                          for i in range(vif_X.shape[1])}
        else:
            reg["note"] += f"  (skipped: only {len(dd)} diffed obs, need >=10)"
    except Exception as e:
        reg["error"] = str(e)
    # fee stability
    stab = {"fee_total_mean": round(m.fee_total.mean(), 6),
            "fee_total_cv": round(m.fee_total.std() / m.fee_total.mean(), 4),
            "l1_share_pct": round(m.fee_l1.sum() / m.fee_total.sum() * 100, 3)}
    return {"stationarity": stationarity, "correlations": corrs, "regression": reg, "stability": stab}


# ---------- RQ4: block fullness vs demand ----------
def rq4(m):
    return {
        "utilization~volume": corr_pair(m, "utilization_pct", "volume"),
        "avg_tx_count~volume": corr_pair(m, "avg_tx_count", "volume"),
        "avg_gas_used~trades": corr_pair(m, "avg_gas_used", "trades"),
        "util_mean_pct": round(m.utilization_pct.mean(), 4) if "utilization_pct" in m else None,
    }


def main():
    sw, net, m = load()
    m_trades = m[m.trades.notna()].copy()
    print(f"loaded: {len(sw)} swaps, {len(net)} hourly rows, {len(m_trades)} hours with trades\n")

    results = {
        "window": {"swaps": len(sw), "hours_with_trades": int(len(m_trades)),
                   "from": str(sw.ts_utc.min()), "to": str(sw.ts_utc.max())},
        "RQ1_price_convergence": rq1(sw),
        "RQ2_event_volatility": rq2(sw),
        "RQ3_fee_drivers": rq3(m_trades),
        "RQ4_block_fullness": rq4(m_trades),
    }

    # console summary
    r3 = results["RQ3_fee_drivers"]
    print("== RQ3 (core) fee drivers ==")
    for k, v in r3["correlations"].items():
        print(f"  {k:28} pearson={v['pearson']} (n={v['n']})")
    print(f"  stability: CV={r3['stability']['fee_total_cv']}  L1 share={r3['stability']['l1_share_pct']}%")
    if "coef" in r3["regression"]:
        print(f"  OLS r2={r3['regression']['r2']} coef={r3['regression']['coef']} VIF={r3['regression'].get('vif')}")
    else:
        print(f"  OLS: {r3['regression'].get('note')}")
    print("\n== RQ1 price tracking (daily) ==")
    r1 = results["RQ1_price_convergence"]
    print(f"  co-movement r={r1.get('price_comovement_r')}  median|premium|={r1.get('median_abs_premium_pct')}%  "
          f"range={r1.get('premium_range_pct')}  (no peg/convergence claim)")
    print("\n== RQ2 event volatility ==")
    r2 = results["RQ2_event_volatility"]
    print(f"  vol pre={r2.get('vol_pre')} post={r2.get('vol_post')} levene_p={r2.get('levene_p')}")
    print("\n== RQ4 block fullness ==")
    r4 = results["RQ4_block_fullness"]
    print(f"  utilization~volume pearson={r4['utilization~volume']['pearson']}  util_mean={r4['util_mean_pct']}%")

    out = os.path.join(DATA, "analysis_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
