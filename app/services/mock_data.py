"""
Mock Demonstration Service for Miracle Hostel (Phase 1 & Phase 2 UI Development).

IMPORTANT ARCHITECTURAL NOTE:
This module contains illustrative demonstration datasets used exclusively to showcase 
the complete UI interactions, branch filtering, responsive tables, and visual states 
prior to Phase 3 database persistence and authentication integration.
Mock data is strictly decoupled from the SQLAlchemy PostgreSQL models.
"""
from datetime import date, timedelta
from app.utils.helpers import calculate_retention_info

TODAY = date.today()

# -------------------------------------------------------------------------
# 1. BRANCHES DATASET
# -------------------------------------------------------------------------
MOCK_BRANCHES = [
    {
        'id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'address': '14, 2nd Avenue, Anna Nagar East, Chennai 600102',
        'contact_number': '+91 98401 23456',
        'is_active': True,
        'created_at': '2023-01-10',
        'total_residents_count': 52,
        'active_residents_count': 44,
        'left_residents_count': 8,
    },
    {
        'id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'branch_code': 'BR-OMR-02',
        'address': 'Plot 88, Rajiv Gandhi Salai, Thoraipakkam, Chennai 600097',
        'contact_number': '+91 98402 34567',
        'is_active': True,
        'created_at': '2023-04-15',
        'total_residents_count': 42,
        'active_residents_count': 37,
        'left_residents_count': 5,
    },
    {
        'id': 3,
        'branch_name': 'Green Valley - Guindy',
        'branch_code': 'BR-GD-03',
        'address': '7, Industrial Estate Main Rd, Guindy, Chennai 600032',
        'contact_number': '+91 98403 45678',
        'is_active': True,
        'created_at': '2023-08-01',
        'total_residents_count': 31,
        'active_residents_count': 28,
        'left_residents_count': 3,
    },
    {
        'id': 4,
        'branch_name': 'West End - Porur (Deactivated)',
        'branch_code': 'BR-PR-04',
        'address': '22, Mount-Poonamallee High Rd, Porur, Chennai 600116',
        'contact_number': '+91 98404 56789',
        'is_active': False,
        'created_at': '2023-02-20',
        'total_residents_count': 16,
        'active_residents_count': 0,
        'left_residents_count': 16,
    }
]

# -------------------------------------------------------------------------
# 2. RESIDENTS DATASET
# -------------------------------------------------------------------------
MOCK_RESIDENTS = [
    {
        'id': 1,
        'resident_code': 'MHL-2024-001',
        'full_name': 'Aravind Krishnan',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'photograph_path': '/static/images/avatars/avatar-1.svg',
        'aadhaar_last_four': '8492',
        'masked_aadhaar': 'XXXX-XXXX-8492',
        'admission_date': TODAY - timedelta(days=220),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 98765 43210',
        'emergency_contact': '+91 98765 11111 (Father)',
        'room_number': 'Room 204 - Bed A',
        'security_deposit': 12000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 8500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 59500.00,
    },
    {
        'id': 2,
        'resident_code': 'MHL-2024-002',
        'full_name': 'Pooja Sundaram',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'photograph_path': '/static/images/avatars/avatar-2.svg',
        'aadhaar_last_four': '3190',
        'masked_aadhaar': 'XXXX-XXXX-3190',
        'admission_date': TODAY - timedelta(days=180),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 97890 12345',
        'emergency_contact': '+91 97890 22222 (Mother)',
        'room_number': 'Room 102 - Bed B',
        'security_deposit': 12000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 8500.00,
        'rent_status': 'PENDING',
        'outstanding_rent': 8500.00,
        'total_rent_paid': 42500.00,
    },
    {
        'id': 3,
        'resident_code': 'MHL-2024-003',
        'full_name': 'Rahul Verma',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'branch_code': 'BR-OMR-02',
        'photograph_path': '/static/images/avatars/avatar-3.svg',
        'aadhaar_last_four': '6721',
        'masked_aadhaar': 'XXXX-XXXX-6721',
        'admission_date': TODAY - timedelta(days=140),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 94440 98765',
        'emergency_contact': '+91 94440 33333 (Brother)',
        'room_number': 'Room 305 - Bed A',
        'security_deposit': 15000.00,
        'deposit_status': 'PARTIAL',
        'monthly_rent': 9500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 38000.00,
    },
    {
        'id': 4,
        'resident_code': 'MHL-2024-004',
        'full_name': 'Deepika Narayanan',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'branch_code': 'BR-OMR-02',
        'photograph_path': '/static/images/avatars/avatar-4.svg',
        'aadhaar_last_four': '5514',
        'masked_aadhaar': 'XXXX-XXXX-5514',
        'admission_date': TODAY - timedelta(days=95),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 91234 56789',
        'emergency_contact': '+91 91234 44444 (Father)',
        'room_number': 'Room 201 - Bed B',
        'security_deposit': 15000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 9500.00,
        'rent_status': 'PARTIAL',
        'outstanding_rent': 3500.00,
        'total_rent_paid': 25000.00,
    },
    {
        'id': 5,
        'resident_code': 'MHL-2024-005',
        'full_name': 'Karthik Raja',
        'branch_id': 3,
        'branch_name': 'Green Valley - Guindy',
        'branch_code': 'BR-GD-03',
        'photograph_path': '/static/images/avatars/avatar-5.svg',
        'aadhaar_last_four': '9044',
        'masked_aadhaar': 'XXXX-XXXX-9044',
        'admission_date': TODAY - timedelta(days=45),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 98840 11223',
        'emergency_contact': '+91 98840 55555 (Uncle)',
        'room_number': 'Room 108 - Bed A',
        'security_deposit': 10000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 7500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 15000.00,
    },
    {
        'id': 6,
        'resident_code': 'MHL-2024-006',
        'full_name': 'Sneha Kulkarni',
        'branch_id': 3,
        'branch_name': 'Green Valley - Guindy',
        'branch_code': 'BR-GD-03',
        'photograph_path': '/static/images/avatars/avatar-6.svg',
        'aadhaar_last_four': '1288',
        'masked_aadhaar': 'XXXX-XXXX-1288',
        'admission_date': TODAY - timedelta(days=12),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 96001 77889',
        'emergency_contact': '+91 96001 66666 (Mother)',
        'room_number': 'Room 110 - Bed B',
        'security_deposit': 10000.00,
        'deposit_status': 'PENDING',
        'monthly_rent': 7500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 7500.00,
    },
    {
        'id': 7,
        'resident_code': 'MHL-2024-007',
        'full_name': 'Vikramaditya Sen',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'photograph_path': '/static/images/avatars/avatar-7.svg',
        'aadhaar_last_four': '4401',
        'masked_aadhaar': 'XXXX-XXXX-4401',
        'admission_date': TODAY - timedelta(days=6),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 98411 99001',
        'emergency_contact': '+91 98411 77777 (Father)',
        'room_number': 'Room 301 - Bed A',
        'security_deposit': 12000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 8500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 8500.00,
    },
    {
        'id': 8,
        'resident_code': 'MHL-2024-008',
        'full_name': 'Ananya Roy',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'branch_code': 'BR-OMR-02',
        'photograph_path': '/static/images/avatars/avatar-8.svg',
        'aadhaar_last_four': '7823',
        'masked_aadhaar': 'XXXX-XXXX-7823',
        'admission_date': TODAY - timedelta(days=2),
        'leaving_date': None,
        'resident_status': 'ACTIVE',
        'phone_number': '+91 99402 33445',
        'emergency_contact': '+91 99402 88888 (Guardian)',
        'room_number': 'Room 202 - Bed A',
        'security_deposit': 15000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 9500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 9500.00,
    },

    # --- PREVIOUS RESIDENTS (Status: LEFT) ---
    {
        'id': 9,
        'resident_code': 'MHL-2023-089',
        'full_name': 'Siddharth Menon',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'photograph_path': '/static/images/avatars/avatar-9.svg',
        'aadhaar_last_four': '1192',
        'masked_aadhaar': 'XXXX-XXXX-1192',
        'admission_date': TODAY - timedelta(days=340),
        'leaving_date': TODAY - timedelta(days=8),  # Left 8 days ago -> 22 days left (Normal)
        'resident_status': 'LEFT',
        'phone_number': '+91 98405 66778',
        'emergency_contact': '+91 98405 99999 (Father)',
        'room_number': 'Vacated Room 204',
        'security_deposit': 12000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 8500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 85000.00,
    },
    {
        'id': 10,
        'resident_code': 'MHL-2023-074',
        'full_name': 'Meera Subramanian',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'branch_code': 'BR-OMR-02',
        'photograph_path': '/static/images/avatars/avatar-10.svg',
        'aadhaar_last_four': '6645',
        'masked_aadhaar': 'XXXX-XXXX-6645',
        'admission_date': TODAY - timedelta(days=280),
        'leaving_date': TODAY - timedelta(days=25),  # Left 25 days ago -> 5 days left (Approaching Deadline!)
        'resident_status': 'LEFT',
        'phone_number': '+91 98406 77889',
        'emergency_contact': '+91 98406 00000 (Sister)',
        'room_number': 'Vacated Room 105',
        'security_deposit': 15000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 9500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 76000.00,
    },
    {
        'id': 11,
        'resident_code': 'MHL-2023-061',
        'full_name': 'Gautam Nambiar',
        'branch_id': 3,
        'branch_name': 'Green Valley - Guindy',
        'branch_code': 'BR-GD-03',
        'photograph_path': '/static/images/avatars/avatar-11.svg',
        'aadhaar_last_four': '8830',
        'masked_aadhaar': 'XXXX-XXXX-8830',
        'admission_date': TODAY - timedelta(days=210),
        'leaving_date': TODAY - timedelta(days=28),  # Left 28 days ago -> 2 days left (Approaching Deadline!)
        'resident_status': 'LEFT',
        'phone_number': '+91 98407 88990',
        'emergency_contact': '+91 98407 12121 (Father)',
        'room_number': 'Vacated Room 112',
        'security_deposit': 10000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 7500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 45000.00,
    },
    {
        'id': 12,
        'resident_code': 'MHL-2023-042',
        'full_name': 'Divya Chandran',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'branch_code': 'BR-AN-01',
        'photograph_path': '/static/images/avatars/avatar-12.svg',
        'aadhaar_last_four': '2941',
        'masked_aadhaar': 'XXXX-XXXX-2941',
        'admission_date': TODAY - timedelta(days=365),
        'leaving_date': TODAY - timedelta(days=36),  # Left 36 days ago -> Overdue / Eligible for deletion!
        'resident_status': 'LEFT',
        'phone_number': '+91 98408 99001',
        'emergency_contact': '+91 98408 34343 (Mother)',
        'room_number': 'Vacated Room 303',
        'security_deposit': 12000.00,
        'deposit_status': 'PAID',
        'monthly_rent': 8500.00,
        'rent_status': 'PAID',
        'outstanding_rent': 0.00,
        'total_rent_paid': 93500.00,
    }
]

# Enrich residents with retention data
for r in MOCK_RESIDENTS:
    if r['resident_status'] == 'LEFT':
        retention = calculate_retention_info(r['leaving_date'])
        r['retention'] = retention
    else:
        r['retention'] = None

# -------------------------------------------------------------------------
# 3. PAYMENTS DATASET
# -------------------------------------------------------------------------
MOCK_PAYMENTS = [
    {
        'id': 101,
        'payment_id': 'PAY-2024-00101',
        'resident_id': 8,
        'resident_name': 'Ananya Roy',
        'resident_code': 'MHL-2024-008',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'payment_type': 'SECURITY_DEPOSIT',
        'amount': 15000.00,
        'payment_date': TODAY - timedelta(days=2),
        'payment_status': 'PAID',
        'payment_method': 'UPI',
        'transaction_reference': 'UPI/428901238912',
        'notes': 'Full security deposit received upon admission.'
    },
    {
        'id': 102,
        'payment_id': 'PAY-2024-00102',
        'resident_id': 8,
        'resident_name': 'Ananya Roy',
        'resident_code': 'MHL-2024-008',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'payment_type': 'RENT',
        'amount': 9500.00,
        'payment_date': TODAY - timedelta(days=2),
        'payment_status': 'PAID',
        'payment_method': 'UPI',
        'transaction_reference': 'UPI/428901238913',
        'notes': 'Initial monthly rent for first cycle.'
    },
    {
        'id': 103,
        'payment_id': 'PAY-2024-00103',
        'resident_id': 7,
        'resident_name': 'Vikramaditya Sen',
        'resident_code': 'MHL-2024-007',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'payment_type': 'SECURITY_DEPOSIT',
        'amount': 12000.00,
        'payment_date': TODAY - timedelta(days=6),
        'payment_status': 'PAID',
        'payment_method': 'BANK_TRANSFER',
        'transaction_reference': 'NEFT/HDFC00012489',
        'notes': 'Online transfer verified with bank ledger.'
    },
    {
        'id': 104,
        'payment_id': 'PAY-2024-00104',
        'resident_id': 7,
        'resident_name': 'Vikramaditya Sen',
        'resident_code': 'MHL-2024-007',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'payment_type': 'RENT',
        'amount': 8500.00,
        'payment_date': TODAY - timedelta(days=6),
        'payment_status': 'PAID',
        'payment_method': 'BANK_TRANSFER',
        'transaction_reference': 'NEFT/HDFC00012490',
        'notes': 'Current month rent received in advance.'
    },
    {
        'id': 105,
        'payment_id': 'PAY-2024-00105',
        'resident_id': 6,
        'resident_name': 'Sneha Kulkarni',
        'resident_code': 'MHL-2024-006',
        'branch_id': 3,
        'branch_name': 'Green Valley - Guindy',
        'payment_type': 'SECURITY_DEPOSIT',
        'amount': 10000.00,
        'payment_date': TODAY - timedelta(days=12),
        'payment_status': 'PENDING',
        'payment_method': 'CASH',
        'transaction_reference': None,
        'notes': 'Resident requested 10 days grace period to clear deposit.'
    },
    {
        'id': 106,
        'payment_id': 'PAY-2024-00106',
        'resident_id': 6,
        'resident_name': 'Sneha Kulkarni',
        'resident_code': 'MHL-2024-006',
        'branch_id': 3,
        'branch_name': 'Green Valley - Guindy',
        'payment_type': 'RENT',
        'amount': 7500.00,
        'payment_date': TODAY - timedelta(days=12),
        'payment_status': 'PAID',
        'payment_method': 'CASH',
        'transaction_reference': 'RCPT/2024-889',
        'notes': 'First month rent paid in cash at counter.'
    },
    {
        'id': 107,
        'payment_id': 'PAY-2024-00107',
        'resident_id': 4,
        'resident_name': 'Deepika Narayanan',
        'resident_code': 'MHL-2024-004',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'payment_type': 'RENT',
        'amount': 6000.00,
        'payment_date': TODAY - timedelta(days=15),
        'payment_status': 'PARTIAL',
        'payment_method': 'UPI',
        'transaction_reference': 'UPI/428119028471',
        'notes': 'Partial payment of 6,000 against monthly rent of 9,500. Outstanding: 3,500.'
    },
    {
        'id': 108,
        'payment_id': 'PAY-2024-00108',
        'resident_id': 3,
        'resident_name': 'Rahul Verma',
        'resident_code': 'MHL-2024-003',
        'branch_id': 2,
        'branch_name': 'City Campus - OMR IT Corridor',
        'payment_type': 'SECURITY_DEPOSIT',
        'amount': 10000.00,
        'payment_date': TODAY - timedelta(days=140),
        'payment_status': 'PARTIAL',
        'payment_method': 'BANK_TRANSFER',
        'transaction_reference': 'IMPS/421100984',
        'notes': 'Partial deposit of 10,000 paid. Remaining balance 5,000 pending.'
    },
    {
        'id': 109,
        'payment_id': 'PAY-2024-00109',
        'resident_id': 2,
        'resident_name': 'Pooja Sundaram',
        'resident_code': 'MHL-2024-002',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'payment_type': 'RENT',
        'amount': 8500.00,
        'payment_date': TODAY - timedelta(days=20),
        'payment_status': 'PENDING',
        'payment_method': 'UPI',
        'transaction_reference': None,
        'notes': 'Overdue monthly rent reminder sent to resident.'
    },
    {
        'id': 110,
        'payment_id': 'PAY-2024-00110',
        'resident_id': 1,
        'resident_name': 'Aravind Krishnan',
        'resident_code': 'MHL-2024-001',
        'branch_id': 1,
        'branch_name': 'Main Branch - Anna Nagar',
        'payment_type': 'RENT',
        'amount': 8500.00,
        'payment_date': TODAY - timedelta(days=22),
        'payment_status': 'PAID',
        'payment_method': 'UPI',
        'transaction_reference': 'UPI/427901198231',
        'notes': 'Monthly rent paid on time via Google Pay.'
    }
]


# -------------------------------------------------------------------------
# 4. QUERY HELPER FUNCTIONS
# -------------------------------------------------------------------------
def get_branches(active_only=False):
    """Return all branches or active only."""
    if active_only:
        return [b for b in MOCK_BRANCHES if b['is_active']]
    return MOCK_BRANCHES


def get_branch_by_id(branch_id):
    """Retrieve a branch by ID."""
    try:
        b_id = int(branch_id)
        for b in MOCK_BRANCHES:
            if b['id'] == b_id:
                return b
    except (ValueError, TypeError):
        pass
    return None


def get_residents(branch_id=None, status=None, search=None, deposit_status=None, rent_status=None):
    """
    Filter residents by branch, status, search string, and financial flags.
    """
    res = list(MOCK_RESIDENTS)

    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            res = [r for r in res if r['branch_id'] == b_id]
        except (ValueError, TypeError):
            pass

    if status and status != 'ALL':
        res = [r for r in res if r['resident_status'] == status]

    if deposit_status and deposit_status != 'ALL':
        res = [r for r in res if r['deposit_status'] == deposit_status]

    if rent_status and rent_status != 'ALL':
        res = [r for r in res if r['rent_status'] == rent_status]

    if search:
        s = search.lower().strip()
        res = [
            r for r in res
            if s in r['full_name'].lower()
            or s in r['resident_code'].lower()
            or s in r['masked_aadhaar'].lower()
            or s in r['room_number'].lower()
        ]

    return res


def get_resident_by_code(resident_code):
    """Retrieve resident details by unique resident code."""
    for r in MOCK_RESIDENTS:
        if r['resident_code'] == resident_code:
            return r
    return None


def get_resident_by_id(resident_id):
    """Retrieve resident by numeric ID."""
    try:
        rid = int(resident_id)
        for r in MOCK_RESIDENTS:
            if r['id'] == rid:
                return r
    except (ValueError, TypeError):
        pass
    return None


def get_resident_payments(resident_id):
    """Return all payment transactions associated with a resident."""
    try:
        rid = int(resident_id)
        return [p for p in MOCK_PAYMENTS if p['resident_id'] == rid]
    except (ValueError, TypeError):
        return []


def get_previous_residents(branch_id=None, search=None, urgency=None):
    """Retrieve residents who have left with retention policy details."""
    left_residents = [r for r in MOCK_RESIDENTS if r['resident_status'] == 'LEFT']

    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            left_residents = [r for r in left_residents if r['branch_id'] == b_id]
        except (ValueError, TypeError):
            pass

    if search:
        s = search.lower().strip()
        left_residents = [
            r for r in left_residents
            if s in r['full_name'].lower()
            or s in r['resident_code'].lower()
        ]

    if urgency and urgency != 'ALL':
        left_residents = [
            r for r in left_residents
            if r.get('retention', {}).get('urgency') == urgency
        ]

    return left_residents


def get_payments(branch_id=None, payment_type=None, status=None, search=None):
    """Retrieve payment records with multi-criteria filtering."""
    pmts = list(MOCK_PAYMENTS)

    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            pmts = [p for p in pmts if p['branch_id'] == b_id]
        except (ValueError, TypeError):
            pass

    if payment_type and payment_type != 'ALL':
        pmts = [p for p in pmts if p['payment_type'] == payment_type]

    if status and status != 'ALL':
        pmts = [p for p in pmts if p['payment_status'] == status]

    if search:
        s = search.lower().strip()
        pmts = [
            p for p in pmts
            if s in p['resident_name'].lower()
            or s in p['resident_code'].lower()
            or s in p['payment_id'].lower()
            or (p.get('transaction_reference') and s in p['transaction_reference'].lower())
        ]

    return pmts


def get_dashboard_stats(branch_id=None):
    """
    Calculate consolidated statistics across All Branches or for a selected branch.
    """
    # Active branches
    active_branches = [b for b in MOCK_BRANCHES if b['is_active']]

    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            branch = get_branch_by_id(b_id)
            if branch:
                # Specific branch statistics
                branch_residents = [r for r in MOCK_RESIDENTS if r['branch_id'] == b_id]
                branch_payments = [p for p in MOCK_PAYMENTS if p['branch_id'] == b_id]

                active_res = [r for r in branch_residents if r['resident_status'] == 'ACTIVE']
                left_res = [r for r in branch_residents if r['resident_status'] == 'LEFT']

                pending_deposits_count = sum(1 for r in active_res if r['deposit_status'] in ('PENDING', 'PARTIAL'))
                pending_deposits_amount = sum(
                    p['amount'] for p in branch_payments 
                    if p['payment_type'] == 'SECURITY_DEPOSIT' and p['payment_status'] in ('PENDING', 'PARTIAL')
                )
                if pending_deposits_amount == 0 and pending_deposits_count > 0:
                    pending_deposits_amount = 10000.00 * pending_deposits_count

                pending_rent_count = sum(1 for r in active_res if r['rent_status'] in ('PENDING', 'PARTIAL'))
                pending_rent_amount = sum(r['outstanding_rent'] for r in active_res)

                total_rent_collected = sum(
                    p['amount'] for p in branch_payments 
                    if p['payment_type'] == 'RENT' and p['payment_status'] == 'PAID'
                )
                total_deposits_collected = sum(
                    p['amount'] for p in branch_payments 
                    if p['payment_type'] == 'SECURITY_DEPOSIT' and p['payment_status'] == 'PAID'
                )

                # Total estimated collection scaled for the branch
                total_collection = total_rent_collected + total_deposits_collected + (branch['total_residents_count'] * 24000)

                return {
                    'branch_name': branch['branch_name'],
                    'branch_code': branch['branch_code'],
                    'is_all_branches': False,
                    'selected_branch_id': b_id,
                    'total_residents': branch['total_residents_count'],
                    'active_residents': branch['active_residents_count'],
                    'left_residents': branch['left_residents_count'],
                    'pending_deposits_count': pending_deposits_count,
                    'pending_deposits_amount': pending_deposits_amount,
                    'pending_rent_count': pending_rent_count,
                    'pending_rent_amount': pending_rent_amount,
                    'total_collection': total_collection,
                    'total_rent_collected': total_rent_collected + (branch['active_residents_count'] * 15000),
                    'total_deposits_collected': total_deposits_collected + (branch['active_residents_count'] * 12000),
                }
        except (ValueError, TypeError):
            pass

    # Consolidated across ALL Branches
    total_all_residents = sum(b['total_residents_count'] for b in MOCK_BRANCHES)
    total_active_residents = sum(b['active_residents_count'] for b in MOCK_BRANCHES)
    total_left_residents = sum(b['left_residents_count'] for b in MOCK_BRANCHES)

    active_res_all = [r for r in MOCK_RESIDENTS if r['resident_status'] == 'ACTIVE']
    pending_deposits_count = sum(1 for r in active_res_all if r['deposit_status'] in ('PENDING', 'PARTIAL'))
    pending_deposits_amount = 25000.00

    pending_rent_count = sum(1 for r in active_res_all if r['rent_status'] in ('PENDING', 'PARTIAL'))
    pending_rent_amount = sum(r['outstanding_rent'] for r in active_res_all)

    # Consolidated collections
    total_deposits_collected = 1320000.00
    total_rent_collected = 1940000.00
    total_collection = total_deposits_collected + total_rent_collected

    return {
        'branch_name': 'All Branches (Consolidated)',
        'branch_code': 'ALL',
        'is_all_branches': True,
        'selected_branch_id': 'all',
        'total_residents': total_all_residents,
        'active_residents': total_active_residents,
        'left_residents': total_left_residents,
        'pending_deposits_count': pending_deposits_count,
        'pending_deposits_amount': pending_deposits_amount,
        'pending_rent_count': pending_rent_count,
        'pending_rent_amount': pending_rent_amount,
        'total_collection': total_collection,
        'total_rent_collected': total_rent_collected,
        'total_deposits_collected': total_deposits_collected,
    }


def get_recent_admissions(branch_id=None, limit=5):
    """Retrieve most recently admitted residents."""
    residents = [r for r in MOCK_RESIDENTS if r['resident_status'] == 'ACTIVE']
    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            residents = [r for r in residents if r['branch_id'] == b_id]
        except (ValueError, TypeError):
            pass
    # Sort by admission date descending
    residents.sort(key=lambda r: r['admission_date'], reverse=True)
    return residents[:limit]


def get_recent_payments(branch_id=None, limit=6):
    """Retrieve most recent payment transactions."""
    pmts = list(MOCK_PAYMENTS)
    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            pmts = [p for p in pmts if p['branch_id'] == b_id]
        except (ValueError, TypeError):
            pass
    pmts.sort(key=lambda p: p['payment_date'], reverse=True)
    return pmts[:limit]


def get_branch_distribution():
    """Return resident distribution metrics per branch for dashboard progress meters."""
    distribution = []
    total_active = sum(b['active_residents_count'] for b in MOCK_BRANCHES if b['is_active']) or 1

    for b in MOCK_BRANCHES:
        pct = round((b['active_residents_count'] / total_active) * 100) if b['is_active'] else 0
        distribution.append({
            'branch_name': b['branch_name'],
            'branch_code': b['branch_code'],
            'is_active': b['is_active'],
            'active_count': b['active_residents_count'],
            'total_count': b['total_residents_count'],
            'percentage': pct,
        })
    return distribution

