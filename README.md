# 🚀 Voratoon Daily Merit Auto-Maxer (General Edition)

Tool otomasi serbaguna (*general-purpose*) untuk memaksimalkan akumulasi **Merit** dan kenaikan **Level** pada sistem Kultivasi Voratoon (`v8.voratoon.com`). Dibuat murni menggunakan modul bawaan Python (*zero external dependencies*) dan mendukung multi-akun secara serentak.

---

## ✨ Fitur Utama
- ⚡ **Auto Daily Login:** Klaim reward login harian otomatis (+20 Merit).
- 📖 **Auto 50 Chapter Reads:** Otomatis membaca 50 chapter dengan simulasi jeda manusiawi/jitter (+500 Merit).
- 💬 **Auto 5 Komentar Organik:** Pengiriman & klaim 5 komentar unik (> 5 kata) dari bank kalimat acak agar lolos filter anti-spam (+75 Merit).
- 🤝 **Symbiotic Like Booster:** Dukungan akun helper/tumbal untuk auto-upvote komentar agar membuka jatah penuh **+100 Merit (Resonansi Qi)** hingga total mentok **695 Merit/hari**.
- 👥 **Multi-Account Support:** Mendukung pemrosesan banyak akun sekaligus dalam satu kali perintah (cukup pisahkan token dengan koma).
- 🎯 **Dynamic Series Discovery:** Menemukan serial komik populer secara otomatis tanpa perlu hardcode ID.
- 🎛️ **CLI Flags Lengkap:** Mendukung `--status-only` untuk cek kuota, `--token` untuk input fleksibel, serta `--delay-mult`.
- ☁️ **GitHub Actions Ready:** Bisa berjalan otomatis 24/7 di cloud GitHub Actions secara **gratis tanpa perlu sewa VPS**.

---

## 🚀 Panduan Penggunaan

### 1. Dapatkan Auth Token Akun
1. Buka browser dan login ke akun Voratoon lo di [v8.voratoon.com](https://v8.voratoon.com).
2. Tekan **F12** (atau klik kanan -> *Inspect*) -> buka tab **Console**.
3. Jalankan baris perintah ini lalu tekan Enter:
   ```javascript
   copy(localStorage.getItem("komikcast_session_persistent"))
   ```
   *(Token sesi personal `oat_...` akan otomatis tersalin ke clipboard).*

---

### OPSI A: Otomatisasi Gratis via GitHub Actions (Tanpa VPS) ☁️
Cocok untuk siapa saja yang ingin jalan otomatis tanpa punya server sendiri:
1. **Fork** repository ini ke akun GitHub lo.
2. Di repository hasil fork lo, masuk ke tab **Settings** -> **Secrets and variables** -> **Actions**.
3. Klik tombol **New repository secret**.
4. Isi Name: `VORATOON_TOKEN` dan Value: Token sesi akun lo (bisa single atau dipisah koma untuk multi-akun).
5. Selesai! Bot akan otomatis berjalan setiap hari pada pukul **00:01 WIB** via GitHub Actions.

---

### OPSI B: Menjalankan Mandiri di Komputer / VPS Linux 💻
1. **Clone Repository:**
   ```bash
   git clone https://github.com/sofwanrsd/voratoon-merit-bot.git
   cd voratoon-merit-bot
   ```

2. **Konfigurasi Environment:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Isi file `.env` dengan token:
   ```env
   # Satu akun:
   VORATOON_TOKEN="oat_PASTE_TOKEN_DISINI"

   # Atau multi-akun (Akun Utama + Akun Helper untuk like booster):
   # ACCOUNT_1_TOKEN="oat_AKUN_UTAMA"
   # ACCOUNT_2_TOKEN="oat_AKUN_HELPER"
   ```

3. **Jalankan Bot:**
   ```bash
   # Eksekusi klaim otomatis
   python3 merit_farmer.py

   # Cek profil & kuota tanpa klaim
   python3 merit_farmer.py --status-only
   ```

4. **Jadwalkan di Crontab (00:01 WIB):**
   ```bash
   crontab -e
   ```
   Tambahkan baris berikut di akhir file:
   ```cron
   1 17 * * * /usr/bin/python3 /path/ke/voratoon-merit-bot/merit_farmer.py >> /path/ke/voratoon-merit-bot/farmer.log 2>&1
   ```

---

## 🛠️ CLI Options
| Flag | Default | Penjelasan |
|---|---|---|
| `-h, --help` | - | Menampilkan panduan parameter CLI |
| `-t, --token` | None | Menentukan token langsung (menimpa file `.env`) |
| `-s, --series` | `magic-emperor` | Target slug komik untuk pembacaan chapter |
| `-d, --delay-mult` | `1.0` | Pengali delay (misal: `1.5` untuk jeda lebih lambat/santai) |
| `--status-only` | `False` | Hanya memeriksa info profil & limit harian tanpa klaim |
| `--no-boost` | `False` | Menonaktifkan helper auto-like booster |

---

## ⚠️ Disclaimer
Project ini dibuat semata-mata untuk tujuan riset, edukasi, dan pembuktian konsep (PoC) mengenai otomasi web dan pengujian ketahanan API. Gunakan secara bijak dan bertanggung jawab.
