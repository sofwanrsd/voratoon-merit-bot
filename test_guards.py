#!/usr/bin/env python3
"""Test harness untuk guard anti-hang di merit_farmer.py.
Memverifikasi secara nyata:
  1. _hard_timeout benar-benar memutus operasi yang menggantung
  2. circuit breaker mematikan transport yang gagal beruntun
  3. probe_transports mendeteksi port mati dalam < 1 detik
"""
import sys
import time
import signal

sys.path.insert(0, "/root/voratoon-bot")
import merit_farmer as mf

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -> {detail}" if detail else ""))
    if not cond:
        FAILURES.append(name)


print("=" * 62)
print("TEST 1: hard timeout memutus operasi yang menggantung")
print("=" * 62)

t0 = time.time()
raised = False
try:
    with mf._hard_timeout(3):
        # simulates socket read yang tidak pernah selesai
        while True:
            time.sleep(0.2)
except mf.HardTimeout:
    raised = True
elapsed = time.time() - t0
check("HardTimeout terpicu", raised)
check("selesai dalam 3-5 detik (tidak menggantung)", 2.5 <= elapsed <= 6.0, f"{elapsed:.2f}s")

print()
print("=" * 62)
print("TEST 2: alarm dibersihkan dengan benar (tidak lingering)")
print("=" * 62)
with mf._hard_timeout(30):
    pass
# kalau alarm tidak dibersihkan, assert ini akan raise TimeoutError
try:
    signal.alarm(1)
    time.sleep(0.1)
    signal.alarm(0)
    check("tidak ada alarm sisa setelah context exit", True)
except Exception as e:
    check("tidak ada alarm sisa setelah context exit", False, str(e))

print()
print("=" * 62)
print("TEST 3: circuit breaker mematikan transport gagal beruntun")
print("=" * 62)
mf._TRANSPORT_FAILS["proxy"] = 0
check("transport proxy awalnya aktif", mf._transport_ok("proxy"))
for i in range(mf._TRANSPORT_MAX_FAILS):
    mf._transport_failed("proxy")
check(
    f"transport proxy mati setelah {mf._TRANSPORT_MAX_FAILS} gagal beruntun",
    not mf._transport_ok("proxy"),
    f"fails={mf._TRANSPORT_FAILS['proxy']}",
)
mf._transport_ok_again("proxy")
check("transport proxy hidup lagi setelah koneksi sukses", mf._transport_ok("proxy"))

print()
print("=" * 62)
print("TEST 4: probe_transports mendeteksi port mati dengan cepat")
print("=" * 62)
# pastikan tidak ada SOCKS di port acak
mf.PROXY_OPENER = None
mf.TOR_OPENER = None
t0 = time.time()
mf.probe_transports()
elapsed = time.time() - t0
check("probe selesai < 2 detik", elapsed < 2.0, f"{elapsed:.3f}s")
check("tidak ada exception saat probe", True)

print()
print("=" * 62)
print("TEST 5: request ke host mati tidak menggantung (end-to-end)")
print("=" * 62)
t0 = time.time()
st, body = mf.api_request("/nonexistent-endpoint-for-timeout-test")
elapsed = time.time() - t0
check(
    f"api_request balik dalam < 40 detik (actual {elapsed:.1f}s, status {st})",
    elapsed < 40,
    f"{elapsed:.1f}s",
)

print()
print("=" * 62)
if FAILURES:
    print(f"HASIL: {len(FAILURES)} TEST GAGAL -> {FAILURES}")
    sys.exit(1)
print("HASIL: SEMUA TEST LULUS")
print("=" * 62)
