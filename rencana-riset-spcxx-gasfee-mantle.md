# Rencana Riset: SPCXx Event Study & Dinamika Gas Fee di Mantle Network

**Untuk:** Mantle Research Challenge — Track 1 (The Research Deep Dive)
**Periode kompetisi:** 16 Juni – 3 Juli 2026
**Status dokumen:** Acuan kerja internal, bukan draf final submission

---

## 1. Latar Belakang

SpaceX resmi melantai di Nasdaq pada 12 Juni 2026 dengan ticker SPCX, harga IPO $135/saham, dana terkumpul ~$75 miliar (IPO terbesar sepanjang sejarah). Valuasi IPO ~$1,8 triliun, dan harga saham melonjak cepat (tutup ~$161 di hari pertama, +19%; menembus ~$201 per 16 Juni) sehingga market cap melampaui $2 triliun dalam beberapa hari. [^1] Bersamaan dengan itu, Mantle mengumumkan listing SPCXx — token tokenized SpaceX terbitan xStocks (bisnis tokenized-equity milik Kraken, diakuisisi Des 2025) — untuk trading 24/7 di Fluxion dan Merchant Moe. [^2]

Pada/sekitar hari listing (Jumat 12 Juni, dilaporkan luas 12–13 Juni — **bukan** 14 Juni), Binance, Bybit, dan Bitget membatalkan kampanye pre-IPO tokenized mereka karena xStocks gagal mengamankan alokasi saham asli, membuat lebih dari $1 miliar pesanan tidak terpenuhi — padahal permintaan ritel sempat menyentuh lebih dari $100 miliar. Sebagai gambaran skala, kampanye Binance saja menarik ~$557 juta deposit dari ~27.700 wallet (oversubscribed ~11x) sebelum dibatalkan. SPCXx tetap diluncurkan setelah IPO selesai, dengan sekitar $24 juta token bersirkulasi onchain di awal (data Arkham). [^3]

> **Catatan validasi (per 17 Juni 2026):** Seluruh klaim faktual di bagian ini sudah dicek silang ke sumber publik. Satu koreksi penting dari draf awal: tanggal pembatalan alokasi adalah **12–13 Juni**, bukan 14 Juni — ini berdampak ke anchor Event B (lihat §4 & §8). Catatan tambahan: SPCXx juga ada di chain lain (mis. Solana via Backpack Securities), jadi pastikan semua data harga/volume diambil dari pool **Mantle (Fluxion/Merchant Moe)**, jangan ketuker.

Fakta teknis penting dari dokumentasi resmi Mantle: jaringan ini **tidak menggunakan EIP-1559** (transaksi diproses sesuai urutan diterima, tanpa lelang priority fee), dan total biaya transaksi adalah gabungan **L2 execution fee + L1 data fee**, di mana L1 data fee biasanya mendominasi karena bergantung pada harga gas Ethereum saat itu. Artinya, secara teori, kemacetan/demand tinggi di Mantle sendiri tidak otomatis menaikkan fee — beda dengan L1 Ethereum.

Belum ada riset publik yang secara spesifik membahas pola gas fee Mantle berdasarkan waktu, apalagi dikaitkan dengan event nyata seperti lonjakan trading SPCXx. Ini jadi celah riset yang akan kita isi.

---

## 2. Tujuan, Pertanyaan Riset & Hipotesis

### Tujuan utama (satu kalimat)
> Menggunakan listing SPCXx sebagai **natural experiment** untuk menguji **apakah dan mengapa** biaya serta performa Mantle tetap stabil di bawah lonjakan demand on-chain yang nyata.

Riset ini **bukan empat pertanyaan terpisah**, melainkan **satu studi stimulus → respons**: SPCXx adalah *stimulus* (guncangan demand nyata), dan stabilitas Mantle adalah *respons*. Keempat RQ memainkan peran berbeda dalam satu garis cerita — bukan cabang yang sejajar.

| Peran | RQ | Pertanyaan | Hipotesis |
|---|---|---|---|
| **INTI — respons biaya** ⭐ | **RQ3** | Seberapa stabil **total fee** Mantle terhadap demand internal (volume SPCXx) & gas ETH L1? Komponen mana (L2 vs L1) yang dominan & apakah merespons? | H3a: Total fee stabil; korelasi ke **keduanya** lemah. Stabilitas dari **desain** (L2 base fee konstan + L1 minim pasca-blob), bukan pass-through L1 |
| Pendukung — *mekanisme* respons | RQ4 | Apakah **block fullness** (tx/blok, gas-used/blok) merespons volume SPCXx, walau block time tetap 2 detik? | H4a: Fullness ~tak merespons → bukti **headroom kapasitas** besar yang menjelaskan kenapa fee/performa tak goyah |
| Pendukung — *stimulus itu nyata* | RQ1 | Apakah harga SPCXx onchain melacak SPCX Nasdaq (premium/discount)? | H1a: Gap kecil & menyempit seiring waktu → SPCXx aset hidup yang representatif |
| Pendukung — *stimulus itu nyata* | RQ2 | Adakah reaksi harga/volatilitas di sekitar event cluster 12–13 Juni? | H2a: Volatilitas naik di window ±3 hari → guncangan demand benar-benar terjadi |

**Cara membaca:** *Ada guncangan demand asli (RQ1/RQ2) → fee Mantle tidak bergeming (RQ3) → karena kapasitasnya kelewat lega (RQ4).* Satu kesimpulan: **"Stable by Design."** RQ3 memikul ~60% bobot laporan; RQ1/RQ2 jadi pengantar singkat (membuktikan stimulus), RQ4 jadi penjelas mekanisme.

> **Catatan revisi hipotesis (berdasar validasi data 17 Juni):** Asumsi awal "L1 data fee mendominasi" **terbantah secara empiris** — sampel 40 user-tx menunjukkan L2 execution fee ≈ 98% dari total, L1 hanya ≈ 1,8% (median). Selain itu block time Mantle terkunci **persis 2,000 detik** (zero variance), sehingga RQ4 di-reframe dari "block time" ke "block fullness". Lihat `feasibility-findings.md` untuk bukti.

---

## 3. Variabel & Sumber Data

| Variabel | Granularitas | Sumber | Catatan |
|---|---|---|---|
| Harga & volume SPCXx onchain | per-swap → agregat per jam | **Rekonstruksi dari `eth_getLogs` (Swap events)** pool `0xd14B…1d2E` | Dexscreener/GeckoTerminal hanya snapshot live, tak punya history → harus dari onchain |
| Total fee Mantle | per-tx → agregat per jam | RPC `eth_getTransactionReceipt`: `gasUsed × effectiveGasPrice + l1Fee` | bukan `eth_feeHistory` (flat/tak berguna) |
| Komponen fee L2 vs L1 | per-tx | receipt: `effectiveGasPrice`, `gasUsed`, `l1Fee`, `l1GasPrice` | dipisah eksplisit (temuan: L2 ≈ 98%) |
| Harga gas Ethereum L1 | per jam | `l1GasPrice` di receipt Mantle **atau** ETH mainnet public RPC `eth_feeHistory` | **Etherscan tidak diperlukan** (tanpa key) |
| Harga SPCX (Nasdaq) | per jam (jam bursa) / harian | Yahoo Finance (`yfinance`) | baseline; trading ~6,5 jam/hari kerja → mismatch vs onchain 24/7 |
| Block fullness Mantle | per blok | RPC `eth_getBlockByNumber`: `gasUsed`, jumlah tx | RQ4 (pengganti block time yang fixed 2s) |
| Sirkulasi token SPCXx | snapshot | Arkham Intelligence | konteks tambahan |

---

## 4. Metodologi & Metode Penelitian

### 4.1 Paradigma & jenis penelitian
Riset **kuantitatif–empiris** bersifat **observasional (non-eksperimental)** — kita tidak memanipulasi variabel, melainkan mengamati data yang terbentuk natural di blockchain. Posisi: **explanatory + descriptive**. Karena volume SPCXx sangat tipis (~64 tx/hari), kita memakai **data populasi penuh (census)** — *seluruh* swap onchain sejak pool dibuat, bukan sampling → tidak ada sampling error.

### 4.2 Desain penelitian (tiga lapis per kelompok RQ)
| RQ | Desain | Teknik utama |
|---|---|---|
| RQ1, RQ2 | **Event study** (financial econometrics) | abnormal volatility, price convergence |
| RQ3 (inti) | **Time-series explanatory** | dekomposisi fee + regresi multivariat dgn kontrol stasioneritas |
| RQ4 | **Descriptive onchain analytics** | block fullness vs aktivitas |

### 4.3 Periode observasi — **expanding (incremental) window**
Ini menjawab langsung: **ya, window-nya incremental.** Periode observasi penuh membentang **12 Juni (listing SPCXx) → ~1–2 Juli (mendekati deadline)** dan **tumbuh setiap hari** lewat dua mekanisme:

- **Backfill retroaktif (sekali, di awal):** tarik mundur seluruh swap + fee + block dari onchain logs untuk 12–17 Juni yang sudah lewat. *Inilah kenapa data lama tidak hilang meski Dexscreener tak punya history* — ground-truth-nya tetap ada di blockchain.
- **Polling forward (harian/berkala):** lanjutkan menambah data baru sampai deadline, append ke dataset yang sama.

Jadi ada **dua jenis "window" yang harus dibedakan** (sering tertukar):

| Istilah | Rentang | Fungsi | Sifat |
|---|---|---|---|
| **Observation window** (estimation period) | 12 Jun → ~1 Jul, *expanding* | basis seluruh analisis korelasi/regresi RQ3; makin panjang makin tinggi statistical power | **incremental** ✅ |
| **Event window** | ±3 hari sekitar event cluster 12–13 Jun | isolasi reaksi abnormal RQ1/RQ2 | **fixed/anchored** |

Implikasi praktis dari sifat expanding ini:
- **RQ1 (price convergence)** justru paling pas dengan expanding window — premium/discount SPCXx vs SPCX di-track sebagai deret yang memanjang; H1a (gap menyempit seiring waktu) diuji langsung dari tren series yang tumbuh.
- **RQ3** memperoleh manfaat statistik langsung: tiap hari tambahan = lebih banyak observasi per-jam → estimasi koefisien lebih stabil, confidence interval menyempit.
- Re-run analisis bersifat **idempoten & deterministik**: ditentukan oleh block number, jadi setiap penambahan data hanya memperpanjang series, bukan mengubah yang lama.

### 4.4 Binning waktu
Agregasi per-swap/per-tx → **bucket per jam (UTC)**. Untuk analisis pola intraday, kelompokkan ke sesi global (Asia/Eropa/AS) agar relevan secara finansial; sediakan juga mapping WIB untuk interpretasi lokal.

### 4.5 Event windows & peringatan overlap
- Event A: 12 Juni (listing SPCXx) → ±3 hari
- Event B: 12–13 Juni (kegagalan alokasi Binance/Bybit/Bitget) → ±3 hari

> **Peringatan metodologis:** Event A & B hampir berhimpit → window ±3 hari **overlap berat**, sehingga efek listing vs kegagalan alokasi **tidak bisa dipisah** secara statistik. Penanganan: perlakukan sebagai **satu event cluster 12–13 Juni** + analisis **intraday** untuk resolusi lebih halus. Akui eksplisit sebagai limitasi.

### 4.6 Metode analisis statistik (diperbarui dari temuan)
1. **Uji stasioneritas (ADF)** lebih dulu pada deret fee/harga/volume. Jika non-stasioner → pakai **first-difference** atau **log-return** agar korelasi tidak *spurious*.
2. **Korelasi Pearson (linear) + Spearman (rank)** sebagai robustness check: total fee vs gas ETH L1, dan total fee vs volume SPCXx.
3. **Regresi OLS:** `Δfee_total ~ Δgas_eth_l1 + Δvolume_spcxx`, dengan **Newey-West HAC standard errors** (autokorelasi time-series) dan **VIF** (deteksi multikolinearitas). Ulangi terpisah untuk komponen `Δfee_L2` dan `Δfee_L1` untuk menunjukkan sumber (in)stabilitas.
4. **Event study (RQ1/RQ2):** bandingkan std. deviasi return / volatilitas **pre vs post** event cluster; RQ1 tambahan: regresi tren premium/discount terhadap waktu (uji konvergensi).
5. **RQ4:** korelasi **block fullness** (tx/blok, gas-used/blok) vs volume SPCXx, dipisah dari analisis fee. Catat block time sebagai **null result** (invariant 2s).

> **Catatan power statistik:** karena volume tipis, hasil non-signifikan bisa berarti *kurang data*, bukan *tidak ada efek*. Laporkan **effect size + confidence interval**, bukan hanya p-value.

### 4.7 Validitas, reliabilitas, reproducibility
- **Internal validity:** data census + ground-truth onchain; confounding (gas L1 & volume naik bersamaan saat event) ditangani via diferensiasi + kontrol regresi.
- **Reliability/reproducibility:** seluruh pipeline deterministik dari block number; replikabel dari RPC publik. Script + raw data di-commit.
- **External validity (diakui jujur):** sampel waktu pendek (<3 minggu), satu token, satu chain → temuan **deskriptif untuk kasus SPCXx–Mantle**, bukan generalisasi universal.

---

## 5. Tools & Tech Stack

- Python: `pandas`, `requests`, `matplotlib`/`plotly`, `scipy`/`statsmodels`
- `yfinance` untuk data SPCX Nasdaq (terpasang & tervalidasi)
- RPC Mantle (`https://rpc.mantle.xyz`, chainId 5000) via JSON-RPC: `eth_getLogs` (rekonstruksi swap), `eth_getTransactionReceipt` (fee + `l1Fee`), `eth_getBlockByNumber` (block fullness)
- ETH mainnet public RPC (`https://ethereum-rpc.publicnode.com`, tanpa key) untuk gas L1 — **menggantikan Etherscan** (tidak perlu API key)
- ~~Etherscan API~~ → **tidak diperlukan**; gas L1 sudah ada di `l1GasPrice` receipt Mantle + ETH public RPC
- Dexscreener API (gratis) hanya untuk **cross-check snapshot live**, bukan sumber history (tak menyediakan OHLCV historis)

---

## 6. Timeline Kerja (selaras window 16 Juni – 3 Juli)

- **Hari 1–3:** setup script, uji koneksi semua API/RPC, tarik data historis yang masih tersedia sejak 12 Juni
- **Hari 4–13:** polling data per jam secara konsisten (bisa pakai cron job sederhana atau jalankan manual terjadwal)
- **Hari 14–15:** bersihkan data, jalankan analisis statistik, buat visualisasi
- **Hari 16–17:** tulis laporan + format jadi X article/thread (chart → gambar), siapkan repo GitHub
- **Hari 18:** review akhir, join Discord, publish di X (follow + tag @Mantle_Official), like & share artikel, submit form (cek wallet!)

---

## 7. Outline Laporan Akhir (format: X long-form article / thread)

> Disajikan untuk dibaca di X — hook kuat di awal, chart sebagai gambar, kesimpulan tegas. Kedalaman akademis dipertahankan, tapi dikemas naratif. Repo GitHub (script + data mentah) di-link sebagai bukti reproducibility.

1. **Hook & temuan utama** (1–2 paragraf pembuka: "Mantle bilang fee-nya stabil. Aku buktikan pakai data SPCXx — dan kebenarannya lebih menarik dari klaimnya.")
2. Pendahuluan & motivasi (kenapa pertanyaan ini penting buat Mantle)
3. Latar belakang fakta (IPO SpaceX, SPCXx, mekanisme fee Mantle)
4. Pertanyaan riset & hipotesis
5. Metodologi & data (ringkas; detail teknis ke repo)
6. **Temuan** (chart korelasi/regresi sebagai gambar; highlight: L2 dominan, fee stabil by design, block time fixed 2s)
7. Implikasi untuk Mantle — kaitkan langsung ke narasi reliability / distribution layer mereka
8. Limitasi & saran riset lanjutan
9. Link repo + sumber

---

## 8. Risiko & Limitasi

- Sampel data terbatas karena SPCXx baru listing 12 Juni — kurang dari 3 minggu data saat deadline.
- Likuiditas pool Fluxion/Merchant Moe untuk SPCXx mungkin masih tipis di awal, sehingga harga onchain bisa noisy/tidak representatif.
- Rate limit di API gratis (Etherscan, Dexscreener) — perlu jeda antar request atau caching lokal.
- Korelasi tidak sama dengan kausalitas — perlu hati-hati saat interpretasi hasil regresi.
- **Event A & B overlap** (12–13 Juni) — efek listing dan kegagalan alokasi tidak bisa dipisah secara bersih (lihat §4).
- **Confounding RQ3:** gas ETH L1 dan volume SPCXx bisa naik bersamaan di event yang sama → risiko korelasi spurious & multikolinearitas. Mitigasi: pakai first-difference/lag pada series, laporkan VIF.
- **`eth_feeHistory` di chain non-EIP-1559** mungkin mengembalikan baseFee konstan/0 dan reward array kosong; fee aktual lebih akurat dihitung dari `effectiveGasPrice × gasUsed` di receipt + L1 data fee dari GasPriceOracle (`0x420...000F`). Wajib diverifikasi di Hari 1.
- **Multi-chain SPCXx:** token tokenized SpaceX ada juga di luar Mantle — semua data harus dikunci ke pool Mantle/Fluxion agar tidak tercampur.

---

## 9. Format Submission & Checklist (sumber: pengumuman resmi @Mantle_Official, 16 Juni 2026)

### Detail campaign
- **Nama:** Mantle Research Challenge — "Prove the Next Move in Onchain Finance"
- **Durasi:** 18 hari, **16 Juni – 3 Juli 2026**
- **Hadiah:** total **$6.000** (dibayar dalam **$MNT**), **30 pemenang** lintas 2 track
- **Track kita:** **Track 1 — The Research Deep Dive** (tulis riset yang kuat & berbasis bukti tentang pergeseran terkini di onchain finance: pilih satu *market move*, jelaskan kenapa terjadi, argumenkan apa yang akan terjadi berikutnya)
- **Topik yang relevan:** RWA → **Stocks & IPOs** (persis kasus SPCXx kita), berita ekosistem Mantle, tren onchain finance lain
- **Angle yang diakui juri:** *"Follow the data — pull the numbers, show the trend, let the evidence make your case"* ← **ini persis pendekatan riset kita**

### ⚠️ Insight format paling penting
**Deliverable utama = riset yang DIPUBLISH DI X**, bukan PDF/paper yang disimpan terpisah. Implikasinya untuk laporan akhir kita:
- Output harus **X-publishable**: long-form X article atau thread terstruktur, dengan **chart sebagai gambar** (bukan tabel mentah).
- Kedalaman akademis tetap dipertahankan (itu nilai jual kita), tapi **disajikan untuk dibaca di X** — narasi jelas, hook kuat di awal, kesimpulan tegas.
- Pertimbangkan dua lapis: (a) X article/thread sebagai submission utama, (b) repo GitHub berisi script + data mentah sebagai bukti reproducibility (di-link dari artikel).

### Kriteria penilaian juri
Quality • Accuracy • Originality • Depth of research. (Originalitas & kedalaman = keunggulan riset data-driven onchain kita.)

### Checklist partisipasi (urutan resmi)
- [ ] Join Mantle creators community di **Discord**
- [ ] **Publish** riset di X
- [ ] **Follow** DAN **tag @Mantle_Official** di post
- [ ] **Like & share** artikel campaign resmi
- [ ] Submit entry lewat **participation form** resmi
- [ ] Cek ulang **alamat wallet** sebelum submit (tidak bisa diganti, reward salah kirim tidak bisa ditarik)
- [ ] Pastikan **karya orisinal** (akun palsu/bot/plagiat = diskualifikasi; dengan ikut, Mantle boleh repost karya kita)
- [ ] Pastikan eligibility: **18+**, bukan dari negara tersanksi/dibatasi

---

## Sumber (validasi fakta per 17 Juni 2026)

[^1]: IPO SpaceX $135/saham, ~$75 miliar, debut +19% → [CoinDesk](https://www.coindesk.com/markets/2026/06/11/spacex-prices-shares-at-usd135-in-largest-ipo-ever), [CNBC](https://www.cnbc.com/2026/06/12/spacex-ipo-spcx-live-updates.html)
[^2]: Listing SPCXx di Fluxion & Merchant Moe → [Chainwire](https://chainwire.org/2026/06/12/mantle-and-xstocks-bring-tokenized-spacex-spcxx-to-fluxion-merchant-moe-as-historys-largest-ipo-goes-live/); mekanisme fee Mantle (non-EIP-1559, L2 exec + L1 data fee) → [Mantle Docs](https://github.com/LayerE/Mantle-Docs/blob/main/Transaction%20Fees%20on%20L2.md)
[^3]: Pembatalan alokasi (12–13 Juni), >$1B order, Binance ~$557M → [The Block](https://www.theblock.co/post/404644/bybit-binance-bitget-cancel-tokenized-spacex-ipo-allocations-share-shortage), [Cryptonomist](https://en.cryptonomist.ch/2026/06/15/spacex-ipo-tokenized-stocks/); ~$24 juta SPCXx onchain + permintaan ritel >$100B (Arkham) → [CoinDesk](https://www.coindesk.com/tech/2026/06/13/spacex-ipo-scramble-reveals-difference-between-tokenizing-a-stock-and-getting-one)
