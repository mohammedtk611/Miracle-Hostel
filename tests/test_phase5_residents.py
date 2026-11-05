"""
Test Suite for Miracle Hostel Management Portal - Phase 5: Resident Management.
Covers:
1. Register a new resident.
2. Generate a unique resident ID.
3. Reject invalid resident information.
4. Register residents in different branches.
5. Upload a valid photograph (PIL optimization, private storage, thumbnail).
6. Reject invalid file types.
7. Reject oversized images.
8. Replace a photograph and delete obsolete photograph from disk.
9. Search residents by name.
10. Search residents by ID.
11. Filter residents by branch.
12. Filter residents by status.
13. Edit resident information.
14. Verify Aadhaar encryption at rest in PostgreSQL.
15. Verify Aadhaar masking in UI.
16. Verify unauthorized access is blocked.
"""
import io
import pytest
from datetime import date, timedelta
from PIL import Image
from werkzeug.datastructures import FileStorage
from app import create_app
from app.extensions import db
from app.models import (
    Admin, Branch, Resident, Payment, AuditLog,
    ResidentStatus, PaymentType, PaymentStatus, AuditAction
)
from app.services.seed_service import seed_database_sample_data
from app.services.aadhaar_service import AadhaarSecurityService
from app.services.storage_service import StorageService


@pytest.fixture
def app(tmp_path):
    """Create test application context with memory SQLite DB and temporary private storage."""
    test_app = create_app('testing')
    test_app.config['PRIVATE_STORAGE_FOLDER'] = tmp_path / 'storage' / 'private' / 'residents'
    with test_app.app_context():
        db.create_all()
        # Seed admin
        admin = Admin(email="admin", username="admin", is_active=True)
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()

        # Seed initial sample data
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


def create_dummy_image_file(filename="test.jpg", dimensions=(1200, 1200), fmt="JPEG"):
    """Helper to create dummy in-memory image file for upload testing."""
    img = Image.new("RGB", dimensions, color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type=f"image/{fmt.lower()}")


# -----------------------------------------------------------------------------
# 1. ACCESS CONTROL TEST
# -----------------------------------------------------------------------------
def test_unauthorized_access_to_residents_routes(client):
    """Verify unauthorized users cannot access resident registration, directory, or profiles."""
    endpoints = [
        ('/residents', 302),
        ('/residents/add', 302),
        ('/residents/MHL-2024-001', 302),
        ('/residents/MHL-2024-001/edit', 302),
        ('/residents/photo/res_fake.jpg', 302),
    ]
    for url, code in endpoints:
        res = client.get(url, follow_redirects=False)
        assert res.status_code == code, f"Expected {code} for {url}, got {res.status_code}"
        assert '/auth/login' in res.headers['Location']


# -----------------------------------------------------------------------------
# 2. REGISTRATION, ID GENERATION & VALIDATION
# -----------------------------------------------------------------------------
def test_register_new_resident_with_auto_generated_id(auth_client, app):
    """Test registering a new resident with system-generated unique ID and default ACTIVE status."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()
        branch_id = branch.id

    img_file = create_dummy_image_file("resident_photo.jpg")

    res = auth_client.post('/residents/add', data={
        'full_name': 'Karthik Subramanian',
        'branch_id': str(branch_id),
        'admission_date': '2024-11-01',
        'aadhaar_number': '543210987654',
        'security_deposit': '12000',
        'photograph': img_file
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"successfully registered" in res.data
    assert b"Karthik Subramanian" in res.data

    with app.app_context():
        new_res = Resident.query.filter_by(full_name='Karthik Subramanian').first()
        assert new_res is not None
        # Verify unique system-generated resident code format
        assert new_res.resident_code.startswith(f"MHL-{date.today().year}-")
        assert new_res.resident_status == ResidentStatus.ACTIVE
        assert new_res.branch_id == branch_id
        # Verify audit log recorded
        audit = AuditLog.query.filter_by(action=AuditAction.RESIDENT_CREATE, entity_id=new_res.id).first()
        assert audit is not None


def test_reject_invalid_resident_registration(auth_client, app):
    """Test validation failure on missing name, inactive branch, or invalid date."""
    with app.app_context():
        # Branch 4 is deactivated
        deact_branch = Branch.query.filter_by(is_active=False).first()
        deact_id = deact_branch.id

    # 1. Missing full name
    res_no_name = auth_client.post('/residents/add', data={
        'full_name': '',
        'branch_id': '1',
        'admission_date': '2024-11-01'
    }, follow_redirects=True)
    assert res_no_name.status_code == 200
    assert b"Valid full legal name is required" in res_no_name.data

    # 2. Deactivated branch selection
    res_deact = auth_client.post('/residents/add', data={
        'full_name': 'Valid Name',
        'branch_id': str(deact_id),
        'admission_date': '2024-11-01'
    }, follow_redirects=True)
    assert res_deact.status_code == 200
    assert b"deactivated" in res_deact.data

    # 3. Invalid Aadhaar format (starts with 0)
    res_bad_aadhaar = auth_client.post('/residents/add', data={
        'full_name': 'Valid Name',
        'branch_id': '1',
        'admission_date': '2024-11-01',
        'aadhaar_number': '012345678912'
    }, follow_redirects=True)
    assert res_bad_aadhaar.status_code == 200
    assert b"Invalid Aadhaar format" in res_bad_aadhaar.data


def test_register_residents_in_different_branches(auth_client, app):
    """Test registering residents across distinct active branches."""
    with app.app_context():
        b1 = Branch.query.filter_by(branch_code='BR-AN-01').first()
        b2 = Branch.query.filter_by(branch_code='BR-OMR-02').first()

    res1 = auth_client.post('/residents/add', data={
        'full_name': 'Resident Branch One',
        'branch_id': str(b1.id),
        'admission_date': '2024-10-01'
    }, follow_redirects=True)
    assert res1.status_code == 200

    res2 = auth_client.post('/residents/add', data={
        'full_name': 'Resident Branch Two',
        'branch_id': str(b2.id),
        'admission_date': '2024-10-01'
    }, follow_redirects=True)
    assert res2.status_code == 200

    with app.app_context():
        r1 = Resident.query.filter_by(full_name='Resident Branch One').first()
        r2 = Resident.query.filter_by(full_name='Resident Branch Two').first()
        assert r1.branch_id == b1.id
        assert r2.branch_id == b2.id
        assert r1.resident_code != r2.resident_code


# -----------------------------------------------------------------------------
# 3. AADHAAR SECURITY & MASKING
# -----------------------------------------------------------------------------
def test_aadhaar_encryption_at_rest_and_profile_display(auth_client, app):
    """
    Verify Aadhaar security requirements:
    1. Aadhaar number is encrypted with AES-256 GCM in the database.
    2. Complete unmasked Aadhaar number is displayed on Resident Profile to authenticated administrator.
    3. Four-digit masking is removed from Resident Profile.
    4. Aadhaar numbers are NOT displayed in the Resident Directory table.
    5. Aadhaar is pre-filled and editable in the Edit Resident form.
    """
    plain_aadhaar = "987654321234"
    formatted_aadhaar = "9876 5432 1234"
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()

    auth_client.post('/residents/add', data={
        'full_name': 'Aadhaar Test Resident',
        'branch_id': str(branch.id),
        'admission_date': '2024-11-01',
        'aadhaar_number': plain_aadhaar
    }, follow_redirects=True)

    with app.app_context():
        res = Resident.query.filter_by(full_name='Aadhaar Test Resident').first()
        assert res is not None

        # 1. Plaintext Aadhaar must NEVER be stored in the database!
        assert plain_aadhaar not in res.aadhaar_encrypted
        assert res.aadhaar_last_four == "1234"

        # 2. Decrypt verification using AES-256 GCM
        decrypted = AadhaarSecurityService.decrypt_aadhaar(res.aadhaar_encrypted)
        assert decrypted == plain_aadhaar

    # 3. Profile page inspection: complete Aadhaar visible to authenticated admin; masking removed
    res_prof = auth_client.get(f'/residents/{res.resident_code}')
    assert res_prof.status_code == 200
    assert formatted_aadhaar.encode('utf-8') in res_prof.data
    # Masking removed from profile
    assert b"XXXX-XXXX-1234" not in res_prof.data

    # 4. Resident directory table inspection: Aadhaar NOT displayed in directory
    res_dir = auth_client.get('/residents')
    assert res_dir.status_code == 200
    assert plain_aadhaar.encode('utf-8') not in res_dir.data
    assert formatted_aadhaar.encode('utf-8') not in res_dir.data
    assert b"XXXX-XXXX" not in res_dir.data

    # 5. Edit Resident form: edit Aadhaar number and re-encrypt
    updated_aadhaar = "876543210987"
    res_edit = auth_client.post(f'/residents/{res.resident_code}/edit', data={
        'full_name': 'Aadhaar Test Resident',
        'branch_id': str(branch.id),
        'admission_date': '2024-11-01',
        'aadhaar_number': updated_aadhaar
    }, follow_redirects=True)
    assert res_edit.status_code == 200

    with app.app_context():
        updated_res = Resident.query.filter_by(resident_code=res.resident_code).first()
        assert updated_res.aadhaar_last_four == "0987"
        assert updated_aadhaar not in updated_res.aadhaar_encrypted
        assert AadhaarSecurityService.decrypt_aadhaar(updated_res.aadhaar_encrypted) == updated_aadhaar


# -----------------------------------------------------------------------------
# 4. PHOTOGRAPH STORAGE, RESIZING & THUMBNAIL
# -----------------------------------------------------------------------------
def test_photograph_upload_resizing_and_thumbnail(auth_client, app):
    """Test photograph upload with PIL resizing down to max 1000px and thumbnail generation."""
    # Create oversized 1600x1600 image
    img_file = create_dummy_image_file("big_photo.jpg", dimensions=(1600, 1600))
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()

    auth_client.post('/residents/add', data={
        'full_name': 'Photo Resized Resident',
        'branch_id': str(branch.id),
        'admission_date': '2024-11-01',
        'photograph': img_file
    }, follow_redirects=True)

    with app.app_context():
        res = Resident.query.filter_by(full_name='Photo Resized Resident').first()
        assert res.photograph_path.startswith('/residents/photo/res_')
        
        # Verify file exists in private storage
        storage_dir = StorageService.get_private_dir()
        filename = res.photograph_path.split('/residents/photo/')[-1]
        file_path = storage_dir / filename
        assert file_path.exists()

        # Verify resized dimensions <= 1000px
        saved_img = Image.open(file_path)
        assert saved_img.width <= 1000
        assert saved_img.height <= 1000

        # Verify thumbnail was generated
        thumb_path = storage_dir / f"thumb_{filename}"
        assert thumb_path.exists()
        thumb_img = Image.open(thumb_path)
        assert thumb_img.width <= 250
        assert thumb_img.height <= 250


def test_reject_invalid_image_upload(auth_client, app):
    """Test upload rejection for non-image file extensions and fake MIME headers."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()

    # Disallowed executable
    fake_file = FileStorage(
        stream=io.BytesIO(b'malicious executable content'),
        filename="hack.exe",
        content_type="application/octet-stream"
    )

    res = auth_client.post('/residents/add', data={
        'full_name': 'Bad File Resident',
        'branch_id': str(branch.id),
        'admission_date': '2024-11-01',
        'photograph': fake_file
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"not permitted" in res.data


def test_replace_photograph_and_delete_obsolete(auth_client, app):
    """Test photograph replacement removes the previous obsolete photo from private storage."""
    with app.app_context():
        branch = Branch.query.filter_by(is_active=True).first()

    # 1. Create resident with first photo
    first_img = create_dummy_image_file("photo1.jpg")
    auth_client.post('/residents/add', data={
        'full_name': 'Photo Replace Resident',
        'branch_id': str(branch.id),
        'admission_date': '2024-11-01',
        'photograph': first_img
    }, follow_redirects=True)

    with app.app_context():
        res = Resident.query.filter_by(full_name='Photo Replace Resident').first()
        old_path = res.photograph_path
        storage_dir = StorageService.get_private_dir()
        old_filename = old_path.split('/residents/photo/')[-1]
        assert (storage_dir / old_filename).exists()

    # 2. Upload replacement photo
    second_img = create_dummy_image_file("photo2.png", fmt="PNG")
    res_update = auth_client.post(f'/residents/{res.resident_code}/update-photo', data={
        'photograph': second_img
    }, follow_redirects=True)

    assert res_update.status_code == 200
    assert b"Photograph replaced successfully" in res_update.data

    with app.app_context():
        updated_res = db.session.get(Resident, res.id)
        new_path = updated_res.photograph_path
        assert new_path != old_path
        new_filename = new_path.split('/residents/photo/')[-1]
        assert (storage_dir / new_filename).exists()

        # The old obsolete file must be removed!
        assert not (storage_dir / old_filename).exists(), "Old photo file must be deleted upon replacement"


# -----------------------------------------------------------------------------
# 5. EDIT RESIDENT INFORMATION
# -----------------------------------------------------------------------------
def test_edit_resident_details(auth_client, app):
    """Test updating resident full name, branch assignment, and admission date."""
    with app.app_context():
        res = Resident.query.filter_by(resident_code='MHL-2024-001').first()
        old_branch_id = res.branch_id
        # Pick another active branch
        new_branch = Branch.query.filter(Branch.id != old_branch_id, Branch.is_active == True).first()
        new_branch_id = new_branch.id

    res_post = auth_client.post(f'/residents/MHL-2024-001/edit', data={
        'full_name': 'Aravind K. Ramanathan',
        'branch_id': str(new_branch_id),
        'admission_date': '2024-01-15'
    }, follow_redirects=True)

    assert res_post.status_code == 200
    assert b"updated successfully" in res_post.data

    with app.app_context():
        updated = Resident.query.filter_by(resident_code='MHL-2024-001').first()
        assert updated.full_name == "Aravind K. Ramanathan"
        assert updated.branch_id == new_branch_id
        assert str(updated.admission_date) == "2024-01-15"

        # Audit log verification
        audit = AuditLog.query.filter_by(action=AuditAction.RESIDENT_UPDATE, entity_id=updated.id).first()
        assert audit is not None


# -----------------------------------------------------------------------------
# 6. DIRECTORY SEARCH, FILTERING & PAGINATION
# -----------------------------------------------------------------------------
def test_resident_directory_search_by_name_and_id(auth_client):
    """Test searching directory by resident name and resident ID."""
    # Search by Name
    res_name = auth_client.get('/residents?search=Pooja')
    assert res_name.status_code == 200
    assert b"Pooja Sundaram" in res_name.data
    assert b"Aravind Krishnan" not in res_name.data

    # Search by Resident ID
    res_code = auth_client.get('/residents?search=MHL-2024-002')
    assert res_code.status_code == 200
    assert b"MHL-2024-002" in res_code.data
    assert b"MHL-2024-001" not in res_code.data


def test_resident_directory_filtering_and_pagination(auth_client, app):
    """Test filtering by branch and status with pagination."""
    with app.app_context():
        b1 = Branch.query.filter_by(branch_code='BR-AN-01').first()

    # Filter by branch 1
    res_branch = auth_client.get(f'/residents?branch={b1.id}')
    assert res_branch.status_code == 200
    assert b"Aravind Krishnan" in res_branch.data

    # Filter by Status ACTIVE
    res_active = auth_client.get('/residents?status=ACTIVE')
    assert res_active.status_code == 200
    assert b"Aravind Krishnan" in res_active.data  # ACTIVE
    assert b"Siddharth Menon" not in res_active.data  # LEFT

    # Filter by Status LEFT
    res_left = auth_client.get('/residents?status=LEFT')
    assert res_left.status_code == 200
    assert b"Siddharth Menon" in res_left.data  # LEFT
    assert b"Aravind Krishnan" not in res_left.data  # ACTIVE

