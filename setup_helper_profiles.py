#!/usr/bin/env python3
"""
Voratoon Helper Natural Identity Provisioner (Fast Cached Edition)
"""

import sys
import io
import os
import time
import json
import random
import urllib.request
from pathlib import Path
from PIL import Image
import socks
from sockshandler import SocksiPyHandler

sys.path.insert(0, "/root/voratoon-bot")
from merit_farmer import load_tokens_config, api_request

HELPER_BIOS = [
    "Suka baca manhwa aksi dan fantasi • Santai aja",
    "Pembaca setia komik tiap malam sebelum tidur",
    "Lagi maraton komik kultivasi dan martial arts",
    "Pecinta manhwa bertema dungeon & leveling",
    "Bukan pembaca kilat, cuma suka nikmatin ceritanya",
    "Menikmati karya author dan tim penerjemah",
    "Daftar bacaan makin panjang, waktu makin dikit",
    "Penikmat komik santai di sela-sela kesibukan",
    "Suka karakter utama yang cerdas dan gak banyak drama",
    "Sering begadang gara-gara keasikan baca bab baru",
    "Koleksi bookmark makin banyak tiap minggu",
    "Pencinta genre fantasy, action, dan isekai",
    "Membaca komik adalah cara terbaik buat refreshing",
    "Menanti update chapter terbaru tiap hari",
    "Manhwa enthusiast • Selalu kepo sama kelanjutan plot",
    "Cuma pembaca biasa yang suka ngikutin cerita seru",
    "Suka art style yang detail dan pertarungan intens",
    "Membaca komik dari zaman webtoon lama sampai sekarang",
    "Kultivasi diri lewat cerita-cerita fiksi menarik",
    "Pecinta cerita regresi dan reinkarnasi nomor satu",
    "Menikmati setiap alur cerita dan perkembangan karakter"
]

AVATAR_DIR = Path("/root/voratoon-bot/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

def prepare_avatars(cover_urls, opener):
    prepared = []
    print(f"[*] Menyiapkan avatar anime lokal di {AVATAR_DIR}...")
    for i, url in enumerate(cover_urls, 1):
        target_path = AVATAR_DIR / f"avatar_{i}.jpg"
        if target_path.exists() and target_path.stat().st_size > 5000:
            prepared.append(target_path)
            continue

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=15) as resp:
                im = Image.open(io.BytesIO(resp.read()))
                w, h = im.size
                dim = min(w, int(h * 0.75))
                cx = w // 2
                cy = int(h * 0.38)
                left = max(0, cx - dim // 2)
                top = max(0, cy - dim // 2)
                right = min(w, left + dim)
                bottom = min(h, top + dim)
                crop = im.crop((left, top, right, bottom))
                crop = crop.resize((400, 400), Image.Resampling.LANCZOS).convert("RGB")
                crop.save(target_path, "JPEG", quality=90)
                prepared.append(target_path)
                print(f"  [+] Avatar #{i} siap: {target_path.name}")
        except Exception as e:
            print(f"  [!] Gagal download cover #{i}: {e}")

    return prepared

def upload_avatar_file(token: str, file_path: Path, opener):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(file_path, "rb") as f:
        img_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"avatar\"; filename=\"avatar.jpg\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + img_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        "https://api.voratoon.com/account/profile",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        data=body,
        method="PATCH"
    )
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def update_bio(token: str, bio_text: str, opener):
    req = urllib.request.Request(
        "https://api.voratoon.com/account/profile",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        data=json.dumps({"bio": bio_text}).encode("utf-8"),
        method="PATCH"
    )
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def main():
    print("=" * 65)
    print("  VORATOON HELPER NATURAL PROFILE SETUP")
    print("=" * 65)

    opener = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 9050))

    # 1. Ambil daftar cover komik resmi
    req_pop = urllib.request.Request("https://api.voratoon.com/popular", headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req_pop, timeout=15) as resp:
        pop_data = json.loads(resp.read().decode()).get("data", [])

    cover_urls = [s.get("data", {}).get("coverImage") for s in pop_data if s.get("data", {}).get("coverImage")]
    avatar_files = prepare_avatars(cover_urls, opener)

    if not avatar_files:
        print("[!] Tidak ada avatar yang berhasil dipersiapkan.")
        sys.exit(1)

    _, _, helper_tokens = load_tokens_config()
    print(f"\n[*] Menerapkan avatar & bio ke {len(helper_tokens)} akun helper...")

    for idx, token in enumerate(helper_tokens, 1):
        try:
            st_me, me = api_request("/auth/me", token=token)
            d = me.get("data", {})
            name = d.get("fullName") or d.get("username") or f"Helper #{idx}"

            # 1. Upload Avatar
            av_file = avatar_files[(idx - 1) % len(avatar_files)]
            upload_avatar_file(token, av_file, opener)

            # 2. Update Bio
            bio = HELPER_BIOS[(idx - 1) % len(HELPER_BIOS)]
            update_bio(token, bio, opener)

            print(f"  [+] Helper #{idx:2d} ({name:<18}): Avatar & Bio sukses dipasang -> \"{bio[:35]}...\"")
            time.sleep(0.2)

        except Exception as e:
            print(f"  [!] Helper #{idx:2d} Error: {e}")

    print("\n" + "=" * 65)
    print("[OK] Seluruh 21 akun helper kini memiliki foto profil & bio natural!")
    print("=" * 65)

if __name__ == "__main__":
    main()
