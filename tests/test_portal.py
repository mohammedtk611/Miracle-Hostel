"""
Comprehensive Test Suite for Miracle Hostel Management Portal.
Phase 3 Authentication & Security Testing:
- Successful login using ID 'admin' and password '1234'
- Invalid credentials handling
- Session ends when website/browser is closed (non-permanent session cookie)
- Secure logout and session clearing
- Unauthorized route access & login redirection
- Password change in Settings
- Secure password recovery workflow with one-time tokens
- Server-side CSRF protection enforcement
- Sliding-window login rate limiting with LoginLog
- Audit logging of administrative operations without sensitive credential leakage
- File upload security (extension, MIME magic bytes, and size validation)
"""
import io
import pytest
from datetime import date, timedelta
from flask import session
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, AuditLog,
    LoginLog, PasswordResetToken, LoginStatus, AuditAction, ResidentStatus
)
from app.services.aadhaar_service import AadhaarSecurityService
from app.services.audit_service import AuditService
from app.services.seed_service import seed_database_sample_data
from app.utils.helpers import calculate_retention_info
from app.utils.file_security import validate_image_upload, verify_image_magic_bytes
from werkzeug.datastructures import FileStorage


@pytest.fixture
def app():
    """Create testing application context with in-memory DB and configured admin."""
    test_app = create_app('testing')
    with test_app.app_context():
        db.create_all()
        # Seed test admin account with requested credentials: admin / 1234
        admin = Admin(
            email="admin",
            username="admin",
            is_active=True
        )
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

        # Seed sample data so residents like MHL-2024-001 exist
        seed_database_sample_data(force=True)

        yield test_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Client authenticated as the test administrator."""
    c = app.test_client()
    c.post('/auth/login', data={
        'email': 'admin',
        'password': '1234'
    }, follow_redirects=True)
    return c


# -----------------------------------------------------------------------------
# 1. ROUTE PROTECTION & UNAUTHORIZED ACCESS TESTS
# -----------------------------------------------------------------------------
def test_unauthorized_route_access(client):
    """Verify that unauthenticated users cannot access protected routes and are redirected to login."""
    protected_routes = [
        ('/', 'Dashboard Root'),
        ('/dashboard', 'Dashboard View'),
        ('/residents', 'Resident Directory'),
        ('/residents/add', 'Add Resident'),
        ('/residents/previous', 'Previous Residents'),
        ('/residents/MHL-2024-001', 'Resident Profile'),
        ('/payments', 'Payments Interface'),
        ('/branches', 'Branch Management'),
        ('/settings', 'Settings View'),
    ]

    for endpoint, name in protected_routes:
        res = client.get(endpoint, follow_redirects=False)
        assert res.status_code == 302, f"Expected 302 redirect for {endpoint} ({name}), got {res.status_code}"
        assert '/auth/login' in res.headers['Location'], f"Expected redirect to /auth/login for {endpoint}"


def test_login_page_renders_for_unauthenticated(client):
    """Verify that unauthenticated visitors can view the login page."""
    res = client.get('/auth/login')
    assert res.status_code == 200
    assert b"Sign In to Portal" in res.data
    assert b"Administrator Email / ID" in res.data


def test_authenticated_routes_status_codes(auth_client):
    """Verify that all protected routes return 200 OK when authenticated."""
    protected_pages = [
        ('/', 'Dashboard Root'),
        ('/dashboard', 'Dashboard View'),
        ('/residents', 'Resident Directory'),
        ('/residents/add', 'Add Resident Page'),
        ('/residents/previous', 'Previous Residents'),
        ('/residents/MHL-2024-001', 'Resident Profile View'),
        ('/payments', 'Payments Management'),
        ('/branches', 'Branch Management'),
        ('/settings', 'Settings View'),
    ]

    for endpoint, name in protected_pages:
        response = auth_client.get(endpoint)
        assert response.status_code == 200, f"Route {endpoint} ({name}) failed with status {response.status_code}"


# -----------------------------------------------------------------------------
# 2. AUTHENTICATION, CREDENTIALS & BROWSER SESSION CLOSING TESTS
# -----------------------------------------------------------------------------
def test_successful_login_with_custom_credentials(client, app):
    """Test successful administrator login with ID 'admin' and password '1234'."""
    res = client.post('/auth/login', data={
        'email': 'admin',
        'password': '1234'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Session authenticated successfully" in res.data

    with app.app_context():
        # Verify LoginLog record
        success_log = LoginLog.query.filter_by(status=LoginStatus.SUCCESS).first()
        assert success_log is not None
        assert success_log.email_attempted == "admin"

        # Verify AuditLog record
        audit_entry = AuditLog.query.filter_by(action=AuditAction.LOGIN).first()
        assert audit_entry is not None
        assert "logged in successfully" in audit_entry.description


def test_session_ends_on_browser_close(client):
    """Verify that sessions are non-permanent (session cookies with no persistent expiry)."""
    res = client.post('/auth/login', data={
        'email': 'admin',
        'password': '1234'
    }, follow_redirects=False)

    # Check the Set-Cookie header for session
    cookies = res.headers.getlist('Set-Cookie')
    session_cookie = next((c for c in cookies if 'session=' in c), None)
    assert session_cookie is not None, "Session cookie must be issued on successful login"

    # Non-permanent browser session cookies do NOT have Expires or Max-Age timestamps
    assert 'Expires=' not in session_cookie
    assert 'Max-Age=' not in session_cookie

    # Ensure no persistent remember_token cookie is issued
    remember_cookie = next((c for c in cookies if 'remember_token=' in c), None)
    assert remember_cookie is None, "Persistent remember_token must not be issued so session closes on browser exit"


def test_invalid_credentials(client, app):
    """Test login rejection when wrong password or non-existent email is provided."""
    # Wrong password
    res_wrong_pw = client.post('/auth/login', data={
        'email': 'admin',
        'password': 'wrongpassword'
    }, follow_redirects=True)

    assert res_wrong_pw.status_code == 401
    assert b"Invalid administrator credentials" in res_wrong_pw.data

    # Non-existent email
    res_wrong_email = client.post('/auth/login', data={
        'email': 'other@123',
        'password': '1234'
    }, follow_redirects=True)

    assert res_wrong_email.status_code == 401
    assert b"Invalid administrator credentials" in res_wrong_email.data

    with app.app_context():
        failed_count = LoginLog.query.filter_by(status=LoginStatus.FAILED).count()
        assert failed_count >= 2


def test_logout(auth_client):
    """Test secure logout and session invalidation."""
    res = auth_client.get('/auth/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b"signed out" in res.data

    # Verify that protected routes are now blocked
    dash_res = auth_client.get('/dashboard', follow_redirects=False)
    assert dash_res.status_code == 302
    assert '/auth/login' in dash_res.headers['Location']


# -----------------------------------------------------------------------------
# 3. RATE LIMITING TESTS
# -----------------------------------------------------------------------------
def test_login_rate_limiting(client, app):
    """Verify sliding-window login rate limiting after 5 failed attempts."""
    target_email = "admin"

    # Make 5 failed attempts
    for i in range(5):
        res = client.post('/auth/login', data={
            'email': target_email,
            'password': f'WrongAttempt{i}!'
        })
        assert res.status_code == 401

    # 6th attempt should be blocked with HTTP 429
    res_blocked = client.post('/auth/login', data={
        'email': target_email,
        'password': '1234'
    })
    assert res_blocked.status_code == 429
    assert b"Too many failed login attempts" in res_blocked.data

    with app.app_context():
        rate_log = LoginLog.query.filter_by(status=LoginStatus.RATE_LIMITED).first()
        assert rate_log is not None


# -----------------------------------------------------------------------------
# 4. PASSWORD CHANGE & RECOVERY TESTS
# -----------------------------------------------------------------------------
def test_password_change(auth_client, app):
    """Verify administrator password change functionality in Settings."""
    res = auth_client.post('/settings', data={
        'action': 'change_password',
        'current_password': '1234',
        'new_password': '5678',
        'confirm_password': '5678'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Administrator password updated successfully" in res.data

    with app.app_context():
        admin = Admin.query.first()
        assert admin.check_password("5678") is True
        assert admin.check_password("1234") is False

        # Verify audit log does not leak password
        audit_log = AuditLog.query.filter_by(action=AuditAction.PASSWORD_CHANGE).first()
        assert audit_log is not None
        assert "5678" not in audit_log.description
        assert "changed password successfully" in audit_log.description


def test_password_recovery_workflow(client, app):
    """Verify complete password recovery with one-time tokens."""
    # 1. Request recovery token
    res_req = client.post('/auth/forgot-password', data={
        'email': 'admin'
    }, follow_redirects=True)
    assert res_req.status_code == 200
    assert b"password recovery instructions have been initiated" in res_req.data

    with app.app_context():
        admin = Admin.query.first()
        token_entry, raw_token = PasswordResetToken.create_for_admin(admin.id)
        db.session.add(token_entry)
        db.session.commit()
        expected_hash = str(token_entry.token_hash)

    # 2. Reset password using valid raw token
    res_reset = client.post(f'/auth/reset-password/{raw_token}', data={
        'new_password': '9999',
        'confirm_password': '9999'
    }, follow_redirects=True)

    assert res_reset.status_code == 200
    assert b"successfully updated" in res_reset.data

    with app.app_context():
        updated_admin = Admin.query.first()
        assert updated_admin.check_password("9999") is True

        # Verify token is now marked used
        updated_token = PasswordResetToken.query.filter_by(token_hash=expected_hash).first()
        assert updated_token.used is True


# -----------------------------------------------------------------------------
# 5. CSRF PROTECTION ENFORCEMENT TEST
# -----------------------------------------------------------------------------
def test_csrf_protection_enforcement(app):
    """Verify that CSRF protection rejects POST requests when CSRF token is missing."""
    app.config['WTF_CSRF_ENABLED'] = True
    test_client = app.test_client()

    # Attempt POST without CSRF token
    res = test_client.post('/auth/login', data={
        'email': 'admin',
        'password': '1234'
    })

    assert res.status_code == 400
    assert b"CSRF" in res.data or b"Security Verification Failed" in res.data

    app.config['WTF_CSRF_ENABLED'] = False


# -----------------------------------------------------------------------------
# 6. AUDIT LOGGING & SENSITIVE CREDENTIAL LEAK PREVENTION
# -----------------------------------------------------------------------------
def test_audit_logging_no_sensitive_data_leakage(app):
    """Verify that audit logs never record passwords, password hashes or reset tokens."""
    with app.app_context():
        AuditService.log(
            action=AuditAction.PASSWORD_CHANGE,
            entity_type='Admin',
            description="Admin changed password: MySecretPassword123 with token=abcdef123456"
        )

        log = AuditLog.query.filter_by(action=AuditAction.PASSWORD_CHANGE).first()
        assert log is not None
        assert "MySecretPassword123" not in log.description
        assert "abcdef123456" not in log.description


# -----------------------------------------------------------------------------
# 7. FILE UPLOAD SECURITY (EXTENSION, MIME, MAGIC BYTES)
# -----------------------------------------------------------------------------
def test_file_upload_security_validation():
    """Verify file upload validation rejects invalid extensions, sizes, and fake MIME headers."""
    # 1. Valid PNG image
    valid_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + (b'\x00' * 50)
    valid_file = FileStorage(
        stream=io.BytesIO(valid_png_bytes),
        filename="resident_photo.png",
        content_type="image/png"
    )
    is_valid, err = validate_image_upload(valid_file)
    assert is_valid is True
    assert err == ""

    # 2. Disallowed extension
    bad_ext_file = FileStorage(
        stream=io.BytesIO(b'malicious content'),
        filename="payload.exe",
        content_type="application/octet-stream"
    )
    is_valid, err = validate_image_upload(bad_ext_file)
    assert is_valid is False
    assert "not permitted" in err

    # 3. Fake JPG (renamed text file with non-JPEG bytes)
    fake_jpg = FileStorage(
        stream=io.BytesIO(b'<!DOCTYPE html><html>fake image</html>'),
        filename="fake.jpg",
        content_type="image/jpeg"
    )
    is_valid, err = validate_image_upload(fake_jpg)
    assert is_valid is False
    assert "failed binary content inspection" in err
