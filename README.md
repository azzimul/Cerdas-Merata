# Cerdas Merata

An AI-powered scholarship eligibility system built for an AI Exhibition. Applicants submit an economic and academic profile; a Forward Chaining engine scores and ranks them automatically. An admin announces results when ready, with full override and audit capabilities.

---

## Features

- **Forward Chaining engine** — 12 IF-THEN rules across 5 categories (poverty, dependents, infrastructure, social, academic) producing a transparent priority score
- **Waiting list queue** — ranked by score; disqualifying a qualified applicant automatically promotes the next in line
- **Announcement system** — scores stay hidden until the admin publishes results in a single action
- **Tie expansion** — if multiple applicants share the cutoff score, all are promoted to qualified for admin review
- **Admin override** — any decision (including disqualification) can be overridden with a mandatory auditable reason
- **Anomaly detection** — 3 rules flag inconsistent data (e.g. zero income but high electricity) for manual review
- **User authentication** — account-based, one application per user, 24-hour session tokens
- **Dual database** — PostgreSQL for production, SQLite for local demo (`USE_SQLITE=1`)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vanilla HTML / CSS / JavaScript |
| Backend | Python 3.11+ · Flask · Flask-CORS |
| Auth | Werkzeug password hashing · secrets tokens |
| Database | PostgreSQL 12+ (prod) · SQLite (demo) |
| Reasoning | Custom Forward Chaining engine (`reasoning/`) |
| Queue | Custom waiting list manager (`queue/`) |

---

## Project Structure

```
├── app.py                  # Flask API — all routes
├── requirements.txt
├── generate_data.py        # CLI tool to generate synthetic demo CSV
├── demo_applicants.csv     # Sample dataset (100 rows)
│
├── db/
│   ├── connection.py       # PostgreSQL / SQLite connection layer
│   └── schema.sql          # PostgreSQL schema
│
├── queue/
│   ├── manager.py          # Waiting list queue logic
│   └── test_queue.py       # Unit tests
│
├── reasoning/
│   ├── engine.py           # Forward Chaining engine
│   ├── rules.json          # Rule definitions (editable)
│   └── test_engine.py      # Unit tests
│
└── frontend/
    ├── auth.html           # Register / Login
    ├── apply.html          # Scholarship application form
    ├── result.html         # Applicant result page
    ├── admin.html          # Admin dashboard
    ├── api.js              # Fetch wrapper
    └── style.css
```

---

## Quick Start — SQLite Demo (no database setup needed)

```bash
# 1. Clone and install dependencies
git clone https://github.com/your-username/cerdas-merata.git
cd cerdas-merata
pip install -r requirements.txt

# 2. Run in SQLite demo mode
set USE_SQLITE=1        # Windows
# export USE_SQLITE=1   # macOS / Linux
python app.py

# 3. Open http://localhost:5000
```

On first run the SQLite database is created automatically.

### Load sample data (optional)

```bash
# Import the included CSV via the admin dashboard
# Admin → Import CSV → select demo_applicants.csv
# Default password for all imported accounts: Demo@1234

# Or generate a fresh dataset
python generate_data.py --count 50 --output my_data.csv
```

---

## Setup — PostgreSQL (production)

```bash
# 1. Create the database
psql -U postgres -c "CREATE DATABASE cerdas_merata;"
psql -U postgres -d cerdas_merata -f db/schema.sql

# 2. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL or individual DB_* variables

# 3. Run
python app.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_SQLITE` | `0` | `1` = SQLite demo mode, `0` = PostgreSQL |
| `DATABASE_URL` | — | Full PostgreSQL connection string |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `cerdas_merata` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASS` | — | Database password |
| `ADMIN_ID` | `admin01` | Admin identifier (for audit logs) |
| `ADMIN_PASS` | `admin123` | Admin dashboard password |
| `PORT` | `5000` | Server port |
| `FLASK_DEBUG` | `1` | Flask debug mode |

---

## Running Tests

```bash
python -m pytest queue/test_queue.py reasoning/test_engine.py -v
```

---

## Scoring Rules Summary

| Category | Rules | Max Points |
|----------|-------|-----------|
| A — Poverty (income) | A1–A5 | 10 |
| B — Dependents | B1–B3 | 6 |
| C — Infrastructure (electricity) | C1–C7 | 11 |
| D — Social (parent status & occupation) | D1–D5 | 10 |
| E — Academic (GPA) | E1–E4, E5 (−8 deduction) | 5 |
| **Maximum** | | **45** |

Rules are defined in [`reasoning/rules.json`](reasoning/rules.json) and can be edited without touching Python code.

---

## Admin Dashboard

Access at `/admin`. Default password: `admin123` (change via `ADMIN_PASS`).

Key actions:
- **Set quota** — number of qualified slots (default 50)
- **Announce Results** — batch-assigns statuses; irreversible
- **Override** — force-change any applicant's status with a mandatory reason; includes disqualification
- **Trace** — view the full per-rule reasoning breakdown for any applicant
- **Export / Import CSV** — bulk data operations
- **Reset All** — clears all applications for demo use; preserves user accounts

---

## Ethical Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| Transparency | Full reasoning trace shown to applicant after announcement |
| Fairness | No demographic attributes (ethnicity, religion, gender) used |
| Privacy | Sensitive data auto-deleted 30 days after submission |
| Human oversight | Admin override on any decision with permanent audit record |
| Anomaly detection | 3 rules flag impossible data combinations for manual review |
| Audit trail | `rank_history` table records all rank changes with timestamp and admin ID |

---

## License

MIT
