"""
Private Storage Service for Miracle Hostel Management Portal.
Ensures resident photographs are NEVER stored in the publicly accessible application directory.
Supports:
1. 'google_drive': Permanent private Google Drive storage via OAuth 2.0 API v3.
   Streams photos securely to authenticated administrators, prevents public link exposure.
2. 'local_private': Private local directory storage outside app/static/, served exclusively
   through an authenticated @login_required endpoint. Includes PIL image compression,
   resizing for oversized uploads, and automatic thumbnail generation.
3. 's3': Cloud object-storage integration using private Amazon S3 (or S3-compatible) buckets
   with private ACL and presigned URL access.
4. 'oci': Modular abstraction prepared for Oracle Cloud Infrastructure (OCI) Object Storage integration.
"""
import io
import os
import uuid
from pathlib import Path
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app, send_from_directory, abort, redirect, Response
from app.utils.file_security import get_file_extension, verify_image_magic_bytes

# Optional Boto3 support for cloud object-storage
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class StorageService:
    """Service for private resident photograph storage, optimization, and lifecycle deletion."""

    MAX_DIMENSION = (1000, 1000)
    THUMB_DIMENSION = (250, 250)
    JPEG_QUALITY = 85

    @classmethod
    def get_private_dir(cls) -> Path:
        """Get and ensure existence of private storage directory."""
        folder = current_app.config.get('PRIVATE_STORAGE_FOLDER')
        if not folder:
            basedir = Path(current_app.root_path).parent
            folder = basedir / 'storage' / 'private' / 'residents'
        os.makedirs(folder, exist_ok=True)
        return Path(folder)

    @classmethod
    def _process_image(cls, file: FileStorage) -> tuple[io.BytesIO, io.BytesIO, str]:
        """
        Resize oversized images, optimize compression, and generate profile thumbnail.
        Returns: (optimized_main_buffer, thumbnail_buffer, format_str)
        """
        file.seek(0)
        img = Image.open(file)

        # Determine image format
        img_format = img.format or 'JPEG'
        if img_format.upper() in ('JPG', 'JPEG'):
            save_format = 'JPEG'
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
        elif img_format.upper() == 'PNG':
            save_format = 'PNG'
        elif img_format.upper() == 'WEBP':
            save_format = 'WEBP'
        else:
            save_format = 'JPEG'
            img = img.convert('RGB')

        # 1. Main image: resize if larger than MAX_DIMENSION maintaining aspect ratio
        main_copy = img.copy()
        main_copy.thumbnail(cls.MAX_DIMENSION, Image.Resampling.LANCZOS)
        main_buf = io.BytesIO()
        if save_format == 'JPEG':
            main_copy.save(main_buf, format=save_format, quality=cls.JPEG_QUALITY, optimize=True)
        else:
            main_copy.save(main_buf, format=save_format, optimize=True)
        main_buf.seek(0)

        # 2. Profile thumbnail
        thumb_copy = img.copy()
        thumb_copy.thumbnail(cls.THUMB_DIMENSION, Image.Resampling.LANCZOS)
        thumb_buf = io.BytesIO()
        if save_format == 'JPEG':
            thumb_copy.save(thumb_buf, format=save_format, quality=cls.JPEG_QUALITY, optimize=True)
        else:
            thumb_copy.save(thumb_buf, format=save_format, optimize=True)
        thumb_buf.seek(0)

        return main_buf, thumb_buf, save_format

    # =========================================================================
    # Google Drive API Integration (OAuth 2.0 with dedicated Google Account)
    # =========================================================================

    @classmethod
    def _get_gdrive_service(cls):
        """
        Build and return an authorized Google Drive API v3 client using OAuth 2.0 refresh token.
        Token refresh is handled automatically by google-auth.
        """
        client_id = current_app.config.get('GOOGLE_DRIVE_CLIENT_ID')
        client_secret = current_app.config.get('GOOGLE_DRIVE_CLIENT_SECRET')
        refresh_token = current_app.config.get('GOOGLE_DRIVE_REFRESH_TOKEN')

        if not client_id or not client_secret or not refresh_token:
            raise ValueError(
                "Google Drive storage requires GOOGLE_DRIVE_CLIENT_ID, GOOGLE_DRIVE_CLIENT_SECRET, "
                "and GOOGLE_DRIVE_REFRESH_TOKEN environment variables."
            )

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as e:
            raise RuntimeError(
                "google-api-python-client and google-auth are required for Google Drive storage. "
                "Install via: pip install google-api-python-client google-auth google-auth-oauthlib"
            ) from e

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )

        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    @classmethod
    def _get_or_create_gdrive_folder(cls, service) -> str:
        """
        Get configured folder ID or discover/create dedicated private folder in Google Drive.
        """
        folder_id = current_app.config.get('GOOGLE_DRIVE_FOLDER_ID')
        if folder_id:
            return folder_id

        # Search for existing folder
        try:
            results = service.files().list(
                q="name='Miracle Hostel Residents (Private)' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
                spaces='drive'
            ).execute()
            files = results.get('files', [])
            if files:
                folder_id = files[0]['id']
                current_app.config['GOOGLE_DRIVE_FOLDER_ID'] = folder_id
                return folder_id

            # Create private folder
            folder_metadata = {
                'name': 'Miracle Hostel Residents (Private)',
                'mimeType': 'application/vnd.google-apps.folder',
                'description': 'Private storage for Miracle Hostel resident photographs'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
            current_app.config['GOOGLE_DRIVE_FOLDER_ID'] = folder_id
            print(f"[Miracle Hostel] Created Google Drive private folder (ID: {folder_id}). Configure GOOGLE_DRIVE_FOLDER_ID={folder_id} in your environment variables.")
            return folder_id
        except Exception as e:
            raise RuntimeError(f"Failed to resolve or create Google Drive folder: {str(e)}") from e

    @classmethod
    def _save_to_google_drive(cls, main_buf: io.BytesIO, thumb_buf: io.BytesIO | None, fmt: str) -> str:
        """
        Upload compressed main photograph and thumbnail to Google Drive.
        Uses randomized, non-identifying filenames.
        Cleans up the main image if thumbnail upload fails.
        Returns reference path e.g. /residents/photo/gdrive_main_<main_id>__thumb_<thumb_id>.jpg
        """
        from googleapiclient.http import MediaIoBaseUpload

        service = cls._get_gdrive_service()
        folder_id = cls._get_or_create_gdrive_folder(service)

        mimetype = f"image/{fmt.lower()}" if fmt else 'image/jpeg'
        rand_token = uuid.uuid4().hex

        # 1. Upload main image
        main_buf.seek(0)
        main_media = MediaIoBaseUpload(main_buf, mimetype=mimetype, resumable=False)
        main_metadata = {
            'name': f"res_{rand_token}.jpg",
            'parents': [folder_id],
            'description': 'Miracle Hostel Resident Photograph'
        }

        try:
            main_file = service.files().create(
                body=main_metadata,
                media_body=main_media,
                fields='id'
            ).execute()
            main_file_id = main_file.get('id')
        except Exception as e:
            raise RuntimeError(f"Google Drive main photograph upload failed: {str(e)}") from e

        # 2. Upload thumbnail if available
        thumb_file_id = None
        if thumb_buf:
            thumb_buf.seek(0)
            thumb_media = MediaIoBaseUpload(thumb_buf, mimetype=mimetype, resumable=False)
            thumb_metadata = {
                'name': f"thumb_res_{rand_token}.jpg",
                'parents': [folder_id],
                'description': 'Miracle Hostel Resident Photograph Thumbnail'
            }
            try:
                thumb_file = service.files().create(
                    body=thumb_metadata,
                    media_body=thumb_media,
                    fields='id'
                ).execute()
                thumb_file_id = thumb_file.get('id')
            except Exception as e:
                # Cleanup uploaded main image to prevent orphaned files
                try:
                    service.files().delete(fileId=main_file_id).execute()
                except Exception:
                    pass
                raise RuntimeError(
                    f"Google Drive thumbnail upload failed. Cleaned up main image: {str(e)}"
                ) from e

        if thumb_file_id:
            return f"/residents/photo/gdrive_main_{main_file_id}__thumb_{thumb_file_id}.jpg"
        return f"/residents/photo/gdrive_main_{main_file_id}.jpg"

    @classmethod
    def _parse_gdrive_ids(cls, filename_or_path: str) -> tuple[str, str | None]:
        """
        Extract main_file_id and optional thumb_file_id from a Google Drive reference or filename.
        Handles:
          - /residents/photo/gdrive_main_ABC__thumb_XYZ.jpg -> ('ABC', 'XYZ')
          - gdrive_main_ABC.jpg -> ('ABC', None)
          - gdrive_ABC_XYZ.jpg -> ('ABC', 'XYZ')
          - gdrive_ABC.jpg -> ('ABC', None)
        """
        clean = filename_or_path.split('/residents/photo/')[-1].strip()
        if clean.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            clean = clean.rsplit('.', 1)[0]

        if clean.startswith('thumb_'):
            clean = clean[len('thumb_'):]

        if clean.startswith('gdrive_main_'):
            clean = clean[len('gdrive_main_'):]
            if '__thumb_' in clean:
                main_id, thumb_id = clean.split('__thumb_', 1)
                return (main_id, thumb_id)
            return (clean, None)
        elif clean.startswith('gdrive_'):
            clean = clean[len('gdrive_'):]
            if '__thumb_' in clean:
                main_id, thumb_id = clean.split('__thumb_', 1)
                return (main_id, thumb_id)
            parts = clean.split('_')
            if len(parts) >= 2:
                return (parts[0], parts[1])
            return (clean, None)

        return (clean, None)

    @classmethod
    def _serve_from_google_drive(cls, filename: str):
        """
        Stream resident photograph directly from Google Drive API to authenticated browser.
        Enforces private caching headers and strict nosniff content security.
        Falls back to default avatar on 404 or missing file.
        """
        from googleapiclient.http import MediaIoBaseDownload
        from googleapiclient.errors import HttpError

        main_id, thumb_id = cls._parse_gdrive_ids(filename)
        target_id = thumb_id if filename.startswith('thumb_') and thumb_id else main_id

        if not target_id:
            abort(404)

        try:
            service = cls._get_gdrive_service()
            req = service.files().get_media(fileId=target_id)
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, req)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            buf.seek(0)
            data = buf.getvalue()
        except HttpError as e:
            if e.resp.status in (404, 403):
                default_avatar_path = Path(current_app.root_path) / 'static' / 'images' / 'default_avatar.svg'
                if default_avatar_path.exists():
                    return send_from_directory(
                        str(default_avatar_path.parent),
                        default_avatar_path.name,
                        mimetype='image/svg+xml'
                    )
                abort(404)
            raise
        except Exception:
            default_avatar_path = Path(current_app.root_path) / 'static' / 'images' / 'default_avatar.svg'
            if default_avatar_path.exists():
                return send_from_directory(
                    str(default_avatar_path.parent),
                    default_avatar_path.name,
                    mimetype='image/svg+xml'
                )
            abort(404)

        mimetype = 'image/jpeg'
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            mimetype = 'image/png'
        elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            mimetype = 'image/webp'
        elif data.startswith(b'<svg') or b'<svg' in data[:100]:
            mimetype = 'image/svg+xml'

        response = Response(data, mimetype=mimetype)
        response.headers['Cache-Control'] = 'private, max-age=3600'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @classmethod
    def _delete_from_google_drive(cls, photograph_path: str) -> bool:
        """
        Delete main photograph and thumbnail from Google Drive.
        Handles already-deleted files (404) safely as success.
        Raises on API failures to prevent permanent resident deletion with orphaned files.
        """
        from googleapiclient.errors import HttpError

        main_id, thumb_id = cls._parse_gdrive_ids(photograph_path)
        if not main_id:
            return False

        service = cls._get_gdrive_service()
        deleted_any = False

        for fid in filter(None, [main_id, thumb_id]):
            try:
                service.files().delete(fileId=fid).execute()
                deleted_any = True
            except HttpError as e:
                if e.resp.status == 404:
                    deleted_any = True
                else:
                    current_app.logger.error(f"Google Drive delete failed for file {fid}: {str(e)}")
                    raise
            except Exception as e:
                current_app.logger.error(f"Google Drive communication error during delete of {fid}: {str(e)}")
                raise

        return deleted_any

    # =========================================================================
    # Unified Public Storage API
    # =========================================================================

    @classmethod
    def save_photograph(cls, file: FileStorage, prefix: str = "res") -> str:
        """
        Save resident photograph to private storage with compression and thumbnail generation.
        Supports: 'google_drive', 'local_private', and 's3'.
        Returns a string reference to be stored in PostgreSQL (e.g. /residents/photo/res_abc123.jpg or /residents/photo/gdrive_main_...).
        """
        if not file or not file.filename:
            return ""

        ext = get_file_extension(file.filename) or 'jpg'
        unique_base = f"{prefix}_{uuid.uuid4().hex[:16]}"
        unique_filename = secure_filename(f"{unique_base}.{ext}")
        thumb_filename = secure_filename(f"thumb_{unique_base}.{ext}")

        # Compress and generate thumbnail via Pillow
        try:
            main_buf, thumb_buf, fmt = cls._process_image(file)
        except Exception:
            file.seek(0)
            main_buf = io.BytesIO(file.read())
            thumb_buf = None
            fmt = ext.upper()

        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

        # 1. Google Drive Backend (Recommended for Render)
        if backend == 'google_drive':
            return cls._save_to_google_drive(main_buf, thumb_buf, fmt)

        # 2. Cloud Object Storage (S3 / OCI S3-Compatible) Option
        if backend in ('s3', 'oci'):
            bucket_name = current_app.config.get('S3_BUCKET_NAME')
            if not bucket_name:
                raise ValueError("S3_BUCKET_NAME must be configured when STORAGE_BACKEND='s3' or 'oci'")
            if not BOTO3_AVAILABLE:
                raise RuntimeError("boto3 is required for cloud object storage. Install via 'pip install boto3'")

            s3_client = boto3.client(
                's3',
                region_name=current_app.config.get('S3_REGION', 'ap-south-1'),
                endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
                aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY')
            )

            s3_key = f"residents/{unique_filename}"
            mime_type = f"image/{fmt.lower()}" if fmt else 'image/jpeg'

            s3_client.upload_fileobj(
                main_buf,
                bucket_name,
                s3_key,
                ExtraArgs={'ACL': 'private', 'ContentType': mime_type}
            )

            if thumb_buf:
                s3_client.upload_fileobj(
                    thumb_buf,
                    bucket_name,
                    f"residents/{thumb_filename}",
                    ExtraArgs={'ACL': 'private', 'ContentType': mime_type}
                )

            return f"/residents/photo/{unique_filename}"

        # 3. Default: Local Private Storage (Outside app/static/)
        private_dir = cls.get_private_dir()
        main_path = private_dir / unique_filename
        with open(main_path, 'wb') as f:
            f.write(main_buf.getvalue())

        if thumb_buf:
            thumb_path = private_dir / thumb_filename
            with open(thumb_path, 'wb') as f:
                f.write(thumb_buf.getvalue())

        return f"/residents/photo/{unique_filename}"

    @classmethod
    def serve_file(cls, filename: str):
        """
        Serve file from private storage to authenticated administrator.
        Prevents path traversal attacks.
        Supports Google Drive streaming, local private files, and fallbacks.
        """
        # 1. Google Drive reference check
        if 'gdrive_' in filename:
            return cls._serve_from_google_drive(filename)

        safe_name = secure_filename(filename)
        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

        # 2. S3 Object Storage
        if backend in ('s3', 'oci'):
            bucket_name = current_app.config.get('S3_BUCKET_NAME')
            if BOTO3_AVAILABLE and bucket_name:
                s3_client = boto3.client(
                    's3',
                    region_name=current_app.config.get('S3_REGION', 'ap-south-1'),
                    endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
                    aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY')
                )
                try:
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': f"residents/{safe_name}"},
                        ExpiresIn=60
                    )
                    return redirect(presigned_url)
                except Exception:
                    abort(404)

        # 3. Local Private Storage
        private_dir = cls.get_private_dir()
        target_path = private_dir / safe_name
        if not target_path.exists() or not target_path.is_file():
            # Fall back to default avatar if photo does not exist locally
            default_avatar_path = Path(current_app.root_path) / 'static' / 'images' / 'default_avatar.svg'
            if default_avatar_path.exists():
                return send_from_directory(
                    str(default_avatar_path.parent),
                    default_avatar_path.name,
                    mimetype='image/svg+xml'
                )
            abort(404)

        return send_from_directory(str(private_dir), safe_name)

    @classmethod
    def delete_photograph(cls, photograph_path: str) -> bool:
        """
        Remove photograph and thumbnail when replaced or permanently purged.
        Supports Google Drive, local private storage, and S3.
        Never removes default avatar assets.
        """
        if not photograph_path or '/residents/photo/' not in photograph_path:
            return False

        # 1. Google Drive Backend
        if 'gdrive_' in photograph_path:
            return cls._delete_from_google_drive(photograph_path)

        filename = secure_filename(photograph_path.split('/residents/photo/')[-1])
        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

        # 2. S3 Object Storage
        if backend in ('s3', 'oci'):
            bucket_name = current_app.config.get('S3_BUCKET_NAME')
            if BOTO3_AVAILABLE and bucket_name:
                try:
                    s3_client = boto3.client(
                        's3',
                        region_name=current_app.config.get('S3_REGION', 'ap-south-1'),
                        endpoint_url=current_app.config.get('S3_ENDPOINT_URL'),
                        aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY_ID'),
                        aws_secret_access_key=current_app.config.get('AWS_SECRET_ACCESS_KEY')
                    )
                    s3_client.delete_object(Bucket=bucket_name, Key=f"residents/{filename}")
                    s3_client.delete_object(Bucket=bucket_name, Key=f"residents/thumb_{filename}")
                    return True
                except Exception:
                    return False

        # 3. Local Private Storage
        private_dir = cls.get_private_dir()
        main_file = private_dir / filename
        thumb_file = private_dir / f"thumb_{filename}"

        deleted = False
        if main_file.exists() and main_file.is_file():
            main_file.unlink(missing_ok=True)
            deleted = True
        if thumb_file.exists() and thumb_file.is_file():
            thumb_file.unlink(missing_ok=True)

        return deleted
