-- Cerdas Merata v2.0 — PostgreSQL Schema
-- Run: psql -U postgres -d cerdas_merata -f db/schema.sql

-- ── User accounts ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL          PRIMARY KEY,
    username        VARCHAR(100)    UNIQUE NOT NULL,
    email           VARCHAR(150)    UNIQUE NOT NULL,
    full_name       VARCHAR(150)    NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ── User sessions (token-based auth) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_sessions (
    token           VARCHAR(64)     PRIMARY KEY,
    user_id         INTEGER         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP       NOT NULL DEFAULT (NOW() + INTERVAL '24 hours')
);

-- ── System config (quota, announcement flag) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS system_config (
    key             VARCHAR(50)     PRIMARY KEY,
    value           TEXT            NOT NULL,
    updated_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);
INSERT INTO system_config (key, value) VALUES ('results_announced', 'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO system_config (key, value) VALUES ('quota', '50')                ON CONFLICT (key) DO NOTHING;

-- ── Applications (scholarship form submissions) ───────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id                  SERIAL          PRIMARY KEY,
    user_id             INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    nama_pendaftar      VARCHAR(100)    NOT NULL,
    pendapatan_ortu     INTEGER         NOT NULL,
    jumlah_tanggungan   SMALLINT        NOT NULL,
    tagihan_listrik     INTEGER         NOT NULL,
    wattage_listrik     SMALLINT        NOT NULL,
    ipk                 NUMERIC(5,2)    NOT NULL,
    status_ortu         VARCHAR(20)     NOT NULL
                            CHECK (status_ortu IN ('lengkap','yatim','piatu','yatim_piatu')),
    pekerjaan_ortu      VARCHAR(30)     NOT NULL
                            CHECK (pekerjaan_ortu IN ('tidak_bekerja','buruh_petani','pedagang_kecil','wiraswasta','pns_swasta_tni')),
    bantuan_lain        BOOLEAN         NOT NULL DEFAULT FALSE,
    kondisi_khusus      TEXT,
    status_aplikasi     VARCHAR(20)     NOT NULL DEFAULT 'pending'
                            CHECK (status_aplikasi IN ('pending','qualified','waiting_list','rejected','disqualified')),
    queue_rank          SMALLINT,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    expire_at           TIMESTAMP       NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    UNIQUE (user_id)
);

-- ── AI Reasoning results ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS results (
    id                  SERIAL          PRIMARY KEY,
    application_id      INTEGER         NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    total_skor          SMALLINT        NOT NULL,
    skor_per_kategori   JSONB           NOT NULL,
    reasoning_trace     JSONB           NOT NULL,
    status_keputusan    VARCHAR(20)     NOT NULL
                            CHECK (status_keputusan IN ('qualified','waiting_list','rejected','disqualified','pending')),
    is_anomaly          BOOLEAN         NOT NULL DEFAULT FALSE,
    anomaly_reasons     JSONB,
    admin_override      BOOLEAN         NOT NULL DEFAULT FALSE,
    override_reason     TEXT,
    disqualify_reason   TEXT,
    processed_at        TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ── Appeals ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appeals (
    id                  SERIAL          PRIMARY KEY,
    application_id      INTEGER         NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    alasan_banding      TEXT            NOT NULL,
    status_banding      VARCHAR(20)     NOT NULL DEFAULT 'open'
                            CHECK (status_banding IN ('open','under_review','resolved')),
    catatan_admin       TEXT,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    resolved_at         TIMESTAMP
);

-- ── Rank change audit trail ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rank_history (
    id                  SERIAL          PRIMARY KEY,
    application_id      INTEGER         NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    rank_lama           SMALLINT        NOT NULL,
    rank_baru           SMALLINT        NOT NULL,
    triggered_by        INTEGER         NOT NULL REFERENCES applications(id),
    admin_id            VARCHAR(50)     NOT NULL,
    changed_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_applications_status  ON applications(status_aplikasi);
CREATE INDEX IF NOT EXISTS idx_applications_rank    ON applications(queue_rank);
CREATE INDEX IF NOT EXISTS idx_applications_user    ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_results_app_id       ON results(application_id);
CREATE INDEX IF NOT EXISTS idx_appeals_app_id       ON appeals(application_id);
CREATE INDEX IF NOT EXISTS idx_rank_history_app_id  ON rank_history(application_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user        ON user_sessions(user_id);

-- Auto-delete expired data (run via pg_cron or scheduled job)
-- DELETE FROM applications WHERE expire_at < NOW();
-- DELETE FROM user_sessions WHERE expires_at < NOW();
