"""
Private Storage Service for Miracle Hostel Management Portal.
Ensures resident photographs are NEVER stored in the publicly accessible application directory.
Supports:
1. 'local_private': Private local directory storage outside app/static/, served exclusively
   through an authenticated @login_required endpoint. Includes PIL image compression,
   resizing for oversized uploads, and automatic thumbnail generation.
2. 's3': Simple cloud object-storage integration using private Amazon S3 (or S3-compatible) buckets
   with private ACL and presigned URL access.
3. 'oci': Modular abstraction prepared for Oracle Cloud Infrastructure (OCI) Object Storage integration.
"""
import io
import os
import uuid
from pathlib import Path
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from flask import current_app, send_from_directory, abort, redirect
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

    @classmethod
    def save_photograph(cls, file: FileStorage, prefix: str = "res") -> str:
        """
        Save resident photograph to private storage with compression and thumbnail generation.
        Returns a string reference to be stored in PostgreSQL (e.g. /residents/photo/res_abc123.jpg).
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
            # Fallback if image manipulation encounters corrupt byte sequence
            file.seek(0)
            main_buf = io.BytesIO(file.read())
            thumb_buf = None

        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

        # Cloud Object Storage (S3 / OCI S3-Compatible) Option
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
            mime_type = f"image/{fmt.lower()}" if 'fmt' in locals() else 'image/jpeg'

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

        # Default: Local Private Storage (Outside app/static/)
        private_dir = cls.get_private_dir()
        main_path = private_dir / unique_filename
        with open(main_path, 'wb') as f:
            f.write(main_buf.getvalue())

        if thumb_buf:
            thumb_path = private_dir / thumb_filename
            with open(thumb_path, 'wb') as f:
                f.write(thumb_buf.getvalue())

        # Return reference for the protected authenticated endpoint
        return f"/residents/photo/{unique_filename}"

    @classmethod
    def serve_file(cls, filename: str):
        """
        Serve file from private storage to authenticated administrator.
        Prevents path traversal attacks.
        """
        safe_name = secure_filename(filename)
        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

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
                    # Generate short-lived presigned URL (valid for 60 seconds)
                    presigned_url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket_name, 'Key': f"residents/{safe_name}"},
                        ExpiresIn=60
                    )
                    return redirect(presigned_url)
                except Exception:
                    abort(404)

        # Local Private Storage
        private_dir = cls.get_private_dir()
        target_path = private_dir / safe_name
        if not target_path.exists() or not target_path.is_file():
            abort(404)

        return send_from_directory(str(private_dir), safe_name)

    @classmethod
    def delete_photograph(cls, photograph_path: str) -> bool:
        """
        Remove obsolete photograph and thumbnail when replaced or deleted.
        Never removes default avatar assets.
        """
        if not photograph_path or '/residents/photo/' not in photograph_path:
            return False

        filename = secure_filename(photograph_path.split('/residents/photo/')[-1])
        backend = current_app.config.get('STORAGE_BACKEND', 'local_private').lower()

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

        # Local Private Storage
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
