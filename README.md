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
   # Eksekusi klaim otomatis
   python3 merit_farmer.py

   # Pemeriksaan status akun tanpa klaim
   python3 merit_farmer.py --status-only
   ```

4. **Jadwal Crontab Linux (00:01 WIB):**
   ```bash
   crontab -e
   ```
   Tambahkan baris berikut di akhir file:
   ```cron
   1 17 * * * /usr/bin/python3 /path/ke/voratoon-merit-bot/merit_farmer.py >> /path/ke/voratoon-merit-bot/farmer.log 2>&1
   ```

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
