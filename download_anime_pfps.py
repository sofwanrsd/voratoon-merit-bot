#!/usr/bin/env python3
"""
Download 21 Iconic Anime Character Profile Pictures from AniList CDN
Crops them into clean, high-resolution square 400x400 JPEGs.
"""

import urllib.request
import io
import json
from pathlib import Path
from PIL import Image

OUT_DIR = Path("/root/voratoon-bot/avatars")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ANIME_CHARACTERS = [
    "Gojo Satoru", "Luffy", "Zoro", "Levi", "Naruto",
    "Sasuke", "Eren Yeager", "Killua", "Tanjiro", "Ken Kaneki",
    "Kakashi", "Itachi", "Saitama", "Goku", "Law",
    "Light Yagami", "Edward Elric", "Rimuru", "Toji Fushiguro",
    "Ace", "Megumi Fushiguro"
]

def main():
    print(f"[*] Mengambil 21 PFP Anime Ikonik untuk 21 Helper...")
    for idx, name in enumerate(ANIME_CHARACTERS, 1):
        target = OUT_DIR / f"anime_{idx}.jpg"
        q = f"""query {{ Character(search: "{name}") {{ image {{ large }} }} }}"""
        req_gql = urllib.request.Request(
            "https://graphql.anilist.co",
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            data=json.dumps({"query": q}).encode()
        )
        try:
            with urllib.request.urlopen(req_gql, timeout=6) as resp:
                data = json.loads(resp.read().decode())
                img_url = data.get("data", {}).get("Character", {}).get("image", {}).get("large")
                if not img_url:
                    continue

            req_img = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_img, timeout=6) as r_img:
                im = Image.open(io.BytesIO(r_img.read()))
                w, h = im.size
                # Crop square fokus wajah bagian atas/tengah
                dim = min(w, int(h * 0.85))
                crop = im.crop((0, 0, dim, dim))
                crop = crop.resize((400, 400), Image.Resampling.LANCZOS).convert("RGB")
                crop.save(target, "JPEG", quality=95)
                print(f"  [+] #{idx:2d} {name:<18} -> {target.name} ({crop.size})")
        except Exception as e:
            print(f"  [-] #{idx:2d} {name}: {e}")

    print("[OK] Selesai mempersiapkan seluruh avatar anime!")

if __name__ == "__main__":
    main()
