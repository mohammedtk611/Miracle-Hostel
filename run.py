"""
Application Entry Point for Miracle Hostel Management Portal.
Includes secure CLI commands for database initialization, migrations, and administrator management.
"""
import os
import sys
import socket
import click

# Ensure project root directory is always on python sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import Admin, Branch
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.seed_service import seed_database_sample_data
from app.services.migration_service import MigrationService

app = create_app(os.environ.get('FLASK_ENV', 'development'))


def get_local_ip():
    """Retrieve primary local LAN IP address for multi-device testing (e.g. mobile on Wi-Fi)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'


def find_available_port(start_port=5000, host='0.0.0.0'):
    """Check if the designated port is free; if not, find the next available port."""
    port = start_port
    while port < start_port + 25:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    return start_port


def seed_or_create_admin(email=None, username=None, password=None):
    """
    Core function to safely initialize or update the administrator account.
    In production: Requires explicitly provided password or ADMIN_DEFAULT_PASSWORD env var.
    In development: Uses developer defaults if not provided.
    """
    with app.app_context():
        is_prod = app.config.get('ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'

        email = email or os.environ.get('ADMIN_EMAIL')
        username = username or os.environ.get('ADMIN_USERNAME')
        password = password or os.environ.get('ADMIN_DEFAULT_PASSWORD')

        if is_prod:
            if not email:
                email = 'admin@miraclehostel.com'
            if not username:
                username = 'admin'
            if not password:
                raise ValueError(
                    "In production, an explicit administrator password must be provided via "
                    "--password CLI option or ADMIN_DEFAULT_PASSWORD environment variable."
                )
        else:
            email = email or 'admin@123'
            username = username or 'admin'
            password = password or '1234'

        existing_admin = Admin.query.first()
        if existing_admin:
            existing_admin.email = email
            existing_admin.username = username
            existing_admin.set_password(password)
            existing_admin.is_active = True
            db.session.commit()
            print(f"[Miracle Hostel] Existing administrator updated: {username} ({email})")
            AuditService.log(
                action=AuditAction.PASSWORD_CHANGE,
                entity_type='Admin',
                entity_id=existing_admin.id,
                description=f"Administrator credentials updated via secure CLI setup for {email}."
            )
            return existing_admin
        else:
            new_admin = Admin(email=email, username=username, is_active=True)
            new_admin.set_password(password)
            db.session.add(new_admin)
            db.session.commit()
            print(f"[Miracle Hostel] Initial administrator account created: {username} ({email})")
            AuditService.log(
                action=AuditAction.LOGIN,
                entity_type='Admin',
                entity_id=new_admin.id,
                description=f"Initial administrator account created via secure CLI for {email}."
            )
            return new_admin


def run_server():
    """Development and production server runner with automatic schema check and multi-device access."""
    is_prod = app.config.get('ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'

    with app.app_context():
        db.create_all()
        MigrationService.migrate_schema()
        if not is_prod:
            if not Admin.query.first():
                seed_or_create_admin()
            if not Branch.query.first():
                seed_database_sample_data()

    requested_port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    port = find_available_port(requested_port, host=host) if not is_prod else requested_port
    debug = (not is_prod) and os.environ.get('FLASK_DEBUG', 'true').lower() in ('true', '1', 'yes')
    local_ip = get_local_ip()

    print(f"\n=========================================================")
    print(f"  Miracle Hostel Management Portal ({app.config.get('ENV', 'development').upper()})")
    print(f"  > Desktop / Laptop:   http://localhost:{port}")
    print(f"  > Local Loopback:     http://127.0.0.1:{port}")
    if local_ip and local_ip != '127.0.0.1':
        print(f"  > Mobile on Wi-Fi:    http://{local_ip}:{port}")
    print(f"  > Sign-in Email:      admin@123")
    print(f"  > Sign-in Password:   1234")
    if port != requested_port:
        print(f"  [Notice] Port {requested_port} was in use; started on port {port}.")
    print(f"=========================================================\n")
    app.run(host=host, port=port, debug=debug)


@app.cli.command("init-db")
@click.option("--seed/--no-seed", default=None, help="Seed sample demo data (defaults to False in production, True in development)")
def init_db(seed):
    """
    CLI command to initialize database schema safely.
    In production: Creates tables and applies schema migrations WITHOUT inserting demo data.
    """
    with app.app_context():
        db.create_all()
        MigrationService.migrate_schema()

        is_prod = app.config.get('ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'
        should_seed = seed if seed is not None else (not is_prod)

        if should_seed:
            seed_database_sample_data()
            print("[Miracle Hostel] Database initialized and sample demonstration data seeded.")
        else:
            print("[Miracle Hostel] Database initialized safely without sample demonstration data.")


@app.cli.command("seed-db")
def seed_db():
    """CLI command to explicitly seed sample branches, residents, and payments (development only)."""
    with app.app_context():
        db.create_all()
        MigrationService.migrate_schema()
        seeded = seed_database_sample_data(force=True)
        print(f"[Miracle Hostel] Database sample data seeded (forced: {seeded}).")


@app.cli.command("create-admin")
@click.option("--email", default=None, help="Administrator email address")
@click.option("--username", default=None, help="Administrator username")
@click.option("--password", default=None, help="Administrator password")
def create_admin_cli(email, username, password):
    """Secure CLI command to create or update the single administrator account."""
    seed_or_create_admin(email, username, password)


if __name__ == '__main__':
    args = sys.argv[1:]
    is_prod = app.config.get('ENV') == 'production' or os.environ.get('FLASK_ENV') == 'production'

    if args and args[0] == 'init-db':
        with app.app_context():
            db.create_all()
            MigrationService.migrate_schema()
            should_seed = False if is_prod else ('--seed' in args or not ('--no-seed' in args))
            if should_seed:
                seed_database_sample_data()
                print("[Miracle Hostel] Database initialized and sample demonstration data seeded.")
            else:
                print("[Miracle Hostel] Database initialized safely without sample demonstration data.")
    elif args and args[0] == 'seed-db':
        with app.app_context():
            db.create_all()
            MigrationService.migrate_schema()
            seed_database_sample_data(force=True)
            print("[Miracle Hostel] Database sample data seeded successfully.")
    elif args and args[0] == 'cleanup-expired-residents':
        with app.app_context():
            from app.services.retention_service import RetentionService
            result = RetentionService.run_retention_cleanup()
            print(f"[Miracle Hostel] {result['message']}")
    elif args and args[0] == 'create-admin':
        email = None
        username = None
        password = None
        for i, arg in enumerate(args):
            if arg == '--email' and i + 1 < len(args):
                email = args[i + 1]
            elif arg == '--username' and i + 1 < len(args):
                username = args[i + 1]
            elif arg == '--password' and i + 1 < len(args):
                password = args[i + 1]
        seed_or_create_admin(email, username, password)
    else:
        run_server()
