"""
Test Suite for Miracle Hostel Management Portal - Complete Mobile Responsiveness Enhancement.
Verifies:
1. Viewport meta tag present across public and authenticated views.
2. Responsive CSS and JS loaded in base layout.
3. Mobile sidebar drawer elements (close button, hamburger button, backdrop).
4. Responsive table-to-card transformations (.table-portal-responsive and data-label attributes).
5. Quick Payment buttons touch target readiness.
6. Responsive layout structure in Dashboard, Directory, Add Resident, Resident Profile,
   Previous Residents, Payments, Branches, and Authentication screens.
7. Mobile JS drawer handlers (open, close, backdrop click, Escape key, auto-close on resize).
8. Mobile-first CSS breakpoint definitions and touch ergonomics (44px min targets).
"""
import os
import pytest
from app import create_app
from app.extensions import db
from app.models import Admin, Resident
from app.services.seed_service import seed_database_sample_data


@pytest.fixture
def app():
    """Create testing application context with in-memory DB and configured admin."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        admin = Admin(
            email="admin@123",
            username="admin",
            is_active=True
        )
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


def test_viewport_meta_tag_unauthenticated(client):
    """Verify viewport meta tag is present on unauthenticated login view."""
    login_res = client.get('/auth/login')
    assert login_res.status_code == 200
    assert b'<meta name="viewport" content="width=device-width, initial-scale=1.0">' in login_res.data


def test_viewport_meta_tag_authenticated(auth_client):
    """Verify viewport meta tag is present on authenticated dashboard view."""
    dash_res = auth_client.get('/dashboard')
    assert dash_res.status_code == 200
    assert b'<meta name="viewport" content="width=device-width, initial-scale=1.0">' in dash_res.data


def test_responsive_assets_included_in_base_template(auth_client):
    """Verify responsive.css and responsive JS hooks are properly referenced."""
    res = auth_client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'css/responsive.css' in html
    assert 'js/main.js' in html


def test_mobile_drawer_navigation_elements(auth_client):
    """Verify mobile navigation drawer buttons and container classes exist."""
    res = auth_client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Mobile menu hamburger trigger in topbar
    assert 'mobile-menu-btn' in html
    # Close button in sidebar
    assert 'sidebarMobileClose' in html
    assert 'sidebar-close-btn' in html
    # App sidebar container
    assert 'app-sidebar' in html
    # Branch selector in topbar
    assert 'topbar-branch-select' in html


def test_dashboard_responsive_kpis_and_recent_admissions(auth_client):
    """Verify dashboard KPI grid and recent admissions responsive table structure."""
    res = auth_client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # KPI stat card grid
    assert 'stat-card-grid' in html
    assert 'stat-card' in html

    # Recent admissions table
    assert 'table-portal-responsive' in html
    assert 'data-label="Resident"' in html
    assert 'data-label="Branch"' in html
    assert 'data-label="Admission"' in html
    assert 'data-label="Deposit"' in html
    assert 'data-label="Action"' in html


def test_resident_directory_responsive_table_and_labels(auth_client):
    """Verify resident directory table uses .table-portal-responsive and data-label attributes."""
    res = auth_client.get('/residents')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Table card transformation classes
    assert 'table-portal-responsive' in html
    assert 'data-label="Resident"' in html
    assert 'data-label="Branch"' in html
    assert 'data-label="Admission"' in html
    assert 'data-label="Deposit"' in html
    assert 'data-label="Rent"' in html
    assert 'data-label="Status"' in html
    assert 'data-label="Actions"' in html

    # Quick payment triggers preserved
    assert 'data-quick-payment' in html
    assert 'quickPaymentModal' in html

    # Filter toolbar
    assert 'filter-toolbar' in html


def test_resident_profile_responsive_ledger_and_cards(auth_client, app):
    """Verify resident profile contains responsive transaction history and action layout."""
    with app.app_context():
        res_obj = Resident.query.filter_by(resident_status='ACTIVE').first()
        res_code = res_obj.resident_code

    res = auth_client.get(f'/residents/{res_code}')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Transaction table card transformation
    assert 'table-portal-responsive' in html
    assert 'data-label="Payment ID"' in html
    assert 'data-label="Type"' in html
    assert 'data-label="Amount"' in html
    assert 'data-label="Date"' in html
    assert 'data-label="Status"' in html

    # Key modals present
    assert 'recordPaymentModal' in html
    assert 'generateRentModal' in html
    assert 'editResidentInfoModal' in html
    assert 'updatePhotoModal' in html


def test_previous_residents_responsive_table(auth_client):
    """Verify previous residents directory table uses responsive cards and retention labels."""
    res = auth_client.get('/residents/previous')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'table-portal-responsive' in html
    assert 'data-label="Resident ID"' in html
    assert 'data-label="Resident"' in html
    assert 'data-label="Branch"' in html
    assert 'data-label="Admission"' in html
    assert 'data-label="Leaving Date"' in html
    assert 'data-label="Balance"' in html
    assert 'data-label="Deadline"' in html
    assert 'data-label="Retention"' in html
    assert 'data-label="Actions"' in html


def test_payments_ledger_responsive_table_and_receipt(auth_client):
    """Verify payments module table has responsive labels and receipt modal."""
    res = auth_client.get('/payments')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'table-portal-responsive' in html
    assert 'data-label="Payment ID"' in html
    assert 'data-label="Resident"' in html
    assert 'data-label="Branch"' in html
    assert 'data-label="Type"' in html
    assert 'data-label="Amount"' in html
    assert 'data-label="Date"' in html
    assert 'data-label="Method"' in html
    assert 'data-label="Status"' in html
    assert 'data-label="Actions"' in html

    # Receipt slip modal
    assert 'receiptModal' in html
    assert 'printableReceipt' in html


def test_branches_management_responsive_table(auth_client):
    """Verify branches view has responsive card table structure."""
    res = auth_client.get('/branches')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'table-portal-responsive' in html
    assert 'data-label="Branch"' in html
    assert 'data-label="Address"' in html
    assert 'data-label="Contact"' in html
    assert 'data-label="Active"' in html
    assert 'data-label="Total Residents"' in html
    assert 'data-label="Status"' in html
    assert 'data-label="Actions"' in html


def test_add_resident_responsive_form(auth_client):
    """Verify Add Resident form has responsive action button ordering."""
    res = auth_client.get('/residents/add')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Full Aadhaar input with security notice
    assert 'data-aadhaar-input' in html
    assert 'security-notice' in html

    # Button stack classes
    assert 'd-flex flex-column flex-sm-row' in html


def test_login_and_auth_screens_responsive(client):
    """Verify login screen includes responsive styling classes."""
    res = client.get('/auth/login')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'login-container' in html
    assert 'card-portal' in html


def test_responsive_css_rules_and_breakpoints():
    """Verify responsive.css file contains all required breakpoint rules and touch targets."""
    css_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'css', 'responsive.css')
    assert os.path.isfile(css_path)

    with open(css_path, 'r', encoding='utf-8') as f:
        css = f.read()

    # Touch targets: 44px minimum for mobile inputs and buttons
    assert 'min-height: 44px' in css
    # iOS auto-zoom prevention: font-size 16px
    assert 'font-size: 16px !important' in css
    # Breakpoint media queries
    assert '@media (max-width: 991.98px)' in css
    assert '@media (max-width: 767.98px)' in css
    assert '@media (max-width: 375px)' in css
    assert '@media (min-width: 376px) and (max-width: 767.98px)' in css
    assert '@media (min-width: 768px) and (max-width: 1023.98px)' in css

    # Table to card transformation
    assert '.table-portal-responsive' in css
    assert 'content: attr(data-label)' in css

    # Off-canvas sidebar
    assert '.app-sidebar.show-mobile' in css
    assert 'sidebar-backdrop' in css


def test_main_js_mobile_drawer_implementation():
    """Verify main.js contains mobile drawer event handlers and resize listeners."""
    js_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'js', 'main.js')
    assert os.path.isfile(js_path)

    with open(js_path, 'r', encoding='utf-8') as f:
        js = f.read()

    assert 'openMobileSidebar' in js
    assert 'closeMobileSidebar' in js
    assert 'Escape' in js
    assert 'sidebarMobileClose' in js
    assert 'resize' in js
