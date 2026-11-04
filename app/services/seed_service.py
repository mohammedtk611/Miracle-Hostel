"""
Database Seeding Service for Miracle Hostel Management Portal.
Populates initial sample branches, residents, and payment records for Phase 4.
Ensures sample data adheres to database constraints and encrypted Aadhaar requirements.
"""
from datetime import date, timedelta
from app.extensions import db
from app.models import Branch, Resident, Payment, ResidentStatus, PaymentType, PaymentStatus, PaymentMethod
from app.services.aadhaar_service import AadhaarSecurityService


def seed_default_branches():
    """
    Seed initial hostel branches if database has no branches.
    Clean state with 0 residents.
    """
    if Branch.query.first():
        return False

    branch1 = Branch(
        branch_name="Miracle Branch 1",
        branch_code="BR-AN-01",
        address="14, 2nd Avenue, Anna Nagar East, Chennai 600102",
        contact_number="+91 98401 23456",
        total_beds=20,
        is_active=True
    )
    branch2 = Branch(
        branch_name="Miracle Branch 2",
        branch_code="BR-OMR-02",
        address="Plot 88, Rajiv Gandhi Salai, Thoraipakkam, Chennai 600097",
        contact_number="+91 98402 34567",
        total_beds=20,
        is_active=True
    )
    branch3 = Branch(
        branch_name="Miracle Branch 3",
        branch_code="BR-GD-03",
        address="7, Industrial Estate Main Rd, Guindy, Chennai 600032",
        contact_number="+91 98403 45678",
        total_beds=20,
        is_active=True
    )
    branch4 = Branch(
        branch_name="Miracle Branch 4",
        branch_code="BR-PR-04",
        address="22, Mount-Poonamallee High Rd, Porur, Chennai 600116",
        contact_number="+91 98404 56789",
        total_beds=20,
        is_active=True
    )

    db.session.add_all([branch1, branch2, branch3, branch4])
    db.session.commit()
    print("[Miracle Hostel] Default branches initialized (clean state, 0 residents).")
    return True


def clear_all_resident_and_dummy_data():
    """
    Safely delete all resident profiles, payment records, obligations,
    stay histories, and retention logs.
    Preserves Administrator accounts and Hostel Branches.
    """
    from app.models import PaymentObligation, ResidentStayHistory, DataRetentionLog, AuditLog
    p_count = Payment.query.delete()
    po_count = PaymentObligation.query.delete()
    sh_count = ResidentStayHistory.query.delete()
    dr_count = DataRetentionLog.query.delete()
    r_count = Resident.query.delete()
    AuditLog.query.filter(AuditLog.entity_type.in_(['Resident', 'Payment', 'PaymentObligation'])).delete(synchronize_session=False)
    db.session.commit()
    print(f"[Miracle Hostel] Successfully cleared all resident data: {r_count} residents, {p_count} payments, {po_count} obligations purged.")
    return {
        'residents_cleared': r_count,
        'payments_cleared': p_count,
        'obligations_cleared': po_count
    }


def seed_database_sample_data(force=False, include_residents=True):
    """
    Seed initial branches and optional sample residents (primarily used by test suites).
    """
    if not force and Branch.query.first():
        return False

    today = date.today()

    # 1. Create Branches
    branch1 = Branch(
        branch_name="Main Branch - Anna Nagar",
        branch_code="BR-AN-01",
        address="14, 2nd Avenue, Anna Nagar East, Chennai 600102",
        contact_number="+91 98401 23456",
        total_beds=10,
        is_active=True
    )
    branch2 = Branch(
        branch_name="City Campus - OMR IT Corridor",
        branch_code="BR-OMR-02",
        address="Plot 88, Rajiv Gandhi Salai, Thoraipakkam, Chennai 600097",
        contact_number="+91 98402 34567",
        total_beds=12,
        is_active=True
    )
    branch3 = Branch(
        branch_name="Green Valley - Guindy",
        branch_code="BR-GD-03",
        address="7, Industrial Estate Main Rd, Guindy, Chennai 600032",
        contact_number="+91 98403 45678",
        total_beds=8,
        is_active=True
    )
    branch4 = Branch(
        branch_name="West End - Porur",
        branch_code="BR-PR-04",
        address="22, Mount-Poonamallee High Rd, Porur, Chennai 600116",
        contact_number="+91 98404 56789",
        total_beds=15,
        is_active=False  # Deactivated branch with historical records
    )

    db.session.add_all([branch1, branch2, branch3, branch4])
    db.session.flush()

    # Helper to encrypt Aadhaar
    def get_enc_aadhaar(number_str):
        enc = AadhaarSecurityService.encrypt_aadhaar(number_str)
        last_four = AadhaarSecurityService.extract_last_four(number_str)
        return enc, last_four

    # 2. Create Sample Residents
    # Branch 1 Residents (Active & Left)
    enc1, last1 = get_enc_aadhaar("234567898492")
    res1 = Resident(
        resident_code="MHL-2024-001",
        branch_id=branch1.id,
        full_name="Aravind Krishnan",
        photograph_path="/static/images/avatars/avatar-1.svg",
        aadhaar_encrypted=enc1,
        aadhaar_last_four=last1,
        admission_date=today - timedelta(days=180),
        leaving_date=None,
        resident_status=ResidentStatus.ACTIVE
    )

    enc2, last2 = get_enc_aadhaar("345678903190")
    res2 = Resident(
        resident_code="MHL-2024-002",
        branch_id=branch1.id,
        full_name="Pooja Sundaram",
        photograph_path="/static/images/avatars/avatar-2.svg",
        aadhaar_encrypted=enc2,
        aadhaar_last_four=last2,
        admission_date=today - timedelta(days=120),
        leaving_date=None,
        notice_date=today + timedelta(days=25),
        resident_status=ResidentStatus.ACTIVE
    )

    enc3, last3 = get_enc_aadhaar("456789011192")
    res3 = Resident(
        resident_code="MHL-2023-089",
        branch_id=branch1.id,
        full_name="Siddharth Menon",
        photograph_path="/static/images/avatars/avatar-9.svg",
        aadhaar_encrypted=enc3,
        aadhaar_last_four=last3,
        admission_date=today - timedelta(days=300),
        leaving_date=today - timedelta(days=8),
        resident_status=ResidentStatus.LEFT
    )

    # Branch 2 Residents (Active & Left)
    enc4, last4 = get_enc_aadhaar("567890126721")
    res4 = Resident(
        resident_code="MHL-2024-003",
        branch_id=branch2.id,
        full_name="Rahul Verma",
        photograph_path="/static/images/avatars/avatar-3.svg",
        aadhaar_encrypted=enc4,
        aadhaar_last_four=last4,
        admission_date=today - timedelta(days=90),
        leaving_date=None,
        resident_status=ResidentStatus.ACTIVE
    )

    enc5, last5 = get_enc_aadhaar("678901237823")
    res5 = Resident(
        resident_code="MHL-2024-008",
        branch_id=branch2.id,
        full_name="Ananya Roy",
        photograph_path="/static/images/avatars/avatar-8.svg",
        aadhaar_encrypted=enc5,
        aadhaar_last_four=last5,
        admission_date=today - timedelta(days=15),
        leaving_date=None,
        resident_status=ResidentStatus.ACTIVE
    )

    enc6, last6 = get_enc_aadhaar("789012346645")
    res6 = Resident(
        resident_code="MHL-2023-074",
        branch_id=branch2.id,
        full_name="Meera Subramanian",
        photograph_path="/static/images/avatars/avatar-10.svg",
        aadhaar_encrypted=enc6,
        aadhaar_last_four=last6,
        admission_date=today - timedelta(days=250),
        leaving_date=today - timedelta(days=22),
        resident_status=ResidentStatus.LEFT
    )

    # Branch 3 Residents (Active)
    enc7, last7 = get_enc_aadhaar("890123458830")
    res7 = Resident(
        resident_code="MHL-2024-005",
        branch_id=branch3.id,
        full_name="Gautam Nambiar",
        photograph_path="/static/images/avatars/avatar-5.svg",
        aadhaar_encrypted=enc7,
        aadhaar_last_four=last7,
        admission_date=today - timedelta(days=45),
        leaving_date=None,
        resident_status=ResidentStatus.ACTIVE
    )

    # Branch 4 (Deactivated) Resident - Historical only (Status=LEFT, 0 active)
    enc8, last8 = get_enc_aadhaar("901234569901")
    res8 = Resident(
        resident_code="MHL-2023-014",
        branch_id=branch4.id,
        full_name="Dinesh Karthik",
        photograph_path="/static/images/avatars/avatar-12.svg",
        aadhaar_encrypted=enc8,
        aadhaar_last_four=last8,
        admission_date=today - timedelta(days=365),
        leaving_date=today - timedelta(days=40),
        resident_status=ResidentStatus.LEFT
    )

    db.session.add_all([res1, res2, res3, res4, res5, res6, res7, res8])
    db.session.flush()

    # 3. Create Sample Payments
    payments = [
        # Branch 1 Payments
        Payment(
            resident_id=res1.id,
            branch_id=branch1.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=12000.00,
            payment_date=today - timedelta(days=180),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374101",
            notes="Initial deposit paid"
        ),
        Payment(
            resident_id=res1.id,
            branch_id=branch1.id,
            payment_type=PaymentType.RENT,
            amount=8500.00,
            payment_date=today - timedelta(days=5),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference="NEFT/882910293811",
            notes="Current month rent"
        ),
        Payment(
            resident_id=res2.id,
            branch_id=branch1.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=12000.00,
            payment_date=today - timedelta(days=120),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            transaction_reference="CASH-DEP-002",
            notes="Security deposit received"
        ),
        Payment(
            resident_id=res2.id,
            branch_id=branch1.id,
            payment_type=PaymentType.RENT,
            amount=8500.00,
            payment_date=today - timedelta(days=2),
            payment_status=PaymentStatus.PENDING,
            payment_method=None,
            transaction_reference=None,
            notes="Pending rent invoice"
        ),
        Payment(
            resident_id=res3.id,
            branch_id=branch1.id,
            payment_type=PaymentType.RENT,
            amount=8500.00,
            payment_date=today - timedelta(days=35),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374109",
            notes="Final settlement rent"
        ),

        # Branch 2 Payments
        Payment(
            resident_id=res4.id,
            branch_id=branch2.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=15000.00,
            payment_date=today - timedelta(days=90),
            payment_status=PaymentStatus.PARTIAL,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374201",
            notes="Partial deposit paid (5000 pending)"
        ),
        Payment(
            resident_id=res4.id,
            branch_id=branch2.id,
            payment_type=PaymentType.RENT,
            amount=9500.00,
            payment_date=today - timedelta(days=10),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374202",
            notes="Monthly rent"
        ),
        Payment(
            resident_id=res5.id,
            branch_id=branch2.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=15000.00,
            payment_date=today - timedelta(days=15),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.BANK_TRANSFER,
            transaction_reference="IMPS/772910293822",
            notes="Full admission deposit"
        ),
        Payment(
            resident_id=res5.id,
            branch_id=branch2.id,
            payment_type=PaymentType.RENT,
            amount=9500.00,
            payment_date=today - timedelta(days=1),
            payment_status=PaymentStatus.PENDING,
            payment_method=None,
            transaction_reference=None,
            notes="Rent pending for new cycle"
        ),

        # Branch 3 Payments
        Payment(
            resident_id=res7.id,
            branch_id=branch3.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=14000.00,
            payment_date=today - timedelta(days=45),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374301",
            notes="Deposit received"
        ),
        Payment(
            resident_id=res7.id,
            branch_id=branch3.id,
            payment_type=PaymentType.RENT,
            amount=9000.00,
            payment_date=today - timedelta(days=12),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.UPI,
            transaction_reference="UPI/401928374302",
            notes="Rent paid"
        ),

        # Branch 4 (Deactivated) Historical Payment
        Payment(
            resident_id=res8.id,
            branch_id=branch4.id,
            payment_type=PaymentType.SECURITY_DEPOSIT,
            amount=11000.00,
            payment_date=today - timedelta(days=365),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            transaction_reference="CASH-LEGACY-014",
            notes="Historical deposit from deactivated branch"
        ),
        Payment(
            resident_id=res8.id,
            branch_id=branch4.id,
            payment_type=PaymentType.RENT,
            amount=8000.00,
            payment_date=today - timedelta(days=45),
            payment_status=PaymentStatus.PAID,
            payment_method=PaymentMethod.CASH,
            transaction_reference="CASH-LEGACY-015",
            notes="Historical final rent"
        ),
    ]

    db.session.add_all(payments)
    db.session.commit()
    return True
