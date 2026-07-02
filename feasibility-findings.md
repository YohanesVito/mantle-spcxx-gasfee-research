# Feasibility Findings — Validasi Sumber Data (Hari 1)

**Tanggal validasi:** 17 Juni 2026
**Status:** in-progress (Dexscreener, GeckoTerminal, Mantle RPC sudah; Etherscan & yfinance belum)

---

## Sumber #1 — Dexscreener (harga/volume SPCXx)
- ✅ Jalan, gratis tanpa key. Pool ketemu: **SPCXx/USDT0 @ Merchant Moe (Mantle)**, pair `0xd14B0DcD319551AE4D7B12787c00EE1C1f9E1d2E`, dibuat **2026-06-12 16:20 UTC** (konfirmasi tanggal listing).
- ❌ **Tidak ada data historis.** Hanya snapshot live + rolling window (m5/h1/h6/h24). Endpoint OHLCV/chart → 404. Tidak bisa backfill 12–16 Juni.
- ⚠️ **Volume sangat tipis:** h24 ≈ $9.290, 33 buy / 31 sell per 24 jam, likuiditas ≈ $108k. h1/h6 volume = 0.
- 📝 Hanya 1 pool Mantle terlihat (Merchant Moe). Fluxion pakai RFQ issuer-direct (bypass AMM) → kemungkinan tidak muncul sebagai pool DEX.

## Sumber #1b — GeckoTerminal (fallback OHLCV historis)
- ⚠️ Mengindeks pool (nama & tanggal cocok) TAPI **price=0.0, volume=None, 0 candle** (hour & day). Tidak punya data trade → **tidak andal untuk history**.

## ➡️ Konsekuensi: history SPCXx harus direkonstruksi dari **Swap event logs onchain** (`eth_getLogs`) sejak block pembuatan pool. Feasible karena volume tipis.

---

## Sumber #2 — Mantle RPC (`https://rpc.mantle.xyz`, chainId 5000)
- ✅ Jalan andal. Latest block ~96,775,877 @ 17 Juni 07:41 UTC.
- ✅ **Receipt punya field fee OP-stack lengkap:** `l1Fee`, `l1GasPrice`, `l1GasUsed`, `l1BaseFeeScalar`, `l1BlobBaseFee`, `effectiveGasPrice`, dll → dekomposisi L1 vs L2 fee per-tx PRESISI.
- ✅ `eth_getLogs` jalan (44 log / 5000 block utk pool) → rekonstruksi swap feasible (perlu chunking utk range besar).

### Temuan kritis yang MENGUBAH desain:
1. **`eth_feeHistory` flat & tidak berguna:** `baseFeePerGas` KONSTAN = **50 Gwei** di semua block; `reward` (priority) = 0. Konfirmasi non-EIP-1559/FIFO.
2. **L2 execution fee MENDOMINASI, bukan L1.** Sampel 40 user-tx: L1 share median **1,8%** (mean 3,05%, maks 9,7%). L2 dominan di 40/40 tx. → **Asumsi dokumen "L1 data fee biasanya mendominasi" SALAH untuk 2026** (efek blob/EIP-4844). RQ3 harus di-reframe.
3. **Block time FIXED 2,000 detik** (stdev 0,0000 atas 500 block). → **RQ4 (block time turun saat volume naik) NULL by design.** Tidak ada variansi untuk dijelaskan. RQ4 harus di-drop atau di-reframe ke metrik lain (tx-per-block / gas-used-per-block / block fullness).

---

## Sumber #3 — Gas ETH L1 (variabel pass-through)
- ✅ **Etherscan TIDAK diperlukan.** Dua alternatif gratis tanpa key:
  1. **Receipt Mantle sudah memuat `l1GasPrice` per-tx** → harga gas L1 yang benar-benar dipakai Mantle, langsung dari onchain.
  2. **ETH mainnet public RPC** (`https://ethereum-rpc.publicnode.com`, no key) → `eth_feeHistory` jalan; baseFee latest ≈ 0,118 Gwei (era pasca-blob, kongesti rendah).
- 📝 Gas L1 saat ini sangat rendah → makin menguatkan temuan bahwa komponen L1 fee Mantle remah-remah.

## Sumber #4 — yfinance (SPCX Nasdaq baseline)
- ✅ Jalan. Interval 1 jam tersedia ~5 hari ke belakang (19 baris, hanya jam bursa). Daily sejak 12 Juni: closes [160.95, 192.5, ...], last ≈ $202.
- ⚠️ SPCX hanya trading ~6,5 jam/hari kerja; SPCXx 24/7 → **mismatch jam** untuk RQ1 (premium/discount). Perlu strategi alignment (bandingkan hanya jam overlap, atau last-close vs harga onchain).

---

## Keputusan desain (disepakati 17 Juni)
- **RQ3** → reframe: uji **stabilitas total fee** terhadap volume SPCXx & gas ETH L1; dekomposisi L1 vs L2; narasi "fee stabil by design, bukan pass-through".
- **RQ4** → reframe: ganti block time (fixed 2s) ke **block fullness** (tx/block, gas-used/block).

---

## Pengumpulan Data — Milestone 1 (17 Juni): swap census ✅

Pool = Merchant Moe **Liquidity Book** (BUKAN Uniswap V2). Identifikasi event via keccak:
- Swap (asli): `0xad7d6f97abf51ce18e17a38f4d70e975be9c0708474987bb3e26ad21bd93ca70`
- `0x87f1f9…`=DepositedToBins · `0xa32e14…`=WithdrawnFromBins · `0x3f0b46…`=CompositionFees · `0x4a39dc…`=TransferBatch(ERC1155). Keempatnya = aktivitas LP, bukan trade.
- Token map: **tokenX = SPCXx (18 dec)** `0x68fa…Ce28`, **tokenY = USDT0 (6 dec)** `0x779D…3736`.
- Decode: data words = [id, amountsIn, amountsOut, volAcc, totalFees, protoFees]; amount bytes32 = amountX(low128)|amountY(high128).

Script: `scripts/backfill_swaps.py` (incremental/resumable) → `data/spcxx_swaps.csv`.

**Hasil 188 swap (12 Jun 18:05 → 16 Jun 21:45 UTC):**
- Harga: 187/188 bersih **$157–$394** (median $188,57); 1 dust outlier ($2e-6) perlu difilter. First $172 → last $208 (tren naik, mendukung H1a).
- Demand: total volume **$46.911**, **121 BUY / 67 SELL**, median trade **$33,54** (retail, tipis → low power).
- Fee (RQ3): **L1 share median 1,26% / mean 1,82% / max 10,30%** → konfirmasi L2 dominan di seluruh populasi swap.
- Eff gas price: floor **50 Gwei**, median **62,5**, max **148,8** → user kadang bayar di atas floor walau FIFO tak kasih keuntungan urutan (worth investigating).
- 44 jam aktif (≥1 trade) di window.

### Pengumpulan Data — Milestone 2 (17 Juni): network hourly ✅
Script `scripts/backfill_network.py` → `data/mantle_hourly.csv` (113 baris, 13–17 Jun).
- Gas ETH L1 (dari `l1GasPrice` receipt): **0,06–0,45 Gwei** (sangat rendah, post-blob).
- Block fullness: 1–2,5 tx/block, gasUsed ~60k–215k. Base fee konstan 50 Gwei.
- Mapping jam→block deterministik (block time 2s): `block = create + jam×1800`.

### Hasil PRELIMINARY (levels, 40 jam ber-trade, belum koreksi stasioneritas)
**RQ3:** fee_total vs volume SPCXx r=+0.10 (≈nol ✅) · fee_total vs gas ETH L1 r=+0.37 · fee_L1 vs gas ETH L1 r=+0.61 (sanity ✓) · eff_gas vs volume r=+0.10. → Komponen L1 tracking ETH gas tapi cuma ~2% total → total fee nyaris tak bergerak oleh demand. Mendukung "stable by design".
**RQ4:** fullness(gasUsed) vs volume r=−0.11 · tx/block vs volume r=−0.17 → kemungkinan null (SPCXx terlalu kecil vs kapasitas jaringan).
**Fee stability:** total fee mean 0,0244 MNT, CV 38,9%, L1 share 1,99%.

### Pengumpulan Data — Milestone 3 (17 Juni): kapasitas & headroom ✅
Script `scripts/capacity_report.py` → `data/capacity_summary.json`; kolom `utilization_pct` & `avg_gas_limit` ditambah ke `mantle_hourly.csv`.
- **Gas limit: 60.000.000 gas/block (konstan)** · block time 2,0s → kapasitas **30 jt gas/detik**.
- **Utilisasi: median 0,18% · mean 0,23% · puncak block 3,96%** → **headroom ~99,77%**.
- tx/block mean 2,33 · ~82k gas/tx · TPS aktual ~1,16 · max TPS ~365 (profil ini) / ~1.429 (transfer 21k).
- Caveat: 365 TPS = plafon dari gas-limit saja; sequencer/L1-DA bisa jadi bottleneck lebih dulu. Metrik bersih = **% utilisasi gas**, bukan TPS absolut.
- Implikasi: demand SPCXx tak menggerakkan fee/blocktime/fullness karena jaringan jalan di ~0,3% kapasitas (RQ4 null = headroom masif).

### Sisa pengumpulan data
- [x] Swap census, network hourly, kapasitas/headroom.
- [ ] Filter dust diterapkan di analisis (usdt0 > $1) — sudah dipakai; pertimbangkan simpan versi bersih.
- [ ] **Forward polling** sampai ~1 Juli (script sudah incremental/resumable — tinggal dijadwalkan).
- [ ] Cross-check gas ETH L1 dgn ETH mainnet RPC (opsional, robustness).
- [ ] Analisis final: ADF → first-difference → OLS + Newey-West + VIF; event-window volatility; konvergensi harga.
