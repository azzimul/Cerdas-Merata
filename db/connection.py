"""
DB connection — PostgreSQL (default) atau SQLite (USE_SQLITE=1 untuk demo offline).
"""

import os
import json

USE_SQLITE = os.getenv("USE_SQLITE", "0") == "1"

if USE_SQLITE:
    import sqlite3

    _DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cerdas_merata_demo.db")

    def get_conn():
        conn = sqlite3.connect(_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_sqlite():
        """Buat tabel SQLite yang ekuivalen dengan schema PostgreSQL."""
        conn = get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_pendaftar TEXT NOT NULL,
                pendapatan_ortu INTEGER NOT NULL,
                jumlah_tanggungan INTEGER NOT NULL,
                tagihan_listrik INTEGER NOT NULL,
                wattage_listrik INTEGER NOT NULL,
                ipk REAL NOT NULL,
                status_ortu TEXT NOT NULL,
                pekerjaan_ortu TEXT NOT NULL,
                bantuan_lain INTEGER NOT NULL DEFAULT 0,
                kondisi_khusus TEXT,
                status_aplikasi TEXT NOT NULL DEFAULT 'pending',
                queue_rank INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expire_at TEXT NOT NULL DEFAULT (datetime('now','+30 days'))
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id),
                total_skor INTEGER NOT NULL,
                skor_per_kategori TEXT NOT NULL,
                reasoning_trace TEXT NOT NULL,
                status_keputusan TEXT NOT NULL,
                is_anomaly INTEGER NOT NULL DEFAULT 0,
                anomaly_reasons TEXT,
                admin_override INTEGER NOT NULL DEFAULT 0,
                override_reason TEXT,
                disqualify_reason TEXT,
                processed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id),
                alasan_banding TEXT NOT NULL,
                status_banding TEXT NOT NULL DEFAULT 'open',
                catatan_admin TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS rank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id),
                rank_lama INTEGER NOT NULL,
                rank_baru INTEGER NOT NULL,
                triggered_by INTEGER NOT NULL REFERENCES applications(id),
                admin_id TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        conn.close()

else:
    import psycopg2
    import psycopg2.extras

    _DSN = os.getenv("DATABASE_URL") or (
        f"host={os.getenv('DB_HOST','localhost')} "
        f"port={os.getenv('DB_PORT','5432')} "
        f"dbname={os.getenv('DB_NAME','cerdas_merata')} "
        f"user={os.getenv('DB_USER','postgres')} "
        f"password={os.getenv('DB_PASS','')}"
    )

    def get_conn():
        conn = psycopg2.connect(_DSN)
        psycopg2.extras.register_default_jsonb(conn)
        return conn


def row_to_dict(row) -> dict:
    """Konversi sqlite3.Row atau psycopg2 row menjadi dict biasa."""
    if row is None:
        return None
    d = dict(row)
    # Parse JSON string fields jika SQLite mode
    for key in ("skor_per_kategori", "reasoning_trace", "anomaly_reasons"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass
    return d
