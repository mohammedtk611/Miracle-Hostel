# Miracle Hostel Management Portal

**Miracle Hostel** is a secure, responsive, lightweight, and comprehensive hostel management application built with **Flask 3**, **PostgreSQL**, **SQLAlchemy 2**, **Jinja2**, and **Bootstrap 5**.

Designed for hostel administrators managing residents across multiple hostel branches with real-time occupancy metrics, automated 30-day retention policies, immutable financial ledgers, AES-256 encrypted Aadhaar governance, and permanent private cloud photograph storage via **Google Drive**.

---

## 🌟 Key Features

1. **Administrator Authentication & Security (Phase 3)**:
   - Single administrator account using **Argon2id** memory-hard cryptographic password hashing.
   - Brute-force sliding-window rate limiting (5 attempts per 15-minute window).
   - Session-scoped cookies (`SESSION_PERMANENT = False`, `HttpOnly`, `SameSite=Lax`, `Secure` in production).
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
   - Private photograph storage with Pillow downsampling (1000x1000 max), Lanczos compression (quality 85), and thumbnail generation (250x250).
   - Server-side search, filtering, and database pagination.

4. **Permanent Private Storage via Google Drive**:
   - Direct integration with Google Drive API v3 using dedicated OAuth 2.0 with offline refresh tokens.
   - Strictly private storage: files and folders are never shared publicly or redirected to public download links.
   - Images are streamed through Flask with `Cache-Control: private, max-age=3600` and `X-Content-Type-Options: nosniff`.
   - Unauthenticated requests are rejected.
   - Safe photo replacement: new photograph is uploaded and committed to the database before the obsolete image is purged.
   - Ephemeral disk resilience: zero dependency on local files on Render.

5. **Financial & Payment Management (Phase 6 & Quick Payment)**:
   - Tracks Security Deposits, Admission Rent, Monthly Rent, and Other Charges.
   - Supports multi-installment partial payments and real-time outstanding balance calculation.
   - Immutable transaction ledger—historical transactions are never overwritten.
   - Quick-edit payment status updates directly from the Resident Directory without full page reloads.

6. **Admission, Departure & Stay History (Phase 7)**:
   - Mark as `LEFT` workflow capturing departure dates and calculating retention deadlines.
   - Tracks distinct occupancy cycles through `ResidentStayHistory`.
   - Returning resident reactivation restoring `ACTIVE` status while preserving prior history.
   - Previous Residents directory with retention urgency indicators (`Safe`, `Approaching`, `Expired`).

7. **Automated 30-Day Data Retention & Deletion (Phase 8)**:
   - Mathematical 30-day retention deadline: $\text{leaving\_date} + 30\text{ days}$.
   - Automated CLI command: `flask cleanup-expired-residents`.
   - Purges personal records (name, encrypted Aadhaar, Google Drive photo files) for expired residents.
   - Statutory accounting preservation: unlinks `resident_id` (`NULL`) and preserves vouchers and payment records with anonymized references (`anonymized_resident_code`).
   - Safe to retry: if Google Drive deletion fails, resident deletion aborts so files are never orphaned.
   - Dedicated `DataRetentionLog` audit table.

8. **Quality Assurance, Optimization & Performance (Phase 9 & Render Prep)**:
   - **113 passing automated tests** across 10 test suites with 100% pass rate.
   - Eliminated N+1 query bottlenecks via SQLAlchemy `joinedload`.
   - PostgreSQL connection pooling with `pool_pre_ping=True`, `pool_recycle=300`, and configurable pool sizes.
   - Custom 404 and 500 error handlers preventing internal tracebacks from leaking.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.10+, Flask 3.0+
- **WSGI Production Server:** Gunicorn 21.2+
- **Database / ORM:** Supabase PostgreSQL (Production) / SQLite (Development) via SQLAlchemy 2.0 & Flask-SQLAlchemy 3.1
- **Cloud Storage:** Google Drive API v3 (`google-api-python-client`, `google-auth-oauthlib`)
- **Security & Cryptography:** `cryptography` (AES-256 GCM), `argon2-cffi` (Argon2id), `Flask-Login`, `Flask-WTF`
- **Image Processing:** `Pillow` (Lanczos resampling, JPEG optimization)
- **Frontend:** Jinja2, HTML5, CSS3, Vanilla JavaScript (ES6+), Bootstrap 5.3.3 & Bootstrap Icons
- **Testing:** `pytest` (113 automated tests)

---

## 🚀 Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/mohammedtk611/Miracle-Hostel.git
cd Miracle-Hostel
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv venv

# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Local Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
For local development, the default values in `.env` or development fallbacks will use SQLite (`miracle_hostel_dev.db`) and local private storage.

### 4. Initialize Database & Seed Development Data
```bash
# Initialize schema and seed demonstration branches & residents
python run.py init-db

# Or using Flask CLI:
flask --app run.py init-db
```

### 5. Start Development Server
```bash
python run.py
```
Open browser at `http://127.0.0.1:5000`.

**Local Development Admin Credentials:**
- **Email:** `admin@123`
- **Password:** `1234`

---

## 🌐 Production Deployment Guide (Render & Supabase)

### 1. GitHub Repository Preparation
Ensure your repository is up to date and pushed to GitHub:
```bash
git status
git add .
git commit -m "Production readiness for Render and Google Drive integration"
git push origin main
```
*Verify that `.env`, OAuth tokens, credentials, and cache folders are excluded by `.gitignore`.*

---

### 2. Supabase PostgreSQL Database Setup

1. Log in to [Supabase](https://supabase.com) and click **New Project**.
2. Set your Project Name (e.g. `miracle-hostel-db`), generate a strong database password, and select your preferred region (e.g. `ap-south-1` Mumbai or nearest).
3. Navigate to **Project Settings** -> **Database**.
4. Under **Connection string**, select **URI** (Session or Transaction pooler, port 5432 or 6543).
5. Copy the connection string. It will look like:
   ```
   postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
6. Replace `[YOUR-PASSWORD]` with your actual Supabase database password.
   *Note: If the URL starts with `postgres://`, Miracle Hostel automatically normalizes it to `postgresql://`.*

---

### 3. Google Cloud Project & Google Drive API Setup

Resident photographs are permanently stored in a dedicated Google Drive folder using a dedicated Google Account.

#### Step A: Create Google Cloud Project & Enable API
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `Miracle-Hostel-Storage`).
3. In the sidebar, go to **APIs & Services** -> **Library**.
4. Search for **Google Drive API** and click **Enable**.

#### Step B: Configure OAuth Consent Screen
1. Go to **APIs & Services** -> **OAuth consent screen**.
2. Select **External** and click **Create**.
3. Fill in:
   - **App name:** `Miracle Hostel Management`
   - **User support email:** Your administrator email
   - **Developer contact information:** Your administrator email
4. Click **Save and Continue**.
5. Under **Scopes**, click **Add or Remove Scopes**.
   - Add scope: `https://www.googleapis.com/auth/drive.file`
   *(This gives access only to files created by the application; it cannot view or modify other personal files in your Drive).*
6. Under **Test Users**, add the Google email address of the account that will hold the hostel photographs.
7. Click **Save and Continue**.
8. **CRITICAL STEP — Publishing Status:**
   - In **OAuth consent screen**, locate **Publishing status**.
   - Click **Publish App** to switch from **Testing** to **In Production**.
   > **IMPORTANT:** In "Testing" mode, Google automatically revokes refresh tokens after **7 days**, which would cause photo uploads to fail after a week! Setting the publishing status to **Production** ensures long-term, non-expiring refresh tokens.

#### Step C: Create OAuth 2.0 Client Credentials
1. Go to **APIs & Services** -> **Credentials**.
2. Click **Create Credentials** -> **OAuth client ID**.
3. Select **Application type:** `Desktop app` (or `Web application` with redirect URI `http://localhost:8080/`).
4. Name: `Miracle Hostel Local CLI`.
5. Click **Create**.
6. Copy the **Client ID** and **Client Secret**.

---

### 4. Generate Long-Term OAuth Refresh Token Locally

Miracle Hostel provides an interactive local utility to generate your refresh token in seconds without manual curl requests:

```bash
# On your local machine:
python scripts/google_drive_auth.py --client-id <YOUR_CLIENT_ID> --client-secret <YOUR_CLIENT_SECRET>
```

1. The script will open your browser and prompt you to sign in with your dedicated Google Account.
2. Grant permission for Miracle Hostel to manage files created by the application.
3. Upon approval, the terminal will print your **GOOGLE_DRIVE_REFRESH_TOKEN**.
4. Save this refresh token securely. Never commit it to GitHub.

---

### 5. (Optional) Create Dedicated Private Google Drive Folder

1. Open [Google Drive](https://drive.google.com/) signed in with the same account.
2. Create a folder named `Miracle Hostel Residents (Private)`.
3. Open the folder and look at the URL in your browser:
   `https://drive.google.com/drive/folders/1A2b3C4d5E6f7G8h9I0j`
4. The string after `/folders/` is your **GOOGLE_DRIVE_FOLDER_ID** (`1A2b3C4d5E6f7G8h9I0j`).
*(If omitted, the application will automatically search for or create this folder and log its ID).*

---

### 6. Render Web Service Deployment

1. Log in to [Render](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository `Miracle-Hostel`.
4. Configure service settings:
   - **Name:** `miracle-hostel`
   - **Region:** Frankfurt (EU Central) or Singapore / nearest to your Supabase region.
   - **Branch:** `main`
   - **Root Directory:** *(leave blank)*
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     gunicorn run:app --bind 0.0.0.0:$PORT
     ```
   - **Plan:** Free (or Starter for non-sleeping production).

---

### 7. Configure Render Environment Variables

In your Render dashboard, navigate to **Environment** -> **Add Environment Variable** and enter the following:

| Variable Name | Example / Description | Required? |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | **Yes** |
| `FLASK_DEBUG` | `false` | **Yes** |
| `SECRET_KEY` | *64-character random hex string* (`python -c "import secrets; print(secrets.token_hex(32))"`) | **Yes** |
| `DATABASE_URL` | `postgresql://postgres.<ref>:<pass>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require` | **Yes** |
| `AADHAAR_ENCRYPTION_KEY` | *32-character AES secret key* (`python -c "import secrets; print(secrets.token_hex(16))"`) | **Yes (Exactly 32 chars)** |
| `SESSION_COOKIE_SECURE` | `true` | **Yes** |
| `STORAGE_BACKEND` | `google_drive` | **Yes** |
| `GOOGLE_DRIVE_CLIENT_ID` | `<YOUR_GOOGLE_CLIENT_ID>` | **Yes** |
| `GOOGLE_DRIVE_CLIENT_SECRET` | `<YOUR_GOOGLE_CLIENT_SECRET>` | **Yes** |
| `GOOGLE_DRIVE_REFRESH_TOKEN` | `<YOUR_REFRESH_TOKEN_FROM_STEP_4>` | **Yes** |
| `GOOGLE_DRIVE_FOLDER_ID` | `<YOUR_FOLDER_ID_FROM_STEP_5>` | Optional (auto-created if empty) |
| `ADMIN_EMAIL` | `admin@miraclehostel.com` | **Yes** |
| `ADMIN_USERNAME` | `admin` | **Yes** |
| `ADMIN_DEFAULT_PASSWORD` | `<STRONG_PRODUCTION_PASSWORD>` | **Yes** |
| `RESIDENT_RETENTION_DAYS` | `30` | Optional (default 30) |

Click **Save Changes**. Render will automatically trigger a fresh deployment.

---

### 8. Production Database Initialisation & Admin Setup

Once Render finishes building and starts the Web Service, open the **Render Shell** tab (or connect via SSH) to initialize the database:

#### A. Initialize Database Schema (Tables Only, No Seed Data)
```bash
flask init-db
```
*In production (`FLASK_ENV=production`), `init-db` creates all tables and applies schema migrations safely without inserting any dummy demo residents or transactions!*

#### B. Create or Update Administrator Account
```bash
flask create-admin --email admin@miraclehostel.com --username admin --password "YourStrongPasswordHere!"
```

---

### 9. Verification & Testing

1. Open your live Render URL (e.g. `https://miracle-hostel.onrender.com`).
2. Log in using your configured administrator credentials.
3. **Branch Setup:** Add your hostel branch(es).
4. **Resident Registration with Photo:** Register a new resident and upload a test photograph.
5. **Verify Google Drive Storage:**
   - Open your Google Drive folder: confirm a new file named `res_<uuid>.jpg` and `thumb_res_<uuid>.jpg` appears.
   - Confirm the file is private (not shared publicly).
6. **Verify Photo Retrieval:**
   - View the resident profile in the portal: verify the photograph renders properly.
   - Inspect network request: confirm `/residents/photo/...` returns HTTP 200 with `Cache-Control: private, max-age=3600`.
   - Log out and attempt to visit the photo URL directly in an incognito window: verify you are redirected to `/auth/login`.

---

### 10. Automated 30-Day Retention Cleanup (Render Cron Job)

Render Web Services do not have built-in system crontab, but Render provides **Cron Jobs**:

1. In Render Dashboard, click **New +** -> **Cron Job**.
2. Connect the `Miracle-Hostel` repository.
3. Set **Schedule:** `0 2 * * *` (Runs every night at 2:00 AM UTC).
4. Set **Command:**
   ```bash
   flask cleanup-expired-residents
   ```
5. Attach the same Environment Group or copy the same environment variables (`DATABASE_URL`, `SECRET_KEY`, `AADHAAR_ENCRYPTION_KEY`, `GOOGLE_DRIVE_*`).

When this runs, any departed resident who left $\ge 30$ days ago will have their Google Drive photograph permanently deleted, their personal record purged, and their vouchers safely anonymized in the financial ledger.

---

### 11. Understanding Render's Free Tier & Ephemeral Filesystem

> [!WARNING] **Render Free Tier Characteristics:**
> 1. **Inactivity Spin-Down:** On the free plan, Render spins down the Web Service container after 15 minutes of inactivity. When a new request arrives, there may be a 30 to 50 second cold start delay. Upgrading to a paid instance ($7/month) eliminates spin-down.
> 2. **Ephemeral Local Filesystem:** Render containers are ephemeral. Every time the application restarts, crashes, or redeploys, all local files are discarded.
> 3. **Why Google Drive is Mandatory:** Because of the ephemeral filesystem, storing resident photos on local disk (`storage/private/residents`) in production would result in lost photos upon container restart. With `STORAGE_BACKEND=google_drive`, resident photos are permanently preserved in Google Drive across all deploys.

---

### 12. Backup, Restoration & Disaster Recovery

#### PostgreSQL (Supabase) Database Backup:
- **Automated Backups:** Supabase automatically performs daily database backups.
- **Manual Backup:** Export complete SQL dump via `pg_dump`:
  ```bash
  pg_dump "postgresql://postgres.<ref>:<pass>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require" -F c -b -v -f miracle_backup_$(date +%Y%m%d).dump
  ```
- **Restore:**
  ```bash
  pg_restore -d "postgresql://..." --clean --if-exists miracle_backup_20261104.dump
  ```

#### Google Drive Photograph Backup:
- In Google Drive, select the `Miracle Hostel Residents (Private)` folder -> click **Download**.
- Google Drive automatically packages all resident photographs and thumbnails into a single `.zip` archive.

---

### 13. Troubleshooting & FAQ

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `ValueError: SECRET_KEY must be set...` | Missing or default secret key in production | Generate a 64-char hex key and set `SECRET_KEY` in Render env. |
| `ValueError: SQLite is not permitted...` | `DATABASE_URL` is empty or points to SQLite | Set `DATABASE_URL` with your Supabase PostgreSQL connection string. |
| `Google Drive delete failed: 403 Forbidden` | OAuth scope mismatch or token revoked | Re-run `python scripts/google_drive_auth.py` and ensure scope `https://www.googleapis.com/auth/drive.file`. |
| Google Drive token expires after 7 days | OAuth consent screen is still in **Testing** mode | Go to Google Cloud Console -> OAuth consent screen -> Click **Publish App** to switch to **Production**. |
| Resident photo shows default avatar | Photo deleted from Drive or file ID mismatch | Inspect browser network tab. If Drive returns 404, application safely displays default avatar without crashing. |
| Supabase connection timeout | Port 5432 blocked or firewall latency | In Supabase, use the **Connection Pooler** URI on port `6543`. |

---

## 🧪 Automated Testing

Execute the complete test suite (113 automated tests):
```bash
python -m pytest tests/ -v
```

Test coverage includes:
- `test_google_drive_storage.py` (Google Drive OAuth, upload, thumbnail rollback, streaming, 404 fallback, retention cleanup, production config validation)
- `test_portal.py` (Authentication & Security)
- `test_phase4_branches.py` (Branch Lifecycle & Constraints)
- `test_phase5_residents.py` (Resident Registration & ID Generation)
- `test_aadhaar_display.py` (AES-256 Aadhaar Governance & Profile Display)
- `test_quick_payment.py` (Directory Quick Payment Status Updates)
- `test_phase6_financial.py` (Ledgers, Payments & Balances)
- `test_phase7_admission_departure.py` (Admission, Departure & Stay History)
- `test_phase8_data_retention.py` (Automated 30-Day Data Retention & Purge)
- `test_phase9_qa_optimization.py` (QA, Error Handlers & Query Optimization)

---

## 📄 License

Proprietary — Developed for Miracle Hostel Management. All rights reserved.
