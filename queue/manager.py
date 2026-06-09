"""
Waiting List Queue Manager — Cerdas Merata v2.0

Core logic (in-memory, db-agnostic):
  - rerank_all()     : sort applicants by score, assign rank + status
  - disqualify()     : mark applicant disqualified, promote those below

DB layer (psycopg2 / sqlite3 compatible):
  - db_rank_and_announce()   : batch-assign qualified/waiting_list/rejected + set announced flag
  - db_rerank_post_announce(): same ranking without touching the announced flag (for disqualify cascade)
  - db_disqualify()          : disqualify in DB, cascade-promote remaining
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone
import math


DEFAULT_QUOTA = 50

STATUS_QUALIFIED     = "qualified"
STATUS_WAITING_LIST  = "waiting_list"
STATUS_REJECTED      = "rejected"
STATUS_DISQUALIFIED  = "disqualified"
STATUS_PENDING       = "pending"


@dataclass
class Applicant:
    application_id: int
    total_skor: int
    status: str = STATUS_PENDING
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
# Helpers
# ---------------------------------------------------------------------------

def _waiting_list_slots(quota: int) -> int:
    """Number of waiting-list slots = 20% of quota (rounded up)."""
    return math.ceil(quota * 0.20)


def _assign_status(rank: int, quota: int) -> tuple[str, Optional[int]]:
    """Return (status, queue_rank) for a 1-based rank position."""
    wl_slots = _waiting_list_slots(quota)
    if rank <= quota:
        return STATUS_QUALIFIED, rank
    elif rank <= quota + wl_slots:
        return STATUS_WAITING_LIST, rank
    else:
        return STATUS_REJECTED, None


# ---------------------------------------------------------------------------
# Core in-memory logic
# ---------------------------------------------------------------------------

def rerank_all(
    applicants: list[Applicant],
    quota: int = DEFAULT_QUOTA,
) -> list[Applicant]:
    """
    Sort all applicants by score (descending), assign rank + status.
    Disqualified applicants are excluded from slot calculation.
    Mutates the list in-place and returns it.
    """
    eligible = [a for a in applicants if a.status != STATUS_DISQUALIFIED]
    eligible.sort(key=lambda a: a.total_skor, reverse=True)

    wl_slots = _waiting_list_slots(quota)
    cutoff_score = eligible[quota - 1].total_skor if len(eligible) >= quota else None

    rank = 0
    wl_count = 0
    below_cutoff = False

    for applicant in eligible:
        rank += 1
        if not below_cutoff and (cutoff_score is None or applicant.total_skor >= cutoff_score):
            applicant.queue_rank = rank
            applicant.status = STATUS_QUALIFIED
        else:
            below_cutoff = True
            wl_count += 1
            if wl_count <= wl_slots:
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
    Mark applicant as disqualified, then re-rank everyone remaining.
    Anyone outside quota who enters qualified/waiting_list is tracked as promoted.

    Raises:
        ValueError: if application_id not found or already disqualified
    """
    target = next((a for a in applicants if a.application_id == application_id), None)
    if target is None:
        raise ValueError(f"Application {application_id} not found.")
    if target.status == STATUS_DISQUALIFIED:
        raise ValueError(f"Application {application_id} is already disqualified.")

    target.status = STATUS_DISQUALIFIED
    target.disqualify_reason = reason
    target.queue_rank = None

    eligible = sorted(
        [a for a in applicants if a.status != STATUS_DISQUALIFIED],
        key=lambda a: a.total_skor,
        reverse=True,
    )

    promoted: list[RankChange] = []
    newly_entered: Optional[int] = None

    for rank_zero, applicant in enumerate(eligible):
        new_rank = rank_zero + 1
        old_rank = applicant.queue_rank
        new_status, new_q_rank = _assign_status(new_rank, quota)

        if old_rank != new_q_rank:
            if old_rank is not None or new_q_rank is not None:
                promoted.append(RankChange(
                    application_id=applicant.application_id,
                    rank_lama=old_rank if old_rank is not None else new_rank + 1,
                    rank_baru=new_q_rank if new_q_rank is not None else old_rank + 1,
                    triggered_by=application_id,
                    admin_id=admin_id,
                ))

            if old_rank is None and new_q_rank is not None:
                newly_entered = applicant.application_id

        applicant.queue_rank = new_q_rank
        applicant.status = new_status

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


def _is_sqlite(conn) -> bool:
    return "sqlite3" in type(conn).__module__


def _rerank_updates(rows: list, quota: int) -> list[tuple]:
    """
    Given sorted (app_id, score) rows, return list of (status, queue_rank, app_id) updates.
    Ties at the quota boundary are expanded: all applicants sharing the cutoff score
    are qualified, so admin handles the oversized pool manually.
    """
    if not rows:
        return []

    wl_slots = _waiting_list_slots(quota)
    cutoff_score = rows[quota - 1][1] if len(rows) >= quota else None

    updates = []
    rank = 0
    wl_count = 0
    below_cutoff = False

    for app_id, score in rows:
        rank += 1
        if not below_cutoff and (cutoff_score is None or score >= cutoff_score):
            updates.append((STATUS_QUALIFIED, rank, app_id))
        else:
            below_cutoff = True
            wl_count += 1
            if wl_count <= wl_slots:
                updates.append((STATUS_WAITING_LIST, rank, app_id))
            else:
                updates.append((STATUS_REJECTED, None, app_id))

    return updates


def db_rank_and_announce(conn, quota: int = DEFAULT_QUOTA) -> dict:
    """
    Batch-assign qualified/waiting_list/rejected to all non-disqualified applicants,
    then set results_announced=true in system_config. Atomic commit.

    Returns dict with counts: {qualified, waiting_list, rejected}
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

    updates = _rerank_updates(rows, quota)

    cur.executemany(_q("""
        UPDATE applications SET status_aplikasi = %s, queue_rank = %s WHERE id = %s
    """, conn), updates)

    cur.executemany(_q("""
        UPDATE results SET status_keputusan = %s WHERE application_id = %s
    """, conn), [(s, app_id) for s, _, app_id in updates])

    # Set announced flag
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(_q("""
        UPDATE system_config SET value = 'true', updated_at = %s WHERE key = 'results_announced'
    """, conn), (now,))

    conn.commit()

    counts = {STATUS_QUALIFIED: 0, STATUS_WAITING_LIST: 0, STATUS_REJECTED: 0}
    for status, _, _ in updates:
        counts[status] = counts.get(status, 0) + 1

    return counts


def db_rerank_post_announce(conn, quota: int = DEFAULT_QUOTA) -> None:
    """
    Re-assign qualified/waiting_list/rejected after a disqualification.
    Does NOT change the announced flag.
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

    updates = _rerank_updates(rows, quota)

    cur.executemany(_q("""
        UPDATE applications SET status_aplikasi = %s, queue_rank = %s WHERE id = %s
    """, conn), updates)

    cur.executemany(_q("""
        UPDATE results SET status_keputusan = %s WHERE application_id = %s
    """, conn), [(s, app_id) for s, _, app_id in updates])

    conn.commit()



def db_disqualify(
    conn,
    application_id: int,
    reason: str,
    admin_id: str,
    quota: int = DEFAULT_QUOTA,
    announced: bool = False,
) -> DisqualifyResult:
    """
    Disqualify applicant in DB, cascade-promote remaining, log to rank_history.
    If announced=True, uses qualified/waiting_list/rejected tiers.
    """
    cur = conn.cursor()

    # Validate
    cur.execute(_q("SELECT status_aplikasi, queue_rank FROM applications WHERE id = %s", conn), (application_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Application {application_id} not found.")
    current_status = row[0]
    if current_status == STATUS_DISQUALIFIED:
        raise ValueError(f"Application {application_id} is already disqualified.")

    # Mark disqualified
    cur.execute(_q("UPDATE applications SET status_aplikasi = %s, queue_rank = NULL WHERE id = %s", conn),
                (STATUS_DISQUALIFIED, application_id))
    cur.execute(_q("UPDATE results SET status_keputusan = %s, disqualify_reason = %s WHERE application_id = %s", conn),
                (STATUS_DISQUALIFIED, reason, application_id))

    # Fetch remaining applicants sorted by score
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

    # Pre-compute tie-aware statuses for the announced case
    if announced:
        status_map = {
            app_id: (status, q_rank)
            for status, q_rank, app_id in _rerank_updates([(r[0], r[1]) for r in rows], quota)
        }

    for rank_zero, (app_id, _, old_rank) in enumerate(rows):
        if announced:
            new_status, new_rank_val = status_map[app_id]
        else:
            # Pre-announcement: keep everything as pending
            new_status = STATUS_PENDING
            new_rank_val = None

        position = rank_zero + 1
        if old_rank != new_rank_val:
            old_for_history = old_rank if old_rank is not None else position + 1
            new_for_history = new_rank_val if new_rank_val is not None else position

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
    cur.executemany(_q("UPDATE results SET status_keputusan = %s WHERE application_id = %s", conn),
                    [(new_status, app_id) for new_status, _, app_id in rank_updates])

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
