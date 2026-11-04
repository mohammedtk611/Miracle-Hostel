"""
Test Suite for Miracle Hostel Management Portal - Phase 7 Admission & Departure Management.
Covers Section 10 test specifications:
1. test_register_new_resident_appears_in_active
2. test_mark_resident_as_left
3. test_marked_left_resident_disappears_from_active_directory
4. test_marked_left_resident_appears_in_previous_residents
5. test_verify_leaving_date_and_validation
6. test_verify_30_day_retention_deadline
7. test_verify_remaining_retention_days
8. test_verify_payment_history_remains_intact_after_departure
9. test_verify_outstanding_balances_remain_intact_and_highlighted
10. test_previous_residents_branch_filtering
11. test_reactivate_returning_resident
12. test_verify_previous_admission_and_departure_history_preserved
13. test_dashboard_statistics_reflect_active_and_previous
14. test_unauthorized_users_blocked_from_departure_and_reactivation
"""
import pytest
from datetime import date, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, PaymentObligation, ResidentStayHistory,
    ResidentStatus, PaymentType, PaymentStatus, PaymentMethod, ObligationType, AuditLog, AuditAction
)
from app.services.seed_service import seed_database_sample_data
from app.services.financial_service import FinancialService
from app.services.dashboard_service import DashboardService


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
# 1. REGISTER NEW RESIDENT APPEARS IN ACTIVE DIRECTORY
# =========================================================================
def test_register_new_resident_appears_in_active(auth_client, app):
    """Newly registered resident has ACTIVE status and appears in Active Residents."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        b_id = branch.id

    reg_res = auth_client.post('/residents/add', data={
        'full_name': 'Lifecycle Test Resident',
        'branch_id': b_id,
        'admission_date': '2026-11-01',
        'security_deposit': '12000',
        'deposit_status': 'PAID',
        'monthly_rent': '8500',
        'rent_status': 'PAID',
        'payment_method': 'UPI'
    }, follow_redirects=True)
    assert reg_res.status_code == 200

    with app.app_context():
        resident = Resident.query.filter_by(full_name='Lifecycle Test Resident').first()
        assert resident is not None
        assert resident.resident_status == ResidentStatus.ACTIVE
        assert resident.leaving_date is None
        code = resident.resident_code

    # Check Active Directory
    dir_res = auth_client.get('/residents')
    assert dir_res.status_code == 200
    assert code.encode() in dir_res.data
    assert b"Lifecycle Test Resident" in dir_res.data


# =========================================================================
# 2. MARK RESIDENT AS LEFT
# =========================================================================
def test_mark_resident_as_left(auth_client, app):
    """Mark an active resident as LEFT, saving leaving date and creating stay history."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = resident.resident_code
        res_id = resident.id
        adm_date = resident.admission_date

    leaving_date_str = str(date.today())
    dep_res = auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': leaving_date_str,
        'notes': 'Completed internship tenure.'
    }, follow_redirects=True)
    assert dep_res.status_code == 200

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        assert updated_res.resident_status == ResidentStatus.LEFT
        assert str(updated_res.leaving_date) == leaving_date_str

        # Verify stay history created
        stay = updated_res.stay_history.first()
        assert stay is not None
        assert stay.admission_date == adm_date
        assert str(stay.leaving_date) == leaving_date_str

        # Verify audit log
        audit = AuditLog.query.filter_by(
            action=AuditAction.RESIDENT_DEPARTURE,
            entity_id=res_id
        ).first()
        assert audit is not None
        assert "marked as LEFT" in audit.description


# =========================================================================
# 3. MARKED LEFT RESIDENT DISAPPEARS FROM ACTIVE DIRECTORY
# =========================================================================
def test_marked_left_resident_disappears_from_active_directory(auth_client, app):
    """Departed resident is removed from Active Residents directory view."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = resident.resident_code

    # Depart
    auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': str(date.today())
    }, follow_redirects=True)

    # Active directory check (status defaults to ACTIVE)
    active_dir = auth_client.get('/residents?status=ACTIVE')
    assert res_code.encode() not in active_dir.data


# =========================================================================
# 4. MARKED LEFT RESIDENT APPEARS IN PREVIOUS RESIDENTS
# =========================================================================
def test_marked_left_resident_appears_in_previous_residents(auth_client, app):
    """Departed resident appears in the Previous Residents directory."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = resident.resident_code
        res_name = resident.full_name

    # Depart
    auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': str(date.today())
    }, follow_redirects=True)

    prev_res = auth_client.get(f'/residents/previous?search={res_code}')
    assert prev_res.status_code == 200
    assert res_code.encode() in prev_res.data
    assert res_name.encode() in prev_res.data


# =========================================================================
# 5. VERIFY LEAVING DATE AND VALIDATION
# =========================================================================
def test_verify_leaving_date_and_validation(auth_client, app):
    """Leaving date cannot be earlier than admission date and duplicate departure is blocked."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = resident.resident_code
        adm_date = resident.admission_date

    # 1. Invalid date (earlier than admission date)
    earlier_date = adm_date - timedelta(days=10)
    err_res = auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': earlier_date.strftime('%Y-%m-%d')
    }, follow_redirects=True)
    assert b"cannot be earlier than admission date" in err_res.data

    # Verify resident remains ACTIVE
    with app.app_context():
        r = Resident.query.filter_by(resident_code=res_code).first()
        assert r.resident_status == ResidentStatus.ACTIVE

    # 2. Valid departure
    valid_dep = auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': str(date.today())
    }, follow_redirects=True)
    assert valid_dep.status_code == 200

    # 3. Duplicate departure submission should be prevented
    dup_res = auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': str(date.today())
    }, follow_redirects=True)
    assert b"already marked as departed" in dup_res.data


# =========================================================================
# 6. VERIFY 30-DAY RETENTION DEADLINE
# =========================================================================
def test_verify_30_day_retention_deadline(auth_client, app):
    """Verify retention deadline is mathematically leaving_date + 30 days."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = resident.resident_code
        res_id = resident.id

    leaving_dt = date(2026, 11, 4)
    auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': '2026-11-04'
    }, follow_redirects=True)

    with app.app_context():
        r = db.session.get(Resident, res_id)
        assert r.retention_deadline == date(2026, 11, 4) + timedelta(days=30)
        assert r.retention_deadline == date(2026, 12, 4)


# =========================================================================
# 7. VERIFY REMAINING RETENTION DAYS
# =========================================================================
def test_verify_remaining_retention_days(app):
    """Verify dynamic remaining retention days and urgency levels."""
    today = date.today()
    with app.app_context():
        branch = Branch.query.first()

        # Resident left 10 days ago -> 20 days remaining (safe/normal)
        r_safe = Resident(
            resident_code="RET-SAFE-01",
            full_name="Safe Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=50),
            leaving_date=today - timedelta(days=10),
            resident_status=ResidentStatus.LEFT
        )
        # Resident left 25 days ago -> 5 days remaining (approaching)
        r_app = Resident(
            resident_code="RET-APP-01",
            full_name="Approaching Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=50),
            leaving_date=today - timedelta(days=25),
            resident_status=ResidentStatus.LEFT
        )
        # Resident left 35 days ago -> -5 days remaining (expired)
        r_exp = Resident(
            resident_code="RET-EXP-01",
            full_name="Expired Resident",
            branch_id=branch.id,
            admission_date=today - timedelta(days=70),
            leaving_date=today - timedelta(days=35),
            resident_status=ResidentStatus.LEFT
        )
        db.session.add_all([r_safe, r_app, r_exp])
        db.session.commit()

        assert r_safe.remaining_retention_days == 20
        assert r_safe.retention['urgency'] == 'normal'
        assert not r_safe.is_eligible_for_deletion

        assert r_app.remaining_retention_days == 5
        assert r_app.retention['urgency'] == 'approaching'
        assert not r_app.is_eligible_for_deletion

        assert r_exp.remaining_retention_days == -5
        assert r_exp.retention['urgency'] == 'expired'
        assert r_exp.is_eligible_for_deletion


# =========================================================================
# 8. VERIFY PAYMENT HISTORY REMAINS INTACT AFTER DEPARTURE
# =========================================================================
def test_verify_payment_history_remains_intact_after_departure(auth_client, app):
    """Verify departure never deletes, resets, or auto-refunds payments."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RES-PAY-DEP",
            full_name="Payment Intact Resident",
            branch_id=branch.id,
            admission_date=date(2026, 10, 1),
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id
        res_code = res.resident_code

        # Add 2 payments
        p1 = Payment(
            resident_id=res_id,
            branch_id=branch.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=12000.00,
            payment_date=date(2026, 10, 1),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI
        )
        p2 = Payment(
            resident_id=res_id,
            branch_id=branch.id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=8500.00,
            payment_date=date(2026, 10, 5),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.BANK_TRANSFER
        )
        db.session.add_all([p1, p2])
        db.session.commit()

    # Depart
    auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': '2026-11-01'
    }, follow_redirects=True)

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        assert updated_res.payments.count() == 2
        assert updated_res.deposit_received == 12000.00
        assert updated_res.total_rent_paid == 8500.00

    # Verify profile displays both payments
    prof = auth_client.get(f'/residents/{res_code}')
    assert prof.status_code == 200
    assert b"12,000" in prof.data
    assert b"8,500" in prof.data


# =========================================================================
# 9. VERIFY OUTSTANDING BALANCES REMAIN INTACT AND HIGHLIGHTED
# =========================================================================
def test_verify_outstanding_balances_remain_intact_and_highlighted(auth_client, app):
    """Departed resident with unpaid dues retains outstanding balances on profile and previous directory."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RES-DUES-DEP",
            full_name="Unpaid Dues Resident",
            branch_id=branch.id,
            admission_date=date(2026, 10, 1),
            security_deposit_due=12000.00,
            monthly_rent_amount=9000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id
        res_code = res.resident_code

        # Add obligation of 9,000 rent (unpaid)
        FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.MONTHLY_RENT,
            expected_amount=9000.00,
            billing_month='2026-10'
        )

    # Depart
    auth_client.post(f'/residents/{res_code}/departure', data={
        'leaving_date': '2026-11-01'
    }, follow_redirects=True)

    with app.app_context():
        r = db.session.get(Resident, res_id)
        assert r.outstanding_rent == 9000.00
        assert r.total_financial_outstanding == 21000.00

    # Verify previous directory displays outstanding balance
    prev_view = auth_client.get(f'/residents/previous?search={res_code}')
    assert prev_view.status_code == 200
    assert b"21,000" in prev_view.data
    assert b"Unsettled" in prev_view.data

    # Verify profile displays dues breakdown
    prof = auth_client.get(f'/residents/{res_code}')
    assert prof.status_code == 200
    assert b"9,000" in prof.data
    assert b"12,000" in prof.data


# =========================================================================
# 10. PREVIOUS RESIDENTS BRANCH FILTERING
# =========================================================================
def test_previous_residents_branch_filtering(auth_client, app):
    """Previous residents list filters correctly by branch ID."""
    with app.app_context():
        branches = Branch.query.all()
        b1_id = branches[0].id
        b2_id = branches[1].id

    # Filter Branch 1
    res_b1 = auth_client.get(f'/residents/previous?branch={b1_id}')
    assert res_b1.status_code == 200

    # Filter Branch 2
    res_b2 = auth_client.get(f'/residents/previous?branch={b2_id}')
    assert res_b2.status_code == 200


# =========================================================================
# 11. REACTIVATE RETURNING RESIDENT
# =========================================================================
def test_reactivate_returning_resident(auth_client, app):
    """Reactivate departed resident: status becomes ACTIVE, leaving date cleared, appears in Active list."""
    with app.app_context():
        departed = Resident.query.filter_by(resident_status=ResidentStatus.LEFT).first()
        code = departed.resident_code
        res_id = departed.id
        old_leaving = departed.leaving_date

    new_adm = date.today()
    react_res = auth_client.post(f'/residents/{code}/reactivate', data={
        'new_admission_date': str(new_adm),
        'notes': 'Returning for new semester'
    }, follow_redirects=True)
    assert react_res.status_code == 200

    with app.app_context():
        updated = db.session.get(Resident, res_id)
        assert updated.resident_status == ResidentStatus.ACTIVE
        assert updated.admission_date == new_adm
        assert updated.leaving_date is None

        # Verify audit log
        audit = AuditLog.query.filter_by(
            action=AuditAction.RESIDENT_REACTIVATE,
            entity_id=res_id
        ).first()
        assert audit is not None
        assert "reactivated to ACTIVE" in audit.description

    # Active directory check
    act_dir = auth_client.get(f'/residents?search={code}')
    assert code.encode() in act_dir.data


# =========================================================================
# 12. PRESERVE PREVIOUS ADMISSION AND DEPARTURE HISTORY
# =========================================================================
def test_verify_previous_admission_and_departure_history_preserved(auth_client, app):
    """Verify past stay records are archived in ResidentStayHistory when resident returns."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RES-STAY-HIST",
            full_name="Stay History Resident",
            branch_id=branch.id,
            admission_date=date(2025, 6, 1),
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id
        code = res.resident_code

    # First departure
    auth_client.post(f'/residents/{code}/departure', data={
        'leaving_date': '2025-12-15',
        'notes': 'First semester completion'
    })

    # Reactivation (second stay)
    auth_client.post(f'/residents/{code}/reactivate', data={
        'new_admission_date': '2026-02-01',
        'notes': 'Second semester return'
    })

    with app.app_context():
        r = db.session.get(Resident, res_id)
        assert r.resident_status == ResidentStatus.ACTIVE
        assert r.admission_date == date(2026, 2, 1)

        # Check stay history records
        stays = r.stay_history.order_by(ResidentStayHistory.stay_number.asc()).all()
        assert len(stays) >= 2
        # Stay 1: closed
        assert stays[0].admission_date == date(2025, 6, 1)
        assert stays[0].leaving_date == date(2025, 12, 15)
        # Stay 2: active
        assert stays[1].admission_date == date(2026, 2, 1)
        assert stays[1].leaving_date is None


# =========================================================================
# 13. DASHBOARD STATISTICS REFLECT ACTIVE AND PREVIOUS
# =========================================================================
def test_dashboard_statistics_reflect_active_and_previous(app):
    """DashboardService accurately counts total, active, and departed residents."""
    with app.app_context():
        stats = DashboardService.get_dashboard_stats('all')
        total = Resident.query.count()
        active = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).count()
        left = Resident.query.filter_by(resident_status=ResidentStatus.LEFT).count()

        assert stats['total_residents'] == total
        assert stats['active_residents'] == active
        assert stats['left_residents'] == left
        assert total == active + left


# =========================================================================
# 14. UNAUTHORIZED USERS BLOCKED FROM DEPARTURE AND REACTIVATION
# =========================================================================
def test_unauthorized_users_blocked_from_departure_and_reactivation(client, app):
    """Unauthenticated users cannot mark departure or reactivate residents."""
    with app.app_context():
        res = Resident.query.first()
        code = res.resident_code

    # Departure blocked
    dep_res = client.post(f'/residents/{code}/departure', data={'leaving_date': '2026-11-04'})
    assert dep_res.status_code == 302
    assert '/auth/login' in dep_res.headers.get('Location', '')

    # Reactivate blocked
    react_res = client.post(f'/residents/{code}/reactivate', data={'new_admission_date': '2026-11-04'})
    assert react_res.status_code == 302
    assert '/auth/login' in react_res.headers.get('Location', '')
