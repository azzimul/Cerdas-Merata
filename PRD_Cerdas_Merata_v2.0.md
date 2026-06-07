# PRODUCT REQUIREMENTS DOCUMENT

## Cerdas Merata — AI-Powered Scholarship Eligibility System

Scholarship Domain | Reasoning + Waiting List Queue | Forward Chaining

---

| Attribute | Detail |
|-----------|--------|
| Document Version | v2.3 — Tie-expansion at quota boundary |
| Date | June 2026 |
| Domain | Education — Scholarship Program |
| Core Algorithm | Forward Chaining Reasoning + Waiting List Queue System |
| Database | PostgreSQL (persistent) / SQLite (demo) |
| Exhibition | AI Exhibition — 10 June 2026 |
| Status | Active |

---

## 1. Overview & Background

Cerdas Merata provides a limited scholarship quota (configurable, default 50 slots per period) for students from low-income households. The selection process was previously manual — inconsistent, slow, and prone to subjective bias.

This project builds an AI-powered web system that automates the selection process:

- **Reasoning (Forward Chaining):** Assesses student eligibility automatically based on economic, academic, and social data submitted via a form.
- **Waiting List Queue:** All qualified applicants enter an ordered waiting list based on score. Admin can disqualify applicants (fraud/data falsification) and the system automatically promotes those below.
- **Announcement System:** Results are hidden until the admin officially announces them — consistent with how real scholarship programs operate.

The system also fulfills **Ethical Guardrails** requirements (50% of grading weight) covering transparency, fairness, privacy, and human oversight.

---

## 2. Project Objectives

### 2.1 Functional Objectives

1. Build a Forward Chaining engine with 12 IF-THEN rules that process student data and produce a transparent priority score.
2. Build a Waiting List Queue that automatically ranks qualified applicants by score, and promotes lower-ranked applicants when a higher-ranked one is disqualified.
3. Implement a **user authentication system** (register/login) so each applicant has a verified account with one application per user.
4. Implement an **announcement system** — results stay hidden as `pending` until the admin announces them, at which point statuses are batch-assigned.
5. Store all applicant data and reasoning results in PostgreSQL as the system's source of truth.
6. Provide a web interface for applicants and admins.
7. Generate a human-readable reasoning trace for every AI decision.

### 2.2 Non-Functional Objectives

8. **Transparency:** Every decision includes a reasoning trace the user can review.
9. **Fairness:** No attributes related to ethnicity, religion, race, or gender are used.
10. **Privacy:** Sensitive data (income, bills) is auto-deleted after 30 days.
11. **Human oversight:** Admin override and disqualification mechanisms are available.
12. **Accessibility:** All UI text in English for international readability.

---

## 3. Scope

### 3.1 In Scope

- User registration and login (account-based access)
- Scholarship application form (9 fields, dropdown-based for scored fields)
- Forward Chaining engine (12 rules, 5 categories)
- Waiting List Queue: ranked by score, cascade-promotion on disqualification
- Announcement system: admin reveals results via a single button press
- PostgreSQL as the primary database
- Admin dashboard: applicant list, scores, statuses, announcement, quota management, override
- Reasoning trace displayed post-announcement
- Configurable quota (admin-adjustable before announcement)
- Synthetic dataset (100 rows) + bias analysis report

### 3.2 Out of Scope

- Real payment integration
- Machine Learning / predictive models
- Mobile application
- Multi-factor auth / enterprise security
- Real-time external scholarship API integration
- Appeal / banding system (removed from v2.0 applicant UI for simplification)

---

## 4. User Roles

| Role | Description | Primary Access |
|------|-------------|----------------|
| Scholarship Applicant | Student / parent applying for scholarship | Register account, fill form, view result (post-announcement) |
| Admin | Staff managing quota, results, and integrity | Dashboard, announce results, override decisions, disqualify |
| Reviewer / Lecturer | Exhibition audience evaluating the system | View reasoning trace, ethical analysis |

---

## 5. Functional Requirements

### 5.1 User Authentication (FR-00)

| # | Requirement |
|---|-------------|
| FR-00.1 | Users must register an account (full name, email, username, password) before applying |
| FR-00.2 | Login via username or email + password |
| FR-00.3 | Sessions managed via server-side tokens (24-hour expiry) stored in localStorage |
| FR-00.4 | One application per user — attempting to submit twice returns HTTP 409 |
| FR-00.5 | Logout invalidates the session token server-side |

### 5.2 Application Form (FR-01)

The form is only accessible after login. If the user already has an application, they are redirected to the result page.

**Form Fields:**

| Field | Type | Options / Notes |
|-------|------|-----------------|
| Full Name | Text input | Required |
| Parent/Guardian Monthly Income | Dropdown | See scoring tiers below |
| Number of Dependents in School | Dropdown | 1, 2, 3, 4+ |
| Monthly Electricity Bill | Dropdown | See scoring tiers below |
| Electricity Power (VA) | Dropdown | 450, 900, 1300, 2200+, No electricity |
| GPA / Academic Score | Dropdown | See scoring tiers below |
| Parent Status | Dropdown | Both alive, Father deceased, Mother deceased, Both deceased |
| Parent/Guardian Occupation | Dropdown | 5 categories (see §5.3) |
| Currently Receiving Another Scholarship? | Radio | Yes / No |
| Special Condition | Textarea (optional) | Free text; may trigger manual review |

**Dropdown value mapping (scored fields):**

*Parent Income:*
| Option | Value Sent | Rule |
|--------|------------|------|
| No income (Rp 0) | 0 | A1: +10 pts |
| Below Rp 1,000,000 | 500,000 | A2: +8 pts |
| Rp 1,000,000 – 1,999,999 | 1,500,000 | A3: +6 pts |
| Rp 2,000,000 – 2,999,999 | 2,500,000 | A4: +4 pts |
| Rp 3,000,000 – 4,500,000 | 3,750,000 | A5: +2 pts |
| Above Rp 4,500,000 | 5,000,000 | No rule: +0 pts |

*Number of Dependents:*
| Option | Value | Rule |
|--------|-------|------|
| 1 | 1 | No rule: +0 pts |
| 2 | 2 | B3: +2 pts |
| 3 | 3 | B2: +4 pts |
| 4 or more | 4 | B1: +6 pts |

*Monthly Electricity Bill:*
| Option | Value | Rule |
|--------|-------|------|
| Rp 0 (no electricity) | 0 | C1: +6 pts |
| Below Rp 100,000 | 50,000 | C2: +4 pts |
| Rp 100,000 – 199,999 | 150,000 | C3: +2 pts |
| Rp 200,000 – 350,000 | 275,000 | C4: +1 pt |
| Above Rp 350,000 | 400,000 | No rule: +0 pts |

*GPA / Academic Score (4.00 scale):*
| Option | Value | Rule |
|--------|-------|------|
| 3.70 – 4.00 (Excellent) | 3.8 | E1: +5 pts |
| 3.50 – 3.69 (Very Good) | 3.6 | E2: +4 pts |
| 3.00 – 3.49 (Good) | 3.2 | E3: +2 pts |
| 2.50 – 2.99 (Satisfactory) | 2.7 | E4: +1 pt |
| Below 2.50 | 2.0 | No rule: +0 pts |

**Post-submission behavior:**  
After submitting, the applicant is redirected to the result page showing a "pending" state. No scores or rankings are shown until the admin announces results.

**Closed-period behavior:**  
Once results are announced, any logged-in user who has not yet submitted an application will see an "Application Period Closed" notice instead of the form. New submissions are not accepted after announcement.

### 5.3 Forward Chaining Engine (FR-02)

12 scoring rules across 5 categories. Each category uses exclusive groups (only the highest-matching tier fires).

**Maximum score: 45 points**

| Category | Rules | Max |
|----------|-------|-----|
| A — Poverty (Income) | A1–A5 (income tiers: 0 / <1M / 1M–1.9M / 2M–2.9M / 3M–4.5M) | 10 pts |
| B — Dependents | B1 (4+), B2 (3), B3 (2) — count of dependents in school | 6 pts |
| C — Infrastructure | C1–C4 (monthly electricity bill tiers) + C5–C7 (installed VA tiers) | 11 pts |
| D — Social | D1–D2 (parent status: both/one deceased) + D3–D5 (occupation) | 10 pts |
| E — Academic | E1–E4 (GPA tiers: ≥3.7 / 3.5–3.69 / 3.0–3.49 / 2.5–2.99) − E5 (active scholarship deduction −8) | 5 pts (+/−8) |

**Anomaly Detection (3 rules):**
- ANO1: 450VA but income > 5,000,000 (inconsistent)
- ANO2: Zero income but electricity bill > 500,000 (impossible)
- ANO3: Zero income but wattage ≥ 2200 VA (impossible)

Anomalies flag the application for manual admin review but do not automatically disqualify.

### 5.4 Waiting List Queue & Announcement (FR-03)

**Pre-announcement:**
- All submitted applications have `status = pending`
- Scores are calculated and stored at submission time but hidden from applicants
- Admin can view all scores and traces at any time
- `GET /api/status` (public, no auth) returns `{"announced": bool}` — used by the apply page to gate form access

**Announcement (admin action):**
1. Admin sets quota (configurable, default 50)
2. Admin clicks "Announce Results"
3. System batch-assigns statuses by score (descending):
   - Score ≥ cutoff score (score at quota position) → **Qualified** *(see tie rule below)*
   - Next ⌈quota×0.20⌉ positions → **Waiting List**
   - Remaining → **Rejected**
4. `results_announced` flag set to `true` in system_config
5. Applicants refreshing their result page now see their actual status

**Tie rule at quota boundary:**
If multiple applicants share the same score as the applicant at position N (the quota cutoff), all of them are promoted to **Qualified** — the qualified pool expands beyond the quota. The waiting list begins at the first applicant scoring below the cutoff. Admin is expected to review the oversized qualified pool and use Override to demote applicants as needed.

**Post-announcement disqualification cascade:**
- Admin disqualifies a Qualified applicant → top Waiting List person becomes Qualified (tie-expansion applies to the rerank as well)
- Admin disqualifies a Waiting List applicant → top Rejected person becomes Waiting List
- All rank changes recorded in `rank_history` for audit

**Quota:**
- Configurable before announcement via admin dashboard
- Cannot be changed after announcement
- Waiting list = 20% of quota (rounded up, e.g. quota=50 → 10 waiting list slots)

### 5.5 Application Status Definitions

| Status | Description |
|--------|-------------|
| `pending` | Submitted, awaiting announcement |
| `qualified` | Selected — score at or above the quota cutoff score (may exceed N slots if tied) |
| `waiting_list` | In next 20% of quota; promoted if a qualified is disqualified |
| `rejected` | Score below waiting list threshold |
| `disqualified` | Admin-flagged for fraud / data integrity violation |

### 5.6 Admin Dashboard (FR-04)

| Feature | Description |
|---------|-------------|
| Login | Password-protected (env: `ADMIN_PASS`, default: `admin123`) |
| Announcement Panel | "Announce Results" button pre-announcement; success banner post-announcement |
| Quota Management | Shows current quota, input field to update (pre-announcement only) |
| Stats Row | Total, Qualified, Waiting List, Rejected, Disqualified, Pending, Quota |
| Applicant Table | Rank, ID, Name, Score, Status badge, Special Condition, Date Applied, Actions |
| Filters | By status, special condition flag, name search |
| Trace Modal | Full reasoning breakdown per category (always visible to admin) |
| Override | Force-change any applicant's status — **Qualified, Waiting List, Rejected, or Disqualified** — with mandatory reason; disqualification triggers cascade promotion |
| Override Reason Tooltip | Status badge shows a `ⓘ` icon for overridden or disqualified applicants; hovering reveals the recorded reason |
| Export CSV | Download all applicant + result data as CSV |
| Import CSV | Upload a CSV (generated by `generate_data.py`) to bulk-create applicants in pending state (demo use) |
| Reset All | Permanently delete all applications and results, reset announced flag; user accounts preserved (demo use only) |

### 5.7 Ethical Guardrails (FR-05)

| Guardrail | Implementation |
|-----------|----------------|
| Transparency | Full reasoning trace shown to applicant after announcement |
| Fairness | Only economic, academic, and family data used — no demographic bias |
| Privacy | Data auto-deleted after 30 days; no third-party sharing |
| Human Oversight | Admin can override any AI decision (including disqualification) via a single Override action with a mandatory, permanently recorded reason |
| Anomaly detection | 3 rules flag impossible/inconsistent data for manual review |
| Audit trail | `rank_history` table records all rank changes with admin ID and timestamp |

---

## 6. Database Schema

### users
```
id, username, email, full_name, password_hash, created_at
```

### user_sessions
```
token (PK), user_id (FK→users), created_at, expires_at
```

### system_config
```
key (PK), value, updated_at
-- Rows: results_announced (false/true), quota (integer)
```

### applications
```
id, user_id (FK→users, UNIQUE), nama_pendaftar,
pendapatan_ortu, jumlah_tanggungan, tagihan_listrik, wattage_listrik, ipk,
status_ortu, pekerjaan_ortu, bantuan_lain, kondisi_khusus,
status_aplikasi (pending|qualified|waiting_list|rejected|disqualified),
queue_rank, created_at, expire_at
```

### results
```
id, application_id (FK), total_skor, skor_per_kategori (JSON),
reasoning_trace (JSON), status_keputusan, is_anomaly, anomaly_reasons (JSON),
admin_override, override_reason, disqualify_reason, processed_at
```

### appeals
```
id, application_id (FK), alasan_banding, status_banding, catatan_admin,
created_at, resolved_at
```

### rank_history
```
id, application_id (FK), rank_lama, rank_baru, triggered_by (FK), admin_id, changed_at
```

---

## 7. Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vanilla HTML / CSS / JavaScript |
| Backend | Python Flask + Flask-CORS |
| Auth | werkzeug password hashing + secrets token |
| Database | PostgreSQL 12+ (production) / SQLite (demo, `USE_SQLITE=1`) |
| Reasoning | Custom Python Forward Chaining engine |
| Rules Config | rules.json (12 scoring rules + 3 anomaly rules) |
| Queue | Custom Python waiting list manager |

---

## 8. Application Flow

```
Applicant                          System                         Admin
─────────                          ──────                         ─────
1. Visit / → auth.html
2. Register account ──────────────→ Create user in DB
3. Login ──────────────────────────→ Issue session token
4. Fill scholarship form ──────────→ Run AI reasoning
                                     Store score (hidden)
                                     status = 'pending'
5. See result page (pending msg)

                                                              6. View all applicants
                                                              7. Set quota
                                                              8. Click "Announce Results"
                                                                 ↓
                                     Batch-assign statuses:
                                     qualified / waiting_list / rejected
                                     Set results_announced = true

9. Refresh result page ────────────→ Return full result
   See: Qualified / Waiting List /   (score + trace visible)
        Rejected / Disqualified

                                                              10. Disqualify (if fraud)
                                     Cascade-promote others
```

---

## 9. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SQLITE` | `0` | Set to `1` for SQLite demo mode |
| `DATABASE_URL` | — | Full PostgreSQL connection string |
| `DB_HOST/PORT/NAME/USER/PASS` | localhost defaults | PostgreSQL connection parts |
| `ADMIN_ID` | `admin01` | Admin identifier for audit logs |
| `ADMIN_PASS` | `admin123` | Admin dashboard password |
| `PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `1` | Debug mode |

---

## 10. Deliverables

- [ ] Working web application (this repo)
- [ ] A1 scientific poster (English)
- [ ] GitHub source code
- [ ] 100-row synthetic dataset + bias_analysis_report.pdf
- [ ] changes_implementation.md (changelog)
- [ ] User manual (installation + usage)

---

## 11. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Admin announces too early | Medium | High | Confirmation modal; flag shown on dashboard |
| Duplicate accounts / fraud | Medium | Medium | UNIQUE(user_id) + one-app-per-user enforcement |
| Score manipulation via dropdown | Low | Medium | Values map to fixed scoring tiers; backend re-validates |
| Token theft (demo) | Low | Low | 24h expiry; HTTPS in production |
| SQLite demo data loss | High | Low | For demo only; PostgreSQL for production |
| Anomaly data not reviewed | Medium | Medium | Anomaly badge visible in admin table |

---

## 12. Grading Criteria Alignment

**Technical (50%)**
- Forward Chaining correctness: 12 rules, 5 categories ✓
- Queue manager: cascade-promotion on disqualification ✓
- DB integration: PostgreSQL/SQLite dual-mode ✓
- Web functionality: auth, form, result, admin ✓
- Announcement system: batch-status assignment ✓

**Ethical/Transformative (50%)**
- Reasoning transparency: trace visible post-announcement ✓
- Fairness: no demographic bias ✓
- Privacy: 30-day auto-delete ✓
- Human oversight: unified override (covers status change + disqualification) with auditable reason ✓
- Anomaly detection: 3 rules ✓
- Audit trail: rank_history ✓
