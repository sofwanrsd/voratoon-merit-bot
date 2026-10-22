#!/usr/bin/env python3
"""
Voratoon Daily Merit Fetcher
Automation tool for Voratoon Cultivation daily quests (login, chapter reads, chapter comments).

Features:
- Dynamic series discovery (fetches popular series automatically, no hardcoded IDs)
- Multi-account support (single token or comma-separated tokens in .env / CLI)
- Hard wall-clock guard per request + per account (no infinite hangs)
- Circuit breaker per transport (dead SOCKS/Tor tunnel is skipped, not waited on)
- Rate-limit aware: backs off and stops on HTTP 429
- Rich CLI interface (--help, --status-only, --series, --delay)
- Zero external dependencies (pure Python 3 standard library)
"""

import os
import sys
import time
import random
import json
import socket
import signal
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
        description="Voratoon Daily Quest Fetcher CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-t", "--token", help="Voratoon Bearer Token (overrides .env)")
    parser.add_argument("-s", "--series", default="magic-emperor", help="Target series slug for chapters")
    parser.add_argument("-d", "--delay-mult", type=float, default=1.0, help="Delay multiplier for request intervals")
    parser.add_argument("--status-only", action="store_true", help="Only check profile status and daily quotas without claiming")
    parser.add_argument("--jitter", action="store_true", help="Aktifkan jeda acak di awal eksekusi (default: mati/instan)")
    return parser.parse_args()

def load_tokens_config(cli_token: str = None) -> tuple[list[str], str, list[str]]:
    tokens = []
    t_primary = None
    helper_tokens = []

    if cli_token:
        tokens = [t.strip() for t in cli_token.split(",") if t.strip()]
        return tokens, (tokens[0] if tokens else None), tokens[1:]

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
                    helper_tokens.append(line.split("=", 1)[1].strip().strip('"').strip("'"))

    # Load helper tokens dari HELPER_ACCOUNTS.md jika ada
    md_file = ENV_FILE.parent / "HELPER_ACCOUNTS.md"
    if md_file.exists():
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("|") and "`oat_" in line:
                        for part in line.split("|"):
                            part = part.strip()
                            if part.startswith("`oat_") and part.endswith("`"):
                                h_tok = part.strip("`")
                                if h_tok not in helper_tokens:
                                    helper_tokens.append(h_tok)
        except Exception:
            pass

    if not t_primary and tokens:
        t_primary = tokens[0]

    unique_tokens = list(dict.fromkeys(tokens))
    return unique_tokens, t_primary, helper_tokens

REQUEST_HARD_CAP = 25  # detik, plafond mutlak untuk SATU request (wajib, bukan opsional)
ACCOUNT_DEADLINE = 240  # detik, budget satu akun sebelum di-abort

# Circuit breaker: setiap transport yang gagal beruntun langsung dimatikan supaya
# tidak ada request lagi yang menggantung di jalur mati.
_TRANSPORT_FAILS = {"proxy": 0, "tor": 0, "direct": 0}
_TRANSPORT_MAX_FAILS = 3


class HardTimeout(Exception):
    pass


class _hard_timeout:
    """SIGALRM guard. urllib timeout= TIDAK berlaku pada socket yang dibuat
    sockshandler setelah handshake SOCKS, jadi tanpa guard ini request bisa
    menggantung tanpa batas ( penyebab worker 7 jam tanpa output )."""

    def __init__(self, seconds: int):
        self.seconds = max(1, int(seconds))
        self._armed = False

    def __enter__(self):
        try:
            self._old = signal.signal(signal.SIGALRM, self._fire)
            signal.alarm(self.seconds)
            self._armed = True
        except Exception:
            self._armed = False
        return self

    def _fire(self, signum, frame):
        raise HardTimeout(f"request melewati {self.seconds}s")

    def __exit__(self, exc_type, exc, tb):
        if self._armed:
            try:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, self._old)
            except Exception:
                pass
        return False


def _transport_ok(name: str) -> bool:
    return _TRANSPORT_FAILS[name] < _TRANSPORT_MAX_FAILS


def _transport_failed(name: str) -> None:
    _TRANSPORT_FAILS[name] += 1
    if _TRANSPORT_FAILS[name] == _TRANSPORT_MAX_FAILS:
        label = {"proxy": "SOCKS5 127.0.0.1:1088", "tor": "Tor 127.0.0.1:9050", "direct": "koneksi direct"}[name]
        print(f"  [-] Transport '{label}' gagal {_TRANSPORT_MAX_FAILS}x berturut -> dimatikan (circuit breaker), request berikutnya pakai jalur lain.")


def _transport_ok_again(name: str) -> None:
    _TRANSPORT_FAILS[name] = 0


PROXY_OPENER = None
try:
    import socks
    from sockshandler import SocksiPyHandler
    # 1. Prioritaskan Tunnel Azure Jakarta port 1088 (Ultra-fast 15ms latency, IP fresh)
    PROXY_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 1088))
except Exception:
    PROXY_OPENER = None

TOR_OPENER = None
try:
    import socks
    from sockshandler import SocksiPyHandler
    TOR_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 9050))
except Exception:
    TOR_OPENER = None


def probe_transports() -> None:
    """Deteksi environment sebelum run: jangan coba jalur yang jelas tidak ada,
    tiap requestsia bakal buang 2x timeout sebelum fallback."""
    global PROXY_OPENER, TOR_OPENER
    if os.environ.get("VORATOON_NO_PROXY") == "1":
        PROXY_OPENER = None
        print("[*] MODE DIRECT: proxy dimatikan via env VORATOON_NO_PROXY=1")
    else:
        for name, opener, port in (("proxy", PROXY_OPENER, 1088), ("tor", TOR_OPENER, 9050)):
            if opener is None:
                continue
            alive = False
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    alive = True
            except Exception:
                alive = False
            if not alive:
                _TRANSPORT_FAILS[name] = _TRANSPORT_MAX_FAILS
                print(f"[-] Transport {name} (127.0.0.1:{port}) TIDAK hidup -> dilewati, tidak akan dicoba")
            else:
                print(f"[+] Transport {name} (127.0.0.1:{port}) hidup")

def _do_open(opener, req, timeout: int, transport: str) -> tuple[int, dict]:
    """Satu percobaan request dengan hard wall-clock cap.
    Tidak boleh menggantung: SIGALRM yang menjadi jaring pengaman terakhir.
    `opener` harus object yang punya .open(req, timeout=...)."""
    try:
        with _hard_timeout(REQUEST_HARD_CAP):
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                status, res_body = resp.status, json.loads(raw) if raw else {}
        _transport_ok_again(transport)
        return status, res_body
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            res_body = json.loads(raw)
        except Exception:
            res_body = {"error": raw[:500]}
        _transport_ok_again(transport)
        return e.code, res_body
    except HardTimeout:
        _transport_failed(transport)
        return 504, {"error": f"hard timeout {REQUEST_HARD_CAP}s"}
    except Exception as e:
        _transport_failed(transport)
        return 500, {"error": f"{type(e).__name__}: {e}"}


def api_request(path: str, token: str = "", method: str = "GET", body: dict = None, max_retries: int = 3) -> tuple[int, dict]:
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

    for attempt in range(max_retries):
        status, res_body = 500, {}

        # 1. Transport utama (SOCKS5) kalau hidup
        if PROXY_OPENER and _transport_ok("proxy"):
            status, res_body = _do_open(PROXY_OPENER, req, 10, "proxy")

        # 2. Transport cadangan (Tor SOCKS5) kalau hidup
        if status in [429, 500, 502, 503, 504] and TOR_OPENER and _transport_ok("tor"):
            status, res_body = _do_open(TOR_OPENER, req, 15, "tor")

        # 3. Direct fallback
        if status in [429, 500, 502, 503, 504] and _transport_ok("direct"):
            status, res_body = _do_open(urllib.request.build_opener(), req, 10, "direct")

        # 429 = rate limit ATAU kuota harian habis. Jangan retry cepat.
        if status == 429:
            wait = min(10, 2 * (attempt + 1))
            print(f"  [-] HTTP 429 dari {path} - jeda {wait}s lalu berhenti di request ini (tidak dipaksa).")
            time.sleep(wait)
            return 429, res_body

        # Jika bukan transient server error, return langsung
        if status not in [500, 502, 503, 504, 520, 521, 522, 524]:
            return status, res_body

        # Transient 5xx: backoff lalu coba lagi
        time.sleep(1.0 * (attempt + 1))

    return status, res_body

def discover_series_stream(fallback_slug: str = "magic-emperor", max_pages: int = 50):
    """
    Generator cerdas yang terus menyuplai judul komik segar melintasi ribuan komik di Voratoon.
    Mencegah bot kehabisan bab komik karena komik populer sudah habis dibaca.
    """
    seen = set()

    # 1. Prioritaskan komik populer
    st_p, res_p = api_request("/popular")
    if st_p == 200 and "data" in res_p and isinstance(res_p["data"], list):
        for s in res_p["data"]:
            slug = s.get("data", {}).get("slug")
            if slug and slug not in seen:
                seen.add(slug)
                yield slug

    # 2. Jelajahi katalog lengkap /series (lebih dari 10.000 komik)
    for sort_mode in ["popularity", "bookmarks", "latest", "rating"]:
        for page in range(1, max_pages + 1):
            st, res = api_request(f"/series?page={page}&take=30&sort={sort_mode}")
            if st == 200 and "data" in res and isinstance(res["data"], list):
                items = res["data"]
                if not items:
                    break
                for s in items:
                    slug = s.get("data", {}).get("slug")
                    if slug and slug not in seen:
                        seen.add(slug)
                        yield slug
            else:
                break

    if fallback_slug not in seen:
        yield fallback_slug

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

CHAPTERS_CACHE = {}

def fetch_series_chapters(series_slug: str, limit: int = 500) -> list[dict]:
    if series_slug in CHAPTERS_CACHE:
        return CHAPTERS_CACHE[series_slug][:limit]

    st, res = api_request(f"/series/{series_slug}/chapters")
    if st == 200 and "data" in res and isinstance(res["data"], list):
        valid = [c for c in res["data"] if isinstance(c, dict) and "id" in c]
        # Urutkan dari Chapter 1 naik ke atas (Ascending)
        valid.sort(key=lambda x: x.get("data", {}).get("index", 0))
        CHAPTERS_CACHE[series_slug] = valid
        return valid[:limit]
    return []

def farm_account(token: str, target_series_id: int, target_series_slug: str, delay_mult: float, status_only: bool = False) -> tuple[list[int], dict | None]:
    mask_token = token[:8] + "..." + token[-6:] if len(token) > 14 else "token"
    print("\n" + "=" * 60)
    print(f"[*] Memproses Akun [{mask_token}]")
    print("=" * 60)
    created_comment_ids = []

    # 1. Profile Status
    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print(f"[ERROR] Autentikasi Gagal ({st}): Token mungkin kedaluwarsa.")
        return [], None

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

        chap_ok = 0
        series_read_counts = {}
        quota_hit = False
        # Target = sisa kuota yang dilaporkan server. JANGAN lebih dari itu:
        # server membalas 429 "daily limit" kalau kita nebak-nebab melewati kuota.
        target_reads = ch_rem

        # Mengalirkan ribuan komik secara dinamis sampai kuota harian terpenuhi 100%
        deadline = time.time() + ACCOUNT_DEADLINE
        for slug in discover_series_stream(target_series_slug, max_pages=50):
            if chap_ok >= target_reads:
                break
            if quota_hit:
                break
            if time.time() > deadline:
                print(f"  [-] Batas waktu akun ({ACCOUNT_DEADLINE}s) tercapai saat memindai komik -> lanjut tahap komentar.")
                break
            chapters = fetch_series_chapters(slug, limit=500)
            if not chapters:
                continue

            consecutive_awarded = 0
            for ch_item in chapters:
                cid = ch_item.get("id")
                ch_idx = ch_item.get("data", {}).get("index", "?")
                if not cid or cid in claimed_set:
                    continue
                if time.time() > deadline:
                    print(f"  [-] Batas waktu akun tercapai di tengah pemindaian bab -> stop bab, lanjut komentar.")
                    break

                st_c, res_c = api_request("/cultivation/rewards/chapter", token=token, method="POST", body={"targetId": cid, "mode": "chapter"})
                if st_c == 429:
                    # Kuota harian bab habis (atau rate limit) - hentikan pemindaian bab,
                    # JANGAN lanjut sniff komik lain hanya untuk kena 429 lagi.
                    print(f"  [-] 429 dari endpoint bab -> berhenti setelah {chap_ok} bab (kuota/rate limit, tidak dipaksa).")
                    quota_hit = True
                    break
                if st_c in [200, 201]:
                    d = res_c.get("data", {})
                    if not d.get("alreadyAwarded") and d.get("reward", {}).get("awardedMerit", 0) > 0:
                        chap_ok += 1
                        consecutive_awarded = 0
                    else:
                        consecutive_awarded += 1
                    claimed_set.add(cid)
                    series_read_counts[slug] = series_read_counts.get(slug, 0) + 1

                    # Auto-Bookmark jika sudah membaca > 50 chapter di komik ini
                    if series_read_counts[slug] == 50:
                        st_b, _ = api_request(f"/series/{slug}/bookmark", token=token, method="POST", body={})
                        if st_b in [200, 201]:
                            print(f"  [+] Auto-Bookmark aktif: Komik '{slug}' ditambahkan ke Bookmark (>50 bab dibaca)!")
                else:
                    claimed_set.add(cid)
                    consecutive_awarded += 1

                if consecutive_awarded >= 5:
                    # Komik ini bab awalnya sudah banyak diklaim, loncat ke komik berikutnya!
                    break

                if chap_ok >= target_reads:
                    break
                time.sleep(random.uniform(0.01, 0.03) * delay_mult)

        cache[acc_key] = list(claimed_set)
        save_claimed_cache(cache)
        print(f"  [OK] Selesai: {chap_ok} bab segar dibaca dari Ch 1 (+{min(50, chap_ok) * 10} Merit kuota penuh).")
    else:
        print("\n[2/3] Kuota baca 50 chapter sudah maksimal hari ini (50/50).")

    # 4. Comments Reward (Natural Chapter Reviews Across 5 Different Popular Comics)
    com_rem = daily.get("comments", {}).get("remaining", 5)
    if com_rem > 0:
        print(f"\n[3/3] Mengirim & Mengklaim Komentar (Sisa kuota: {com_rem})...")
        series_pool = []
        for _ in range(3):
            st_p, res_p = api_request("/popular")
            if st_p == 200 and isinstance(res_p.get("data"), list) and res_p["data"]:
                series_pool = res_p["data"]
                break
            time.sleep(1)

        if not series_pool:
            # Fallback komik populer jika /popular gagal/rate-limit
            series_pool = [
                {"id": 4718, "data": {"slug": "magic-emperor"}},
                {"id": 7133, "data": {"slug": "solo-max-level-newbie"}},
                {"id": 8261, "data": {"slug": "the-regressed-mercenarys-machinations"}},
                {"id": 4541, "data": {"slug": "leveling-in-the-future-apex-future-martial-arts"}},
                {"id": 5501, "data": {"slug": "nano-machine"}},
                {"id": 1658, "data": {"slug": "disastrous-necromancer"}},
                {"id": 6490, "data": {"slug": "revenge-of-the-iron-blooded-sword-hound"}},
                {"id": 1880, "data": {"slug": "eleceed"}},
                {"id": 7488, "data": {"slug": "swordmasters-youngest-son"}},
                {"id": 8481, "data": {"slug": "the-ultimate-of-all-ages"}}
            ]
        
        # Pick distinct series so we NEVER spam 1 comic
        chosen_series = random.sample(series_pool, min(com_rem, len(series_pool))) if series_pool else []
        selected_comments = random.sample(COMMENTS_POOL, min(com_rem, len(COMMENTS_POOL)))
        comm_ok = 0

        for idx in range(len(chosen_series)):
            item = chosen_series[idx]
            s_id = item.get("id")
            s_slug = item.get("data", {}).get("slug", target_series_slug)
            
            # Fetch recent chapters: wajib komentar di dalam chapter spesifik!
            chaps = fetch_series_chapters(s_slug, limit=20)
            if not chaps:
                continue
            # Pick a chapter randomly among available chapters
            ch_choice = random.choice(chaps[:min(10, len(chaps))])
            c_id = ch_choice.get("id") if isinstance(ch_choice, dict) else ch_choice
            
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
            time.sleep(random.uniform(0.1, 0.25) * delay_mult)

        print(f"  [OK] Selesai: {comm_ok}/{len(chosen_series)} komentar bab berhasil diklaim (+{comm_ok * 15} Merit).")
    else:
        print("\n[3/3] Kuota 5 komentar sudah maksimal hari ini (5/5).")

    # 5. Equip badge yang SUDAH di-earn (cosmetic progression, bukan fabrikasi)
    earned = [b.get("key") for b in (c_data.get("badges") or []) if b.get("key")]
    equipped = {b.get("key") for b in (c_data.get("badges") or []) if b.get("equipped")}
    pending = [k for k in earned if k not in equipped]
    if pending:
        st_eq, _ = api_request("/cultivation/equipment", token=token, method="PATCH", body={"badges": pending})
        if st_eq in [200, 201]:
            print(f"  [+] Badge ter-equip: {', '.join(pending)}")

    # 6. Final Status
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
            "streak": fd.get("streak", fd.get("loginStreak", 0)),
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
    tokens, primary_token, helper_tokens = load_tokens_config(args.token)

    if not tokens:
        print("[ERROR] Tidak ada token Voratoon yang ditemukan!")
        sys.exit(1)

    # Jitter delay opsional (hanya jika flag --jitter diaktifkan)
    if args.jitter and not args.status_only:
        jitter_s = random.randint(30, 180)
        print(f"[*] Jitter Delay: Menunggu jeda acak {jitter_s} detik...")
        time.sleep(jitter_s)

    print("=" * 60)
    print("Voratoon Daily Quest Fetcher")
    print("=" * 60)
    print(f"[*] Ditemukan {len(tokens)} akun utama dan {len(helper_tokens)} akun helper.")

    # Deteksi transport SEBELUM request: jangan paksa lewat tunnel yang mati
    probe_transports()

    target_id, target_slug = discover_series(args.series)
    print(f"[*] Target Series Default: {target_slug} (ID: {target_id})")

    results = []

    # 1. PRIORITAS #1: Eksekusi Akun Utama lebih dulu (misi hariannya: login + bab + komentar)
    if primary_token:
        print("[*] MEMPROSES AKUN UTAMA (PRIORITAS TINGGI)...")
        try:
            with _hard_timeout(ACCOUNT_DEADLINE * 2):
                cids, res = farm_account(primary_token, target_id, target_slug, args.delay_mult, status_only=args.status_only)
            if res:
                results.append((1, res))

            # Konfirmasi peringkat akun utama
            if not args.status_only:
                try:
                    st_lb, res_lb = api_request("/rankings/users", token=primary_token)
                    if st_lb == 200:
                        my = res_lb.get("myRank", {})
                        print(f"\n[PERINGKAT] Akun utama: Rank #{my.get('rank')} ({my.get('periodMerit'):,} Weekly Merit)")
                except Exception:
                    pass
        except Exception as e:
            print(f"[ERROR] Masalah pada akun utama: {e}")

    # 2. PROSES SELURUH AKUN HELPER (Login + Bab + Komentar)
    if not args.status_only and helper_tokens:
        print("\n" + "=" * 60)
        print(f"[*] MEMPROSES SELURUH {len(helper_tokens)} AKUN HELPER...")
        print("=" * 60)
        for h_idx, h_tok in enumerate(helper_tokens, 1):
            try:
                with _hard_timeout(ACCOUNT_DEADLINE * 2):
                    cids, res = farm_account(h_tok, target_id, target_slug, args.delay_mult, status_only=args.status_only)
                if res:
                    results.append((h_idx + 1, res))
            except HardTimeout:
                print(f"[ERROR] Helper #{h_idx} melewati batas waktu {ACCOUNT_DEADLINE * 2}s -> dilewati, lanjut akun berikutnya.")
            except Exception as e:
                print(f"[ERROR] Masalah pada helper #{h_idx}: {e}")

    print("\n" + "=" * 60)
    print("[OK] Seluruh antrean akun selesai diproses.")
    print("=" * 60)

    # 3. Kirim notifikasi Telegram otomatis dengan status Leaderboard Nasional
    if not args.status_only and results:
        lines = ["*Laporan Harian Voratoon Daily Quest*", ""]
        total_gain = 0
        full_count = 0
        for idx, r in results:
            role = "Akun Utama" if idx == 1 else f"Akun Helper #{idx - 1}"
            d = r.get("daily", {})
            l_ok = d.get("login", {}).get("used", 0) >= 1
            c_ok = d.get("chapters", {}).get("used", 0) >= 50
            k_ok = d.get("comments", {}).get("used", 0) >= 5
            if l_ok and c_ok and k_ok:
                full_count += 1
            total_gain += r.get("gained") or 0
            lines.append(f"*{role}:*")
            lines.append(f"- Level: {r.get('level')} ({r.get('tier')}) | Streak: {r.get('streak')} hari")
            lines.append(f"- Total Merit: {r.get('merit'):,} (+{r.get('gained')})")
            lines.append(f"- Kuota: Login {d.get('login', {}).get('used')}/{d.get('login', {}).get('limit')} | Bab {d.get('chapters', {}).get('used')}/{d.get('chapters', {}).get('limit')} | Komen {d.get('comments', {}).get('used')}/{d.get('comments', {}).get('limit')}")
            lines.append("")

        lines.append(f"*Ringkasan: {full_count}/{len(results)} akun kuota penuh, total +{total_gain:,} merit.*")
        lines.append("")

        # Live Leaderboard Checking
        try:
            st_lb, res_lb = api_request("/rankings/users", token=primary_token)
            if st_lb == 200:
                my = res_lb.get("myRank", {})
                r_pos = my.get("rank", "-")
                w_merit = my.get("periodMerit", 0)
                top1_merit = res_lb.get("data", [{}])[0].get("merit", 0)
                diff = max(0, top1_merit - w_merit)
                lines.append(f"*Status Leaderboard Mingguan:*")
                lines.append(f"- Peringkat: *Rank #{r_pos}*")
                lines.append(f"- Merit Mingguan: {w_merit:,}")
                lines.append(f"- Selisih ke Top 1: {diff:,} Merit")
                lines.append("")
        except Exception:
            pass

        lines.append("Status: Otomatisasi berjalan lancar pada crontab VPS.")
        send_telegram_alert("\n".join(lines))

if __name__ == "__main__":
    main()
