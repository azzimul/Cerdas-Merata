"""
Cerdas Merata — Flask API Entry Point
Jalankan:
  PostgreSQL : python app.py
  SQLite demo: USE_SQLITE=1 python app.py   (Windows: set USE_SQLITE=1 && python app.py)
"""

import csv
import io
import json
import os

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS

from db.connection import USE_SQLITE, get_conn, row_to_dict
from reasoning.engine import run as reasoning_run
from queue.manager import db_rerank_all, db_disqualify

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/result")
def result_page():
    return send_from_directory(FRONTEND_DIR, "result.html")

@app.get("/admin")
def admin_page():
    return send_from_directory(FRONTEND_DIR, "admin.html")

ADMIN_ID = os.getenv("ADMIN_ID", "admin01")
QUOTA = int(os.getenv("QUOTA", "50"))


# ── Bootstrap ────────────────────────────────────────────────────────────────

def _bootstrap():
    if USE_SQLITE:
        from db.connection import init_sqlite
        init_sqlite()
    # PostgreSQL: schema.sql dijalankan manual sebelum start

_bootstrap()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _placeholder(n=1):
    """Hasilkan %s (postgres) atau ? (sqlite) sesuai mode."""
    ph = "?" if USE_SQLITE else "%s"
    return ", ".join([ph] * n)


def _ph():
    return "?" if USE_SQLITE else "%s"


def _json_val(obj):
    """Simpan JSONB (postgres) atau JSON string (sqlite)."""
    return json.dumps(obj) if USE_SQLITE else json.dumps(obj)


def _execute(cur, sql, params=()):
    """Eksekusi query dengan placeholder yang benar."""
    if USE_SQLITE:
        sql = sql.replace("%s", "?")
    cur.execute(sql, params)


def _validate_apply(data: dict) -> str | None:
    required = ["nama_pendaftar", "pendapatan_ortu", "jumlah_tanggungan",
                 "tagihan_listrik", "wattage_listrik", "ipk",
                 "status_ortu", "pekerjaan_ortu"]
    for field in required:
        if field not in data or data[field] is None or data[field] == "":
            return f"Field '{field}' wajib diisi."

    if data["pendapatan_ortu"] < 0:
        return "Pendapatan tidak boleh negatif."
    if not (0 <= data["ipk"] <= 100):
        return "IPK harus antara 0 dan 100 (atau 0–4 untuk skala IPK)."
    valid_status = {"lengkap", "yatim", "piatu", "yatim_piatu"}
    if data["status_ortu"] not in valid_status:
        return f"Status orang tua tidak valid. Pilih salah satu: {valid_status}"
    valid_pekerjaan = {"tidak_bekerja", "buruh_petani", "pedagang_kecil", "wiraswasta", "pns_swasta_tni"}
    if data["pekerjaan_ortu"] not in valid_pekerjaan:
        return f"Pekerjaan orang tua tidak valid."
    return None


# ── Routes: Pendaftar ─────────────────────────────────────────────────────────

@app.post("/api/apply")
def apply():
    data = request.get_json(silent=True) or {}
    err = _validate_apply(data)
    if err:
        return jsonify({"error": err}), 400

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

    conn = get_conn()
    try:
        cur = conn.cursor()

        # 1. INSERT aplikasi
        _execute(cur, """
            INSERT INTO applications
                (nama_pendaftar, pendapatan_ortu, jumlah_tanggungan, tagihan_listrik,
                 wattage_listrik, ipk, status_ortu, pekerjaan_ortu, bantuan_lain, kondisi_khusus)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
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

        # 2. INSERT result awal (status pending — akan diupdate setelah rerank)
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

        # 3. Rerank semua pendaftar (update status + queue_rank di applications + results)
        db_rerank_all(conn, quota=QUOTA)

        # 4. Baca posisi akhir pendaftar ini
        cur = conn.cursor()
        _execute(cur, "SELECT status_aplikasi, queue_rank FROM applications WHERE id = %s", (app_id,))
        app_row = cur.fetchone()
        status_akhir = app_row[0]
        queue_rank   = app_row[1]

        # Update status_keputusan di results
        _execute(cur, "UPDATE results SET status_keputusan = %s WHERE application_id = %s",
                 (status_akhir, app_id))
        conn.commit()

        return jsonify({
            "application_id":   app_id,
            "nama_pendaftar":   data["nama_pendaftar"].strip(),
            "total_skor":       result.total_skor,
            "skor_per_kategori":result.skor_per_kategori,
            "reasoning_trace":  result.reasoning_trace,
            "status_keputusan": status_akhir,
            "queue_rank":       queue_rank,
            "is_anomaly":       result.is_anomaly,
            "anomaly_reasons":  result.anomaly_reasons,
            "processed_at":     _now_iso(),
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
            return jsonify({"error": "Aplikasi tidak ditemukan."}), 404

        keys = ["id","nama_pendaftar","status_aplikasi","queue_rank","created_at",
                "total_skor","skor_per_kategori","reasoning_trace",
                "status_keputusan","is_anomaly","anomaly_reasons","processed_at"]
        d = dict(zip(keys, row))
        _parse_json_fields(d)
        d["is_anomaly"] = bool(d["is_anomaly"])
        d["application_id"] = d.pop("id")
        return jsonify(d)
    finally:
        conn.close()


@app.post("/api/appeal")
def submit_appeal():
    data = request.get_json(silent=True) or {}
    app_id = data.get("application_id")
    alasan = (data.get("alasan_banding") or "").strip()

    if not app_id or not alasan:
        return jsonify({"error": "application_id dan alasan_banding wajib diisi."}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        # Cek aplikasi ada
        _execute(cur, "SELECT id FROM applications WHERE id = %s", (app_id,))
        if not cur.fetchone():
            return jsonify({"error": "Aplikasi tidak ditemukan."}), 404

        _execute(cur, """
            INSERT INTO appeals (application_id, alasan_banding) VALUES (%s, %s)
        """, (app_id, alasan))
        _execute(cur, """
            UPDATE applications SET status_aplikasi = 'appealed' WHERE id = %s
        """, (app_id,))
        conn.commit()
        return jsonify({"ok": True, "message": "Banding berhasil dikirim. Admin akan meninjau."})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


# ── Routes: Admin ─────────────────────────────────────────────────────────────

@app.get("/api/admin/applicants")
def admin_list():
    status  = request.args.get("status")
    anomaly = request.args.get("anomaly")

    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = """
            SELECT a.id, a.nama_pendaftar, a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.is_anomaly, r.admin_override
            FROM applications a
            LEFT JOIN results r ON r.application_id = a.id
            WHERE 1=1
        """
        params = []
        if status:
            sql += " AND a.status_aplikasi = %s"
            params.append(status)
        if anomaly == "1":
            sql += " AND r.is_anomaly = %s"
            params.append(1 if USE_SQLITE else True)
        sql += " ORDER BY COALESCE(a.queue_rank, 9999), r.total_skor DESC NULLS LAST"

        _execute(cur, sql, params) if params else cur.execute(
            sql.replace("%s", "?") if USE_SQLITE else sql
        )
        rows = cur.fetchall()

        cols = ["id","nama_pendaftar","status_aplikasi","queue_rank","created_at",
                "total_skor","is_anomaly","admin_override"]
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
        cur.execute("SELECT COUNT(*) FROM applications" if not USE_SQLITE else "SELECT COUNT(*) FROM applications")
        total = cur.fetchone()[0]

        def count(status):
            _execute(cur, "SELECT COUNT(*) FROM applications WHERE status_aplikasi = %s", (status,))
            return cur.fetchone()[0]

        _execute(cur, "SELECT COUNT(*) FROM appeals WHERE status_banding = %s", ("open",))
        open_appeals = cur.fetchone()[0]

        return jsonify({
            "total":        total,
            "waiting_list": count("waiting_list"),
            "rejected":     count("rejected"),
            "disqualified": count("disqualified"),
            "appealed":     open_appeals,
        })
    finally:
        conn.close()


@app.post("/api/admin/disqualify/<int:app_id>")
def admin_disqualify(app_id):
    data   = request.get_json(silent=True) or {}
    reason = (data.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Alasan diskualifikasi wajib diisi."}), 400

    conn = get_conn()
    try:
        result = db_disqualify(conn, app_id, reason, ADMIN_ID, quota=QUOTA)
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
        return jsonify({"error": "Alasan override wajib diisi."}), 400
    if status not in ("waiting_list", "rejected"):
        return jsonify({"error": "Status override harus 'waiting_list' atau 'rejected'."}), 400

    conn = get_conn()
    try:
        cur = conn.cursor()
        _execute(cur, """
            UPDATE applications SET status_aplikasi = %s WHERE id = %s
        """, (status, app_id))
        _execute(cur, """
            UPDATE results
            SET status_keputusan = %s, admin_override = %s, override_reason = %s
            WHERE application_id = %s
        """, (status, 1 if USE_SQLITE else True, reason, app_id))
        conn.commit()

        if status == "waiting_list":
            db_rerank_all(conn, quota=QUOTA)

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


@app.get("/api/admin/export")
def admin_export():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.nama_pendaftar, a.pendapatan_ortu, a.jumlah_tanggungan,
                   a.tagihan_listrik, a.wattage_listrik, a.ipk,
                   a.status_ortu, a.pekerjaan_ortu, a.bantuan_lain,
                   a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.is_anomaly, r.admin_override, r.override_reason, r.disqualify_reason
            FROM applications a
            LEFT JOIN results r ON r.application_id = a.id
            ORDER BY COALESCE(a.queue_rank, 9999), a.id
        """ if not USE_SQLITE else """
            SELECT a.id, a.nama_pendaftar, a.pendapatan_ortu, a.jumlah_tanggungan,
                   a.tagihan_listrik, a.wattage_listrik, a.ipk,
                   a.status_ortu, a.pekerjaan_ortu, a.bantuan_lain,
                   a.status_aplikasi, a.queue_rank, a.created_at,
                   r.total_skor, r.is_anomaly, r.admin_override, r.override_reason, r.disqualify_reason
            FROM applications a
            LEFT JOIN results r ON r.application_id = a.id
            ORDER BY COALESCE(a.queue_rank, 9999), a.id
        """)
        rows = cur.fetchall()
        cols = ["id","nama","pendapatan","tanggungan","tagihan_listrik","wattage",
                "ipk","status_ortu","pekerjaan","beasiswa_lain",
                "status","rank","tgl_daftar","skor","anomali","override","alasan_override","alasan_dq"]

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


# ── Utils ─────────────────────────────────────────────────────────────────────

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


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f"  Mode: {'SQLite (demo)' if USE_SQLITE else 'PostgreSQL'}")
    print(f"  URL : http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
