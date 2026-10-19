#!/usr/bin/env python3
"""
Voratoon Helper Farm Phase 2 (Helper #12 - #21)
Menggenapkan kuota baca 50 bab & 5 komentar untuk sisa helper
sehingga seluruh 21 helper mengunci posisi 595 Merit di Leaderboard Nasional!
"""

import sys
import time
import json
import random
from pathlib import Path

sys.path.insert(0, "/root/voratoon-bot")
from merit_farmer import (
    api_request,
    load_tokens_config,
    fetch_series_chapters,
    discover_series_stream,
    load_claimed_cache,
    save_claimed_cache,
    COMMENTS_POOL
)

def farm_helper_sequential(h_idx, token):
    mask = token[:8] + "..." + token[-6:]
    print(f"\n[*] [Helper #{h_idx}] Memulai panen [{mask}]...")

    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print(f"[!] [Helper #{h_idx}] Token gagal ({st})")
        return False

    c_data = me.get("data", {})
    daily = c_data.get("daily", {})
    ch_rem = daily.get("chapters", {}).get("remaining", 50)
    com_rem = daily.get("comments", {}).get("remaining", 5)

    if daily.get("login", {}).get("remaining", 1) > 0:
        api_request("/cultivation/rewards/daily-login", token=token, method="POST", body={})

    if ch_rem > 0:
        cache = load_claimed_cache()
        claimed_set = set(cache.get(mask, []))
        chap_ok = 0
        for slug in discover_series_stream("magic-emperor", max_pages=30):
            if chap_ok >= ch_rem:
                break
            chapters = fetch_series_chapters(slug, limit=300)
            if not chapters:
                continue

            for ch in chapters:
                cid = ch.get("id")
                if not cid or cid in claimed_set:
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
                time.sleep(0.12)

        cache[mask] = list(claimed_set)
        save_claimed_cache(cache)
        print(f"  [+] [Helper #{h_idx}] Sukses klaim {chap_ok} bab komik!")

    if com_rem > 0:
        st_p, res_p = api_request("/popular")
        series_pool = res_p.get("data", []) if (st_p == 200 and isinstance(res_p.get("data"), list)) else []
        chosen_series = random.sample(series_pool, min(com_rem, len(series_pool))) if series_pool else []
        selected_comments = random.sample(COMMENTS_POOL, min(com_rem, len(COMMENTS_POOL)))

        comm_ok = 0
        for i in range(len(chosen_series)):
            item = chosen_series[i]
            s_id = item.get("id")
            s_slug = item.get("data", {}).get("slug", "magic-emperor")
            chaps = fetch_series_chapters(s_slug, limit=15)
            if not chaps:
                continue
            ch_choice = random.choice(chaps[:min(8, len(chaps))])
            c_id = ch_choice.get("id") if isinstance(ch_choice, dict) else ch_choice
            text = selected_comments[i]

            st_post, res_post = api_request("/comments", token=token, method="POST", body={"seriesId": s_id, "chapterId": c_id, "content": text})
            if st_post in [200, 201] and "data" in res_post and "id" in res_post["data"]:
                comment_id = res_post["data"]["id"]
                api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": comment_id})
                comm_ok += 1
            time.sleep(0.4)

        print(f"  [+] [Helper #{h_idx}] Sukses kirim {comm_ok} komentar bab!")

    st_end, me_end = api_request("/cultivation/me", token=token)
    d_end = me_end.get("data", {})
    print(f"[OK] [Helper #{h_idx}] SELESAI: Level {d_end.get('level')} | Total Merit {d_end.get('merit')} | Exp {d_end.get('exp')}")
    return True

def main():
    _, _, helper_tokens = load_tokens_config()
    targets = list(range(11, len(helper_tokens)))
    print(f"[*] Menjalankan panen untuk {len(targets)} helper tersisa (Helper #12 - #{len(helper_tokens)})...")

    for idx in targets:
        token = helper_tokens[idx]
        farm_helper_sequential(idx + 1, token)
        time.sleep(0.5)

    print("\n[OK] Seluruh sisa helper berhasil dipanen!")

if __name__ == "__main__":
    main()
