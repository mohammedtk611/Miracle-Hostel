"""
Settings and administrative profile routes for Miracle Hostel.
Protected with Flask-Login administrator session requirement.
Includes functional password change with verification and real audit log viewing.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.audit_log import AuditLog, AuditAction
from app.services.audit_service import AuditService

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('', methods=['GET', 'POST'])
@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Settings interface with Admin profile, password update, and system policies."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'change_password':
            current_pwd = request.form.get('current_password', '').strip()
            new_pwd = request.form.get('new_password', '').strip()
            confirm_pwd = request.form.get('confirm_password', '').strip()

            if not current_pwd or not new_pwd:
                flash("Please fill in all password fields.", "danger")
            elif not current_user.check_password(current_pwd):
                flash("Current password verification failed. Please check your existing password.", "danger")
            elif len(new_pwd) < 4:
                flash("New password must be at least 4 characters long.", "danger")
            elif new_pwd != confirm_pwd:
                flash("New password and confirmation password do not match.", "danger")
            else:
                # Update password securely in database
                current_user.set_password(new_pwd)
                db.session.commit()

                # Audit Log: Notice we NEVER log the password or hash
                AuditService.log(
                    action=AuditAction.PASSWORD_CHANGE,
                    entity_type='Admin',
                    entity_id=current_user.id,
                    description=f"Administrator '{current_user.username}' changed password successfully."
                )

                flash("Administrator password updated successfully!", "success")
                return redirect(url_for('settings.index'))

    admin_info = {
        'username': current_user.username,
        'email': current_user.email,
        'role': 'Super Administrator (Single Admin Account)',
        'last_login': current_user.last_login.strftime('%d %b %Y, %I:%M %p UTC') if current_user.last_login else 'Current Active Session',
        'last_login_ip': current_user.last_login_ip or '127.0.0.1',
        'created_at': current_user.created_at.strftime('%d %b %Y') if current_user.created_at else 'Initial Setup',
        'auth_policy': 'Argon2id Memory-Hard Cryptographic Hashing (RFC 9106)',
        'retention_policy_days': current_app.config.get('RESIDENT_RETENTION_DAYS', 30)
    }

    # Fetch recent audit logs from database
    recent_db_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    audit_logs_display = []
    if recent_db_logs:
        for log in recent_db_logs:
            audit_logs_display.append({
                'action': log.action,
                'entity': f"{log.entity_type}{f' #{log.entity_id}' if log.entity_id else ''}",
                'time': log.created_at.strftime('%d %b, %H:%M'),
                'details': log.description
            })
    else:
        # Fallback default initial audit events
        audit_logs_display = [
            {
                'action': 'SYSTEM_INIT',
                'entity': 'System Security',
                'time': 'Just now',
                'details': 'Administrator authentication & audit logging initialized'
            }
        ]

    # Fetch recent retention logs
    from app.models.data_retention_log import DataRetentionLog
    recent_retention_logs = DataRetentionLog.query.order_by(DataRetentionLog.executed_at.desc()).limit(5).all()

    return render_template(
        'settings/index.html',
        admin=admin_info,
        audit_logs=audit_logs_display,
        retention_logs=recent_retention_logs
    )
