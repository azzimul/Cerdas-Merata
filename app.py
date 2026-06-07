"""
Cerdas Merata — Flask API Entry Point v2.0
Run:
  PostgreSQL : python app.py
  SQLite demo: set USE_SQLITE=1 && python app.py
"""

import csv
import io
import json
import os
import re
import secrets

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from db.connection import USE_SQLITE, get_conn, row_to_dict
from reasoning.engine import run as reasoning_run
from queue.manager import db_disqualify, db_rank_and_announce, db_rerank_post_announce

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

ADMIN_ID   = os.getenv("ADMIN_ID", "admin01")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")


# ── Bootstrap ────────────────────────────────────────────────────────────────

def _bootstrap():
    if USE_SQLITE:
        from db.connection import init_sqlite
        init_sqlite()
    else:
        # PostgreSQL: seed system_config if empty (schema.sql already has ON CONFLICT DO NOTHING)
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO system_config (key, value) VALUES ('results_announced', 'false') ON CONFLICT (key) DO NOTHING")
            cur.execute("INSERT INTO system_config (key, value) VALUES ('quota', '50') ON CONFLICT (key) DO NOTHING")
            conn.commit()
            conn.close()
        except Exception:
            pass

_bootstrap()


# ── Page Routes ──────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "auth.html")

@app.get("/auth")
def auth_page():
    return send_from_directory(FRONTEND_DIR, "auth.html")

@app.get("/apply")
def apply_page():
    return send_from_directory(FRONTEND_DIR, "apply.html")

@app.get("/result")
def result_page():
    return send_from_directory(FRONTEND_DIR, "result.html")

@app.get("/admin")
def admin_page():
    return send_from_directory(FRONTEND_DIR, "admin.html")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _ph():
    return "?" if USE_SQLITE else "%s"

def _json_val(obj):
    return json.dumps(obj)

def _execute(cur, sql, params=()):
    if USE_SQLITE:
        sql = sql.replace("%s", "?")
    cur.execute(sql, params)

def _now_iso():
    from datetime import datetime, timezone
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


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
def auth_register():
    data = request.get_json(silent=True) or {}
    username  = (data.get("username") or "").strip().lower()
    email     = (data.get("email") or "").strip().lower()
    full_name = (data.get("full_name") or "").strip()
    password  = data.get("password") or ""

    if not username or not email or not full_name or not password:
        return jsonify({"error": "All fields are required."}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email address."}), 400

    from datetime import datetime, timezone, timedelta
    pw_hash = generate_password_hash(password)
    token   = secrets.token_hex(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    conn = get_conn()
    try:
        cur = conn.cursor()
        # Check uniqueness
        _execute(cur, "SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            return jsonify({"error": "Username or email already registered."}), 409

        _execute(cur, """
            INSERT INTO users (username, email, full_name, password_hash)
            VALUES (%s, %s, %s, %s)
        """, (username, email, full_name, pw_hash))

        if USE_SQLITE:
            cur.execute("SELECT last_insert_rowid()")
        else:
            cur.execute("SELECT lastval()")
        user_id = cur.fetchone()[0]

        _execute(cur, """
            INSERT INTO user_sessions (token, user_id, expires_at) VALUES (%s, %s, %s)
        """, (token, user_id, expires))
        conn.commit()

        return jsonify({"token": token, "username": username, "full_name": full_name})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/auth/login")
def auth_login():
    data     = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        _execute(cur, "SELECT id, username, full_name, password_hash FROM users WHERE username = %s OR email = %s",
                 (username, username))
        row = cur.fetchone()
        if not row or not check_password_hash(row[3], password):
            return jsonify({"error": "Invalid username or password."}), 401

        user_id   = row[0]
        uname     = row[1]
        full_name = row[2]

        from datetime import datetime, timezone, timedelta
        token   = secrets.token_hex(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

        _execute(cur, """
            INSERT INTO user_sessions (token, user_id, expires_at) VALUES (%s, %s, %s)
        """, (token, user_id, expires))
        conn.commit()

        return jsonify({"token": token, "username": uname, "full_name": full_name})
    finally:
        conn.close()


@app.post("/api/auth/logout")
def auth_logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        conn = get_conn()
        try:
            cur = conn.cursor()
            _execute(cur, "DELETE FROM user_sessions WHERE token = %s", (token,))
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def auth_me():
    conn = get_conn()
    try:
        user = _get_auth_user(conn)
        if not user:
            return jsonify({"error": "Not authenticated."}), 401

        cur = conn.cursor()
        _execute(cur, "SELECT id FROM applications WHERE user_id = %s", (user["id"],))
        app_row = cur.fetchone()
        user["has_application"] = app_row is not None
        user["app_id"] = app_row[0] if app_row else None
        return jsonify(user)
    finally:
        conn.close()


# ── Application Routes ────────────────────────────────────────────────────────

@app.get("/api/status")
def public_status():
    conn = get_conn()
    try:
        announced = _get_config(conn, "results_announced", "false") == "true"
        return jsonify({"announced": announced})
    finally:
        conn.close()


@app.post("/api/apply")
def apply():
    conn = get_conn()
    try:
        user = _get_auth_user(conn)
        if not user:
            return jsonify({"error": "Authentication required."}), 401

        data = request.get_json(silent=True) or {}
        err = _validate_apply(data)
        if err:
            return jsonify({"error": err}), 400

        # Enforce one application per user
        cur = conn.cursor()
        _execute(cur, "SELECT id FROM applications WHERE user_id = %s", (user["id"],))
        if cur.fetchone():
            return jsonify({"error": "You have already submitted an application."}), 409

        facts = {
            "pendapatan_ortu":   int(data["pendapatan_ortu"]),
            "jumlah_tanggungan": int(data["jumlah_tanggungan"]),
            "tagihan_listrik":   int(data["tagihan_listrik"]),
            "wattage_listrik":   int(data["wattage_listrik"]),
            "ipk":               float(data["ipk"]),
            "status_ortu":       data["status_ortu"],
            "pekerjaan_ortu":    data["pekerjaan_ortu"],
            "bantuan_lain":      bool(data.get("bantuan_lain", False)),
        }

        result = reasoning_run(facts)

        # INSERT application — status stays 'pending' until admin announces
        _execute(cur, """
            INSERT INTO applications
                (user_id, nama_pendaftar, pendapatan_ortu, jumlah_tanggungan, tagihan_listrik,
                 wattage_listrik, ipk, status_ortu, pekerjaan_ortu, bantuan_lain, kondisi_khusus)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user["id"],
            data["nama_pendaftar"].strip(),
            facts["pendapatan_ortu"], facts["jumlah_tanggungan"],
            facts["tagihan_listrik"], facts["wattage_listrik"],
            facts["ipk"], facts["status_ortu"], facts["pekerjaan_ortu"],
            1 if facts["bantuan_lain"] else 0,
            data.get("kondisi_khusus") or None,
        ))

        if USE_SQLITE:
            cur.execute("SELECT last_insert_rowid()")
        else:
            cur.execute("SELECT lastval()")
        app_id = cur.fetchone()[0]

        # INSERT reasoning result (score stored but not revealed until announced)
        _execute(cur, """
            INSERT INTO results
                (application_id, total_skor, skor_per_kategori, reasoning_trace,
                 status_keputusan, is_anomaly, anomaly_reasons)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            app_id,
            result.total_skor,
            _json_val(result.skor_per_kategori),
            _json_val(result.reasoning_trace),
            "pending",
            1 if result.is_anomaly else 0,
            _json_val(result.anomaly_reasons),
        ))
        conn.commit()

        return jsonify({
            "application_id": app_id,
            "message": "Application submitted successfully. Results will be announced by the scholarship committee.",
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.get("/api/result/<int:app_id>")
def get_result(app_id):
    conn = get_conn()
    try:
        announced   = _get_config(conn, "results_announced", "false") == "true"
        admin_view  = request.headers.get("X-Admin-View") == "1"

        cur = conn.cursor()
        _execute(cur, """
            SELECT a.id, a.nama_pendaftar, a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.skor_per_kategori, r.reasoning_trace,
                   r.status_keputusan, r.is_anomaly, r.anomaly_reasons, r.processed_at
            FROM applications a
            JOIN results r ON r.application_id = a.id
            WHERE a.id = %s
        """, (app_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Application not found."}), 404

        keys = ["id","nama_pendaftar","status_aplikasi","queue_rank","created_at",
                "total_skor","skor_per_kategori","reasoning_trace",
                "status_keputusan","is_anomaly","anomaly_reasons","processed_at"]
        d = dict(zip(keys, row))
        _parse_json_fields(d)
        d["is_anomaly"] = bool(d["is_anomaly"])
        d["application_id"] = d.pop("id")
        d["announced"] = announced

        if not announced and not admin_view:
            # Hide score and trace from applicants until announcement
            for key in ("total_skor", "skor_per_kategori", "reasoning_trace",
                        "queue_rank", "anomaly_reasons"):
                d[key] = None
            d["is_anomaly"] = False
            d["status_aplikasi"] = "pending"
            d["status_keputusan"] = "pending"

        return jsonify(d)
    finally:
        conn.close()


# ── Admin Routes ──────────────────────────────────────────────────────────────

@app.get("/api/admin/config")
def admin_config():
    conn = get_conn()
    try:
        announced = _get_config(conn, "results_announced", "false") == "true"
        quota     = int(_get_config(conn, "quota", "50"))
        return jsonify({"announced": announced, "quota": quota})
    finally:
        conn.close()


@app.post("/api/admin/announce")
def admin_announce():
    conn = get_conn()
    try:
        if _get_config(conn, "results_announced", "false") == "true":
            return jsonify({"error": "Results have already been announced."}), 409

        quota = int(_get_config(conn, "quota", "50"))
        counts = db_rank_and_announce(conn, quota=quota)
        return jsonify({
            "ok": True,
            "qualified":    counts.get("qualified", 0),
            "waiting_list": counts.get("waiting_list", 0),
            "rejected":     counts.get("rejected", 0),
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/admin/quota")
def admin_set_quota():
    data = request.get_json(silent=True) or {}
    quota = data.get("quota")
    if quota is None or not str(quota).isdigit() or int(quota) < 1:
        return jsonify({"error": "Quota must be a positive integer."}), 400

    conn = get_conn()
    try:
        if _get_config(conn, "results_announced", "false") == "true":
            return jsonify({"error": "Cannot change quota after results have been announced."}), 409
        _set_config(conn, "quota", str(int(quota)))
        return jsonify({"ok": True, "quota": int(quota)})
    finally:
        conn.close()


@app.get("/api/admin/applicants")
def admin_list():
    status  = request.args.get("status")
    anomaly = request.args.get("anomaly")

    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = """
            SELECT a.id, a.nama_pendaftar, a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.is_anomaly, r.admin_override, a.kondisi_khusus,
                   r.override_reason, r.disqualify_reason
            FROM applications a
            LEFT JOIN results r ON r.application_id = a.id
            WHERE 1=1
        """
        params = []
        if status:
            sql += " AND a.status_aplikasi = %s"
            params.append(status)
        if anomaly == "1":
            sql += " AND a.kondisi_khusus IS NOT NULL AND a.kondisi_khusus != ''"
        sql += " ORDER BY COALESCE(a.queue_rank, 9999), r.total_skor DESC NULLS LAST" if not USE_SQLITE else \
               " ORDER BY COALESCE(a.queue_rank, 9999), COALESCE(r.total_skor, 0) DESC"

        _execute(cur, sql, params) if params else cur.execute(
            sql.replace("%s", "?") if USE_SQLITE else sql
        )
        rows = cur.fetchall()

        cols = ["id","nama_pendaftar","status_aplikasi","queue_rank","created_at",
                "total_skor","is_anomaly","admin_override","kondisi_khusus",
                "override_reason","disqualify_reason"]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["is_anomaly"] = bool(d["is_anomaly"])
            result.append(d)
        return jsonify(result)
    finally:
        conn.close()


@app.get("/api/admin/stats")
def admin_stats():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM applications")
        total = cur.fetchone()[0]

        def count(status):
            _execute(cur, "SELECT COUNT(*) FROM applications WHERE status_aplikasi = %s", (status,))
            return cur.fetchone()[0]

        _execute(cur, "SELECT COUNT(*) FROM appeals WHERE status_banding = %s", ("open",))
        open_appeals = cur.fetchone()[0]

        announced = _get_config(conn, "results_announced", "false") == "true"
        quota     = int(_get_config(conn, "quota", "50"))

        return jsonify({
            "total":        total,
            "pending":      count("pending"),
            "qualified":    count("qualified"),
            "waiting_list": count("waiting_list"),
            "rejected":     count("rejected"),
            "disqualified": count("disqualified"),
            "open_appeals": open_appeals,
            "announced":    announced,
            "quota":        quota,
        })
    finally:
        conn.close()


@app.post("/api/admin/disqualify/<int:app_id>")
def admin_disqualify(app_id):
    data   = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Disqualification reason is required."}), 400

    conn = get_conn()
    try:
        announced = _get_config(conn, "results_announced", "false") == "true"
        quota     = int(_get_config(conn, "quota", "50"))
        result    = db_disqualify(conn, app_id, reason, ADMIN_ID, quota=quota, announced=announced)
        return jsonify({
            "ok": True,
            "disqualified_id": result.disqualified_id,
            "rank_changes":    len(result.promoted),
            "newly_entered":   result.newly_entered,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/admin/override/<int:app_id>")
def admin_override(app_id):
    data   = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    status = data.get("status", "")

    if not reason:
        return jsonify({"error": "Override reason is required."}), 400
    if status not in ("qualified", "waiting_list", "rejected", "disqualified"):
        return jsonify({"error": "Status must be qualified, waiting_list, rejected, or disqualified."}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        _execute(cur, "UPDATE applications SET status_aplikasi = %s WHERE id = %s", (status, app_id))
        _execute(cur, """
            UPDATE results
            SET status_keputusan = %s, admin_override = %s, override_reason = %s
            WHERE application_id = %s
        """, (status, 1 if USE_SQLITE else True, reason, app_id))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/admin/appeal/<int:appeal_id>/resolve")
def admin_resolve_appeal(appeal_id):
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()

    conn = get_conn()
    try:
        cur = conn.cursor()
        _execute(cur, """
            UPDATE appeals
            SET status_banding = 'resolved', catatan_admin = %s, resolved_at = %s
            WHERE id = %s
        """, (note or None, _now_iso(), appeal_id))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/admin/reset")
def admin_reset():
    """Reset all applications for demo purposes. User accounts are preserved."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        # Delete in dependency order to avoid FK violations
        cur.execute("DELETE FROM rank_history" if not USE_SQLITE else "DELETE FROM rank_history")
        cur.execute("DELETE FROM appeals")
        cur.execute("DELETE FROM results")
        cur.execute("DELETE FROM applications")
        _execute(cur, "UPDATE system_config SET value = 'false', updated_at = %s WHERE key = 'results_announced'",
                 (_now_iso(),))
        conn.commit()
        return jsonify({"ok": True, "message": "All applications have been reset. User accounts are preserved."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.post("/api/admin/import")
def admin_import():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "File must be a .csv."}), 400

    IMPORT_PASSWORD = "Demo@1234"
    pw_hash = generate_password_hash(IMPORT_PASSWORD)

    stream  = io.StringIO(f.stream.read().decode("utf-8", errors="replace"))
    reader  = csv.DictReader(stream)

    required_cols = {
        "full_name", "pendapatan_ortu", "jumlah_tanggungan",
        "tagihan_listrik", "wattage_listrik", "ipk",
        "status_ortu", "pekerjaan_ortu", "bantuan_lain",
    }

    conn = get_conn()
    imported = skipped = 0
    errors = []

    try:
        from datetime import datetime, timezone, timedelta

        for row_num, row in enumerate(reader, start=2):
            missing = required_cols - set(row.keys())
            if missing:
                errors.append(f"Row {row_num}: missing columns {missing}")
                skipped += 1
                continue

            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                errors.append(f"Row {row_num}: full_name is empty")
                skipped += 1
                continue

            try:
                facts = {
                    "pendapatan_ortu":   int(row["pendapatan_ortu"]),
                    "jumlah_tanggungan": int(row["jumlah_tanggungan"]),
                    "tagihan_listrik":   int(row["tagihan_listrik"]),
                    "wattage_listrik":   int(row["wattage_listrik"]),
                    "ipk":               float(row["ipk"]),
                    "status_ortu":       row["status_ortu"].strip(),
                    "pekerjaan_ortu":    row["pekerjaan_ortu"].strip(),
                    "bantuan_lain":      row["bantuan_lain"].strip().lower() in ("true", "1", "yes"),
                }
            except (ValueError, KeyError) as e:
                errors.append(f"Row {row_num}: invalid data — {e}")
                skipped += 1
                continue

            err = _validate_apply({**facts, "nama_pendaftar": full_name})
            if err:
                errors.append(f"Row {row_num}: {err}")
                skipped += 1
                continue

            slug     = re.sub(r"[^a-z0-9]+", "_", full_name.lower())[:20].strip("_")
            username = f"{slug}_{row_num:03d}"
            email    = f"{username}@demo.local"

            try:
                cur = conn.cursor()
                _execute(cur, "SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                existing = cur.fetchone()

                if existing:
                    user_id = existing[0]
                    # Skip only if they already have an application (reset clears apps, so this allows re-import)
                    _execute(cur, "SELECT id FROM applications WHERE user_id = %s", (user_id,))
                    if cur.fetchone():
                        skipped += 1
                        continue
                else:
                    _execute(cur, """
                        INSERT INTO users (username, email, full_name, password_hash)
                        VALUES (%s, %s, %s, %s)
                    """, (username, email, full_name, pw_hash))

                    if USE_SQLITE:
                        cur.execute("SELECT last_insert_rowid()")
                    else:
                        cur.execute("SELECT lastval()")
                    user_id = cur.fetchone()[0]

                result_r = reasoning_run(facts)
                kondisi  = (row.get("kondisi_khusus") or "").strip() or None

                _execute(cur, """
                    INSERT INTO applications
                        (user_id, nama_pendaftar, pendapatan_ortu, jumlah_tanggungan,
                         tagihan_listrik, wattage_listrik, ipk, status_ortu,
                         pekerjaan_ortu, bantuan_lain, kondisi_khusus)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    user_id, full_name,
                    facts["pendapatan_ortu"], facts["jumlah_tanggungan"],
                    facts["tagihan_listrik"], facts["wattage_listrik"],
                    facts["ipk"], facts["status_ortu"], facts["pekerjaan_ortu"],
                    1 if facts["bantuan_lain"] else 0, kondisi,
                ))

                if USE_SQLITE:
                    cur.execute("SELECT last_insert_rowid()")
                else:
                    cur.execute("SELECT lastval()")
                app_id = cur.fetchone()[0]

                _execute(cur, """
                    INSERT INTO results
                        (application_id, total_skor, skor_per_kategori, reasoning_trace,
                         status_keputusan, is_anomaly, anomaly_reasons)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    app_id,
                    result_r.total_skor,
                    _json_val(result_r.skor_per_kategori),
                    _json_val(result_r.reasoning_trace),
                    "pending",
                    1 if result_r.is_anomaly else 0,
                    _json_val(result_r.anomaly_reasons),
                ))

                imported += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {e}")
                skipped += 1
                continue

        conn.commit()
        return jsonify({
            "ok":              True,
            "imported":        imported,
            "skipped":         skipped,
            "errors":          errors[:20],
            "import_password": IMPORT_PASSWORD,
        })

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.get("/api/admin/export")
def admin_export():
    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = """
            SELECT a.id, a.nama_pendaftar, a.pendapatan_ortu, a.jumlah_tanggungan,
                   a.tagihan_listrik, a.wattage_listrik, a.ipk,
                   a.status_ortu, a.pekerjaan_ortu, a.bantuan_lain,
                   a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.is_anomaly, r.admin_override, r.override_reason, r.disqualify_reason
            FROM applications a
            LEFT JOIN results r ON r.application_id = a.id
            ORDER BY COALESCE(a.queue_rank, 9999), a.id
        """
        cur.execute(sql.replace("%s","?") if USE_SQLITE else sql)
        rows = cur.fetchall()
        cols = ["id","name","income","dependents","electricity_bill","wattage",
                "gpa","parent_status","parent_job","other_scholarship",
                "status","rank","applied_at","score","anomaly","override","override_reason","disqualify_reason"]

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(cols)
        writer.writerows(rows)
        buf.seek(0)

        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=cerdas_merata_export.csv"},
        )
    finally:
        conn.close()


# ── Admin login check (server-side password validation) ──────────────────────

@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    if data.get("password") == ADMIN_PASS:
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid admin password."}), 401


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"  Mode  : {'SQLite (demo)' if USE_SQLITE else 'PostgreSQL'}")
    print(f"  URL   : http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
