# 🚀 Voratoon Daily Merit Auto-Maxer

Bot otomatisasi harian untuk memaksimalkan perolehan **Merit** dan **Level** pada sistem Kultivasi Voratoon (`v2.voratoon.com`), dirancang untuk bersaing di papan peringkat (*Leaderboard* bulanan) perebutan voucher Google Play Card / Steam Wallet.

---

## ✨ Fitur Utama
- ⚡ **Auto Daily Login:** Klaim login harian otomatis (+20 Merit).
- 📖 **Auto 50 Chapter Reads:** Otomatis membaca 50 chapter valid dengan jeda delay natural (+500 Merit).
- 💬 **Auto 5 Komentar:** Otomatis mengirim & klaim reward 5 komentar dinamis dengan panjang > 5 kata sesuai aturan anti-spam backend (+75 Merit).
- 🛡️ **Cloudflare & WAF Friendly:** Berjalan menggunakan simulasi header origin resmi tanpa membebani server.
- ⏰ **Otomatisasi 24/7:** Siap dipasang di Crontab / Task Scheduler untuk berjalan setiap jam 00:01 WIB.

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Clone Repository
```bash
git clone https://github.com/sofwanrsd/voratoon-merit-bot.git
cd voratoon-merit-bot
```

### 2. Dapatkan Auth Token Akun Voratoon
1. Buka browser dan login ke akun lo di [v2.voratoon.com](https://v2.voratoon.com).
2. Tekan **F12** (atau klik kanan -> *Inspect*) -> pilih tab **Console**.
3. Jalankan kode berikut lalu tekan Enter:
   ```javascript
   copy(localStorage.getItem("komikcast_session_persistent"))
   ```
   *(Token otomatis tersalin ke clipboard lo).*

### 3. Konfigurasi Environment
Salin file contoh konfigurasi dan masukkan token lo:
```bash
cp .env.example .env
nano .env
```
Isi file `.env`:
```env
VORATOON_TOKEN="oat_PASTE_TOKEN_LO_DISINI"
```
*(Pastikan hak akses file dibatasi: `chmod 600 .env`)*

### 4. Jalankan Bot
Script ini murni menggunakan library standar Python (tanpa perlu install pip library tambahan):
```bash
python3 merit_farmer.py
```

---

## ⏰ Menjalankan Otomatis Setiap Hari (Crontab Linux)

Agar bot berjalan otomatis tepat saat reset harian Voratoon pukul **00:01 WIB** (17:01 UTC):

1. Buka konfigurasi crontab:
   ```bash
   crontab -e
   ```
2. Tambahkan baris berikut di bagian paling bawah:
   ```cron
   1 17 * * * /usr/bin/python3 /path/ke/voratoon-merit-bot/merit_farmer.py >> /path/ke/voratoon-merit-bot/farmer.log 2>&1
   ```

---

## ⚠️ Disclaimer
Project ini dibuat semata-mata untuk tujuan riset, edukasi, dan pembuktian konsep (PoC) mengenai otomasi web dan pengujian ketahanan API. Gunakan secara bijak dan bertanggung jawab.
