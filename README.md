# Voratoon Daily Merit Auto-Maxer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF.svg?logo=github-actions&logoColor=white)](.github/workflows/daily_farm.yml)

Tool otomasi untuk memaksimalkan akumulasi Merit dan kenaikan Level pada sistem Kultivasi Voratoon (`v8.voratoon.com`). Dibuat menggunakan modul bawaan Python tanpa dependensi eksternal tambahan dan mendukung pemrosesan multi-akun.

---

## Fitur Utama

- **Auto Daily Login:** Klaim reward login harian otomatis (+20 Merit).
- **Auto 50 Chapter Reads:** Otomatis membaca 50 chapter dengan jeda simulasi acak / jitter (+500 Merit).
- **Auto 5 Komentar Organik:** Pengiriman dan klaim 5 komentar unik (> 5 kata) dari bank kalimat acak agar sesuai dengan aturan anti-spam (+75 Merit).
- **Symbiotic Like Booster:** Dukungan akun pembantu (helper/tumbal) untuk melakukan upvote silang komentar agar membuka jatah penuh +100 Merit (Resonansi Qi) hingga total maksimal 695 Merit per hari.
- **Dukungan Multi-Akun:** Mendukung pemrosesan banyak akun sekaligus dalam satu kali eksekusi (cukup pisahkan token dengan tanda koma).
- **Pencarian Serial Dinamis:** Mendeteksi komik populer secara dinamis tanpa perlu konfigurasi ID manual.
- **Parameter CLI:** Mendukung `--status-only` untuk pemeriksaan kuota, `--token` untuk input langsung, dan `--delay-mult`.
- **Integrasi GitHub Actions:** Mendukung eksekusi terjadwal otomatis di cloud GitHub Actions tanpa perlu server VPS pribadi.

---

## Panduan Penggunaan

### 1. Dapatkan Token Sesi Akun

1. Buka browser dan login ke akun Voratoon di [v8.voratoon.com](https://v8.voratoon.com).
2. Buka DevTools Console (**F12** atau klik kanan -> *Inspect* -> pilih tab *Console*).
3. Jalankan perintah berikut lalu tekan Enter:
   ```javascript
   copy(localStorage.getItem("komikcast_session_persistent"))
   ```
   *(Token sesi format `oat_...` akan langsung tersalin ke clipboard).*

---

### Metode 1: Otomatisasi via GitHub Actions (Cloud Serverless)

1. **Fork** repositori ini ke akun GitHub Anda.
2. Buka repositori hasil fork, masuk ke menu **Settings** -> **Secrets and variables** -> **Actions**.
3. Klik **New repository secret**.
4. Isi Name dengan `VORATOON_TOKEN` dan Value dengan token akun Anda (dapat diisi satu token atau beberapa token yang dipisahkan koma).
5. Selesai. Workflow GitHub Actions akan otomatis dijalankan setiap hari pada pukul **00:01 WIB** (17:01 UTC).

---

### Metode 2: Menjalankan Mandiri di Linux / VPS / Komputer Lokal

1. **Clone Repositori:**
   ```bash
   git clone https://github.com/sofwanrsd/voratoon-merit-bot.git
   cd voratoon-merit-bot
   ```

2. **Konfigurasi Environment:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Isi file `.env`:
   ```env
   # Format satu akun:
   VORATOON_TOKEN="oat_TOKEN_DISINI"

   # Atau format dua akun (Akun Utama + Akun Helper untuk like booster):
   # ACCOUNT_1_TOKEN="oat_AKUN_UTAMA"
   # ACCOUNT_2_TOKEN="oat_AKUN_HELPER"
   ```
   *(Pastikan permission file dibatasi: `chmod 600 .env`)*

3. **Menjalankan Script:**
   ```bash
   # Skrip utama (contract-driven, baca /cultivation/catalog)
   python3 claim_daily_merit.py

   # Pemeriksaan status akun tanpa klaim
   python3 claim_daily_merit.py --status-only

   # Legacy (logika lama, tidak disarankan)
   python3 merit_farmer.py
   ```

   `claim_daily_merit.py` adalah script yang dipakai runner harian. Semua nilai
   limit diambil dari kontrak server, dan hasilnya divalidasi ulang terhadap
   leaderboard harian (top1 harus sama dengan plafon yang dihitung).

4. **Jadwal Crontab Linux (00:00:30 WIB):**
   ```bash
   crontab -e
   ```
   Tambahkan baris berikut di akhir file:
   ```cron
   0 17 * * * cd /path/ke/voratoon-merit-bot && sleep 30 && /usr/bin/python3 -u claim_daily_merit.py >> /path/ke/voratoon-merit-bot/farmer.log 2>&1
   ```
   Fallback kedua (idempoten, kuota yang sudah penuh otomatis dilewati):
   ```cron
   40 18 * * * cd /path/ke/voratoon-merit-bot && /usr/bin/python3 -u claim_daily_merit.py >> /path/ke/voratoon-merit-bot/farmer.log 2>&1
   ```

   **Penting:** pakai hanya satu runner. Dua runner dari IP berbeda akan
   saling men-toggle like (endpoint upvote itu toggle) dan merit bisa turun.

---

## Fakta Kontrak (Diverifikasi 2026-10-22)

Semua angka diambil dari `GET /cultivation/catalog`, bukan asumsi.

| Source | Merit | Limit | `meritDailyLimit` | Total Merit/Hari |
|---|---|---|---|---|
| `daily-login` | 20 | 1 | - | 20 |
| `chapter` | 10 | 50 | - | 500 |
| `comment` | 15 | 5 | - | 75 |
| `comment-like` | 2 | 100 like | 50 | 100 |
| `marathon` | 0 | 50 | - | 0 (exp only, butuh Premium Ultimate) |
| `premium-bonus` | 0 | - | - | 0 (exp only) |
| | | | **TOTAL** | **695** |

**Penting:** `meritDailyLimit` adalah jumlah **AKSI** yang memberi merit, bukan jumlah merit.
Jadi `comment-like` dengan `merit: 2` dan `meritDailyLimit: 50` menghasilkan `50 x 2 = 100` merit.

Bukti independen dari leaderboard server (`/rankings/users?period=daily|weekly|monthly`):
- 10 user teratas di leaderboard **harian** tepat `695` (tidak ada yang 645)
- Bulanan top-1 = `15290` = `22 x 695` persis
- Mingguan = `2780` = `4 x 695` persis

### Aturan endpoint upvote (toggle)

`POST /comments/{id}/upvote` bersifat **toggle**, dan `GET /comments/{id}` tidak ada (404):

| Response | Arti | Merit |
|---|---|---|
| `data.vote == 1` | Like baru berlaku | **+2** |
| `data.vote == null` | Vote lama dicabut (toggle off) | 0, harus di-*restore* |

Karena itu satu voter hanya boleh dipakai **sekali per komentar**, dan kalau kena toggle
langsung vote ulang untuk memulihkan. Kalau tidak, like yang sudah ada ikut tercabut.

---

## Rate Limit

Server membalas `HTTP 429` bila request terlalu cepat, dan limit-nya **per-IP**:
request yang sama dari IP berbeda langsung `200`.

Penanganan yang sudah terpasang:
- `_throttle()` -- rate limiter global, semua thread berbagi (default 0.12s antar request)
- Backoff `429` bertingkat: 5s -> 10s -> 20s -> 30s, lalu berhenti (tidak dipaksa)
- Transport berurutan: **Tor -> proxy -> direct**, dengan rotasi exit node (`SIGNAL NEWNYM`
  via ControlPort 9051) setiap 40 request

Aktifkan Tor di runner:
```bash
sudo apt-get install -y tor python3-pip
python3 -m pip install --break-system-packages PySocks
sudo sed -i 's/^#ControlPort 9051/ControlPort 9051/' /etc/tor/torrc
sudo systemctl restart tor
```

Variabel lingkungan opsional:
| Variabel | Default | Fungsi |
|---|---|---|
| `VORATOON_MIN_INTERVAL` | `0.12` | Jarak minimum antar request (detik) |
| `VORATOON_TOR_ROTATE` | `40` | Rotasi exit node Tor setiap N request |
| `VORATOON_NO_PROXY` | - | Set `1` untuk mematikan proxy/Tor (mode direct) |

---

## Parameter CLI

| Parameter | Nilai Default | Penjelasan |
|---|---|---|
| `-h, --help` | - | Menampilkan panduan opsi CLI |
| `-t, --token` | None | Menentukan token secara langsung (menimpa file `.env`) |
| `-s, --series` | `magic-emperor` | Target slug serial komik untuk pembacaan chapter |
| `-d, --delay-mult` | `1.0` | Pengali jeda waktu antar request |
| `--status-only` | `False` | Hanya menampilkan info profil dan sisa kuota harian |
| `--no-boost` | `False` | Menonaktifkan helper auto-like booster |

---

## Kontribusi

Kontribusi, perbaikan bug, saran fitur, issue, dan pull request sangat terbuka bebas bagi siapa saja yang ingin mengembangkan proyek ini lebih lanjut. Silakan fork repositori ini dan kirimkan PR Anda.

---

## Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Lihat file [LICENSE](LICENSE) untuk detail lengkap.

---

## Catatan

Proyek ini dibuat untuk tujuan riset, edukasi, dan pembuktian konsep (PoC) mengenai otomasi web dan pengujian ketahanan API. Gunakan secara bijak dan bertanggung jawab.
