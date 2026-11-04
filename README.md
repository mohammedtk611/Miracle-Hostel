# Miracle Hostel Management Portal

**Miracle Hostel** is a secure, responsive, lightweight, and comprehensive hostel management application built with **Flask**, **PostgreSQL**, **SQLAlchemy**, **Jinja2**, and **Bootstrap 5**.

Designed specifically for hostel administrators managing residents across multiple hostel branches with real-time occupancy metrics, automated 30-day retention policies, immutable financial ledgers, and AES-256 encrypted Aadhaar governance.

---

## 🌟 Key Features

1. **Administrator Authentication & Security (Phase 3)**:
   - Single administrator account using **Argon2id** memory-hard cryptographic password hashing.
   - Brute-force sliding-window rate limiting (5 attempts per 15-minute window).
   - Session-scoped cookies (`SESSION_PERMANENT = False`, `HttpOnly`, `SameSite=Lax`).
   - CSRF protection across all forms and state-changing requests via `Flask-WTF`.
   - Comprehensive audit logging without leaking sensitive passwords, tokens, or Aadhaar numbers.

2. **Branch Management (Phase 4)**:
   - Full branch lifecycle (Add, Edit, Activate, Deactivate).
   - Unique case-insensitive branch codes (`func.lower(branch_code)`).
   - Deactivation protection: prevents deactivating branches with active residents.
   - Preserves historical records and transactions for deactivated branches.
   - Global consolidated and branch-specific reporting.

3. **Resident Management & Aadhaar Security (Phase 5 & Aadhaar Policy)**:
   - Automatic unique resident ID generation (`MHL-YYYY-SEQ`).
   - Strict AES-256 GCM authenticated encryption at rest for 12-digit Aadhaar numbers.
   - Masked display (`XXXX-XXXX-1234`) on directory tables; full Aadhaar revealed only on authenticated individual profiles.
   - Private photograph storage outside `app/static/` with Pillow downsampling, Lanczos compression, and thumbnail generation.
   - Server-side search, filtering, and database pagination.

4. **Financial & Payment Management (Phase 6 & Quick Payment)**:
   - Tracks Security Deposits, Admission Rent, Monthly Rent, and Other Charges.
   - Supports multi-installment partial payments and real-time outstanding balance calculation.
   - Immutable transaction ledger—historical transactions are never overwritten.
   - Quick-edit payment status updates directly from the Resident Directory without full page reloads.

5. **Admission, Departure & Stay History (Phase 7)**:
   - Mark as `LEFT` workflow capturing departure dates and calculating retention deadlines.
   - Tracks distinct occupancy cycles through `ResidentStayHistory`.
   - Returning resident reactivation restoring `ACTIVE` status while preserving prior history.
   - Previous Residents directory with retention urgency indicators (`Safe`, `Approaching`, `Expired`).

6. **Automated 30-Day Data Retention & Deletion (Phase 8)**:
   - Mathematical 30-day retention deadline: $\text{leaving\_date} + 30\text{ days}$.
   - Automated CLI command: `flask cleanup-expired-residents`.
   - Purges personal records (name, encrypted Aadhaar, photo files) for expired residents.
   - Statutory accounting preservation: unlinks `resident_id` (`NULL`) and preserves vouchers and payment records with anonymized references (`anonymized_resident_code`).
   - Dedicated `DataRetentionLog` audit table.

7. **Quality Assurance, Optimization & Performance (Phase 9)**:
   - 97 passing automated tests across 9 comprehensive test suites.
   - Eliminated N+1 query bottlenecks via SQLAlchemy `joinedload`.
   - Custom 404 and 500 error handlers preventing internal tracebacks from leaking.
   - Optimized database indexes on all high-frequency query columns.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.10+, Flask 3.0+
- **Database / ORM:** PostgreSQL / SQLite (Development) via SQLAlchemy 2.0 & Flask-SQLAlchemy 3.1
- **Security & Cryptography:** `cryptography` (AES-256 GCM), `argon2-cffi` (Argon2id), `Flask-Login`, `Flask-WTF`
- **Image Processing:** `Pillow` (Lanczos resampling, JPEG optimization)
- **Frontend:** Jinja2, HTML5, CSS3, Vanilla JavaScript (ES6+), Bootstrap 5.3.3 & Bootstrap Icons
- **Testing:** `pytest` (97 automated tests)

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/mohammedtk611/Miracle-Hostel.git
cd Miracle-Hostel
```

### 2. Set Up Virtual Environment & Dependencies
```bash
# Create and activate virtual environment
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```
Ensure `SECRET_KEY`, `AADHAAR_ENCRYPTION_KEY` (32 characters), and `DATABASE_URL` are configured.

### 4. Initialize Database & Seed Sample Data
```bash
# Initialize schema and seed demonstration branches & residents
python run.py init-db

# Or using Flask CLI:
flask --app run.py init-db
```

### 5. Run the Application
```bash
python run.py
```
Open your browser at `http://127.0.0.1:5000`.

**Default Administrator Credentials:**
- **Email:** `admin@123`
- **Password:** `1234`

---

## ⚙️ Automated Retention Cleanup CLI

To manually trigger or test the 30-day retention cleanup:
```bash
flask --app run.py cleanup-expired-residents

# Or override retention threshold:
flask --app run.py cleanup-expired-residents --days 30
```

### Production Daily Cron Job
Add to production crontab (`crontab -e`):
```cron
0 2 * * * cd /opt/miracle-hostel && /opt/miracle-hostel/venv/bin/flask --app run.py cleanup-expired-residents >> /var/log/miracle_cleanup.log 2>&1
```

---

## 🧪 Running the Test Suite

Execute all 97 automated tests with pytest:
```bash
python -m pytest tests/ -v
```

All 9 test suites will run:
- `test_portal.py` (Authentication & Security)
- `test_phase4_branches.py` (Branch Management)
- `test_phase5_residents.py` (Resident Management)
- `test_aadhaar_display.py` (Aadhaar Policy)
- `test_quick_payment.py` (Quick Payment Status Editing)
- `test_phase6_financial.py` (Financial & Payment Engine)
- `test_phase7_admission_departure.py` (Admission & Departure Lifecycle)
- `test_phase8_data_retention.py` (30-Day Retention & Deletion)
- `test_phase9_qa_optimization.py` (QA, 404/500 Handlers & Performance)

---

## 📄 License

Proprietary — Developed for Miracle Hostel Management. All rights reserved.
