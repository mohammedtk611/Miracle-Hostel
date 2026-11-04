"""
Automated Test Suite for Phase 8: Automated Data Retention and Deletion.
Validates the complete 30-day retention and cleanup lifecycle:
1. Resident leaving date is recorded.
2. Retention deadline is calculated correctly.
3. Residents within the retention period are preserved.
4. Expired residents are identified.
5. Active residents are never deleted.
6. Reactivated residents are not deleted.
7. Associated photographs are deleted (handling shared & missing files).
8. Eligible personal information is deleted.
9. Required financial records are preserved where applicable.
10. Deletion logs are generated without personal data leakage.
11. Repeated cleanup execution is safe and idempotent.
12. Failed storage deletion can be retried.
13. Branch records remain intact.
"""
import os
from datetime import date, timedelta
from decimal import Decimal
import pytest
from app import create_app
from app.extensions import db
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.resident_stay_history import ResidentStayHistory
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentMethod
from app.models.payment_obligation import PaymentObligation, ObligationType
from app.models.data_retention_log import DataRetentionLog, RetentionLogStatus
from app.services.retention_service import RetentionService
from app.services.storage_service import StorageService
from app.services.aadhaar_service import AadhaarSecurityService
from app.services.seed_service import seed_database_sample_data


@pytest.fixture
def app(tmp_path):
    """Create test application context with memory SQLite DB."""
    test_app = create_app('testing')
    test_app.config['PRIVATE_STORAGE_FOLDER'] = tmp_path / 'storage' / 'private' / 'residents'
    with test_app.app_context():
        db.create_all()
        admin = Admin(email="admin@123", username="admin", is_active=True)
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

        seed_database_sample_data(force=True)

        yield test_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Unauthenticated client fixture."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Authenticated administrator client fixture."""
    c = app.test_client()
    c.post('/auth/login', data={
        'email': 'admin@123',
        'password': '1234'
    }, follow_redirects=True)
    return c


# =========================================================================
# 1. RESIDENT LEAVING DATE IS RECORDED
# =========================================================================
def test_leaving_date_recorded_and_persisted(auth_client, app):
    """Verify that when a resident leaves, leaving date is recorded and persisted."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RET-TEST-001",
            full_name="Leaving Resident One",
            branch_id=branch.id,
            admission_date=date(2026, 9, 1),
            resident_status=ResidentStatus.ACTIVE
        )
        db.session.add(res)
        db.session.commit()
        res_code = res.resident_code
        res_id = res.id

    depart_date = date(2026, 10, 1)
    response = auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': depart_date.strftime('%Y-%m-%d')
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        updated = db.session.get(Resident, res_id)
        assert updated.resident_status == ResidentStatus.LEFT
        assert updated.leaving_date == depart_date


# =========================================================================
# 2. RETENTION DEADLINE IS CALCULATED CORRECTLY
# =========================================================================
def test_retention_deadline_calculated_correctly(app):
    """Verify retention deadline is mathematically leaving_date + 30 days."""
    with app.app_context():
        branch = Branch.query.first()
        leaving_dt = date(2026, 8, 15)
        res = Resident(
            resident_code="RET-TEST-002",
            full_name="Retention Math Resident",
            branch_id=branch.id,
            admission_date=date(2026, 7, 1),
            leaving_date=leaving_dt,
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()

        assert res.retention_deadline == leaving_dt + timedelta(days=30)
        assert res.retention_deadline == date(2026, 9, 14)


# =========================================================================
# 3. RESIDENTS WITHIN RETENTION PERIOD ARE PRESERVED
# =========================================================================
def test_residents_within_retention_period_are_preserved(app):
    """Residents who left within the 30-day window are NOT deleted."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        # Left 10 days ago (20 days remaining)
        res = Resident(
            resident_code="RET-SAFE-010",
            full_name="Preserved Safe Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=40),
            leaving_date=today - timedelta(days=10),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        assert not res.is_eligible_for_deletion
        assert res.remaining_retention_days == 20

        # Execute retention cleanup
        result = RetentionService.run_retention_cleanup()
        
        # Verify resident is still present in database
        check_res = db.session.get(Resident, res_id)
        assert check_res is not None
        assert check_res.resident_status == ResidentStatus.LEFT


# =========================================================================
# 4. EXPIRED RESIDENTS ARE IDENTIFIED
# =========================================================================
def test_expired_residents_are_identified(app):
    """Residents whose leaving date is >30 days ago are correctly identified as eligible."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        res_expired = Resident(
            resident_code="RET-EXP-035",
            full_name="Identified Expired Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=70),
            leaving_date=today - timedelta(days=35),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res_expired)
        db.session.commit()
        res_id = res_expired.id

        expired_list = RetentionService.get_expired_residents()
        expired_ids = [r.id for r in expired_list]
        assert res_id in expired_ids
        assert res_expired.is_eligible_for_deletion


# =========================================================================
# 5. ACTIVE RESIDENTS ARE NEVER DELETED
# =========================================================================
def test_active_residents_are_never_deleted(app):
    """Active residents admitted long ago are NEVER eligible or deleted."""
    with app.app_context():
        branch = Branch.query.first()
        res_active = Resident(
            resident_code="RET-ACT-100",
            full_name="Active Longtime Resident",
            branch_id=branch.id,
            admission_date=date(2025, 1, 1),
            resident_status=ResidentStatus.ACTIVE
        )
        db.session.add(res_active)
        db.session.commit()
        res_id = res_active.id

        assert not res_active.is_eligible_for_deletion

        # Run cleanup
        RetentionService.run_retention_cleanup()

        check_res = db.session.get(Resident, res_id)
        assert check_res is not None
        assert check_res.resident_status == ResidentStatus.ACTIVE


# =========================================================================
# 6. REACTIVATED RESIDENTS ARE NOT DELETED
# =========================================================================
def test_reactivated_residents_are_not_deleted(auth_client, app):
    """A departed resident who was reactivated has leaving_date cleared and is not deleted."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RET-REACT-01",
            full_name="Reactivated Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        code = res.resident_code
        res_id = res.id

    # Reactivate
    auth_client.post(f'/residents/{code}/reactivate', data={
        'new_admission_date': str(today),
        'notes': 'Re-enrolled resident'
    }, follow_redirects=True)

    with app.app_context():
        reactivated = db.session.get(Resident, res_id)
        assert reactivated.resident_status == ResidentStatus.ACTIVE
        assert reactivated.leaving_date is None
        assert not reactivated.is_eligible_for_deletion

    # Run cleanup
    RetentionService.run_retention_cleanup()

    with app.app_context():
        check_res = db.session.get(Resident, res_id)
        assert check_res is not None
        assert check_res.resident_status == ResidentStatus.ACTIVE


# =========================================================================
# 7. ASSOCIATED PHOTOGRAPHS ARE DELETED
# =========================================================================
def test_associated_photographs_are_deleted_from_storage(app):
    """Expired resident's private photograph and thumbnail are removed from disk."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        private_dir = StorageService.get_private_dir()
        dummy_filename = "res_test_phase8_del.jpg"
        dummy_thumbname = f"thumb_{dummy_filename}"
        
        main_path = private_dir / dummy_filename
        thumb_path = private_dir / dummy_thumbname

        with open(main_path, 'wb') as f:
            f.write(b"dummy_main_image_bytes")
        with open(thumb_path, 'wb') as f:
            f.write(b"dummy_thumb_image_bytes")

        assert main_path.exists()
        assert thumb_path.exists()

        res = Resident(
            resident_code="RET-PHOTO-DEL",
            full_name="Photo Deletion Resident",
            branch_id=branch.id,
            photograph_path=f"/residents/photo/{dummy_filename}",
            admission_date=today - timedelta(days=80),
            leaving_date=today - timedelta(days=40),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        # Run cleanup
        RetentionService.run_retention_cleanup()

        # Verify resident is deleted
        assert db.session.get(Resident, res_id) is None
        # Verify physical image files are deleted
        assert not main_path.exists()
        assert not thumb_path.exists()


def test_shared_photograph_with_active_resident_is_not_deleted(app):
    """If another active resident references the same photo, physical file is preserved."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        private_dir = StorageService.get_private_dir()
        shared_filename = "res_shared_active.jpg"
        main_path = private_dir / shared_filename

        with open(main_path, 'wb') as f:
            f.write(b"shared_active_image_bytes")

        # Expired resident
        r_exp = Resident(
            resident_code="RET-SHARED-EXP",
            full_name="Expired Shared Resident",
            branch_id=branch.id,
            photograph_path=f"/residents/photo/{shared_filename}",
            admission_date=today - timedelta(days=80),
            leaving_date=today - timedelta(days=40),
            resident_status=ResidentStatus.LEFT
        )
        # Active resident sharing same photo reference
        r_active = Resident(
            resident_code="RET-SHARED-ACT",
            full_name="Active Sharing Resident",
            branch_id=branch.id,
            photograph_path=f"/residents/photo/{shared_filename}",
            admission_date=today - timedelta(days=20),
            resident_status=ResidentStatus.ACTIVE
        )
        db.session.add_all([r_exp, r_active])
        db.session.commit()
        exp_id = r_exp.id

        RetentionService.run_retention_cleanup()

        # Expired resident is deleted
        assert db.session.get(Resident, exp_id) is None
        # But file on disk is preserved because r_active still references it
        assert main_path.exists()

        # Cleanup test file
        main_path.unlink(missing_ok=True)


# =========================================================================
# 8. ELIGIBLE PERSONAL INFORMATION IS DELETED
# =========================================================================
def test_eligible_personal_information_is_deleted(app):
    """Verify full name, Aadhaar encrypted data, room bed, and stay history are purged."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        enc_aadhaar = AadhaarSecurityService.encrypt_aadhaar("987654321098")
        res = Resident(
            resident_code="RET-PERS-001",
            full_name="Personal Info Test Resident",
            branch_id=branch.id,
            aadhaar_encrypted=enc_aadhaar,
            aadhaar_last_four="1098",
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        # Add stay cycle
        stay = ResidentStayHistory(
            resident_id=res_id,
            branch_id=branch.id,
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            stay_number=1,
            notes="Completed stay cycle"
        )
        db.session.add(stay)
        db.session.commit()

        # Execute cleanup
        RetentionService.run_retention_cleanup()

        # Resident row must no longer exist
        assert db.session.get(Resident, res_id) is None
        # Stay history row must no longer exist
        assert ResidentStayHistory.query.filter_by(resident_id=res_id).count() == 0


# =========================================================================
# 9. REQUIRED FINANCIAL RECORDS ARE PRESERVED
# =========================================================================
def test_required_financial_records_are_preserved_and_anonymized(app):
    """
    Statutory accounting requirement:
    Payments are NOT deleted when the resident is purged; resident_id becomes NULL,
    amount, date, method, transaction ref are preserved, and resident info is anonymized.
    """
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RET-FIN-001",
            full_name="Financial Ledger Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id
        code = res.resident_code

        # Add 2 payments
        p1 = Payment(
            resident_id=res_id,
            branch_id=branch.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=Decimal("12000.00"),
            payment_date=today - timedelta(days=90),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI-FIN-12000"
        )
        p2 = Payment(
            resident_id=res_id,
            branch_id=branch.id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=Decimal("8500.00"),
            payment_date=today - timedelta(days=60),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference="NEFT-FIN-8500"
        )
        db.session.add_all([p1, p2])
        db.session.commit()
        p1_id = p1.id
        p2_id = p2.id

        # Execute retention cleanup
        res_cleanup = RetentionService.run_retention_cleanup()
        assert res_cleanup['purged'] >= 1

        # 1. Resident record is deleted
        assert db.session.get(Resident, res_id) is None

        # 2. Both payments remain in the database intact!
        pay1 = db.session.get(Payment, p1_id)
        pay2 = db.session.get(Payment, p2_id)
        assert pay1 is not None
        assert pay2 is not None

        # 3. resident_id is now NULL (unlinked)
        assert pay1.resident_id is None
        assert pay2.resident_id is None

        # 4. Financial fields remain exact
        assert pay1.amount == Decimal("12000.00")
        assert pay1.transaction_reference == "UPI-FIN-12000"
        assert pay2.amount == Decimal("8500.00")
        assert pay2.transaction_reference == "NEFT-FIN-8500"

        # 5. Resident name rendered as placeholder
        assert pay1.resident_name == "[Deleted Resident]"
        assert "Purged" in pay1.resident_code or code in pay1.resident_code


# =========================================================================
# 10. DELETION LOGS ARE GENERATED
# =========================================================================
def test_deletion_logs_are_generated_without_personal_data(app):
    """Cleanup generates DataRetentionLog containing metrics without leaking personal data."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RET-LOG-001",
            full_name="Secret Identity Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()

        # Run cleanup
        result = RetentionService.run_retention_cleanup()
        assert result['status'] == RetentionLogStatus.SUCCESS

        # Retrieve log entry
        log = db.session.get(DataRetentionLog, result['log_id'])
        assert log is not None
        assert log.records_purged >= 1
        assert log.records_failed == 0
        assert log.status == RetentionLogStatus.SUCCESS

        # Verify no sensitive personal data leaked in log description
        assert "Secret Identity Resident" not in log.details
        assert "aadhaar" not in log.details.lower()
        assert "password" not in log.details.lower()


# =========================================================================
# 11. REPEATED CLEANUP EXECUTION IS SAFE (IDEMPOTENT)
# =========================================================================
def test_repeated_cleanup_execution_is_safe_and_idempotent(app):
    """Running cleanup twice consecutively causes no errors and logs NO_OP on the second run."""
    with app.app_context():
        # First execution (may purge any remaining expired)
        run1 = RetentionService.run_retention_cleanup()
        assert run1['status'] in (RetentionLogStatus.SUCCESS, RetentionLogStatus.NO_OP)

        # Immediate second execution (no candidates remaining)
        run2 = RetentionService.run_retention_cleanup()
        assert run2['status'] == RetentionLogStatus.NO_OP
        assert run2['purged'] == 0
        assert run2['failed'] == 0


# =========================================================================
# 12. FAILED STORAGE DELETION CAN BE RETRIED
# =========================================================================
def test_failed_storage_deletion_rolls_back_and_can_be_retried(app, monkeypatch):
    """When storage deletion fails, the database deletion rolls back and can be retried later."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RET-RETRY-01",
            full_name="Retryable Failure Resident",
            branch_id=branch.id,
            photograph_path="/residents/photo/res_mock_fail.jpg",
            admission_date=today - timedelta(days=90),
            leaving_date=today - timedelta(days=45),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        # 1. Simulate storage failure
        def mock_failing_delete(photo_path):
            raise IOError("Storage write locked or network timeout")

        monkeypatch.setattr(StorageService, "delete_photograph", mock_failing_delete)

        # Run cleanup
        result = RetentionService.run_retention_cleanup()
        assert result['failed'] >= 1
        assert "RET-RETRY-01" in result['failed_codes']

        # Verify resident record was ROLLED BACK and NOT deleted
        unpurged = db.session.get(Resident, res_id)
        assert unpurged is not None
        assert unpurged.resident_status == ResidentStatus.LEFT

        # 2. Fix the storage problem (restore original or working method)
        monkeypatch.undo()

        # Run cleanup again
        retry_result = RetentionService.run_retention_cleanup()
        assert retry_result['status'] == RetentionLogStatus.SUCCESS
        assert "RET-RETRY-01" in retry_result['purged_codes']

        # Verify resident is now successfully purged
        purged = db.session.get(Resident, res_id)
        assert purged is None


# =========================================================================
# 13. BRANCH RECORDS REMAIN INTACT
# =========================================================================
def test_branch_records_remain_completely_intact(app):
    """Branch records and statistics are never altered or deleted during retention cleanup."""
    with app.app_context():
        branches_before = Branch.query.all()
        branch_count_before = len(branches_before)
        branch_ids_before = [b.id for b in branches_before]

        # Run cleanup
        RetentionService.run_retention_cleanup()

        branches_after = Branch.query.all()
        branch_count_after = len(branches_after)
        branch_ids_after = [b.id for b in branches_after]

        assert branch_count_before == branch_count_after
        assert branch_ids_before == branch_ids_after
