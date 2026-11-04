"""
Comprehensive Test Suite for Google Drive Storage Integration and Production Readiness.
Covers:
- Google Drive authentication using mocked credentials
- Photograph and thumbnail uploads with Pillow optimization
- Thumbnail failure rollback (cleanup of main image)
- Authenticated and unauthenticated photograph retrieval
- Private caching headers and nosniff protection
- Default avatar fallback on 404/HttpError
- Safe photograph replacement without accidental photo loss
- Google Drive photograph and thumbnail deletion
- 30-day retention cleanup integration with Google Drive
- Backwards compatibility with local storage and static avatars
- Production configuration security validation
"""
import io
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock
import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from googleapiclient.errors import HttpError

from app import create_app
from app.extensions import db
from app.models import Admin, Branch, Resident, Payment
from app.services.storage_service import StorageService
from app.services.retention_service import RetentionService
from config import ProductionConfig


class FakeDownloader:
    """Mock helper for googleapiclient.http.MediaIoBaseDownload."""
    def __init__(self, fh, request, data=b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01'):
        self.fh = fh
        self.request = request
        self.data = data

    def next_chunk(self):
        self.fh.write(self.data)
        return None, True


def create_test_image(format='JPEG', size=(200, 200), color='blue'):
    """Helper to create dummy in-memory image for upload testing."""
    buf = io.BytesIO()
    img = Image.new('RGB', size, color=color)
    img.save(buf, format=format)
    buf.seek(0)
    return FileStorage(stream=buf, filename=f"test.{format.lower()}", content_type=f"image/{format.lower()}")


@pytest.fixture
def gdrive_app():
    """Create test application with Google Drive storage backend enabled."""
    app = create_app('testing')
    app.config.update({
        'STORAGE_BACKEND': 'google_drive',
        'GOOGLE_DRIVE_CLIENT_ID': 'test-client-id.apps.googleusercontent.com',
        'GOOGLE_DRIVE_CLIENT_SECRET': 'test-client-secret-123',
        'GOOGLE_DRIVE_REFRESH_TOKEN': '1//test-mock-refresh-token-xyz',
        'GOOGLE_DRIVE_FOLDER_ID': 'mock-gdrive-folder-456',
        'WTF_CSRF_ENABLED': False,
    })

    with app.app_context():
        db.create_all()
        # Create test branch
        branch = Branch(
            branch_name="Drive Test Branch",
            branch_code="DTB",
            address="123 Tech Park, Bangalore",
            contact_number="9876543210",
            is_active=True
        )
        db.session.add(branch)

        # Create test admin
        admin = Admin(
            email="admin@drive.com",
            username="driveadmin",
            is_active=True
        )
        admin.set_password("SecurePassword123!")
        db.session.add(admin)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(gdrive_app):
    return gdrive_app.test_client()


def test_google_drive_missing_config(gdrive_app):
    """Verify ValueError is raised when required Google Drive credentials are missing."""
    with gdrive_app.app_context():
        gdrive_app.config['GOOGLE_DRIVE_CLIENT_ID'] = ''
        with pytest.raises(ValueError, match="Google Drive storage requires GOOGLE_DRIVE_CLIENT_ID"):
            StorageService._get_gdrive_service()


def test_google_drive_auth_credentials(gdrive_app):
    """Verify Credentials and build are invoked with correct OAuth scope and parameters."""
    with gdrive_app.app_context():
        with patch('google.oauth2.credentials.Credentials') as mock_creds_cls:
            with patch('googleapiclient.discovery.build') as mock_build:
                StorageService._get_gdrive_service()

                mock_creds_cls.assert_called_once_with(
                    token=None,
                    refresh_token='1//test-mock-refresh-token-xyz',
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id='test-client-id.apps.googleusercontent.com',
                    client_secret='test-client-secret-123',
                    scopes=['https://www.googleapis.com/auth/drive.file']
                )
                mock_build.assert_called_once()
                assert mock_build.call_args[0][0] == 'drive'
                assert mock_build.call_args[0][1] == 'v3'


def test_google_drive_upload_success(gdrive_app):
    """Verify photograph upload to Google Drive creates main file and thumbnail with non-identifying filenames."""
    file = create_test_image()

    mock_service = MagicMock()
    mock_service.files().create().execute.side_effect = [
        {'id': 'main_file_001'},
        {'id': 'thumb_file_002'}
    ]
    mock_service.files().create.reset_mock()

    with gdrive_app.app_context():
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            ref = StorageService.save_photograph(file, prefix="res")

            assert ref == "/residents/photo/gdrive_main_main_file_001__thumb_thumb_file_002.jpg"
            assert mock_service.files().create.call_count == 2

            # Verify non-identifying filename & private parents
            calls = mock_service.files().create.call_args_list
            main_metadata = calls[0].kwargs.get('body')
            assert main_metadata['parents'] == ['mock-gdrive-folder-456']
            assert main_metadata['name'].startswith('res_')
            assert 'test' not in main_metadata['name']  # Original filename sanitized away


def test_google_drive_folder_auto_creation(gdrive_app):
    """Verify that if GOOGLE_DRIVE_FOLDER_ID is empty, it finds or auto-creates the private folder."""
    file = create_test_image()

    mock_service = MagicMock()
    # List returns empty, create returns new folder id
    mock_service.files().list().execute.return_value = {'files': []}
    mock_service.files().create().execute.side_effect = [
        {'id': 'auto_created_folder_999'},  # Folder creation
        {'id': 'main_file_003'},            # Main image
        {'id': 'thumb_file_004'}            # Thumbnail
    ]

    with gdrive_app.app_context():
        gdrive_app.config['GOOGLE_DRIVE_FOLDER_ID'] = ''
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            ref = StorageService.save_photograph(file, prefix="res")

            assert gdrive_app.config['GOOGLE_DRIVE_FOLDER_ID'] == 'auto_created_folder_999'
            assert ref == "/residents/photo/gdrive_main_main_file_003__thumb_thumb_file_004.jpg"


def test_google_drive_upload_thumb_failure_cleanup(gdrive_app):
    """Verify that if thumbnail upload fails, the uploaded main image is rolled back and deleted."""
    file = create_test_image()

    mock_service = MagicMock()
    mock_service.files().create().execute.side_effect = [
        {'id': 'main_file_orphan_test'},
        RuntimeError("Google Drive API rate limit reached")
    ]
    mock_service.reset_mock()

    with gdrive_app.app_context():
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            with pytest.raises(RuntimeError, match="Google Drive thumbnail upload failed"):
                StorageService.save_photograph(file)

            # Main image must be deleted to avoid orphaned files in Drive
            assert mock_service.files().delete.call_count == 1
            deleted_id = mock_service.files().delete.call_args.kwargs.get('fileId')
            assert deleted_id == 'main_file_orphan_test'


def test_google_drive_serve_authenticated(client, gdrive_app):
    """Verify authenticated administrator can stream Google Drive photograph with private cache headers."""
    # Log in
    client.post('/auth/login', data={'email': 'admin@drive.com', 'password': 'SecurePassword123!'})

    mock_service = MagicMock()
    mock_service.files().get_media.return_value = Mock()

    with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
        with patch('googleapiclient.http.MediaIoBaseDownload', FakeDownloader):
            response = client.get('/residents/photo/gdrive_main_main001__thumb_thumb002.jpg')

            assert response.status_code == 200
            assert response.content_type == 'image/jpeg'
            assert 'private' in response.headers.get('Cache-Control', '')
            assert response.headers.get('X-Content-Type-Options') == 'nosniff'
            assert response.data == b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01'


def test_google_drive_serve_unauthenticated(client):
    """Verify unauthenticated user cannot access resident photograph and is redirected to login."""
    response = client.get('/residents/photo/gdrive_main_main001__thumb_thumb002.jpg')
    assert response.status_code == 302
    assert '/auth/login' in response.headers.get('Location', '')


def test_google_drive_serve_not_found_fallback(client, gdrive_app):
    """Verify that when a Google Drive file returns 404 HttpError, it gracefully falls back to default avatar."""
    client.post('/auth/login', data={'email': 'admin@drive.com', 'password': 'SecurePassword123!'})

    resp_mock = Mock(status=404, reason="Not Found")
    http_err = HttpError(resp_mock, b"File not found")

    mock_service = MagicMock()
    mock_service.files().get_media.side_effect = http_err

    with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
        response = client.get('/residents/photo/gdrive_main_missing_file.jpg')
        # Returns default avatar with SVG mime type
        assert response.status_code == 200
        assert 'svg' in response.content_type.lower()


def test_google_drive_delete_photograph(gdrive_app):
    """Verify delete_photograph deletes both main image and thumbnail from Google Drive."""
    mock_service = MagicMock()
    mock_service.files().delete().execute.return_value = {}
    mock_service.reset_mock()

    with gdrive_app.app_context():
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            result = StorageService.delete_photograph('/residents/photo/gdrive_main_fid123__thumb_tfid456.jpg')

            assert result is True
            assert mock_service.files().delete.call_count == 2
            deleted_ids = [c.kwargs.get('fileId') for c in mock_service.files().delete.call_args_list]
            assert deleted_ids == ['fid123', 'tfid456']


def test_google_drive_delete_already_deleted_404(gdrive_app):
    """Verify delete_photograph handles already-deleted files (404) safely as success."""
    resp_mock = Mock(status=404, reason="File not found")
    http_err = HttpError(resp_mock, b"File not found")

    mock_service = MagicMock()
    mock_service.files().delete().execute.side_effect = http_err
    mock_service.reset_mock()

    with gdrive_app.app_context():
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            result = StorageService.delete_photograph('/residents/photo/gdrive_main_already_gone.jpg')
            assert result is True


def test_google_drive_delete_api_failure_raises(gdrive_app):
    """Verify unexpected Google Drive delete failures raise exceptions so retention cleanup does not orphan files."""
    resp_mock = Mock(status=500, reason="Backend Server Error")
    http_err = HttpError(resp_mock, b"Internal Drive Error")

    mock_service = MagicMock()
    mock_service.files().delete().execute.side_effect = http_err

    with gdrive_app.app_context():
        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            with pytest.raises(HttpError):
                StorageService.delete_photograph('/residents/photo/gdrive_main_error_file.jpg')


def test_resident_photo_replacement_safety(client, gdrive_app):
    """Verify photograph replacement uploads new image first, commits DB, and only deletes old image afterwards."""
    client.post('/auth/login', data={'email': 'admin@drive.com', 'password': 'SecurePassword123!'})

    with gdrive_app.app_context():
        branch = Branch.query.first()
        resident = Resident(
            resident_code="RES-GDR-01",
            full_name="Google Drive Resident",
            branch_id=branch.id,
            admission_date=datetime.utcnow().date(),
            resident_status='ACTIVE',
            photograph_path="/residents/photo/gdrive_main_old_main__thumb_old_thumb.jpg",
            aadhaar_encrypted="enc_aadhaar",
            aadhaar_last_four="1234"
        )
        db.session.add(resident)
        db.session.commit()

    mock_service = MagicMock()
    mock_service.files().create().execute.side_effect = [
        {'id': 'new_main_777'},
        {'id': 'new_thumb_888'}
    ]
    mock_service.files().delete().execute.return_value = {}

    file = create_test_image(color='yellow')

    with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
        response = client.post(
            f'/residents/RES-GDR-01/update-photo',
            data={'photograph': file},
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200

        with gdrive_app.app_context():
            updated_res = Resident.query.filter_by(resident_code="RES-GDR-01").first()
            assert updated_res.photograph_path == "/residents/photo/gdrive_main_new_main_777__thumb_new_thumb_888.jpg"

            # Old files deleted
            deleted_ids = [c.kwargs.get('fileId') for c in mock_service.files().delete.call_args_list]
            assert 'old_main' in deleted_ids
            assert 'old_thumb' in deleted_ids


def test_retention_cleanup_with_google_drive(gdrive_app):
    """Verify that eligible resident data retention permanently purges Google Drive photos and DB record."""
    with gdrive_app.app_context():
        branch = Branch.query.first()
        past_leave = datetime.utcnow().date() - timedelta(days=380)
        resident = Resident(
            resident_code="RES-LEFT-01",
            full_name="Left Resident",
            branch_id=branch.id,
            admission_date=past_leave - timedelta(days=60),
            leaving_date=past_leave,
            resident_status='LEFT',
            photograph_path="/residents/photo/gdrive_main_purged_main__thumb_purged_thumb.jpg",
            aadhaar_encrypted="enc_aadhaar",
            aadhaar_last_four="5678"
        )
        db.session.add(resident)
        db.session.commit()

        mock_service = MagicMock()
        mock_service.files().delete().execute.return_value = {}

        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            result = RetentionService.run_retention_cleanup()

            assert result['status'] == 'SUCCESS'
            assert 'RES-LEFT-01' in result['purged_codes']

            # Verify resident purged from DB
            assert Resident.query.filter_by(resident_code="RES-LEFT-01").first() is None

            # Verify Drive files deleted
            deleted_ids = [c.kwargs.get('fileId') for c in mock_service.files().delete.call_args_list]
            assert 'purged_main' in deleted_ids
            assert 'purged_thumb' in deleted_ids


def test_retention_cleanup_aborts_when_gdrive_delete_fails(gdrive_app):
    """Verify that if Google Drive deletion fails, resident record is NOT purged (safe to retry)."""
    with gdrive_app.app_context():
        branch = Branch.query.first()
        past_leave = datetime.utcnow().date() - timedelta(days=380)
        resident = Resident(
            resident_code="RES-LEFT-RETRY",
            full_name="Left Resident Retry",
            branch_id=branch.id,
            admission_date=past_leave - timedelta(days=60),
            leaving_date=past_leave,
            resident_status='LEFT',
            photograph_path="/residents/photo/gdrive_main_fail_main.jpg",
            aadhaar_encrypted="enc_aadhaar",
            aadhaar_last_four="9999"
        )
        db.session.add(resident)
        db.session.commit()

        resp_mock = Mock(status=500, reason="Server Error")
        http_err = HttpError(resp_mock, b"Drive API Unavailable")

        mock_service = MagicMock()
        mock_service.files().delete().execute.side_effect = http_err

        with patch.object(StorageService, '_get_gdrive_service', return_value=mock_service):
            result = RetentionService.run_retention_cleanup()

            assert result['status'] in ('PARTIAL', 'FAILED')
            assert 'RES-LEFT-RETRY' in result['failed_codes']

            # Resident must NOT be deleted so cleanup can be retried once Drive recovers
            still_exists = Resident.query.filter_by(resident_code="RES-LEFT-RETRY").first()
            assert still_exists is not None


def test_backwards_compatibility_local_storage(client, gdrive_app):
    """Verify local files and default avatars continue to be served when STORAGE_BACKEND is google_drive."""
    client.post('/auth/login', data={'email': 'admin@drive.com', 'password': 'SecurePassword123!'})

    # 1. Default static avatar
    resp = client.get('/static/images/default_avatar.svg')
    assert resp.status_code == 200

    # 2. Local photo file in private folder
    private_dir = StorageService.get_private_dir()
    test_local_file = private_dir / 'local_compat_test.jpg'
    with open(test_local_file, 'wb') as f:
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01local_compat')

    try:
        resp = client.get('/residents/photo/local_compat_test.jpg')
        assert resp.status_code == 200
        assert b'local_compat' in resp.data
        resp.close()
    finally:
        if test_local_file.exists():
            try:
                test_local_file.unlink()
            except PermissionError:
                pass


def test_production_config_validation():
    """Verify ProductionConfig strictly requires SECRET_KEY, PostgreSQL DATABASE_URL, and 32-byte AADHAAR_KEY."""
    # 1. Missing SECRET_KEY
    with patch.dict(os.environ, {'SECRET_KEY': '', 'DATABASE_URL': 'postgresql://user:pass@host:5432/db', 'AADHAAR_ENCRYPTION_KEY': '12345678901234567890123456789012'}):
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            ProductionConfig.validate_production()

    # 2. Missing DATABASE_URL
    with patch.dict(os.environ, {'SECRET_KEY': 'secure-prod-key', 'DATABASE_URL': '', 'AADHAAR_ENCRYPTION_KEY': '12345678901234567890123456789012'}):
        with pytest.raises(ValueError, match="DATABASE_URL is required"):
            ProductionConfig.validate_production()

    # 3. SQLite in production
    with patch.dict(os.environ, {'SECRET_KEY': 'secure-prod-key', 'DATABASE_URL': 'sqlite:///prod.db', 'AADHAAR_ENCRYPTION_KEY': '12345678901234567890123456789012'}):
        with pytest.raises(ValueError, match="SQLite is not permitted in production"):
            ProductionConfig.validate_production()

    # 4. Invalid length AADHAAR_ENCRYPTION_KEY
    with patch.dict(os.environ, {'SECRET_KEY': 'secure-prod-key', 'DATABASE_URL': 'postgresql://user:pass@host:5432/db', 'AADHAAR_ENCRYPTION_KEY': 'short_key'}):
        with pytest.raises(ValueError, match="AADHAAR_ENCRYPTION_KEY must be exactly 32 bytes"):
            ProductionConfig.validate_production()

    # 5. All valid
    with patch.dict(os.environ, {'SECRET_KEY': 'secure-prod-key-1234567890', 'DATABASE_URL': 'postgresql://user:pass@host:5432/db', 'AADHAAR_ENCRYPTION_KEY': '12345678901234567890123456789012'}):
        ProductionConfig.validate_production()  # Must not raise
