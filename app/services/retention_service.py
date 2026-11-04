"""
Retention Service for Miracle Hostel Management Portal.
Automates 30-day resident data retention and permanent deletion.
Ensures:
- Residents with status LEFT whose 30-day retention deadline has passed are eligible.
- Active and reactivated residents are NEVER deleted.
- Associated photographs are deleted from private storage (avoiding active residents' files).
- Personal identifiers (full name, Aadhaar numbers, profile details, stay history) are permanently purged.
- Statutory financial records (payments, transaction vouchers, amounts, methods) are preserved and anonymized.
- Branch records are never touched.
- Deletion logs record execution metadata without leaking deleted personal information.
- All operations are idempotent, safe to repeat, and failures are retryable.
"""
from datetime import date, datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.resident import Resident, ResidentStatus
from app.models.payment import Payment
from app.models.data_retention_log import DataRetentionLog, RetentionLogStatus
from app.services.storage_service import StorageService


class RetentionService:
    """Service encapsulating 30-day retention policies, identification, and permanent purging."""

    @classmethod
    def get_retention_days(cls) -> int:
        """Configured retention period in days (default: 30 days)."""
        try:
            return current_app.config.get('RESIDENT_RETENTION_DAYS', 30)
        except RuntimeError:
            return 30

    @classmethod
    def get_expired_residents(cls, cutoff_date: date = None) -> list[Resident]:
        """
        Identify residents eligible for permanent deletion under the retention rule:
        1. Status must be LEFT.
        2. Must have a valid leaving_date.
        3. Leaving date must be <= (today - 30 days), meaning the 30-day retention period has elapsed.
        4. Must NOT have been reactivated (status must remain LEFT).
        """
        if cutoff_date is None:
            retention_days = cls.get_retention_days()
            cutoff_date = date.today() - timedelta(days=retention_days)

        # Query only residents with status LEFT and leaving_date <= cutoff_date
        candidates = Resident.query.filter(
            Resident.resident_status == ResidentStatus.LEFT,
            Resident.leaving_date.isnot(None),
            Resident.leaving_date <= cutoff_date
        ).order_by(Resident.leaving_date.asc()).all()

        # Double check using the model's dynamic property
        eligible = [
            r for r in candidates 
            if r.resident_status == ResidentStatus.LEFT and r.is_eligible_for_deletion
        ]
        return eligible

    @classmethod
    def purge_resident(cls, resident_id: int) -> str:
        """
        Permanently delete an eligible expired resident while preserving required financial records.
        
        Steps:
        1. Strict validation (must be LEFT and expired).
        2. Delete associated photograph from storage (unless used by another resident or default avatar).
        3. Anonymize and preserve financial transactions (payments):
           - Sets resident_id = NULL
           - Preserves anonymized_resident_code, amount, date, method, transaction reference, branch_id
           - Appends audit notice to notes
        4. Delete non-statutory obligations and stay history.
        5. Permanently remove the Resident row (erasing name, Aadhaar, room, dates).
        6. Commit database transaction.

        Returns:
            The anonymized resident_code string for logging.
        """
        resident = db.session.get(Resident, resident_id)
        if not resident:
            raise ValueError(f"Resident #{resident_id} not found.")

        # Strict eligibility verification
        if resident.resident_status != ResidentStatus.LEFT:
            raise ValueError(
                f"Resident '{resident.resident_code}' cannot be deleted: Status is '{resident.resident_status}', not 'LEFT'."
            )

        if not resident.is_eligible_for_deletion:
            raise ValueError(
                f"Resident '{resident.resident_code}' cannot be deleted: Retention deadline has not passed yet."
            )

        resident_code = resident.resident_code
        photo_path = resident.photograph_path

        # ---------------------------------------------------------------------
        # 1. Photograph Deletion
        # ---------------------------------------------------------------------
        if photo_path and '/residents/photo/' in photo_path:
            # Check if any OTHER resident references this identical photo file
            other_ref = Resident.query.filter(
                Resident.id != resident.id,
                Resident.photograph_path == photo_path
            ).first()

            if not other_ref:
                try:
                    StorageService.delete_photograph(photo_path)
                except Exception as e:
                    # Critical storage failure: abort database deletion so file isn't orphaned
                    raise RuntimeError(f"Storage deletion failed for '{resident_code}': {str(e)}")

        # ---------------------------------------------------------------------
        # 2. Financial Record Preservation & Anonymization
        # ---------------------------------------------------------------------
        # Unlink payments from resident so they are preserved in accounting ledgers
        payments = resident.payments.all()
        for p in payments:
            p.resident_id = None
            if not p.anonymized_resident_code:
                p.anonymized_resident_code = f"{resident_code} (Purged)"
            
            anonymize_notice = "[Retained financial record: Resident personal data purged under 30-day retention policy]"
            if anonymize_notice not in (p.notes or ''):
                p.notes = f"{p.notes or ''} {anonymize_notice}".strip()

        db.session.flush()

        # ---------------------------------------------------------------------
        # 3. Obligations and Stay History Deletion
        # ---------------------------------------------------------------------
        for ob in resident.obligations.all():
            db.session.delete(ob)

        for sh in resident.stay_history.all():
            db.session.delete(sh)

        db.session.flush()

        # ---------------------------------------------------------------------
        # 4. Permanent Personal Record Deletion
        # ---------------------------------------------------------------------
        db.session.delete(resident)
        db.session.commit()

        return resident_code

    @classmethod
    def run_retention_cleanup(cls, retention_days: int = None, force: bool = False) -> dict:
        """
        Execute automated 30-day data retention cleanup.
        Safe to run repeatedly (idempotent).
        Performs per-resident transaction isolation to ensure failed deletions
        do not block other records and remain retryable.

        Returns:
            Dict containing cleanup summary metrics and execution log id.
        """
        if retention_days is not None:
            cutoff = date.today() - timedelta(days=retention_days)
        else:
            cutoff = None

        expired_residents = cls.get_expired_residents(cutoff_date=cutoff)
        total_identified = len(expired_residents)

        if total_identified == 0:
            # Record NO_OP log
            log = DataRetentionLog(
                records_identified=0,
                records_purged=0,
                records_failed=0,
                status=RetentionLogStatus.NO_OP,
                details="Automated retention cleanup ran: 0 expired resident records eligible for deletion."
            )
            db.session.add(log)
            db.session.commit()
            return {
                'identified': 0,
                'purged': 0,
                'failed': 0,
                'purged_codes': [],
                'failed_codes': [],
                'status': RetentionLogStatus.NO_OP,
                'log_id': log.id,
                'message': "Data retention cleanup completed: 0 expired records eligible."
            }

        purged_codes = []
        failed_codes = []
        failure_messages = []

        for resident in expired_residents:
            res_id = resident.id
            res_code = resident.resident_code
            try:
                # Purge individual resident with its own committed transaction
                purged_code = cls.purge_resident(res_id)
                purged_codes.append(purged_code)
            except Exception as e:
                db.session.rollback()
                failed_codes.append(res_code)
                failure_messages.append(f"{res_code}: {str(e)}")

        # Determine overall execution status
        if len(failed_codes) == 0:
            status = RetentionLogStatus.SUCCESS
        elif len(purged_codes) > 0:
            status = RetentionLogStatus.PARTIAL
        else:
            status = RetentionLogStatus.FAILED

        # Build log summary (without retaining any deleted names, Aadhaar, or photos)
        summary_details = (
            f"Automated retention cleanup processed {total_identified} records: "
            f"{len(purged_codes)} successfully purged [{', '.join(purged_codes)}], "
            f"{len(failed_codes)} failed."
        )

        log = DataRetentionLog(
            records_identified=total_identified,
            records_purged=len(purged_codes),
            records_failed=len(failed_codes),
            status=status,
            details=summary_details,
            failure_reason="; ".join(failure_messages) if failure_messages else None
        )
        db.session.add(log)
        db.session.commit()

        return {
            'identified': total_identified,
            'purged': len(purged_codes),
            'failed': len(failed_codes),
            'purged_codes': purged_codes,
            'failed_codes': failed_codes,
            'status': status,
            'log_id': log.id,
            'message': (
                f"Data retention cleanup completed: {len(purged_codes)} expired resident(s) purged, "
                f"{len(failed_codes)} failed."
            )
        }

