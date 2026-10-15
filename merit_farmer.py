#!/usr/bin/env python3
"""
Voratoon Daily Merit Auto-Maxer
A clean, multi-account compatible automation tool for Voratoon Cultivation system.

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
CACHE_FILE = Path(__file__).parent / "claimed_chapters.json"

def load_claimed_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_claimed_cache(cache: dict):
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Gagal menyimpan cache bab: {e}")

COMMENTS_POOL = [
    "Art style di chapter ini makin memanjakan mata, eksekusi visualnya gokil",
    "Alur ceritanya bener-bener gak ngebosenin, selalu seru tiap babnya",
    "Panel terakhir bener-bener bikin penasaran sama kelanjutan ceritanya",
    "Pertarungan di bagian ini seru dan intens banget, puas bacanya",
    "Karakter utamanya cerdas banget ngambil keputusan di situasi begini",
    "Pacing ceritanya rapi, perkembangan karakternya dapet banget feelnya",
    "Terjemahannya enak dibaca dan rapi, makasih banyak min udah update",
    "Plot twistnya mantap, gak nyangka bakal dibawa ke arah sini alurnya",
    "Selalu seru nungguin update tiap minggu, makin greget ceritanya",
    "Visual efek pertarungannya juara sih, berasa banget tensi adegannya",
    "Bagus banget pendalaman dunianya, salah satu komik terbaik saat ini",
    "Gak sabar nunggu kelanjutan aksinya di chapter berikutnya min",
    "Kombinasi aksi dan tensi ceritanya dapet banget di bab ini",
    "Detail gambarnya makin rapi, ekspresi karakternya hidup banget",
    "Ceritanya konsisten bagus dari awal rilis, auto masuk list favorit",
    "Koreografi pertarungannya rapi banget, enak diliat gerakannya",
    "Karakter utamanya sat-set banget gak banyak drama, suka tipe begini",
    "Semangat terus min garap komik ini, sehat selalu tim translator",
    "Komplit banget ceritanya, ada selipan santai tapi aksinya tetep dapet",
    "Kualitas gambar jernih banget, panel aksinya bener-bener memuaskan",
    "Gak pernah bosen baca komik ini, selalu ada kejutan di tiap chapter",
    "Ekspektasi terbayar lunas di bab ini, klimaks ceritanya keren banget",
    "Pengembangan karakternya terasa natural dan gak dipaksakan",
    "Tiap minggu selalu jadi komik pertama yang gw buka pas rilis",
    "Pertarungan antar karakternya berbobot, gak cuma modal teriak jurus doang"
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

def boost_helper_likes(helper_token: str, target_comment_ids: list[int]):
    if not target_comment_ids:
        return
    print("\n" + "=" * 60)
    print(f"[*] Helper menyukai {len(target_comment_ids)} komentar bab akun utama...")
    print("=" * 60)
    
    likes_done = 0
    for cid in target_comment_ids:
        st_u, _ = api_request(f"/comments/{cid}/upvote", token=helper_token, method="POST", body={})
        if st_u in [200, 201]:
            likes_done += 1
        time.sleep(0.3)

    print(f"[OK] Helper Selesai: {likes_done}/{len(target_comment_ids)} komentar disukai secara natural.")

def farm_account(token: str, target_series_id: int, target_series_slug: str, delay_mult: float, status_only: bool = False) -> list[int]:
    mask_token = token[:8] + "..." + token[-6:] if len(token) > 14 else "token"
    print("\n" + "=" * 60)
    print(f"[*] Memproses Akun [{mask_token}]")
    print("=" * 60)
    created_comment_ids = []

    # 1. Profile Status
    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print(f"[ERROR] Autentikasi Gagal ({st}): Token mungkin kedaluwarsa.")
        return

    c_data = me.get("data", {})
    daily = c_data.get("daily", {})
    print(f"[-] Pengguna   : {c_data.get('username', 'Member')}")
    print(f"[-] Kultivasi  : Level {c_data.get('level')} ({c_data.get('tier', {}).get('name', '-')})")
    print(f"[-] Total Merit: {c_data.get('merit', 0)} | Exp: {c_data.get('exp', 0)}")
    print(f"[-] Kuota Hari : Login {daily.get('login', {}).get('used', 0)}/{daily.get('login', {}).get('limit', 1)} | "
          f"Bab {daily.get('chapters', {}).get('used', 0)}/{daily.get('chapters', {}).get('limit', 50)} | "
          f"Komen {daily.get('comments', {}).get('used', 0)}/{daily.get('comments', {}).get('limit', 5)}")

    if status_only:
        print("[INFO] Mode --status-only aktif, klaim dilewati.")
        return [], None

    # 2. Daily Login Reward
    if daily.get("login", {}).get("remaining", 1) > 0:
        print("\n[1/3] Mengklaim Login Harian (+20 Merit)...")
        st_l, res_l = api_request("/cultivation/rewards/daily-login", token=token, method="POST", body={})
        if st_l in [200, 201]:
            print("  [OK] Login harian berhasil diklaim!")
        else:
            print(f"  [-] Login harian: {res_l.get('message', res_l.get('error', 'Sudah diklaim'))}")
    else:
        print("\n[1/3] Login harian sudah selesai hari ini.")

    # 3. Chapter Reads Reward (Dynamic Multi-Series Crawler with Cache)
    ch_rem = daily.get("chapters", {}).get("remaining", 50)
    if ch_rem > 0:
        print(f"\n[2/3] Membaca Chapter (Sisa kuota: {ch_rem})...")
        cache = load_claimed_cache()
        acc_key = mask_token
        claimed_set = set(cache.get(acc_key, []))

        # Discover popular series pool to guarantee fresh, unread chapters
        st_p, res_p = api_request("/popular")
        series_pool = []
        if st_p == 200 and "data" in res_p and isinstance(res_p["data"], list):
            for s in res_p["data"]:
                slug = s.get("data", {}).get("slug")
                if slug and slug not in series_pool:
                    series_pool.append(slug)
        if not series_pool:
            series_pool = [target_series_slug]

        chap_ok = 0
        for slug in series_pool:
            if chap_ok >= ch_rem:
                break
            chapters = fetch_series_chapters(slug, limit=300)
            if not chapters:
                continue

            for cid in reversed(chapters):
                if cid in claimed_set:
                    continue
                st_c, res_c = api_request("/cultivation/rewards/chapter", token=token, method="POST", body={"targetId": cid, "mode": "chapter"})
                if st_c in [200, 201]:
                    d = res_c.get("data", {})
                    if not d.get("alreadyAwarded") and d.get("reward", {}).get("awardedMerit", 0) > 0:
                        chap_ok += 1
                        claimed_set.add(cid)
                    else:
                        claimed_set.add(cid)
                if chap_ok >= ch_rem:
                    break
                time.sleep(random.uniform(0.1, 0.25) * delay_mult)

        cache[acc_key] = list(claimed_set)
        save_claimed_cache(cache)
        print(f"  [OK] Selesai: {chap_ok}/{ch_rem} bab segar berhasil diklaim (+{chap_ok * 10} Merit).")
    else:
        print("\n[2/3] Kuota baca 50 chapter sudah maksimal hari ini (50/50).")

    # 4. Comments Reward (Natural Chapter Reviews Across 5 Different Popular Comics)
    com_rem = daily.get("comments", {}).get("remaining", 5)
    if com_rem > 0:
        print(f"\n[3/3] Mengirim & Mengklaim Komentar (Sisa kuota: {com_rem})...")
        st_p, res_p = api_request("/popular")
        series_pool = res_p.get("data", []) if (st_p == 200 and isinstance(res_p.get("data"), list)) else []
        
        # Pick distinct series so we NEVER spam 1 comic
        chosen_series = random.sample(series_pool, min(com_rem, len(series_pool))) if series_pool else []
        selected_comments = random.sample(COMMENTS_POOL, min(com_rem, len(COMMENTS_POOL)))
        comm_ok = 0

        for idx in range(len(chosen_series)):
            item = chosen_series[idx]
            s_id = item.get("id")
            s_slug = item.get("data", {}).get("slug", target_series_slug)
            
            # Fetch recent chapters: wajib komentar di dalam chapter spesifik!
            chaps = fetch_series_chapters(s_slug, limit=10)
            if not chaps:
                continue
            # Pick a recent chapter randomly among the top 5
            c_id = random.choice(chaps[:min(5, len(chaps))])
            
            text = selected_comments[idx]
            body = {
                "seriesId": s_id,
                "chapterId": c_id,
                "content": text
            }

            st_post, res_post = api_request("/comments", token=token, method="POST", body=body)
            if st_post in [200, 201] and "data" in res_post and "id" in res_post["data"]:
                cid = res_post["data"]["id"]
                created_comment_ids.append(cid)
                st_claim, _ = api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": cid})
                if st_claim in [200, 201]:
                    comm_ok += 1
                    print(f"  [OK] Komentar #{comm_ok} di {s_slug} [Chapter {c_id}]: \"{text[:45]}...\"")
            time.sleep(random.uniform(0.8, 1.5) * delay_mult)

        print(f"  [OK] Selesai: {comm_ok}/{len(chosen_series)} komentar bab berhasil diklaim (+{comm_ok * 15} Merit).")
    else:
        print("\n[3/3] Kuota 5 komentar sudah maksimal hari ini (5/5).")

    # 5. Final Status
    result_data = None
    st_f, final_me = api_request("/cultivation/me", token=token)
    if st_f == 200:
        fd = final_me.get("data", {})
        f_daily = fd.get("daily", {})
        gained = fd.get("merit", 0) - c_data.get("merit", 0)
        print("\n" + "-" * 60)
        print(f"[STATUS] Level {fd.get('level')} | Total Merit {fd.get('merit')} (+{gained})")
        print(f"[STATUS] Hasil Hari Ini: Login {f_daily.get('login', {}).get('used')}/{f_daily.get('login', {}).get('limit')} | "
              f"Bab {f_daily.get('chapters', {}).get('used')}/{f_daily.get('chapters', {}).get('limit')} | "
              f"Komen {f_daily.get('comments', {}).get('used')}/{f_daily.get('comments', {}).get('limit')}")
        result_data = {
            "level": fd.get("level"),
            "merit": fd.get("merit"),
            "gained": gained,
            "tier": fd.get("tier", {}).get("name", "Commoner"),
            "daily": f_daily,
            "username": fd.get("username", "Member")
        }

    return created_comment_ids, result_data

def send_telegram_alert(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    try:
        hermes_env = Path("/root/.hermes/.env")
        if not token and hermes_env.exists():
            with open(hermes_env, "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip('"\'')
    except Exception:
        pass
    if not token:
        return

    targets = [
        {"chat_id": "5678748710"},
        {"chat_id": "-1004385053126", "thread_id": 572}
    ]
    for tgt in targets:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": tgt["chat_id"],
                "text": text,
                "parse_mode": "Markdown"
            }
            if "thread_id" in tgt:
                payload["message_thread_id"] = int(tgt["thread_id"])
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            pass

def main():
    args = parse_args()
    tokens, primary_token, helper_token = load_tokens_config(args.token)

    if not tokens:
        print("[ERROR] Tidak ada token Voratoon yang ditemukan!")
        sys.exit(1)

    print("=" * 60)
    print("Voratoon Cultivation Merit Auto-Maxer")
    print("=" * 60)
    print(f"[*] Ditemukan {len(tokens)} akun untuk diproses.")

    target_id, target_slug = discover_series(args.series)
    print(f"[*] Target Series Default: {target_slug} (ID: {target_id})")

    primary_created_comments = []
    results = []

    # 1. Farm individual quotas for all accounts
    for idx, token in enumerate(tokens, 1):
        try:
            cids, res = farm_account(token, target_id, target_slug, args.delay_mult, status_only=args.status_only)
            if idx == 1 and cids:
                primary_created_comments = cids
            if res:
                results.append((idx, res))
        except Exception as e:
            print(f"[ERROR] Masalah pada akun #{idx}: {e}")

    # 2. If helper account exists, like the primary account's natural chapter reviews
    if not args.status_only and not args.no_boost and helper_token and primary_created_comments:
        try:
            boost_helper_likes(helper_token, primary_created_comments)
        except Exception as e:
            print(f"[ERROR] Masalah saat helper like boost: {e}")

    print("\n" + "=" * 60)
    print("[OK] Seluruh antrean akun dan auto-boost selesai diproses.")
    print("=" * 60)

    # 3. Kirim notifikasi Telegram otomatis
    if not args.status_only and results:
        lines = ["*Laporan Harian Voratoon Merit Auto-Maxer*", ""]
        for idx, r in results:
            role = "Akun Utama" if idx == 1 else f"Akun Helper #{idx - 1}"
            d = r.get("daily", {})
            lines.append(f"*{role}:*")
            lines.append(f"- Level: {r.get('level')} ({r.get('tier')})")
            lines.append(f"- Total Merit: {r.get('merit'):,} (+{r.get('gained')})")
            lines.append(f"- Kuota: Login {d.get('login', {}).get('used')}/{d.get('login', {}).get('limit')} | Bab {d.get('chapters', {}).get('used')}/{d.get('chapters', {}).get('limit')} | Komen {d.get('comments', {}).get('used')}/{d.get('comments', {}).get('limit')}")
            lines.append("")
        lines.append("Status: Otomatisasi berjalan lancar pada crontab VPS.")
        send_telegram_alert("\n".join(lines))

if __name__ == "__main__":
    main()
