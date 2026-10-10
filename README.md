# 🚀 Voratoon Daily Merit Auto-Maxer (General Edition)

Tool otomasi serbaguna (*general-purpose*) untuk memaksimalkan akumulasi **Merit** dan kenaikan **Level** pada sistem Kultivasi Voratoon (`v8.voratoon.com`). Dibuat murni menggunakan modul bawaan Python (*zero external dependencies*) dan mendukung multi-akun secara serentak.

---

## ✨ Fitur Utama
- ⚡ **Auto Daily Login:** Klaim reward login harian otomatis (+20 Merit).
- 📖 **Auto 50 Chapter Reads:** Otomatis membaca 50 chapter dengan simulasi jeda manusiawi/jitter (+500 Merit).
- 💬 **Auto 5 Komentar Organik:** Pengiriman & klaim 5 komentar unik (> 5 kata) dari bank kalimat acak agar lolos filter anti-spam (+75 Merit).
- 👥 **Multi-Account Support:** Mendukung pemrosesan banyak akun sekaligus dalam satu kali perintah (cukup pisahkan token dengan koma).
- 🎯 **Dynamic Series Discovery:** Menemukan serial komik populer secara otomatis tanpa perlu hardcode ID.
- 🎛️ **CLI Flags Lengkap:** Mendukung `--status-only` untuk cek kuota, `--token` untuk input fleksibel, serta `--delay-mult`.
- 🛡️ **Zero Dependencies:** Berjalan langsung di semua lingkungan Python 3 (Linux, macOS, Windows) tanpa perlu `pip install`.

---

## 🚀 Panduan Penggunaan

### 1. Clone Repository
```bash
git clone https://github.com/sofwanrsd/voratoon-merit-bot.git
cd voratoon-merit-bot
```

### 2. Dapatkan Auth Token Akun
1. Buka browser dan login ke akun Voratoon lo di [v8.voratoon.com](https://v8.voratoon.com).
2. Tekan **F12** (atau klik kanan -> *Inspect*) -> buka tab **Console**.
3. Jalankan baris perintah ini lalu tekan Enter:
   ```javascript
   copy(localStorage.getItem("komikcast_session_persistent"))
   ```
   *(Token sesi personal `oat_...` akan otomatis tersalin ke clipboard).*

### 3. Konfigurasi Token
Salin file template environment:
```bash
cp .env.example .env
nano .env
```
Isi file `.env` dengan token lo:
```env
# Satu akun:
VORATOON_TOKEN="oat_PASTE_TOKEN_DISINI"

# Atau multi-akun (pisahkan dengan koma):
# VORATOON_TOKEN="oat_AKUN_1,oat_AKUN_2,oat_AKUN_3"
```
*(Amankan file credential lo: `chmod 600 .env`)*

### 4. Menjalankan Script
```bash
# Eksekusi klaim otomatis semua akun
python3 merit_farmer.py

# Cek profil & sisa kuota hari ini tanpa melakukan klaim
python3 merit_farmer.py --status-only

# Jalankan dengan token langsung lewat argumen CLI
python3 merit_farmer.py -t "oat_xxx"

# Lihat semua opsi bantuan
python3 merit_farmer.py --help
```

---

## ⏰ Menjalankan Otomatis Harian (Crontab Linux VPS)

Server Voratoon melakukan reset kuota harian tepat pada pukul **00:00 WIB** (17:00 UTC). Pasang bot ini di crontab agar berjalan otomatis pada **00:01 WIB**:

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

---

## ⚠️ Disclaimer
Project ini dibuat semata-mata untuk tujuan riset, edukasi, dan pembuktian konsep (PoC) mengenai otomasi web dan pengujian ketahanan API. Gunakan secara bijak dan bertanggung jawab.
