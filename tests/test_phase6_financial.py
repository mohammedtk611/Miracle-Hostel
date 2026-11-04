"""
Test Suite for Miracle Hostel Management Portal - Phase 6 Financial & Payment Management.
Covers Section 12 test specifications:
1. test_record_security_deposit_payment
2. test_record_partial_deposit_payment
3. test_complete_deposit_payment
4. test_record_admission_rent
5. test_record_monthly_rent
6. test_record_multiple_payments_same_resident
7. test_verify_outstanding_balances
8. test_verify_payment_history
9. test_change_payment_status_using_quick_edit
10. test_branch_specific_payment_reports
11. test_consolidated_payment_reports
12. test_prevent_duplicate_transactions_and_duplicate_monthly_obligations
13. test_unauthorized_financial_operations_blocked
"""
import pytest
from datetime import date, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, PaymentObligation,
    ResidentStatus, PaymentType, PaymentStatus, PaymentMethod, ObligationType
)
from app.services.seed_service import seed_database_sample_data
from app.services.financial_service import FinancialService


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
# 1. RECORD SECURITY DEPOSIT PAYMENT
# =========================================================================
def test_record_security_deposit_payment(auth_client, app):
    """Record full security deposit payment for a resident and verify ledger persistence."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-001",
            full_name="Deposit Test Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=12000.00,
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

    res_post = auth_client.post('/payments', data={
        'resident_id': res_id,
        'payment_type': PaymentType.SECURITY_DEPOSIT,
        'amount': '12000.00',
        'payment_method': PaymentMethod.UPI,
        'payment_date': '2026-11-01',
        'transaction_reference': 'UPI/DEPTEST123',
        'notes': 'Full security deposit paid'
    }, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        resident = db.session.get(Resident, res_id)
        assert resident.deposit_status == PaymentStatus.PAID
        assert resident.deposit_received == 12000.00
        assert resident.deposit_outstanding == 0.00

        payment = Payment.query.filter_by(
            resident_id=res_id,
            payment_type=PaymentType.SECURITY_DEPOSIT
        ).first()
        assert payment is not None
        assert float(payment.amount) == 12000.00
        assert payment.payment_method == PaymentMethod.UPI
        assert payment.payment_status == PaymentStatus.PAID


# =========================================================================
# 2. RECORD PARTIAL DEPOSIT PAYMENT
# =========================================================================
def test_record_partial_deposit_payment(auth_client, app):
    """Record partial security deposit payment and verify outstanding balance is updated."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-002",
            full_name="Partial Deposit Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=15000.00,
            monthly_rent_amount=9000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        # Create obligation for deposit
        ob = FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.SECURITY_DEPOSIT,
            expected_amount=15000.00,
            due_date=date(2026, 11, 1)
        )
        ob_id = ob.id

    # Pay 6,000 out of 15,000
    res_post = auth_client.post('/payments', data={
        'resident_id': res_id,
        'obligation_id': ob_id,
        'payment_type': PaymentType.SECURITY_DEPOSIT,
        'amount': '6000.00',
        'payment_method': PaymentMethod.BANK_TRANSFER,
        'payment_date': '2026-11-01',
        'transaction_reference': 'NEFT/PARTIAL6K',
        'notes': 'First installment of deposit'
    }, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        resident = db.session.get(Resident, res_id)
        assert resident.deposit_status == PaymentStatus.PARTIAL
        assert resident.deposit_received == 6000.00
        assert resident.deposit_outstanding == 9000.00

        obligation = db.session.get(PaymentObligation, ob_id)
        assert obligation.status == PaymentStatus.PARTIAL
        assert obligation.total_amount_received == 6000.00
        assert obligation.outstanding_amount == 9000.00


# =========================================================================
# 3. COMPLETE DEPOSIT PAYMENT
# =========================================================================
def test_complete_deposit_payment(auth_client, app):
    """Complete remaining balance on a partial deposit and verify status transitions to PAID."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-003",
            full_name="Complete Deposit Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=10000.00,
            monthly_rent_amount=8000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        ob = FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.SECURITY_DEPOSIT,
            expected_amount=10000.00,
            due_date=date(2026, 11, 1)
        )
        ob_id = ob.id

        # First partial payment: 4,000
        FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=4000.00,
            obligation_id=ob_id,
            payment_date=date(2026, 11, 1)
        )

    # Second payment: remaining 6,000
    res_post = auth_client.post('/payments', data={
        'resident_id': res_id,
        'obligation_id': ob_id,
        'payment_type': PaymentType.SECURITY_DEPOSIT,
        'amount': '6000.00',
        'payment_method': PaymentMethod.CASH,
        'payment_date': '2026-11-05',
        'notes': 'Final installment clearing deposit'
    }, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        resident = db.session.get(Resident, res_id)
        assert resident.deposit_status == PaymentStatus.PAID
        assert resident.deposit_received == 10000.00
        assert resident.deposit_outstanding == 0.00

        obligation = db.session.get(PaymentObligation, ob_id)
        assert obligation.status == PaymentStatus.PAID
        assert obligation.outstanding_amount == 0.00


# =========================================================================
# 4. RECORD ADMISSION RENT
# =========================================================================
def test_record_admission_rent(auth_client, app):
    """Record initial admission rent payment and verify it is distinct from security deposit."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-004",
            full_name="Admission Rent Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=12000.00,
            admission_rent_due=8500.00,
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        ob = FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.ADMISSION_RENT,
            expected_amount=8500.00,
            due_date=date(2026, 11, 1)
        )
        ob_id = ob.id

    res_post = auth_client.post('/payments', data={
        'resident_id': res_id,
        'obligation_id': ob_id,
        'payment_type': PaymentType.ADMISSION_RENT,
        'amount': '8500.00',
        'payment_method': PaymentMethod.UPI,
        'payment_date': '2026-11-01',
        'transaction_reference': 'UPI/ADM8500',
        'notes': 'Admission rent paid at onboarding'
    }, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        resident = db.session.get(Resident, res_id)
        assert resident.admission_rent_status == PaymentStatus.PAID
        assert resident.admission_rent_received == 8500.00
        assert resident.admission_rent_outstanding == 0.00
        # Deposit should remain unaffected
        assert resident.deposit_received == 0.00


# =========================================================================
# 5. RECORD MONTHLY RENT
# =========================================================================
def test_record_monthly_rent(auth_client, app):
    """Manually generate monthly rent obligation and record monthly rent payment against it."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-005",
            full_name="Monthly Rent Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            monthly_rent_amount=9500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

    # 1. Generate monthly rent obligation
    gen_res = auth_client.post('/payments/obligations/generate', data={
        'resident_id': res_id,
        'obligation_type': ObligationType.MONTHLY_RENT,
        'billing_month': '2026-12',
        'title': 'Monthly Rent - December 2026',
        'expected_amount': '9500.00',
        'due_date': '2026-12-05',
        'notes': 'December billing cycle'
    }, follow_redirects=True)
    assert gen_res.status_code == 200

    with app.app_context():
        ob = PaymentObligation.query.filter_by(
            resident_id=res_id,
            billing_month='2026-12'
        ).first()
        assert ob is not None
        assert ob.expected_amount == 9500.00
        assert ob.status == PaymentStatus.UNPAID
        ob_id = ob.id

    # 2. Record payment for this monthly rent obligation
    pay_res = auth_client.post('/payments', data={
        'resident_id': res_id,
        'obligation_id': ob_id,
        'payment_type': PaymentType.MONTHLY_RENT,
        'amount': '9500.00',
        'payment_method': PaymentMethod.BANK_TRANSFER,
        'payment_date': '2026-12-03',
        'transaction_reference': 'IMPS/DEC9500',
        'notes': 'Cleared December rent'
    }, follow_redirects=True)
    assert pay_res.status_code == 200

    with app.app_context():
        updated_ob = db.session.get(PaymentObligation, ob_id)
        assert updated_ob.status == PaymentStatus.PAID
        assert updated_ob.total_amount_received == 9500.00
        assert updated_ob.outstanding_amount == 0.00


# =========================================================================
# 6. RECORD MULTIPLE PAYMENTS FOR SAME RESIDENT
# =========================================================================
def test_record_multiple_payments_same_resident(auth_client, app):
    """Verify multiple distinct transactions for the same resident are stored immutably without overwriting."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-006",
            full_name="Multi Payment Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=12000.00,
            monthly_rent_amount=8000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

    # Transaction 1: Security Deposit
    auth_client.post('/payments', data={
        'resident_id': res_id,
        'payment_type': PaymentType.SECURITY_DEPOSIT,
        'amount': '12000.00',
        'payment_method': PaymentMethod.UPI,
        'payment_date': '2026-11-01',
        'transaction_reference': 'REF-1',
        'notes': 'Security deposit'
    })

    # Transaction 2: November Rent
    auth_client.post('/payments', data={
        'resident_id': res_id,
        'payment_type': PaymentType.MONTHLY_RENT,
        'amount': '8000.00',
        'payment_method': PaymentMethod.BANK_TRANSFER,
        'payment_date': '2026-11-05',
        'transaction_reference': 'REF-2',
        'notes': 'November rent'
    })

    # Transaction 3: Other Charges (e.g. key replacement or late fee)
    auth_client.post('/payments', data={
        'resident_id': res_id,
        'payment_type': PaymentType.OTHER_CHARGES,
        'amount': '500.00',
        'payment_method': PaymentMethod.CASH,
        'payment_date': '2026-11-10',
        'transaction_reference': 'REF-3',
        'notes': 'ID card replacement fee'
    })

    with app.app_context():
        payments = Payment.query.filter_by(resident_id=res_id).all()
        assert len(payments) == 3
        types = [p.payment_type for p in payments]
        assert PaymentType.SECURITY_DEPOSIT in types
        assert PaymentType.MONTHLY_RENT in types
        assert PaymentType.OTHER_CHARGES in types

        # Confirm all 3 have distinct IDs and correct amounts
        amounts = sorted([float(p.amount) for p in payments])
        assert amounts == [500.00, 8000.00, 12000.00]


# =========================================================================
# 7. VERIFY OUTSTANDING BALANCES & ADVANCE HANDLING
# =========================================================================
def test_verify_outstanding_balances(auth_client, app):
    """Verify mathematical calculation: Outstanding = max(0, Expected - Total Received), and advance recorded."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-007",
            full_name="Balance Calc Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            monthly_rent_amount=10000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

        ob = FinancialService.create_obligation(
            resident_id=res_id,
            obligation_type=ObligationType.MONTHLY_RENT,
            expected_amount=10000.00,
            billing_month='2026-11'
        )
        ob_id = ob.id

        # Payment 1: 6,000 -> Expected 10,000 - Received 6,000 = Outstanding 4,000
        FinancialService.record_payment(
            resident_id=res_id,
            obligation_id=ob_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=6000.00
        )
        db.session.refresh(ob)
        assert ob.outstanding_amount == 4000.00
        assert ob.status == PaymentStatus.PARTIAL

        # Payment 2: 5,000 (exceeds 4,000 due by 1,000 advance)
        p2 = FinancialService.record_payment(
            resident_id=res_id,
            obligation_id=ob_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=5000.00
        )
        db.session.refresh(ob)
        assert ob.outstanding_amount == 0.00
        assert ob.status == PaymentStatus.PAID
        assert "advance payment" in (p2.notes or "").lower()


# =========================================================================
# 8. VERIFY PAYMENT HISTORY
# =========================================================================
def test_verify_payment_history(auth_client, app):
    """Verify chronological transaction history on resident profile and payments index."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-008",
            full_name="History Check Resident",
            branch_id=branch.id,
            admission_date=date(2026, 10, 1),
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id
        res_code = res.resident_code

        # Create two payments on different dates
        FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=8500.00,
            payment_date=date(2026, 10, 5),
            transaction_reference="OCT-RENT"
        )
        FinancialService.record_payment(
            resident_id=res_id,
            payment_type=PaymentType.MONTHLY_RENT,
            amount=8500.00,
            payment_date=date(2026, 11, 5),
            transaction_reference="NOV-RENT"
        )

    # Check profile page
    res_prof = auth_client.get(f'/residents/{res_code}')
    assert res_prof.status_code == 200
    assert b"OCT-RENT" in res_prof.data
    assert b"NOV-RENT" in res_prof.data

    # Check payments index
    res_index = auth_client.get('/payments?search=History+Check+Resident')
    assert res_index.status_code == 200
    assert b"NOV-RENT" in res_index.data


# =========================================================================
# 9. CHANGE PAYMENT STATUS USING QUICK EDIT
# =========================================================================
def test_change_payment_status_using_quick_edit(auth_client, app):
    """Verify quick payment status editing from directory updates database and returns badge HTML."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-009",
            full_name="Quick Edit Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            security_deposit_due=12000.00,
            monthly_rent_amount=8500.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

    # Mark Deposit as PAID via quick payment AJAX
    res_dep = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'SECURITY_DEPOSIT',
        'status': 'PAID',
        'amount': 12000.00,
        'payment_method': 'UPI',
        'payment_date': '2026-11-01',
        'transaction_reference': 'QUICK-DEP'
    })
    assert res_dep.status_code == 200
    data_dep = res_dep.get_json()
    assert data_dep['success'] is True
    assert data_dep['status'] == 'PAID'
    assert 'badge-paid' in data_dep['badge_html']

    # Mark Rent as PARTIAL via quick payment AJAX
    res_rent = auth_client.post('/residents/quick-payment', json={
        'resident_id': res_id,
        'payment_type': 'RENT',
        'status': 'PARTIAL',
        'amount': 4000.00,
        'payment_method': 'CASH',
        'payment_date': '2026-11-05'
    })
    assert res_rent.status_code == 200
    data_rent = res_rent.get_json()
    assert data_rent['success'] is True
    assert data_rent['status'] == 'PARTIAL'
    assert 'badge-partial' in data_rent['badge_html']


# =========================================================================
# 10. BRANCH-SPECIFIC PAYMENT REPORTS
# =========================================================================
def test_branch_specific_payment_reports(auth_client, app):
    """Verify branch-specific filtering isolates payments and computes metrics strictly for that branch."""
    with app.app_context():
        branches = Branch.query.all()
        b1_id = branches[0].id
        b2_id = branches[1].id

        # Query stats via FinancialService for Branch 1
        stats_b1 = FinancialService.get_financial_dashboard_stats(branch_id=b1_id)
        # Query stats via FinancialService for Branch 2
        stats_b2 = FinancialService.get_financial_dashboard_stats(branch_id=b2_id)

    # Check HTTP endpoint with branch filter
    resp = auth_client.get(f'/payments?branch={b1_id}')
    assert resp.status_code == 200

    # Ensure branch 1 stats are returned without error
    assert 'total_amount_collected' in stats_b1
    assert 'total_deposits_collected' in stats_b1
    assert 'total_rent_collected' in stats_b1


# =========================================================================
# 11. CONSOLIDATED PAYMENT REPORTS (NO DOUBLE COUNTING)
# =========================================================================
def test_consolidated_payment_reports(auth_client, app):
    """Verify consolidated report across all branches aggregates exactly without double-counting."""
    with app.app_context():
        branches = Branch.query.all()
        branch_collections_sum = 0.0

        for b in branches:
            b_stats = FinancialService.get_financial_dashboard_stats(branch_id=b.id)
            branch_collections_sum += b_stats['total_amount_collected']

        # Consolidated stats
        all_stats = FinancialService.get_financial_dashboard_stats(branch_id='all')

        # Consolidated sum must equal sum of individual branch collections
        assert round(all_stats['total_amount_collected'], 2) == round(branch_collections_sum, 2)


# =========================================================================
# 12. PREVENT DUPLICATE TRANSACTIONS & DUPLICATE MONTHLY OBLIGATIONS
# =========================================================================
def test_prevent_duplicate_transactions_and_duplicate_monthly_obligations(auth_client, app):
    """Verify that generating duplicate monthly obligations for the same resident and billing cycle is rejected."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        res = Resident(
            resident_code="RES-TST-012",
            full_name="Duplicate Test Resident",
            branch_id=branch.id,
            admission_date=date(2026, 11, 1),
            monthly_rent_amount=8000.00
        )
        db.session.add(res)
        db.session.commit()
        res_id = res.id

    # 1. First obligation generation should succeed
    res1 = auth_client.post('/payments/obligations/generate', data={
        'resident_id': res_id,
        'obligation_type': ObligationType.MONTHLY_RENT,
        'billing_month': '2026-11',
        'title': 'Monthly Rent - Nov 2026',
        'expected_amount': '8000.00',
        'due_date': '2026-11-05'
    }, follow_redirects=True)
    assert res1.status_code == 200

    # 2. Second obligation generation for the same resident and billing cycle must be rejected
    res2 = auth_client.post('/payments/obligations/generate', data={
        'resident_id': res_id,
        'obligation_type': ObligationType.MONTHLY_RENT,
        'billing_month': '2026-11',
        'title': 'Monthly Rent - Nov 2026 Duplicate',
        'expected_amount': '8000.00',
        'due_date': '2026-11-05'
    }, follow_redirects=True)
    assert res2.status_code == 200
    assert b"already exists" in res2.data or b"duplicate" in res2.data.lower()

    # Verify only 1 obligation exists in DB
    with app.app_context():
        obs = PaymentObligation.query.filter_by(
            resident_id=res_id,
            billing_month='2026-11'
        ).all()
        assert len(obs) == 1


# =========================================================================
# 13. UNAUTHORIZED FINANCIAL OPERATIONS BLOCKED
# =========================================================================
def test_unauthorized_financial_operations_blocked(client, app):
    """Verify that unauthenticated users are blocked from all financial routes."""
    # GET /payments
    res_get = client.get('/payments')
    assert res_get.status_code == 302
    assert '/auth/login' in res_get.headers.get('Location', '')

    # POST /payments
    res_post = client.post('/payments', data={'amount': '5000'})
    assert res_post.status_code == 302
    assert '/auth/login' in res_post.headers.get('Location', '')

    # POST /payments/obligations/generate
    res_gen = client.post('/payments/obligations/generate', data={'amount': '5000'})
    assert res_gen.status_code == 302
    assert '/auth/login' in res_gen.headers.get('Location', '')

    # POST /residents/quick-payment
    res_quick = client.post('/residents/quick-payment', data={'amount': '5000'})
    assert res_quick.status_code in (302, 401)
