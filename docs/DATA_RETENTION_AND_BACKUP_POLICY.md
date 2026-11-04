# Miracle Hostel Management Portal
## Data Retention, Automated Cleanup & Backup Policy

This document defines the 30-day automated data retention architecture, statutory financial preservation rules, live deletion behavior, and historical backup expiration lifecycle for the Miracle Hostel Management Portal.

---

### 1. The 30-Day Retention Rule

In compliance with data minimization and personal data privacy requirements (such as the Digital Personal Data Protection Act / DPDP and standard hospitality privacy practices):

1. **Departure Transition**:
   * When a resident vacates the hostel, their administrative status is transitioned to `LEFT`.
   * The actual departure date (`leaving_date`) is recorded.
   * The system mathematically calculates the **30-day retention deadline**:
     $$\text{retention\_deadline} = \text{leaving\_date} + 30\text{ calendar days}$$
2. **Retention Period Access**:
   * During the active 30-day retention window, the resident's historical records, photographs, and payment ledgers remain accessible under the **Previous Residents** directory (`/residents/previous`).
   * The administrator can review unsettled dues or reactivate returning residents.
   * Editing unrelated resident information never resets the retention deadline.
3. **Permanent Deletion Eligibility**:
   * Once $\text{today} \ge \text{retention\_deadline}$, the resident is classified as `Eligible for Deletion`.
   * Active residents and reactivated residents **never** qualify for deletion.

---

### 2. Live Database Deletion & Financial Ledger Preservation

#### What is Permanently Purged from Live Storage
When the cleanup process executes, the following resident personal information is permanently destroyed:
* **Resident Identity Record**: Full name, room number, bed allocation, admission/leaving dates.
* **Aadhaar Data**: The AES-256 GCM encrypted ciphertext and masked 4-digit display fields are permanently wiped.
* **Photographs**: Resident photograph and thumbnail image files stored in the private directory (`storage/private/residents/`) or Amazon S3 object storage are unlinked and permanently deleted. (Photographs referenced by other residents or default avatars are protected).
* **Stay Cycles & Obligations**: Internal billing expectations and stay cycle history records are permanently deleted.

#### Statutory Financial Record Preservation
Under applicable tax laws and accounting standards (e.g., Income Tax Act, Companies Act, GST):
* Monetary transactions, payment receipts, vouchers, and accounting records must be retained for statutory audits and tax filing (7–8 years).
* **Anonymization Technique**:
  * Financial transactions in the `payments` table are **never deleted**.
  * The direct personal foreign key (`resident_id`) is set to `NULL` (`ON DELETE SET NULL`).
  * The payment amount, payment date, payment category, payment method, transaction reference, and hostel branch association are preserved 100% intact.
  * Personal identifiers are replaced with an anonymized reference (`anonymized_resident_code`, e.g., `MHL-2024-001 (Purged)`), ensuring that auditing balances and revenue metrics remain completely accurate without exposing deleted personal data or Aadhaar identifiers.

---

### 3. Deletion Logs & Audit Governance

Every retention cleanup execution records a summary entry in the `data_retention_logs` table:
* **Execution Timestamp**: Date and time of the cleanup run.
* **Record Counts**: Records identified, successfully purged, and failed.
* **Execution Status**: `SUCCESS`, `PARTIAL`, `NO_OP`, or `FAILED`.
* **Details**: Non-sensitive summary (e.g., `"Automated retention cleanup processed 2 records: 2 successfully purged [MHL-2024-001, MHL-2024-002], 0 failed."`).
* **Privacy Safeguard**: The deletion log strictly prohibits recording the resident's full name, Aadhaar number, photograph, or personal contact info.

---

### 4. Live Deletion vs. Historical Backup Expiration

> [!IMPORTANT]
> **Live Database Deletion vs. Historical Backups**:
> Executing `flask cleanup-expired-residents` immediately and permanently erases personal data from the **live PostgreSQL database** and active file system.
> However, data is **not** instantaneously erased from pre-existing immutable database backups or snapshot archives created prior to the deletion event.

#### Backup Rotation Schedule & Expiration Window
To ensure complete data lifecycle compliance:
1. **Daily Incremental Backups**:
   * Stored in encrypted private storage.
   * Retained for **14 calendar days**, after which they are automatically rotated and overwritten.
2. **Weekly Full Backups**:
   * Retained for **30 calendar days**, then permanently purged.
3. **End-to-End Erasure Guarantee**:
   * Any personal data deleted from the live system will completely and irreversibly age out of all historical backup archives within **30 days** of live deletion.
   * If a disaster recovery restoration is ever performed from an older backup, the daily cleanup command automatically identifies and re-purges any expired records.

---

### 5. Production Scheduling via Cron

The cleanup job does not require persistent background workers like Celery or Redis. It is designed to be executed via standard system `cron` once daily during off-peak hours.

#### Linux / Production Server Setup (`crontab -e`):
```cron
# Miracle Hostel: Run automated 30-day resident data retention cleanup every morning at 2:00 AM UTC
0 2 * * * cd /opt/miracle-hostel && /opt/miracle-hostel/venv/bin/flask --app run.py cleanup-expired-residents >> /var/log/miracle_retention_cleanup.log 2>&1
```

#### Manual Administrator Execution:
Operators can also execute the cleanup command on demand at any time from the project root:
```bash
# Using Flask CLI
flask --app run.py cleanup-expired-residents

# Using Application Entry Point
python run.py cleanup-expired-residents
```
Both commands are fully idempotent and safe to run repeatedly.

