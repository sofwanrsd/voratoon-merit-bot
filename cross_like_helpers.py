#!/usr/bin/env python3
"""
Voratoon Helper Cross-Like Syndicate
Memberikan 50 like ke setiap komentar dari 21 akun helper
sehingga seluruh 21 akun helper mendapatkan +100 Merit (Total 695 Merit Maksimal)
dan mendominasi Top 1 - Top 25 Leaderboard Nasional Voratoon!
"""

import sys
import time
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/root/voratoon-bot")
from merit_farmer import (
    api_request,
    load_tokens_config,
    fetch_series_chapters,
    COMMENTS_POOL
)

def ensure_helper_comments(token_info):
    h_idx, token = token_info
    st_c, res_c = api_request("/user/comments", token=token)
    comments = res_c.get("data", []) if st_c == 200 else []
    comment_ids = [c["id"] for c in comments if "id" in c]

    # Jika komentar kurang dari 5, tambahkan komentar agar genap 5
    needed = 5 - len(comment_ids)
    if needed > 0:
        print(f"[*] [Helper #{h_idx}] Membutuhkan {needed} komentar tambahan...")
        st_p, res_p = api_request("/popular")
        series_pool = res_p.get("data", []) if (st_p == 200 and isinstance(res_p.get("data"), list)) else []
        chosen = random.sample(series_pool, min(needed, len(series_pool))) if series_pool else []
        texts = random.sample(COMMENTS_POOL, min(needed, len(COMMENTS_POOL)))

        for i in range(len(chosen)):
            s_id = chosen[i].get("id")
            s_slug = chosen[i].get("data", {}).get("slug", "magic-emperor")
            chaps = fetch_series_chapters(s_slug, limit=15)
            if not chaps:
                continue
            ch_choice = random.choice(chaps[:min(8, len(chaps))])
            c_id = ch_choice.get("id") if isinstance(ch_choice, dict) else ch_choice
            text = texts[i]

            st_post, res_post = api_request("/comments", token=token, method="POST", body={"seriesId": s_id, "chapterId": c_id, "content": text})
            if st_post in [200, 201] and "data" in res_post and "id" in res_post["data"]:
                cid = res_post["data"]["id"]
                comment_ids.append(cid)
                api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": cid})
            time.sleep(0.3)

    return h_idx, token, comment_ids[:5]

def upvote_helper_task(target_tuple, all_helpers):
    target_idx, target_token, target_cids = target_tuple
    num_helpers = len(all_helpers)

    # 10 helper berikutnya yang akan nge-like target
    # 10 helper x 5 komentar = 50 likes = +100 Merit
    likes_success = 0
    for offset in range(1, 11):
        voter_idx = (target_idx - 1 + offset) % num_helpers
        _, voter_token, _ = all_helpers[voter_idx]

        for cid in target_cids:
            st_u, res_u = api_request(f"/comments/{cid}/upvote", token=voter_token, method="POST", body={})
            if st_u in [200, 201]:
                likes_success += 1
            time.sleep(0.08)

    # Cek status merit terbaru
    st_me, me = api_request("/cultivation/me", token=target_token)
    d = me.get("data", {})
    daily = d.get("daily", {})
    wm = d.get("periodMerit", d.get("merit"))
    print(f"[OK] [Helper #{target_idx:2d}] Selesai! Disuntik {likes_success} Like -> Total Merit: {d.get('merit')} | Exp: {d.get('exp')}")
    return target_idx, likes_success

def main():
    print("=" * 68)
    print("  VORATOON HELPER CROSS-LIKE ENGINE - 695 MERIT MAX")
    print("=" * 68)

    _, _, helper_tokens = load_tokens_config()
    print(f"[*] Memeriksa komentar untuk {len(helper_tokens)} akun helper...")

    token_pairs = list(enumerate(helper_tokens, 1))

    # 1. Kumpulkan 5 komentar dari setiap helper secara paralel
    with ThreadPoolExecutor(max_workers=5) as ex:
        all_helpers = list(ex.map(ensure_helper_comments, token_pairs))

    # Urutkan berdasarkan index helper
    all_helpers.sort(key=lambda x: x[0])
    for h_idx, _, cids in all_helpers:
        print(f"  Helper #{h_idx:2d}: {len(cids)} komentar -> {cids}")

    print(f"\n[*] Memulai proses Cross-Like Silang (10 helper per target)...")

    # 2. Eksekusi cross-like secara terkendali (2 worker paralel)
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(lambda h: upvote_helper_task(h, all_helpers), all_helpers))

    print("\n" + "=" * 68)
    print("[OK] Seluruh 21 akun helper berhasil disuntik 50 Like!")
    print("=" * 68)

if __name__ == "__main__":
    main()
