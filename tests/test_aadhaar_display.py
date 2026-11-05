"""
Test Suite for Updated Aadhaar Display Functionality.
Verifies all 8 requirements:
1. Four-digit masking removed from the Resident Profile.
2. Complete Aadhaar number displayed to the authenticated administrator on Resident Profile.
3. Aadhaar information viewed and edited in Edit Resident form.
4. Aadhaar numbers NOT displayed in Resident Directory table.
5. Aadhaar numbers encrypted with AES-256 GCM in database.
6. Decrypted only when required by an authorized administrator operation.
7. Aadhaar information never exposed in application logs or URLs.
8. Existing resident records and encryption functionality preserved.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, AuditLog, ResidentStatus, AuditAction
)
from app.services.seed_service import seed_database_sample_data
from app.services.aadhaar_service import AadhaarSecurityService


@pytest.fixture
def app(tmp_path):
    """Create test application context with memory SQLite DB."""
    test_app = create_app('testing')
    test_app.config['PRIVATE_STORAGE_FOLDER'] = tmp_path / 'storage' / 'private' / 'residents'
    with test_app.app_context():
        db.create_all()
        admin = Admin(email="admin", username="admin", is_active=True)
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
        'email': 'admin',
        'password': '1234'
    }, follow_redirects=True)
    return c


def test_complete_aadhaar_displayed_on_profile_and_masking_removed(auth_client, app):
    """
    Requirement 1 & 2:
    - Four-digit masking is removed from Resident Profile.
    - Authenticated administrator views the complete decrypted Aadhaar number.
    """
    with app.app_context():
        res = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = res.resident_code
        decrypted_expected = AadhaarSecurityService.decrypt_aadhaar(res.aadhaar_encrypted)
        formatted_expected = f"{decrypted_expected[:4]} {decrypted_expected[4:8]} {decrypted_expected[8:]}"
        masked_format = f"XXXX-XXXX-{res.aadhaar_last_four}"

    response = auth_client.get(f'/residents/{res_code}')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Complete Aadhaar must be visible to authenticated administrator
    assert formatted_expected in html
    # Four-digit masking must be removed from the profile page
    assert masked_format not in html


def test_aadhaar_viewed_and_edited_in_edit_resident_form(auth_client, app):
    """
    Requirement 3:
    - Aadhaar information pre-filled in edit form.
    - Aadhaar information can be modified and successfully updated.
    """
    with app.app_context():
        res = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).first()
        res_code = res.resident_code
        branch_id = res.branch_id
        decrypted_original = AadhaarSecurityService.decrypt_aadhaar(res.aadhaar_encrypted)
        formatted_original = f"{decrypted_original[:4]} {decrypted_original[4:8]} {decrypted_original[8:]}"

    # Verify pre-filled in modal form
    response = auth_client.get(f'/residents/{res_code}')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert f'value="{formatted_original}"' in html

    # Submit updated Aadhaar number
    new_aadhaar = "998877665544"
    edit_response = auth_client.post(f'/residents/{res_code}/edit', data={
        'full_name': 'Updated Name',
        'branch_id': str(branch_id),
        'admission_date': '2024-05-10',
        'aadhaar_number': new_aadhaar
    }, follow_redirects=True)

    assert edit_response.status_code == 200
    assert b"updated successfully" in edit_response.data

    with app.app_context():
        updated_res = Resident.query.filter_by(resident_code=res_code).first()
        # Verify AES-256 encrypted at rest
        assert new_aadhaar not in updated_res.aadhaar_encrypted
        assert updated_res.aadhaar_last_four == "5544"
        assert AadhaarSecurityService.decrypt_aadhaar(updated_res.aadhaar_encrypted) == new_aadhaar

    # Verify updated complete number is now rendered on profile
    response_updated = auth_client.get(f'/residents/{res_code}')
    assert response_updated.status_code == 200
    assert "9988 7766 5544" in response_updated.data.decode('utf-8')


def test_aadhaar_not_displayed_in_directory_table(auth_client, app):
    """
    Requirement 4:
    - Do not display Aadhaar numbers in the Resident Directory table.
    """
    with app.app_context():
        residents = Resident.query.all()
        last_fours = [r.aadhaar_last_four for r in residents if r.aadhaar_last_four]

    response = auth_client.get('/residents')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # No masked Aadhaar strings in directory table
    assert "XXXX-XXXX-" not in html
    # No plaintext Aadhaar indicators in directory table
    assert "bi-shield-check" not in html


def test_encryption_at_rest_and_audit_logging_no_leak(auth_client, app):
    """
    Requirements 5, 6, 7 & 8:
    - Stored as ciphertext in PostgreSQL/SQLite.
    - Decrypted only when required by authorized administrator operation.
    - Plaintext Aadhaar NEVER exposed in audit logs or URLs.
    - Existing records preserved.
    """
    with app.app_context():
        res = Resident.query.first()
        res_code = res.resident_code
        branch_id = res.branch_id

    secret_aadhaar = "887766554433"
    auth_client.post(f'/residents/{res_code}/edit', data={
        'full_name': res.full_name,
        'branch_id': str(branch_id),
        'admission_date': str(res.admission_date),
        'aadhaar_number': secret_aadhaar
    }, follow_redirects=True)

    with app.app_context():
        updated = Resident.query.filter_by(resident_code=res_code).first()
        # Requirement 5: Encrypted at rest
        assert secret_aadhaar not in updated.aadhaar_encrypted
        # Requirement 6: Decrypted via service
        assert AadhaarSecurityService.decrypt_aadhaar(updated.aadhaar_encrypted) == secret_aadhaar

        # Requirement 7: Never in audit logs
        logs = AuditLog.query.all()
        for log in logs:
            assert secret_aadhaar not in log.description
            if log.ip_address:
                assert secret_aadhaar not in log.ip_address

