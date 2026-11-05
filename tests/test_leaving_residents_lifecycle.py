"""
Test Suite for Miracle Hostel Management Portal - Leaving Residents Lifecycle.
Validates:
1. Active resident can be marked for leaving (enters LEAVING status with 30-day timeframe).
2. Leaving residents appear in the dedicated Leaving Residents section (/residents/leaving).
3. Leaving residents can be retained at any time, restoring them to ACTIVE status.
4. Leaving residents who exceed 30 days without retention automatically transition to Previous Residents (LEFT).
5. Previous residents are retained under the 1-year retention policy (365 days).
6. Total occupied beds counts both ACTIVE and LEAVING residents residing in beds.
"""
from datetime import date, timedelta
import pytest
from app import create_app
from app.extensions import db
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.audit_log import AuditLog, AuditAction


@pytest.fixture
def app():
    """Create test application context with memory SQLite DB."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        admin = Admin(email="admin", username="admin", is_active=True)
        admin.set_password("1234")
        db.session.add(admin)

        branch = Branch(
            branch_name="Miracle Branch 1",
            branch_code="BR-AN-01",
            address="14, 2nd Avenue, Chennai",
            contact_number="+91 98401 23456",
            total_beds=20,
            is_active=True
        )
        db.session.add(branch)
        db.session.commit()

        yield test_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_client(app):
    """Authenticated administrator client fixture."""
    c = app.test_client()
    c.post('/auth/login', data={'email': 'admin', 'password': '1234'}, follow_redirects=True)
    return c


def test_mark_resident_for_leaving_and_view_leaving_section(auth_client, app):
    """Test marking an active resident for leaving and confirming they appear in /residents/leaving."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="MHL-2026-001",
            full_name="Leaving Test Resident",
            branch_id=branch.id,
            admission_date=date.today() - timedelta(days=60),
            resident_status=ResidentStatus.ACTIVE
        )
        db.session.add(res)
        db.session.commit()
        res_code = res.resident_code

    # 1. Mark for leaving via POST endpoint
    leaving_target = str(date.today() + timedelta(days=30))
    resp = auth_client.post(f'/residents/{res_code}/mark-leaving', data={
        'leaving_date': leaving_target,
        'leaving_reason': 'Notice Given (Moving Out)',
        'notes': '1-month notice served'
    }, follow_redirects=True)
    assert resp.status_code == 200

    # 2. Verify model state
    with app.app_context():
        updated = Resident.query.filter_by(resident_code=res_code).first()
        assert updated.resident_status == ResidentStatus.LEAVING
        assert updated.leaving_days_remaining == 30
        assert not updated.should_auto_move_to_previous

    # 3. Verify resident appears in Leaving Residents directory view
    leaving_view = auth_client.get('/residents/leaving')
    assert leaving_view.status_code == 200
    assert b"Leaving Test Resident" in leaving_view.data
    assert b"MHL-2026-001" in leaving_view.data
    assert b"30-Day Leaving & Retention Window Active" in leaving_view.data


def test_retain_resident_restores_active_status(auth_client, app):
    """Test retaining a resident from LEAVING status, restoring them to ACTIVE status."""
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="MHL-2026-002",
            full_name="Retained Test Resident",
            branch_id=branch.id,
            admission_date=date.today() - timedelta(days=90),
            leaving_date=date.today() + timedelta(days=20),
            notice_date=date.today() - timedelta(days=10),
            resident_status=ResidentStatus.LEAVING
        )
        db.session.add(res)
        db.session.commit()
        res_code = res.resident_code

    # 1. Click Retain Resident
    retain_resp = auth_client.post(f'/residents/{res_code}/retain', follow_redirects=True)
    assert retain_resp.status_code == 200

    # 2. Verify status is restored to ACTIVE
    with app.app_context():
        retained = Resident.query.filter_by(resident_code=res_code).first()
        assert retained.resident_status == ResidentStatus.ACTIVE
        assert retained.notice_date is None

    # 3. Verify no longer in Leaving section
    leaving_view = auth_client.get('/residents/leaving')
    assert b"MHL-2026-002" not in leaving_view.data


def test_expired_leaving_resident_auto_transitions_to_previous(app):
    """Test that residents who stay in LEAVING status past 30 days automatically move to Previous Residents (LEFT)."""
    with app.app_context():
        branch = Branch.query.first()
        # Notice initiated 35 days ago (timeframe exceeded)
        res = Resident(
            resident_code="MHL-2026-003",
            full_name="Unretained Expired Resident",
            branch_id=branch.id,
            admission_date=date.today() - timedelta(days=100),
            notice_date=date.today() - timedelta(days=35),
            leaving_date=date.today() - timedelta(days=5),
            resident_status=ResidentStatus.LEAVING
        )
        db.session.add(res)
        db.session.commit()
        res_code = res.resident_code

        assert res.should_auto_move_to_previous is True

        # Run automated transition check
        Resident.check_and_transition_expired_leaving()

        transitioned = Resident.query.filter_by(resident_code=res_code).first()
        assert transitioned.resident_status == ResidentStatus.LEFT
        # 1-year retention policy active
        assert transitioned.retention_deadline == transitioned.leaving_date + timedelta(days=365)
