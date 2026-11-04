"""
Test Suite for Phase 9: Quality Assurance, Bug Fixing, and Performance Optimization.
Covers:
1. Custom 404 response and template for missing resident records.
2. Custom 404 response for arbitrary missing routes.
3. 500 error handler protection (preventing stack trace leakage).
4. Multi-installment partial payment calculation accuracy.
5. Immutability of multiple payment transactions across cycles.
6. Unpaid status quick-edit does not insert fake transactions.
7. Dashboard financial totals match transaction sums.
8. HTTP security headers enforcement on application responses.
9. Session cookie security configuration (HttpOnly, SameSite, non-permanent).
10. Argon2id password security.
"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from app import create_app
from app.extensions import db
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentMethod
from app.models.payment_obligation import PaymentObligation, ObligationType
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
# 1. ERROR HANDLING: 404 ON MISSING RESIDENT
# =========================================================================
def test_404_error_page_for_non_existent_resident(auth_client):
    """Requesting a non-existent resident profile returns HTTP 404 and renders 404 template."""
    res = auth_client.get('/residents/NON-EXISTENT-CODE-999')
    assert res.status_code == 404
    assert b"404 - Resource Not Found" in res.data
    assert b"Dashboard" in res.data


def test_404_error_page_for_non_existent_page(auth_client):
    """Requesting an arbitrary non-existent route returns 404."""
    res = auth_client.get('/some/completely/random/missing/url')
    assert res.status_code == 404
    assert b"404 - Resource Not Found" in res.data


# =========================================================================
# 2. ERROR HANDLING: 500 SERVER ERROR SHIELDING
# =========================================================================
def test_500_error_handler_renders_clean_template_without_stack_trace(app):
    """Internal server errors return 500 with friendly message and no stack trace."""
    # Register temporary failing test endpoint
    @app.route('/test-trigger-500')
    def trigger_error():
        raise RuntimeError("Simulated internal database crash")

    # Disable testing exception re-raising to test errorhandler pipeline
    app.testing = False
    client = app.test_client()
    res = client.get('/test-trigger-500')
    assert res.status_code == 500
    assert b"500 - Internal System Error" in res.data
    assert b"Simulated internal database crash" not in res.data
    assert b"Traceback" not in res.data


# =========================================================================
# 3. FINANCIAL: MULTI-INSTALLMENT PARTIAL PAYMENT ACCURACY
# =========================================================================
def test_payment_multi_partial_payment_calculation_accuracy(auth_client, app):
    """
    Simulate a multi-installment payment lifecycle:
    1. Obligation of 9,000 rent created.
    2. Installment 1: 3,000 paid -> Balance: 6,000, Status: PARTIAL.
    3. Installment 2: 3,000 paid -> Balance: 3,000, Status: PARTIAL.
    4. Installment 3: 3,000 paid -> Balance: 0, Status: PAID.
    Verify all 3 transactions exist immutably and balances compute correctly.
    """
    with app.app_context():
        branch = Branch.query.first()
        res = Resident(
            resident_code="RES-INSTALLMENT",
            full_name="Installment Payer",
            branch_id=branch.id,
            admission_date=date(2026, 10, 1),
            monthly_rent_amount=9000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        # 1. Create monthly obligation
        ob = FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.MONTHLY_RENT,
            expected_amount=9000.00,
            billing_month='2026-10'
        )
        assert ob.outstanding_amount == 9000.00
        assert ob.status == 'UNPAID'

        # 2. Payment 1: 3,000
        p1 = FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=3000.00,
            payment_date=date(2026, 10, 5),
            payment_method=PaymentMethod.UPI,
            obligation_id=ob.id
        )
        assert ob.outstanding_amount == 6000.00
        assert ob.status == 'PARTIAL'
        assert p1.payment_status == PaymentStatus.PARTIAL

        # 3. Payment 2: 3,000
        p2 = FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=3000.00,
            payment_date=date(2026, 10, 15),
            payment_method=PaymentMethod.BANK_TRANSFER,
            obligation_id=ob.id
        )
        assert ob.outstanding_amount == 3000.00
        assert ob.status == 'PARTIAL'

        # 4. Payment 3: 3,000 (final settlement)
        p3 = FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=3000.00,
            payment_date=date(2026, 10, 25),
            payment_method=PaymentMethod.CASH,
            obligation_id=ob.id
        )
        assert ob.outstanding_amount == 0.00
        assert ob.status == 'PAID'
        assert p3.payment_status == PaymentStatus.PAID

        # Verify resident totals
        resident_check = db.session.get(Resident, res_id)
        assert resident_check.payments.count() == 3
        assert resident_check.total_rent_paid == 9000.00
        assert resident_check.outstanding_rent == 0.00


# =========================================================================
# 4. FINANCIAL: UNPAID STATUS DOES NOT CREATE FAKE PAYMENT
# =========================================================================
def test_unpaid_status_does_not_create_fake_payment_transaction(auth_client, app):
    """Quick-editing a status to UNPAID does not add fictitious paid money and preserves history."""
    with app.app_context():
        res = Resident.query.first()
        res_id = res.id
        initial_rent_paid = res.total_rent_paid
        prior_payment_ids = [p.id for p in res.payments.all()]

    # Trigger quick payment update to UNPAID
    res = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'UNPAID'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        resident = db.session.get(Resident, res_id)
        # Ensure total paid money did not increase by fake amounts
        assert resident.total_rent_paid == initial_rent_paid
        # Ensure all prior transactions are preserved
        for pid in prior_payment_ids:
            assert db.session.get(Payment, pid) is not None


# =========================================================================
# 5. DASHBOARD: FINANCIAL TOTALS MATCH TRANSACTION SUMS
# =========================================================================
def test_dashboard_collection_totals_match_actual_transactions(app):
    """Verify that DashboardService and FinancialService collection figures match DB sums."""
    with app.app_context():
        stats = DashboardService.get_dashboard_stats(selected_branch='all')
        
        # Calculate expected total from all PAID payments
        paid_payments = Payment.query.filter_by(payment_status=PaymentStatus.PAID).all()
        expected_total = sum(float(p.amount) for p in paid_payments)

        assert abs(stats['total_collection'] - expected_total) < 0.01


# =========================================================================
# 6. SECURITY: HTTP HEADERS ENFORCED ON ALL RESPONSES
# =========================================================================
def test_security_headers_enforced_on_all_responses(auth_client):
    """Enforce X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy."""
    response = auth_client.get('/')
    assert response.status_code == 200
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert response.headers.get('X-XSS-Protection') == '1; mode=block'
    assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


# =========================================================================
# 7. SECURITY: SESSION COOKIE CONFIGURATION
# =========================================================================
def test_session_cookie_security_configuration(app):
    """Verify cookie security settings: HttpOnly, SameSite, and non-permanent."""
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert app.config['SESSION_PERMANENT'] is False


# =========================================================================
# 8. SECURITY: ARGON2ID PASSWORD SECURITY
# =========================================================================
def test_argon2id_password_security(app):
    """Administrator password is encrypted using Argon2id and never stored plaintext."""
    with app.app_context():
        admin = Admin.query.first()
        assert admin is not None
        assert admin.password_hash != "1234"
        assert admin.password_hash.startswith("$argon2id$")
        assert admin.check_password("1234") is True
        assert admin.check_password("wrong_password") is False
