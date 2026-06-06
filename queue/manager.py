"""
Waiting List Queue Manager — Cerdas Merata v1.3

Core logic (in-memory, db-agnostic):
  - rerank_all()     : urutkan semua pendaftar berdasarkan skor, tetapkan rank + status
  - disqualify()     : tandai peserta sebagai disqualified, naikkan rank semua di bawahnya

DB layer (opsional, psycopg2):
  - db_rerank_all()
  - db_disqualify()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone


DEFAULT_QUOTA = 50

STATUS_WAITING_LIST  = "waiting_list"
STATUS_REJECTED      = "rejected"
STATUS_DISQUALIFIED  = "disqualified"


@dataclass
class Applicant:
    application_id: int
    total_skor: int
    status: str = STATUS_REJECTED
    queue_rank: Optional[int] = None
    disqualify_reason: Optional[str] = None


@dataclass
class RankChange:
    application_id: int
    rank_lama: int
    rank_baru: int
    triggered_by: int
    admin_id: str
    changed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DisqualifyResult:
    disqualified_id: int
    promoted: list[RankChange]
    newly_entered: Optional[int]


# ---------------------------------------------------------------------------
# Core in-memory logic
# ---------------------------------------------------------------------------

def rerank_all(
    applicants: list[Applicant],
    quota: int = DEFAULT_QUOTA,
) -> list[Applicant]:
    """
    Urutkan semua pendaftar berdasarkan skor (descending), tetapkan rank + status.
    Peserta yang sudah disqualified dikeluarkan dari hitungan slot.

    Returns list yang sama (in-place mutation) untuk kemudahan chaining.
    """
    eligible = [a for a in applicants if a.status != STATUS_DISQUALIFIED]
    eligible.sort(key=lambda a: a.total_skor, reverse=True)

    for rank_zero, applicant in enumerate(eligible):
        rank = rank_zero + 1
        if rank <= quota:
            applicant.queue_rank = rank
            applicant.status = STATUS_WAITING_LIST
        else:
            applicant.queue_rank = None
            applicant.status = STATUS_REJECTED

    return applicants


def disqualify(
    applicants: list[Applicant],
    application_id: int,
    reason: str,
    admin_id: str,
    quota: int = DEFAULT_QUOTA,
) -> DisqualifyResult:
    """
    Tandai peserta sebagai disqualified, lalu naikkan rank semua peserta di bawahnya.
    Peserta di luar 50 besar yang naik ke dalam kuota mendapat status waiting_list.

    Raises:
        ValueError: jika application_id tidak ditemukan atau sudah disqualified
    """
    target = next((a for a in applicants if a.application_id == application_id), None)
    if target is None:
        raise ValueError(f"Aplikasi {application_id} tidak ditemukan.")
    if target.status == STATUS_DISQUALIFIED:
        raise ValueError(f"Aplikasi {application_id} sudah berstatus disqualified.")

    old_rank = target.queue_rank
    target.status = STATUS_DISQUALIFIED
    target.disqualify_reason = reason
    target.queue_rank = None

    # Semua peserta aktif (bukan disqualified) yang punya rank, urutkan ulang
    eligible = sorted(
        [a for a in applicants if a.status != STATUS_DISQUALIFIED],
        key=lambda a: a.total_skor,
        reverse=True,
    )

    promoted: list[RankChange] = []
    newly_entered: Optional[int] = None

    for rank_zero, applicant in enumerate(eligible):
        new_rank = rank_zero + 1
        old = applicant.queue_rank

        if old != new_rank:
            # Catat perubahan jika rank berubah DAN ada kaitannya dengan diskualifikasi
            if old is not None or new_rank <= quota:
                promoted.append(RankChange(
                    application_id=applicant.application_id,
                    rank_lama=old if old is not None else new_rank + 1,
                    rank_baru=new_rank,
                    triggered_by=application_id,
                    admin_id=admin_id,
                ))

            if old is None and new_rank <= quota:
                newly_entered = applicant.application_id

        applicant.queue_rank = new_rank if new_rank <= quota else None
        applicant.status = STATUS_WAITING_LIST if new_rank <= quota else STATUS_REJECTED

    return DisqualifyResult(
        disqualified_id=application_id,
        promoted=promoted,
        newly_entered=newly_entered,
    )


# ---------------------------------------------------------------------------
# DB layer — psycopg2 + SQLite compatible
# ---------------------------------------------------------------------------

def _ph(conn) -> str:
    """Return placeholder style: ? for sqlite3, %s for psycopg2."""
    return "?" if "sqlite3" in type(conn).__module__ else "%s"


def _q(sql: str, conn) -> str:
    """Rewrite %s placeholders to ? when using SQLite."""
    if "sqlite3" in type(conn).__module__:
        return sql.replace("%s", "?")
    return sql


def db_rerank_all(conn, quota: int = DEFAULT_QUOTA) -> None:
    """
    Baca semua pendaftar aktif dari DB, hitung ulang rank, update ke DB.
    Dipanggil setelah ada pendaftar baru masuk.
    """
    cur = conn.cursor()
    cur.execute(_q("""
        SELECT a.id, r.total_skor
        FROM applications a
        JOIN results r ON r.application_id = a.id
        WHERE a.status_aplikasi != %s
        ORDER BY r.total_skor DESC
    """, conn), (STATUS_DISQUALIFIED,))
    rows = cur.fetchall()

    updates = []
    for rank_zero, (app_id, _) in enumerate(rows):
        rank = rank_zero + 1
        if rank <= quota:
            updates.append((STATUS_WAITING_LIST, rank, app_id))
        else:
            updates.append((STATUS_REJECTED, None, app_id))

    cur.executemany(_q("""
        UPDATE applications
        SET status_aplikasi = %s, queue_rank = %s
        WHERE id = %s
    """, conn), updates)
    conn.commit()


def db_disqualify(
    conn,
    application_id: int,
    reason: str,
    admin_id: str,
    quota: int = DEFAULT_QUOTA,
) -> DisqualifyResult:
    """
    Diskualifikasi peserta di DB, naikkan rank semua di bawahnya, catat ke rank_history.
    """
    cur = conn.cursor()

    # Validasi
    cur.execute(_q("SELECT status_aplikasi, queue_rank FROM applications WHERE id = %s", conn), (application_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Aplikasi {application_id} tidak ditemukan.")
    current_status = row[0]
    if current_status == STATUS_DISQUALIFIED:
        raise ValueError(f"Aplikasi {application_id} sudah disqualified.")

    # Tandai disqualified + simpan alasan di results
    cur.execute(_q("UPDATE applications SET status_aplikasi = %s, queue_rank = NULL WHERE id = %s", conn),
                (STATUS_DISQUALIFIED, application_id))
    cur.execute(_q("UPDATE results SET status_keputusan = %s, disqualify_reason = %s WHERE application_id = %s", conn),
                (STATUS_DISQUALIFIED, reason, application_id))

    # Ambil semua pendaftar aktif, urutkan ulang
    cur.execute(_q("""
        SELECT a.id, r.total_skor, a.queue_rank
        FROM applications a
        JOIN results r ON r.application_id = a.id
        WHERE a.status_aplikasi != %s
        ORDER BY r.total_skor DESC
    """, conn), (STATUS_DISQUALIFIED,))
    rows = cur.fetchall()

    promoted: list[RankChange] = []
    newly_entered: Optional[int] = None
    now = datetime.now(timezone.utc)

    rank_updates = []
    history_inserts = []

    for rank_zero, (app_id, _, old_rank) in enumerate(rows):
        new_rank = rank_zero + 1
        new_status = STATUS_WAITING_LIST if new_rank <= quota else STATUS_REJECTED
        new_rank_val = new_rank if new_rank <= quota else None

        if old_rank != new_rank_val:
            old_for_history = old_rank if old_rank is not None else (new_rank + 1)
            new_for_history = new_rank_val if new_rank_val is not None else (old_rank + 1 if old_rank else new_rank)

            promoted.append(RankChange(
                application_id=app_id,
                rank_lama=old_for_history,
                rank_baru=new_for_history,
                triggered_by=application_id,
                admin_id=admin_id,
                changed_at=now,
            ))
            history_inserts.append((app_id, old_for_history, new_for_history, application_id, admin_id, str(now)))

            if old_rank is None and new_rank_val is not None:
                newly_entered = app_id

        rank_updates.append((new_status, new_rank_val, app_id))

    cur.executemany(_q("UPDATE applications SET status_aplikasi = %s, queue_rank = %s WHERE id = %s", conn), rank_updates)

    if history_inserts:
        cur.executemany(_q("""
            INSERT INTO rank_history
                (application_id, rank_lama, rank_baru, triggered_by, admin_id, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, conn), history_inserts)

    conn.commit()

    return DisqualifyResult(
        disqualified_id=application_id,
        promoted=promoted,
        newly_entered=newly_entered,
    )
