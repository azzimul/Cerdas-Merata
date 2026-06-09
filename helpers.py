import json
from datetime import datetime, timezone

from flask import request

from db.connection import USE_SQLITE, get_conn


def _json_val(obj):
    return json.dumps(obj)

def _execute(cur, sql, params=()):
    if USE_SQLITE:
        sql = sql.replace("%s", "?")
    cur.execute(sql, params)

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _parse_json_fields(d: dict):
    for key in ("skor_per_kategori", "reasoning_trace", "anomaly_reasons"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                pass

def _get_config(conn, key: str, default=None) -> str:
    cur = conn.cursor()
    _execute(cur, "SELECT value FROM system_config WHERE key = %s", (key,))
    row = cur.fetchone()
    return row[0] if row else default

def _set_config(conn, key: str, value: str):
    cur = conn.cursor()
    _execute(cur, """
        UPDATE system_config SET value = %s, updated_at = %s WHERE key = %s
    """, (value, _now_iso(), key))
    conn.commit()

def _get_auth_user(conn=None):
    """
    Read Bearer token from Authorization header, validate against user_sessions.
    Returns user dict {id, username, full_name} or None.
    Opens its own DB connection if conn not provided.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None

    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    try:
        cur = conn.cursor()
        _execute(cur, """
            SELECT u.id, u.username, u.full_name
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = %s AND s.expires_at > %s
        """, (token, _now_iso()))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "username": row[1], "full_name": row[2]}
    finally:
        if own_conn:
            conn.close()

def _validate_apply(data: dict) -> str | None:
    required = ["nama_pendaftar", "pendapatan_ortu", "jumlah_tanggungan",
                 "tagihan_listrik", "wattage_listrik", "ipk",
                 "status_ortu", "pekerjaan_ortu"]
    for field_name in required:
        if field_name not in data or data[field_name] is None or data[field_name] == "":
            return f"Field '{field_name}' is required."
    if data["pendapatan_ortu"] < 0:
        return "Income cannot be negative."
    if not (0 <= data["ipk"] <= 100):
        return "GPA must be between 0 and 100 (or 0–4 scale)."
    valid_status = {"lengkap", "yatim", "piatu", "yatim_piatu"}
    if data["status_ortu"] not in valid_status:
        return f"Invalid parent status. Choose one of: {valid_status}"
    valid_pekerjaan = {"tidak_bekerja", "buruh_petani", "pedagang_kecil", "wiraswasta", "pns_swasta_tni"}
    if data["pekerjaan_ortu"] not in valid_pekerjaan:
        return "Invalid parent occupation."
    return None
