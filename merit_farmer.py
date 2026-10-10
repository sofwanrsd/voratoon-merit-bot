#!/usr/bin/env python3
"""
Voratoon Daily Merit Auto-Maxer (General Public Edition)
A generic, multi-account compatible automation tool for Voratoon Cultivation system.

Features:
- Dynamic series discovery (fetches popular series automatically, no hardcoded IDs)
- Multi-account support (single token or comma-separated tokens in .env / CLI)
- Helper / Symbiotic Auto-Like Boost (+100 Merit from Resonansi Qi)
- Stealth jitter & natural human delay simulation
- Rich CLI interface (--help, --status-only, --series, --delay)
- Zero external dependencies (pure Python 3 standard library)
"""

import os
import sys
import time
import random
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

BASE_API = "https://api.voratoon.com"
ORIGIN = "https://v8.voratoon.com"
ENV_FILE = Path(__file__).parent / ".env"

COMMENTS_POOL = [
    "Karakter utamanya semakin berkembang sangat baik di sini",
    "Alur ceritanya tidak membosankan dan selalu seru dibaca",
    "Kualitas art dan visual komik ini sangat memanjakan mata",
    "Pertarungan di bagian ini sangat menegangkan dan memuaskan",
    "Terima kasih untuk mimin yang selalu update dengan cepat",
    "Plot twist di chapter ini bener-bener gak ketebak sama sekali",
    "Gak sabar nunggu kelanjutan cerita di chapter berikutnya",
    "Panel terakhir bener-bener bikin penasaran kelanjutannya",
    "Visualisasi jurus dan efek pertarungannya keren banget",
    "Pembangunan karakter sampingannya juga dapet banget feelnya",
    "Semoga mimin sehat selalu dan lancar terus garapannya",
    "Bagus banget ceritanya, sangat rekomendasi buat dibaca maraton",
    "Art style makin ke sini makin rapi dan detail banget",
    "Konflik ceritanya makin matang dan seru buat diikutin",
    "Gokil sih ini adaptasinya rapi banget terjemahannya",
    "Setiap minggunya selalu nungguin rilis komik ini",
    "Pengembangan dunianya detail dan seru untuk diikuti",
    "Makin seru aja tensi ceritanya, auto bookmark"
]

SERIES_POOL = [4718, 7133, 8261, 4541, 5501, 1658, 6490, 1880, 7488, 797]

def parse_args():
    parser = argparse.ArgumentParser(
        description="Voratoon Cultivation Merit Auto-Maxer CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-t", "--token", help="Voratoon Bearer Token (overrides .env)")
    parser.add_argument("-s", "--series", default="magic-emperor", help="Target series slug for chapters")
    parser.add_argument("-d", "--delay-mult", type=float, default=1.0, help="Delay multiplier for request intervals")
    parser.add_argument("--status-only", action="store_true", help="Only check profile status and daily quotas without claiming")
    parser.add_argument("--no-boost", action="store_true", help="Disable helper account auto-like booster")
    return parser.parse_args()

def load_tokens_config(cli_token: str = None) -> tuple[list[str], str, str]:
    """Load tokens, including primary and helper tokens if set."""
    tokens = []
    t_primary = None
    t_helper = None

    if cli_token:
        tokens = [t.strip() for t in cli_token.split(",") if t.strip()]
        return tokens, (tokens[0] if tokens else None), (tokens[1] if len(tokens) > 1 else None)

    env_token = os.environ.get("VORATOON_TOKEN")
    if env_token:
        tokens = [t.strip() for t in env_token.split(",") if t.strip()]

    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("VORATOON_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    tokens.extend([t.strip() for t in val.split(",") if t.strip()])
                elif line.startswith("ACCOUNT_1_TOKEN="):
                    t_primary = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("ACCOUNT_2_TOKEN="):
                    t_helper = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not t_primary and tokens:
        t_primary = tokens[0]
    if not t_helper and len(tokens) > 1:
        t_helper = tokens[1]

    unique_tokens = list(dict.fromkeys(tokens))
    return unique_tokens, t_primary, t_helper

def api_request(path: str, token: str = "", method: str = "GET", body: dict = None) -> tuple[int, dict]:
    url = f"{BASE_API}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": ORIGIN,
        "Referer": f"{ORIGIN}/",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_body = resp.read().decode("utf-8")
            return resp.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error": err_body}
    except Exception as e:
        return 500, {"error": str(e)}

def discover_series(fallback_slug: str = "magic-emperor") -> tuple[int, str]:
    st, res = api_request("/popular")
    if st == 200 and "data" in res and isinstance(res["data"], list) and len(res["data"]) > 0:
        first = res["data"][0]
        s_id = first.get("id")
        s_slug = first.get("data", {}).get("slug")
        if s_id and s_slug:
            return s_id, s_slug

    st_fb, res_fb = api_request(f"/series/{fallback_slug}")
    if st_fb == 200 and "data" in res_fb:
        return res_fb["data"].get("id", 4718), fallback_slug

    return 4718, fallback_slug

def fetch_series_chapters(series_slug: str, limit: int = 50) -> list[int]:
    st, res = api_request(f"/series/{series_slug}/chapters")
    if st == 200 and "data" in res and isinstance(res["data"], list):
        chapters = [c["id"] for c in res["data"] if isinstance(c, dict) and "id" in c]
        return chapters[:limit]
    return []

def boost_helper_likes(primary_token: str, helper_token: str, target_likes: int = 50):
    """Account 2 upvotes Account 1's comments to unlock full Resonansi Qi (+100 Merit)."""
    print("\n" + "=" * 60)
    print("🤝 Menjalankan Helper Booster: Like Komentar Silang (Resonansi Qi)")
    print("=" * 60)
    
    likes_done = 0
    for i in range(target_likes):
        sid = random.choice(SERIES_POOL)
        phrase = random.choice(COMMENTS_POOL) + f" #{random.randint(100, 999)}"
        
        st_p, res_p = api_request("/comments", token=primary_token, method="POST", body={"seriesId": sid, "content": phrase})
        if st_p in [200, 201] and "data" in res_p and "id" in res_p["data"]:
            cid = res_p["data"]["id"]
            st_u, _ = api_request(f"/comments/{cid}/upvote", token=helper_token, method="POST", body={})
            if st_u in [200, 201]:
                likes_done += 1
        time.sleep(0.18)

    print(f"✓ Helper Booster Selesai: {likes_done}/{target_likes} like berhasil disuntikkan!")

def farm_account(token: str, target_series_id: int, target_series_slug: str, delay_mult: float, status_only: bool = False):
    mask_token = token[:8] + "..." + token[-6:] if len(token) > 14 else "token"
    print("\n" + "=" * 60)
    print(f"🔑 Processing Account [{mask_token}]")
    print("=" * 60)

    # 1. Profile Status
    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print(f"❌ Autentikasi Gagal ({st}): Token mungkin kedaluwarsa.")
        return

    c_data = me.get("data", {})
    daily = c_data.get("daily", {})
    print(f"👤 Pengguna   : {c_data.get('username', 'Member')}")
    print(f"🏆 Kultivasi  : Level {c_data.get('level')} ({c_data.get('tier', {}).get('name', '-')})")
    print(f"✨ Total Merit: {c_data.get('merit', 0)} | Exp: {c_data.get('exp', 0)}")
    print(f"📊 Kuota Hari : Login {daily.get('login', {}).get('used', 0)}/{daily.get('login', {}).get('limit', 1)} | "
          f"Bab {daily.get('chapters', {}).get('used', 0)}/{daily.get('chapters', {}).get('limit', 50)} | "
          f"Komen {daily.get('comments', {}).get('used', 0)}/{daily.get('comments', {}).get('limit', 5)}")

    if status_only:
        print("ℹ️ Mode --status-only aktif, klaim dilewati.")
        return

    # 2. Daily Login Reward
    if daily.get("login", {}).get("remaining", 1) > 0:
        print("\n[1/3] Mengklaim Login Harian (+20 Merit)...")
        st_l, res_l = api_request("/cultivation/rewards/daily-login", token=token, method="POST", body={})
        if st_l in [200, 201]:
            print("  ✓ Login harian berhasil diklaim!")
        else:
            print(f"  - Login harian: {res_l.get('message', res_l.get('error', 'Sudah diklaim'))}")
    else:
        print("\n[1/3] Login harian sudah selesai hari ini.")

    # 3. Chapter Reads Reward
    ch_rem = daily.get("chapters", {}).get("remaining", 50)
    if ch_rem > 0:
        print(f"\n[2/3] Membaca Chapter (Sisa kuota: {ch_rem})...")
        chapters = fetch_series_chapters(target_series_slug, limit=ch_rem)
        if not chapters:
            print("  ⚠ Gagal mengambil daftar bab. Melewati langkah ini.")
        else:
            chap_ok = 0
            for cid in chapters:
                st_c, _ = api_request("/cultivation/rewards/chapter", token=token, method="POST", body={"targetId": cid, "mode": "chapter"})
                if st_c in [200, 201]:
                    chap_ok += 1
                time.sleep(random.uniform(0.2, 0.5) * delay_mult)
            print(f"  ✓ Selesai: {chap_ok}/{len(chapters)} bab berhasil diklaim.")
    else:
        print("\n[2/3] Kuota baca 50 chapter sudah maksimal hari ini.")

    # 4. Comments Reward
    com_rem = daily.get("comments", {}).get("remaining", 5)
    if com_rem > 0:
        print(f"\n[3/3] Mengirim & Mengklaim Komentar (Sisa kuota: {com_rem})...")
        selected_comments = random.sample(COMMENTS_POOL, min(com_rem, len(COMMENTS_POOL)))
        comm_ok = 0
        for text in selected_comments:
            st_post, res_post = api_request("/comments", token=token, method="POST", body={"seriesId": target_series_id, "content": text})
            if st_post in [200, 201] and "data" in res_post and "id" in res_post["data"]:
                cid = res_post["data"]["id"]
                st_claim, _ = api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": cid})
                if st_claim in [200, 201]:
                    comm_ok += 1
            time.sleep(random.uniform(0.7, 1.4) * delay_mult)
        print(f"  ✓ Selesai: {comm_ok}/{len(selected_comments)} komentar berhasil diklaim.")
    else:
        print("\n[3/3] Kuota 5 komentar sudah maksimal hari ini.")

    # 5. Final Status
    st_f, final_me = api_request("/cultivation/me", token=token)
    if st_f == 200:
        fd = final_me.get("data", {})
        f_daily = fd.get("daily", {})
        print("\n" + "-" * 60)
        print(f"🎉 STATUS AKHIR: Level {fd.get('level')} | Total Merit {fd.get('merit')} (+{fd.get('merit', 0) - c_data.get('merit', 0)})")
        print(f"📈 HASIL HARI INI: Login {f_daily.get('login', {}).get('used')}/{f_daily.get('login', {}).get('limit')} | "
              f"Bab {f_daily.get('chapters', {}).get('used')}/{f_daily.get('chapters', {}).get('limit')} | "
              f"Komen {f_daily.get('comments', {}).get('used')}/{f_daily.get('comments', {}).get('limit')}")

def main():
    args = parse_args()
    tokens, primary_token, helper_token = load_tokens_config(args.token)

    if not tokens:
        print("❌ [ERROR] Tidak ada token Voratoon yang ditemukan!")
        sys.exit(1)

    print("=" * 60)
    print("🚀 VORATOON CULTIVATION MERIT AUTO-MAXER (GENERAL EDITION)")
    print("=" * 60)
    print(f"📌 Ditemukan {len(tokens)} akun untuk diproses.")

    target_id, target_slug = discover_series(args.series)
    print(f"🎯 Target Series: {target_slug} (ID: {target_id})")

    # 1. Farm individual quotas for all accounts
    for idx, token in enumerate(tokens, 1):
        try:
            farm_account(token, target_id, target_slug, args.delay_mult, status_only=args.status_only)
        except Exception as e:
            print(f"❌ Error pada akun #{idx}: {e}")

    # 2. If helper account exists, run symbiotic auto-like boost for primary account
    if not args.status_only and not args.no_boost and primary_token and helper_token and primary_token != helper_token:
        try:
            boost_helper_likes(primary_token, helper_token, target_likes=50)
        except Exception as e:
            print(f"❌ Error saat helper like boost: {e}")

    print("\n" + "=" * 60)
    print("✅ Seluruh antrean akun & auto-boost telah selesai diproses.")
    print("=" * 60)

if __name__ == "__main__":
    main()
