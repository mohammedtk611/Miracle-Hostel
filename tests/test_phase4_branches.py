"""
Test Suite for Miracle Hostel Management Portal - Phase 4: Branch Management.
Tests:
1. Create a new branch.
2. Reject duplicate branch codes.
3. Edit branch details.
4. Deactivate a branch with active residents safeguard and clean deactivation.
5. Verify that branch records, residents, and payments are preserved (never deleted).
6. Verify that active branches appear in selectors.
7. Verify that deactivated branches do not appear in normal active selection.
8. Switch between branches on dashboard.
9. Verify consolidated dashboard statistics.
10. Verify branch-specific dashboard statistics.
11. Verify resident and payment branch foreign key associations remain intact.
12. Verify unauthorized users cannot access branch management.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, AuditLog,
    ResidentStatus, PaymentType, PaymentStatus, AuditAction
)
from app.services.seed_service import seed_database_sample_data
from app.services.dashboard_service import DashboardService


@pytest.fixture
def app():
    """Create test application context with memory SQLite DB and seed data."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        # Seed admin
        admin = Admin(email="admin", username="admin", is_active=True)
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

        # Seed sample branches, residents, and payments
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
        'email': 'admin',
        'password': '1234'
    }, follow_redirects=True)
    return c


# -----------------------------------------------------------------------------
# 1. ACCESS CONTROL TEST
# -----------------------------------------------------------------------------
def test_unauthorized_access_to_branch_management(client):
    """Verify unauthorized visitors cannot access branch management routes."""
    res_get = client.get('/branches', follow_redirects=False)
    assert res_get.status_code == 302
    assert '/auth/login' in res_get.headers['Location']

    res_post = client.post('/branches', data={'action': 'add'}, follow_redirects=False)
    assert res_post.status_code == 302
    assert '/auth/login' in res_post.headers['Location']


# -----------------------------------------------------------------------------
# 2. CREATE BRANCH & DUPLICATE REJECTION
# -----------------------------------------------------------------------------
def test_create_new_branch(auth_client, app):
    """Test creating a new branch with unique code and persistence in database."""
    res = auth_client.post('/branches', data={
        'action': 'add',
        'branch_name': 'North Shore - Ennore',
        'branch_code': 'BR-NS-05',
        'address': '55 Express Way, Ennore, Chennai 600057',
        'contact_number': '+91 98405 11223'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"successfully created and activated" in res.data

    with app.app_context():
        branch = Branch.query.filter_by(branch_code='BR-NS-05').first()
        assert branch is not None
        assert branch.branch_name == "North Shore - Ennore"
        assert branch.is_active is True

        # Verify audit log
        audit = AuditLog.query.filter_by(action=AuditAction.BRANCH_CREATE, entity_id=branch.id).first()
        assert audit is not None
        assert "BR-NS-05" in audit.description


def test_reject_duplicate_branch_code(auth_client, app):
    """Test rejection when attempting to create a branch with an already existing branch code."""
    # BR-AN-01 already exists in seed data
    res = auth_client.post('/branches', data={
        'action': 'add',
        'branch_name': 'Duplicate Code Test Branch',
        'branch_code': 'BR-AN-01',  # Duplicate!
        'address': '123 Fake Street',
        'contact_number': '+91 90000 00000'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"already exists" in res.data

    with app.app_context():
        # Count should still be 1 for BR-AN-01
        count = Branch.query.filter_by(branch_code='BR-AN-01').count()
        assert count == 1


# -----------------------------------------------------------------------------
# 3. EDIT BRANCH
# -----------------------------------------------------------------------------
def test_edit_branch_details(auth_client, app):
    """Test editing branch name, address, contact, and maintaining referential integrity."""
    with app.app_context():
        branch = Branch.query.filter_by(branch_code='BR-GD-03').first()
        branch_id = branch.id

    res = auth_client.post('/branches', data={
        'action': 'edit',
        'branch_id': str(branch_id),
        'branch_name': 'Green Valley - Guindy Hub',
        'branch_code': 'BR-GD-03',
        'address': '9, Industrial Estate Main Rd, Guindy, Chennai 600032',
        'contact_number': '+91 98403 99999'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"updated successfully" in res.data

    with app.app_context():
        updated = db.session.get(Branch, branch_id)
        assert updated.branch_name == "Green Valley - Guindy Hub"
        assert updated.contact_number == "+91 98403 99999"

        # Verify audit log
        audit = AuditLog.query.filter_by(action=AuditAction.BRANCH_UPDATE, entity_id=branch_id).first()
        assert audit is not None


# -----------------------------------------------------------------------------
# 4. DEACTIVATE BRANCH & ACTIVE RESIDENT SAFEGUARD
# -----------------------------------------------------------------------------
def test_deactivate_branch_blocked_when_active_residents_exist(auth_client, app):
    """Verify that deactivation is strictly blocked if the branch has active residents."""
    with app.app_context():
        branch1 = Branch.query.filter_by(branch_code='BR-AN-01').first()
        assert branch1.active_residents_count > 0
        branch_id = branch1.id

    res = auth_client.post('/branches', data={
        'action': 'toggle_status',
        'branch_id': str(branch_id),
        'new_status': 'deactivate'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Cannot deactivate" in res.data
    assert b"active resident" in res.data

    with app.app_context():
        branch = db.session.get(Branch, branch_id)
        # Branch must remain active!
        assert branch.is_active is True


def test_deactivate_branch_success_when_zero_active_residents(auth_client, app):
    """Test that a branch with zero active residents deactivates cleanly without deleting data."""
    # Create a branch with 0 residents
    with app.app_context():
        empty_branch = Branch(
            branch_name="Empty Branch",
            branch_code="BR-EMP-99",
            address="Empty Street",
            contact_number="+91 98000 00000",
            is_active=True
        )
        db.session.add(empty_branch)
        db.session.commit()
        branch_id = empty_branch.id

    res = auth_client.post('/branches', data={
        'action': 'toggle_status',
        'branch_id': str(branch_id),
        'new_status': 'deactivate'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"deactivated successfully" in res.data

    with app.app_context():
        branch = db.session.get(Branch, branch_id)
        assert branch.is_active is False

        # Test reactivating it
        res_act = auth_client.post('/branches', data={
            'action': 'toggle_status',
            'branch_id': str(branch_id),
            'new_status': 'activate'
        }, follow_redirects=True)
        assert res_act.status_code == 200
        assert b"reactivated successfully" in res_act.data
        assert branch.is_active is True


# -----------------------------------------------------------------------------
# 5. DATA PRESERVATION & RELATIONSHIPS
# -----------------------------------------------------------------------------
def test_branch_deactivation_preserves_historical_records(app):
    """Verify that deactivating a branch preserves its residents and payment ledgers."""
    with app.app_context():
        # Branch 4 (BR-PR-04) is deactivated in seed data
        deact_branch = Branch.query.filter_by(branch_code='BR-PR-04').first()
        assert deact_branch is not None
        assert deact_branch.is_active is False

        # It must still retain its residents and payment records!
        residents_count = deact_branch.residents.count()
        assert residents_count > 0, "Deactivated branch must retain historical residents"

        payments_count = deact_branch.payments.count()
        assert payments_count > 0, "Deactivated branch must retain historical payment ledgers"

        for p in deact_branch.payments:
            assert p.branch_id == deact_branch.id
            assert p.resident is not None


# -----------------------------------------------------------------------------
# 6. ACTIVE SELECTOR & HIDING DEACTIVATED BRANCHES
# -----------------------------------------------------------------------------
def test_active_branches_selector_and_deactivated_hidden(auth_client):
    """Verify that active branches appear in selectors and deactivated branches are hidden from new admissions."""
    # 1. Topbar active branches injection
    res_dash = auth_client.get('/dashboard')
    assert res_dash.status_code == 200
    assert b"Main Branch - Anna Nagar" in res_dash.data
    assert b"City Campus - OMR IT Corridor" in res_dash.data
    assert b"Green Valley - Guindy" in res_dash.data

    # 2. Add Resident page should only show active branches
    res_add = auth_client.get('/residents/add')
    assert res_add.status_code == 200
    assert b"Main Branch - Anna Nagar" in res_add.data
    # Deactivated branch must NOT be an option for new admissions!
    assert b"BR-PR-04" not in res_add.data


# -----------------------------------------------------------------------------
# 7. DASHBOARD BRANCH FILTERING & STATISTICS
# -----------------------------------------------------------------------------
def test_dashboard_consolidated_statistics(auth_client, app):
    """Verify consolidated dashboard statistics across all branches."""
    res = auth_client.get('/dashboard?branch=all')
    assert res.status_code == 200
    assert b"Consolidated Overview" in res.data

    with app.app_context():
        stats = DashboardService.get_dashboard_stats('all')
        assert stats['is_all_branches'] is True
        assert stats['total_residents'] == 8
        assert stats['active_residents'] == 5
        assert stats['left_residents'] == 3
        assert stats['total_collection'] == 107500.0


def test_dashboard_branch_specific_statistics(auth_client, app):
    """Verify individual branch filtering updates statistics and recent records."""
    with app.app_context():
        branch1 = Branch.query.filter_by(branch_code='BR-AN-01').first()
        b1_id = branch1.id

    res = auth_client.get(f'/dashboard?branch={b1_id}')
    assert res.status_code == 200
    assert b"Main Branch - Anna Nagar" in res.data

    with app.app_context():
        stats = DashboardService.get_dashboard_stats(b1_id)
        assert stats['is_all_branches'] is False
        assert stats['branch_name'] == "Main Branch - Anna Nagar"
        assert stats['total_residents'] == 3
        assert stats['active_residents'] == 2
        assert stats['left_residents'] == 1
        assert stats['pending_rent_amount'] == 8500.0
        assert stats['total_collection'] == 41000.0

        # Verify recent admissions are only for branch 1
        admissions = DashboardService.get_recent_admissions(b1_id)
        for a in admissions:
            assert a['branch_code'] == 'BR-AN-01'

        # Verify recent payments are only for branch 1
        payments = DashboardService.get_recent_payments(b1_id)
        for p in payments:
            assert p['branch_name'] == 'Main Branch - Anna Nagar'


# -----------------------------------------------------------------------------
# 8. BRANCH DIRECTORY SEARCH & STATUS FILTERING
# -----------------------------------------------------------------------------
def test_branch_directory_search_and_filters(auth_client):
    """Verify search by name/code and active/inactive status filtering."""
    # Search by code: BR-OMR
    res_search = auth_client.get('/branches?search=OMR')
    assert res_search.status_code == 200
    table_search = res_search.data.split(b'<tbody>')[1].split(b'</tbody>')[0]
    assert b"BR-OMR-02" in table_search
    assert b"BR-AN-01" not in table_search

    # Filter active only
    res_active = auth_client.get('/branches?status=active')
    assert res_active.status_code == 200
    table_active = res_active.data.split(b'<tbody>')[1].split(b'</tbody>')[0]
    assert b"BR-AN-01" in table_active
    assert b"BR-PR-04" not in table_active  # Inactive branch filtered out of table

    # Filter inactive only
    res_inactive = auth_client.get('/branches?status=inactive')
    assert res_inactive.status_code == 200
    table_inactive = res_inactive.data.split(b'<tbody>')[1].split(b'</tbody>')[0]
    assert b"BR-PR-04" in table_inactive
    assert b"BR-AN-01" not in table_inactive  # Active branch filtered out of table


# -----------------------------------------------------------------------------
# 9. TOTAL BEDS AVAILABLE & REAL-TIME OCCUPANCY (GREEN/YELLOW) TESTS
# -----------------------------------------------------------------------------
def test_branch_total_beds_and_availability(auth_client, app):
    """Verify total beds configuration and real-time available beds calculation."""
    res = auth_client.post('/branches', data={
        'action': 'add',
        'branch_name': 'Horizon Residency',
        'branch_code': 'BR-HR-07',
        'address': '99 Beach Rd, Chennai 600041',
        'contact_number': '+91 98409 99887',
        'total_beds': '25'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        b = Branch.query.filter_by(branch_code='BR-HR-07').first()
        assert b is not None
        assert b.total_beds == 25
        assert b.occupied_beds == 0
        assert b.available_beds == 25
        assert b.occupancy_rate == 0.0


def test_branch_distribution_real_time_occupancy_and_notice_period(auth_client, app):
    """
    Verify real-time bed distribution calculation with:
    - Green segment for staying residents.
    - Yellow segment for residents with notice period leaving next month.
    """
    with app.app_context():
        distribution = DashboardService.get_branch_distribution()
        assert len(distribution) > 0

        # Branch 1 in seed data has 2 active residents, one of which has notice_date in next month
        b1_dist = next((item for item in distribution if item['branch_code'] == 'BR-AN-01'), None)
        assert b1_dist is not None
        assert b1_dist['total_beds'] == 10
        assert b1_dist['occupied_count'] == 2
        assert b1_dist['available_beds'] == 8
        assert b1_dist['staying_count'] == 1
        assert b1_dist['leaving_count'] == 1
        assert b1_dist['staying_pct'] == 10.0
        assert b1_dist['leaving_pct'] == 10.0
        assert b1_dist['occupancy_pct'] == 20.0

    # Also verify dashboard HTML contains the real-time elements synced to Image 3
    dash_res = auth_client.get('/dashboard')
    assert dash_res.status_code == 200
    html = dash_res.data.decode('utf-8')
    assert 'Real-Time Bed Occupancy' in html
    assert 'bg-success' in html
    assert 'bg-warning' in html
    assert 'Free' in html
    assert 'd-none d-md-table-cell' in html  # Admission Date hidden on mobile


def test_branch_distribution_active_vs_leaving_transition(auth_client, app):
    """
    Verify:
    1. Active resident is counted as Stay (green).
    2. Marked for leaving resident is counted as Notice (yellow).
    3. Retained resident immediately reverts back to Stay (green).
    """
    with app.app_context():
        # Get Branch 2 (OMR Corridor) which has 2 active residents without notice in seed data
        b2 = Branch.query.filter_by(branch_code='BR-OMR-02').first()
        assert b2 is not None

        # Check initial distribution: all active residents are in staying_count
        dist = next(item for item in DashboardService.get_branch_distribution() if item['branch_code'] == 'BR-OMR-02')
        assert dist['staying_count'] == 2
        assert dist['leaving_count'] == 0

        # Mark 1 resident for leaving
        r1 = b2.residents.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        r_code = r1.resident_code

    # Mark as leaving via POST
    res = auth_client.post(f'/residents/{r_code}/mark-leaving', follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        dist = next(item for item in DashboardService.get_branch_distribution() if item['branch_code'] == 'BR-OMR-02')
        assert dist['staying_count'] == 1
        assert dist['leaving_count'] == 1

    # Retain the resident back to ACTIVE
    res2 = auth_client.post(f'/residents/{r_code}/retain', follow_redirects=True)
    assert res2.status_code == 200

    with app.app_context():
        dist = next(item for item in DashboardService.get_branch_distribution() if item['branch_code'] == 'BR-OMR-02')
        assert dist['staying_count'] == 2
        assert dist['leaving_count'] == 0
        r_retained = Resident.query.filter_by(resident_code=r_code).first()
        assert r_retained.resident_status == ResidentStatus.ACTIVE
        assert r_retained.leaving_date is None
        assert r_retained.notice_date is None


