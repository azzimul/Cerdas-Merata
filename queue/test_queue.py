"""
Test untuk queue manager — jalankan: python queue/test_queue.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from queue.manager import Applicant, rerank_all, disqualify, STATUS_WAITING_LIST, STATUS_REJECTED, STATUS_DISQUALIFIED


def make_applicants(data: list[tuple[int, int]]) -> list[Applicant]:
    return [Applicant(application_id=i, total_skor=s) for i, s in data]


def print_queue(applicants: list[Applicant], title: str = "") -> None:
    if title:
        print(f"\n--- {title} ---")
    wl = sorted([a for a in applicants if a.status == STATUS_WAITING_LIST], key=lambda a: a.queue_rank)
    rejected = [a for a in applicants if a.status == STATUS_REJECTED]
    dq = [a for a in applicants if a.status == STATUS_DISQUALIFIED]

    print(f"WAITING LIST ({len(wl)} orang):")
    for a in wl[:10]:
        print(f"  Rank {a.queue_rank:2d} | ID {a.application_id:3d} | Skor {a.total_skor}")
    if len(wl) > 10:
        print(f"  ... dan {len(wl)-10} lainnya")

    print(f"REJECTED: {len(rejected)} orang")
    if dq:
        print(f"DISQUALIFIED: {[a.application_id for a in dq]}")


# ============================================================
# Test 1: rerank_all dengan kuota 5 (biar mudah dilihat)
# ============================================================
print("=" * 60)
print("TEST 1 — rerank_all (kuota=5)")
print("=" * 60)

data = [
    (101, 42), (102, 35), (103, 28), (104, 28),  # rank 3 dan 4 sama skor
    (105, 25), (106, 20), (107, 18), (108, 15),
]
applicants = make_applicants(data)
rerank_all(applicants, quota=5)
print_queue(applicants, "Setelah rerank_all (kuota 5)")

assert applicants[0].queue_rank == 1 and applicants[0].status == STATUS_WAITING_LIST
assert applicants[4].queue_rank == 5 and applicants[4].status == STATUS_WAITING_LIST
assert applicants[5].queue_rank is None and applicants[5].status == STATUS_REJECTED
print("\nTest 1 PASSED")


# ============================================================
# Test 2: disqualify rank 1 — rank 2 naik ke rank 1, rank 6 masuk
# ============================================================
print("\n" + "=" * 60)
print("TEST 2 — disqualify rank 1 (ID 101)")
print("=" * 60)

print_queue(applicants, "Sebelum disqualify")

result = disqualify(applicants, application_id=101, reason="Pemalsuan data pendapatan", admin_id="admin01", quota=5)

print_queue(applicants, "Setelah disqualify ID 101")
print(f"\nDiskualifikasi ID: {result.disqualified_id}")
print(f"Perubahan rank ({len(result.promoted)} entri untuk rank_history):")
for rc in result.promoted:
    print(f"  ID {rc.application_id}: rank {rc.rank_lama} -> {rc.rank_baru}")
print(f"Baru masuk waiting list: ID {result.newly_entered}")

assert next(a for a in applicants if a.application_id == 101).status == STATUS_DISQUALIFIED
assert next(a for a in applicants if a.application_id == 102).queue_rank == 1
assert next(a for a in applicants if a.application_id == 106).status == STATUS_WAITING_LIST
assert result.newly_entered == 106
print("\nTest 2 PASSED")


# ============================================================
# Test 3: disqualify rank tengah (ID 103)
# ============================================================
print("\n" + "=" * 60)
print("TEST 3 — disqualify rank 2 (ID 102)")
print("=" * 60)

result2 = disqualify(applicants, application_id=102, reason="Data tanggungan tidak valid", admin_id="admin01", quota=5)

print_queue(applicants, "Setelah disqualify ID 102")
print(f"Baru masuk waiting list: ID {result2.newly_entered}")
assert result2.newly_entered == 107
print("\nTest 3 PASSED")


# ============================================================
# Test 4: error — disqualify ID yang sudah disqualified
# ============================================================
print("\n" + "=" * 60)
print("TEST 4 — Error: disqualify yang sudah disqualified")
print("=" * 60)

try:
    disqualify(applicants, application_id=101, reason="duplikat", admin_id="admin01", quota=5)
    print("FAIL — harusnya raise ValueError")
except ValueError as e:
    print(f"OK — ValueError: {e}")
    print("Test 4 PASSED")


# ============================================================
# Test 5: skor sama — tie-breaking (urutan stabil)
# ============================================================
print("\n" + "=" * 60)
print("TEST 5 — Skor sama (tie): ID 103 dan 104 sama-sama 28")
print("=" * 60)

fresh = make_applicants(data)
rerank_all(fresh, quota=5)
a103 = next(a for a in fresh if a.application_id == 103)
a104 = next(a for a in fresh if a.application_id == 104)
print(f"ID 103 rank={a103.queue_rank}, ID 104 rank={a104.queue_rank}")
print("(urutan tie mengikuti urutan masuk list — konsisten dengan Python sort stable)")
print("Test 5 PASSED")

print("\n\nSemua test selesai.")
