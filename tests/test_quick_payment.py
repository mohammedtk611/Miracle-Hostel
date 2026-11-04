"""
Test Suite for Miracle Hostel Management Portal - Quick Payment Status Editing Feature.
Verifies:
1. Unauthenticated requests to /residents/quick-payment are blocked.
2. Marking Security Deposit as PAID with valid amount, payment method, and transaction reference.
3. Marking Rent as PAID with valid amount.
4. Marking Rent as PARTIAL with balance calculation and historical transaction preservation.
5. Marking as UNPAID does not create fictitious payment transactions and preserves historical records.
6. Rejection of zero or negative amounts for PAID and PARTIAL.
7. Rejection of invalid payment types, invalid statuses, and non-existent residents.
8. Audit logging for all quick payment status modifications.
9. Resident Directory UI displays clickable buttons with correct badge styling (Green/Paid, Red/Unpaid, Amber/Partial).
"""
import pytest
from datetime import date
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, AuditLog,
    ResidentStatus, PaymentType, PaymentStatus, AuditAction
)
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


# -----------------------------------------------------------------------------
# 1. ACCESS CONTROL
# -----------------------------------------------------------------------------
def test_unauthenticated_quick_payment_blocked(client):
    """Verify unauthenticated requests cannot update payment statuses."""
    res = client.post('/residents/quick-payment', json={
        'resident_id': 1,
        'payment_type': 'RENT',
        'status': 'PAID',
        'amount': 8500.0
    }, follow_redirects=False)

    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']


# -----------------------------------------------------------------------------
# 2. MARK AS PAID
# -----------------------------------------------------------------------------
def test_quick_payment_mark_paid_security_deposit(auth_client, app):
    """Verify marking Security Deposit as PAID creates a valid transaction and updates status."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_id = resident.id
        initial_payments_count = resident.payments.count()

    res = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'SECURITY_DEPOSIT',
        'status': 'PAID',
        'amount': 15000.00,
        'payment_date': str(date.today()),
        'payment_method': 'UPI',
        'transaction_reference': 'UPI/TEST998877',
        'notes': 'Full security deposit cleared'
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['status'] == 'PAID'
    assert 'badge-paid' in data['badge_html']
    assert '15,000.00' in data['badge_html']

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        assert updated_res.payments.count() == initial_payments_count + 1
        assert updated_res.deposit_status == 'PAID'
        assert updated_res.security_deposit_amount == 15000.00

        # Check audit log
        audit = AuditLog.query.filter_by(action=AuditAction.PAYMENT_UPDATE).order_by(AuditLog.id.desc()).first()
        assert audit is not None
        assert "SECURITY_DEPOSIT" in audit.description
        assert "15,000.00" in audit.description


def test_quick_payment_mark_paid_rent(auth_client, app):
    """Verify marking Rent as PAID creates a new rent transaction and updates displayed rent status."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_id = resident.id
        initial_rent_paid = resident.total_rent_paid

    res = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'PAID',
        'amount': 9000.00,
        'payment_method': 'BANK_TRANSFER',
        'transaction_reference': 'NEFT/TEST1234',
        'notes': 'Rent for current cycle'
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['status'] == 'PAID'
    assert 'badge-paid' in data['badge_html']

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        assert updated_res.rent_status == 'PAID'
        assert updated_res.total_rent_paid == initial_rent_paid + 9000.00


# -----------------------------------------------------------------------------
# 3. MARK AS PARTIAL
# -----------------------------------------------------------------------------
def test_quick_payment_mark_partial_rent(auth_client, app):
    """Verify marking status as PARTIAL records partial payment and calculates balance due."""
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_id = resident.id

    res = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'PARTIAL',
        'amount': 4000.00,
        'total_expected': 10000.00,
        'payment_method': 'CASH',
        'notes': 'Promised remaining 6000 by 15th'
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['status'] == 'PARTIAL'
    assert data['balance_due'] == 6000.00
    assert 'badge-partial' in data['badge_html']
    assert '6,000.00' in data['badge_html']

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        assert updated_res.rent_status == 'PARTIAL'
        latest_payment = updated_res.payments.filter_by(payment_type='RENT').order_by(db.desc('id')).first()
        assert latest_payment.payment_status == PaymentStatus.PARTIAL
        assert float(latest_payment.amount) == 4000.00
        assert "Outstanding balance: ₹6,000.00" in latest_payment.notes


# -----------------------------------------------------------------------------
# 4. MARK AS UNPAID
# -----------------------------------------------------------------------------
def test_quick_payment_mark_unpaid_preserves_history(auth_client, app):
    """
    Verify marking as UNPAID:
    - Does NOT create fictitious payment money (amount = 0.00).
    - Preserves all previously recorded transactions.
    - Sets displayed status to UNPAID (PENDING).
    """
    with app.app_context():
        resident = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_id = resident.id
        prior_total_rent_paid = resident.total_rent_paid
        prior_payment_ids = [p.id for p in resident.payments.all()]

    res = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'UNPAID',
        'notes': 'New billing cycle invoice generated - unpaid'
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['status'] == 'UNPAID'
    assert 'badge-unpaid' in data['badge_html']

    with app.app_context():
        updated_res = db.session.get(Resident, res_id)
        # Status should now evaluate to PENDING (Unpaid)
        assert updated_res.rent_status == 'PENDING'

        # Total paid rent must NOT increase by fake amounts
        assert updated_res.total_rent_paid == prior_total_rent_paid

        # All previous payment records must still exist intact
        current_payment_ids = [p.id for p in updated_res.payments.all()]
        for pid in prior_payment_ids:
            assert pid in current_payment_ids

        # Latest payment record is the due ledger record
        latest = updated_res.payments.filter_by(payment_type='RENT').order_by(db.desc('id')).first()
        assert latest.payment_status == PaymentStatus.PENDING
        assert float(latest.amount) == 0.00
        assert latest.payment_method is None
        assert latest.transaction_reference is None


# -----------------------------------------------------------------------------
# 5. VALIDATION & REJECTIONS
# -----------------------------------------------------------------------------
def test_quick_payment_rejects_negative_or_zero_amount(auth_client, app):
    """Verify negative and zero amounts are strictly rejected."""
    with app.app_context():
        res_id = Resident.query.first().id

    # Zero amount
    res1 = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'PAID',
        'amount': 0.00
    })
    assert res1.status_code == 400
    assert "greater than zero" in res1.get_json()['message']

    # Negative amount
    res2 = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'SECURITY_DEPOSIT',
        'status': 'PARTIAL',
        'amount': -500.00
    })
    assert res2.status_code == 400
    assert "greater than zero" in res2.get_json()['message']


def test_quick_payment_rejects_invalid_inputs(auth_client):
    """Verify bad resident IDs, payment types, and statuses are rejected."""
    # Non-existent resident
    res1 = auth_client.post('/residents/quick-payment', json={
        'resident_id': 99999,
        'payment_type': 'RENT',
        'status': 'PAID',
        'amount': 5000.0
    })
    assert res1.status_code == 404

    # Invalid payment type
    res2 = auth_client.post('/residents/quick-payment', json={
        'resident_id': 1,
        'payment_type': 'INVALID_TYPE',
        'status': 'PAID',
        'amount': 5000.0
    })
    assert res2.status_code == 400

    # Invalid status
    res3 = auth_client.post('/residents/quick-payment', json={
        'resident_id': 1,
        'payment_type': 'RENT',
        'status': 'UNKNOWN_STATUS',
        'amount': 5000.0
    })
    assert res3.status_code == 400


# -----------------------------------------------------------------------------
# 6. RESIDENT DIRECTORY UI CHECKS
# -----------------------------------------------------------------------------
def test_resident_directory_renders_quick_payment_controls(auth_client):
    """Verify Resident Directory renders clickable quick-edit buttons with proper attributes."""
    res = auth_client.get('/residents')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'data-quick-payment' in html
    assert 'data-payment-type="SECURITY_DEPOSIT"' in html
    assert 'data-payment-type="RENT"' in html
    assert 'id="quickPaymentModal"' in html
    assert 'badge-status' in html
