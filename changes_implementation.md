# Cerdas Merata — Implementation Changelog
## Version 2.0 (June 2026)

This document records all changes made during the v1.3 → v2.0 redesign.

---

## Summary of Changes

| Area | Change |
|------|--------|
| Auth | Added full user registration + login system with session tokens |
| Application Flow | Applications stay `pending` until admin announces results |
| Status System | Added `qualified` status; 20% of quota becomes `waiting_list` |
| Admin | Announcement button, configurable quota, English UI, Special Condition viewer, Reset button |
| Form | Dropdowns for income/dependents/bill/GPA based on PRD scoring tiers |
| Language | All UI text changed to English |
| Theme | Branding updated from "bimbel subsidy" to "scholarship program" |
| PRD | Updated to v2.0 |

---

## File-by-File Changes

### `db/schema.sql`
- Added `users` table (id, username, email, full_name, password_hash, created_at)
- Added `user_sessions` table (token, user_id FK, created_at, expires_at)
- Added `system_config` table (key, value, updated_at) with seed rows for `results_announced=false` and `quota=50`
- `applications`: added `user_id` FK column; added UNIQUE(user_id) for one-application-per-user; updated `status_aplikasi` CHECK to include `qualified`, removed `appealed`
- `results`: updated `status_keputusan` CHECK to include `qualified`

### `db/connection.py`
- Updated `init_sqlite()` to create all new tables (users, user_sessions, system_config)
- Added `ALTER TABLE IF NOT EXISTS` for `user_id` column in applications
- Added INSERT OR IGNORE to seed system_config defaults

### `queue/manager.py`
- Added `STATUS_QUALIFIED = "qualified"` constant
- Added `db_rank_and_announce(conn, quota)`: batch-assigns qualified/waiting_list/rejected post-announcement, sets system_config `results_announced=true`
- Added `db_rerank_post_announce(conn, quota)`: same ranking logic without touching the announced flag (used by disqualify cascade)
- Updated `db_disqualify()`: post-announcement, uses qualified/waiting_list/rejected tiers instead of waiting_list/rejected

### `app.py`
- Added imports: `secrets`, `werkzeug.security`
- Removed `QUOTA` env var (now read from `system_config` DB table)
- Added helpers: `_get_config()`, `_set_config()`, `_get_auth_user()`
- Added routes: `GET /auth`, `GET /apply`
- Added endpoints:
  - `POST /api/auth/register` — create user account
  - `POST /api/auth/login` — login, return session token
  - `POST /api/auth/logout` — invalidate token
  - `GET /api/auth/me` — return current user + application status
  - `POST /api/admin/announce` — batch-announce results (one-time)
  - `POST /api/admin/quota` — update quota (pre-announcement only)
  - `GET /api/admin/config` — return {announced, quota}
- Updated `POST /api/apply`: requires auth, enforces one-per-user, no reranking, status stays `pending`
- Updated `GET /api/result/<id>`: returns pending-only data if not announced
- Updated `GET /api/admin/stats`: added `announced`, `qualified`, `pending` counts
- Updated `POST /api/admin/override`: allows `qualified` as target status
- Updated `_bootstrap()`: seeds system_config if missing

### `frontend/auth.html` (NEW)
- Login / Register page with tab toggle
- Register: Full Name, Email, Username, Password, Confirm Password
- Login: Username, Password
- Stores token in `localStorage.cm_token`, redirects to `/apply`

### `frontend/apply.html` (NEW — replaces index.html)
- Auth gate: checks token on load, redirects to `/auth` if not authenticated
- If user already has an application, redirects to `/result`
- All form labels in English
- **Dropdowns** for: Parent Income, Number of Dependents, Electricity Bill, GPA
- `kondisi_khusus` renamed to "Special Condition"
- Post-submit: stores `cm_app_id` in localStorage, redirects to `/result`
- Navbar updated: shows "My Application" + "Log Out" links

### `frontend/result.html` (UPDATED)
- Auth gate: checks token on load
- **Pre-announcement**: shows "Application Submitted" badge + "Results will be announced soon" message
- **Post-announcement**: shows full status (Qualified / Waiting List / Rejected / Disqualified)
- Status-specific messages for each outcome
- Score + reasoning trace shown only post-announcement
- Removed appeal button (simplified flow)

### `frontend/admin.html` (UPDATED)
- All text in English
- Added **Quota Management** section: shows current quota, input + "Update Quota" button
- Added **Announce Results** section: prominent button pre-announcement, green banner post-announcement
- Stats row updated: Qualified, Waiting List, Rejected, Disqualified, Pending counts
- Status filter dropdown: added Qualified, renamed labels to English
- Table headers in English
- Confirmation modal before announcing (irreversible action)
- Status badges updated for `qualified`
- **"Anomaly" column renamed to "Special Condition"** — shows "View" button when `kondisi_khusus` is present; opens modal with full text
- **"Reset All Applications" button** (danger, confirmation modal) — clears all applications + resets announced flag; user accounts preserved (for demo use)

### `frontend/api.js` (UPDATED)
- `apiFetch()` now reads `localStorage.cm_token` and sends `Authorization: Bearer` header
- Auto-redirects to `/auth` on 401 response
- Added auth methods: `api.register()`, `api.login()`, `api.logout()`, `api.me()`
- Added admin methods: `api.announce()`, `api.updateQuota()`, `api.adminConfig()`
- Updated `statusBadge()`: added `qualified` (green), updated labels to English
- Updated `catLabel()`: all category labels in English

### `frontend/style.css` (UPDATED)
- Added `.badge-teal` for qualified status (distinct from waiting_list orange)
- Updated navbar subtitle to "Scholarship Program"
- Added `.status-announced` banner styles
- Added `.announce-panel` styles for admin announcement section

### `PRD_Cerdas_Merata_v2.0.md` (NEW)
- Full updated product requirements document
- Added: User Authentication, Announcement System, updated Status Definitions
- Updated: Form field specifications (dropdowns), Admin capabilities, English UI requirement

---

## New Status Flow

```
User registers account → submits form → status = pending
                                              ↓
                              (admin announces results)
                                              ↓
              qualified (top N)  |  waiting_list (20% of N)  |  rejected (rest)
                                              ↓
                     Admin can disqualify → cascade promotes up
```

## Dropdown Value Mapping

| Field | Option | Value Sent | Points |
|-------|--------|------------|--------|
| Income | No income | 0 | +10 |
| Income | < Rp 1,000,000 | 500000 | +8 |
| Income | Rp 1M – 1.9M | 1500000 | +6 |
| Income | Rp 2M – 2.9M | 2500000 | +4 |
| Income | Rp 3M – 4.5M | 3750000 | +2 |
| Income | > Rp 4,500,000 | 5000000 | +0 |
| Dependents | 1 | 1 | +0 |
| Dependents | 2 | 2 | +2 |
| Dependents | 3 | 3 | +4 |
| Dependents | 4+ | 4 | +6 |
| Electricity Bill | Rp 0 | 0 | +6 |
| Electricity Bill | < Rp 100K | 50000 | +4 |
| Electricity Bill | Rp 100K–199K | 150000 | +2 |
| Electricity Bill | Rp 200K–350K | 275000 | +1 |
| Electricity Bill | > Rp 350K | 400000 | +0 |
| GPA | 3.70–4.00 | 3.8 | +5 |
| GPA | 3.50–3.69 | 3.6 | +4 |
| GPA | 3.00–3.49 | 3.2 | +2 |
| GPA | 2.50–2.99 | 2.7 | +1 |
| GPA | < 2.50 | 2.0 | +0 |
