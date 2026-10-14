#!/usr/bin/env python3
"""
Voratoon Spam Comments Cleaner
Safely deletes old spam comments containing '#' or generated junk,
WITHOUT reducing Merit, Exp, or daily rewards.
"""

import sys
import time
import argparse
sys.path.insert(0, "/root/voratoon-bot")
from merit_farmer import api_request, load_tokens_config

def clean_account_comments(token: str, acc_label: str, dry_run: bool = False, only_hash: bool = True):
    print(f"\n[*] Memeriksa komentar untuk {acc_label}...")
    st, res = api_request("/user/comments", token=token)
    if st != 200:
        print(f"[ERROR] Gagal mengambil komentar ({st})")
        return

    total = res.get("meta", {}).get("total", 0)
    print(f"[-] Total komentar di profil: {total}")
    if total == 0:
        print("[OK] Tidak ada komentar untuk dibersihkan.")
        return

    deleted_count = 0

    if dry_run:
        last_page = res.get("meta", {}).get("lastPage", 1)
        for p in range(1, last_page + 1):
            st_p, res_p = api_request(f"/user/comments?page={p}", token=token)
            if st_p != 200:
                break
            for c in res_p.get("data", []):
                text = c.get("content", "")
                if not only_hash or "#" in text:
                    deleted_count += 1
                    if deleted_count <= 10 or deleted_count % 50 == 0:
                        print(f"  [DRY-RUN #{deleted_count}] ID {c['id']}: {text[:50]}")
            time.sleep(0.05)
        print(f"[DRY-RUN Selesai] Ditemukan {deleted_count} komentar spam yang dapat dihapus.")
        return

    # Real deletion loop: always read page 1 as deletion shifts records
    consecutive_empty = 0
    while True:
        st_p, res_p = api_request("/user/comments?page=1", token=token)
        if st_p != 200:
            break
        comments = res_p.get("data", [])
        if not comments:
            break

        to_delete = []
        for c in comments:
            text = c.get("content", "")
            if not only_hash or "#" in text:
                to_delete.append((c["id"], text))

        if not to_delete:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                break
            # check page 2 if page 1 has legitimate comments
            st_p2, res_p2 = api_request(f"/user/comments?page={consecutive_empty + 1}", token=token)
            if st_p2 != 200 or not res_p2.get("data"):
                break
            for c in res_p2.get("data", []):
                text = c.get("content", "")
                if not only_hash or "#" in text:
                    to_delete.append((c["id"], text))

        if not to_delete:
            break

        consecutive_empty = 0
        for cid, text in to_delete:
            st_del, _ = api_request(f"/comments/{cid}", token=token, method="DELETE")
            if st_del in [200, 204]:
                deleted_count += 1
                if deleted_count % 10 == 0:
                    print(f"  [OK] Terhapus: {deleted_count} komentar spam...")
            time.sleep(0.12)

    print(f"[OK] Selesai! Total {deleted_count} komentar spam berhasil dibersihkan dari {acc_label}.")

def main():
    parser = argparse.ArgumentParser(description="Voratoon Comments Cleaner")
    parser.add_argument("--dry-run", action="store_true", help="Simulate deletion without actually deleting")
    parser.add_argument("--all", action="store_true", help="Delete all comments instead of only comments with '#'")
    args = parser.parse_args()

    tokens, t1, t2 = load_tokens_config()
    clean_account_comments(t1, "Akun Utama", dry_run=args.dry_run, only_hash=not args.all)
    if t2 and t1 != t2:
        clean_account_comments(t2, "Akun Helper", dry_run=args.dry_run, only_hash=not args.all)

if __name__ == "__main__":
    main()
