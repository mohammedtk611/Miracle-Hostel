"""
Resident management routes for Miracle Hostel.
Protected with Flask-Login administrator session requirement.
Complete PostgreSQL integration with:
- Resident registration with server-side validation and auto-generated resident ID
- Server-side search by name/ID, branch filter, status filter, and database pagination
- Encrypted Aadhaar handling (AES-256 GCM)
- Photograph management with upload, preview, resizing, thumbnailing, and obsolete photo deletion
- Detailed individual resident profile
- Edit resident details with branch validation, photo replacement, and audit logging
"""
from datetime import datetime, date, timedelta
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required
from sqlalchemy import or_
from app.extensions import db
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentMethod
from app.models.payment_obligation import PaymentObligation, ObligationType
from app.models.resident_stay_history import ResidentStayHistory
from app.models.audit_log import AuditAction
from app.services.aadhaar_service import AadhaarSecurityService
from app.services.audit_service import AuditService
from app.services.storage_service import StorageService
from app.services.financial_service import FinancialService
from app.utils.file_security import validate_image_upload

residents_bp = Blueprint('residents', __name__, url_prefix='/residents')


@residents_bp.route('')
@residents_bp.route('/')
@login_required
def index():
    """Resident Directory view with server-side search, branch filter, status filter, and pagination."""
    search = request.args.get('search', '').strip()
    branch_id = request.args.get('branch', 'all')
    status = request.args.get('status', 'ALL').upper()
    deposit_status = request.args.get('deposit_status', 'ALL').upper()
    rent_status = request.args.get('rent_status', 'ALL').upper()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Resident.query.options(db.joinedload(Resident.branch)).join(Branch)

    # 1. Search by resident name or resident ID
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Resident.full_name.ilike(search_filter),
                Resident.resident_code.ilike(search_filter)
            )
        )

    # 2. Branch filter
    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            query = query.filter(Resident.branch_id == b_id)
        except (ValueError, TypeError):
            pass

    # 3. Resident Status filter (Active / Left)
    if status == 'ACTIVE':
        query = query.filter(Resident.resident_status == ResidentStatus.ACTIVE)
    elif status == 'LEFT':
        query = query.filter(Resident.resident_status == ResidentStatus.LEFT)

    # Order by admission date / ID descending
    query = query.order_by(Resident.admission_date.desc(), Resident.id.desc())

    # Database Pagination (Limits records fetched per query)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    residents_list = pagination.items

    # Filter in Python if specific deposit/rent status filter is requested
    if deposit_status != 'ALL':
        residents_list = [r for r in residents_list if r.deposit_status == deposit_status]
    if rent_status != 'ALL':
        residents_list = [r for r in residents_list if r.rent_status == rent_status]

    branches = Branch.query.order_by(Branch.branch_name.asc()).all()
    active_branches = [b for b in branches if b.is_active]

    return render_template(
        'residents/index.html',
        residents=residents_list,
        pagination=pagination,
        branches=branches,
        active_branches=active_branches,
        selected_branch=branch_id,
        selected_status=status,
        selected_deposit_status=deposit_status,
        selected_rent_status=rent_status,
        search_query=search,
        total_count=pagination.total
    )


@residents_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add Resident registration form with validation, encrypted Aadhaar, and photo upload."""
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        aadhaar_number = request.form.get('aadhaar_number', '').strip()
        branch_id = request.form.get('branch_id')
        admission_date_str = request.form.get('admission_date', '').strip()
        security_deposit_str = request.form.get('security_deposit', '').strip()
        deposit_status = request.form.get('deposit_status', PaymentStatus.PAID)

        # Form validation
        errors = []
        if not full_name or len(full_name) < 2:
            errors.append("Valid full legal name is required (minimum 2 characters).")

        # Validate branch exists and is active
        target_branch = None
        if not branch_id:
            errors.append("Please select a Hostel Branch.")
        else:
            try:
                target_branch = db.session.get(Branch, int(branch_id))
                if not target_branch:
                    errors.append("Selected branch does not exist.")
                elif not target_branch.is_active:
                    errors.append("Selected branch is deactivated. Please choose an active branch.")
            except (ValueError, TypeError):
                errors.append("Invalid branch selection.")

        # Validate admission date
        parsed_admission_date = None
        if not admission_date_str:
            errors.append("Admission Date is required.")
        else:
            try:
                parsed_admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Invalid admission date format. Use YYYY-MM-DD.")

        # Aadhaar format validation if supplied
        if aadhaar_number:
            if not AadhaarSecurityService.validate_format(aadhaar_number):
                errors.append("Invalid Aadhaar format. Must be a 12-digit number (cannot start with 0 or 1).")

        # Photograph file validation if uploaded
        photo_file = request.files.get('photograph')
        photo_path = None
        if photo_file and photo_file.filename:
            is_valid_img, img_err = validate_image_upload(photo_file)
            if not is_valid_img:
                errors.append(f"Photograph upload error: {img_err}")
            else:
                photo_path = StorageService.save_photograph(photo_file, prefix="res")
        else:
            # Default placeholder avatar
            photo_path = "/static/images/avatars/avatar-1.svg"

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                'residents/add.html',
                branches=branches,
                form_data=request.form,
                today=admission_date_str or date.today().strftime('%Y-%m-%d')
            )

        # Encrypt Aadhaar before database storage
        if aadhaar_number:
            enc_aadhaar = AadhaarSecurityService.encrypt_aadhaar(aadhaar_number)
            last_four = AadhaarSecurityService.extract_last_four(aadhaar_number)
        else:
            enc_aadhaar = ""
            last_four = ""

        # Auto-generate unique resident ID (MHL-YYYY-NNN)
        resident_code = Resident.generate_unique_code()

        # Parse financial baselines
        monthly_rent_str = request.form.get('monthly_rent', '8500').strip()
        admission_rent_str = request.form.get('admission_rent', '').strip()
        admission_rent_status = request.form.get('admission_rent_status', PaymentStatus.PAID)

        try:
            dep_due = float(security_deposit_str) if security_deposit_str else 12000.00
        except ValueError:
            dep_due = 12000.00

        try:
            m_rent = float(monthly_rent_str) if monthly_rent_str else 8500.00
        except ValueError:
            m_rent = 8500.00

        try:
            adm_due = float(admission_rent_str) if admission_rent_str else m_rent
        except ValueError:
            adm_due = m_rent

        # Create and save in PostgreSQL
        new_resident = Resident(
            resident_code=resident_code,
            branch_id=target_branch.id,
            full_name=full_name,
            photograph_path=photo_path,
            aadhaar_encrypted=enc_aadhaar,
            aadhaar_last_four=last_four,
            admission_date=parsed_admission_date,
            resident_status=ResidentStatus.ACTIVE,
            security_deposit_due=dep_due,
            monthly_rent_amount=m_rent,
            admission_rent_due=adm_due
        )
        db.session.add(new_resident)
        db.session.flush()

        # 1. Initial Security Deposit Obligation & Payment
        dep_ob = PaymentObligation(
            resident_id=new_resident.id,
            branch_id=new_resident.branch_id,
            obligation_type=ObligationType.SECURITY_DEPOSIT,
            title="Initial Security Deposit",
            expected_amount=dep_due,
            due_date=parsed_admission_date,
            notes="Security deposit agreed upon admission"
        )
        db.session.add(dep_ob)
        db.session.flush()

        if dep_due > 0 and deposit_status in (PaymentStatus.PAID, PaymentStatus.PARTIAL):
            dep_pay_amt = dep_due if deposit_status == PaymentStatus.PAID else (dep_due / 2)
            deposit_payment = Payment(
                resident_id=new_resident.id,
                branch_id=new_resident.branch_id,
                obligation_id=dep_ob.id,
                payment_type=PaymentType.SECURITY_DEPOSIT,
                amount=dep_pay_amt,
                payment_date=parsed_admission_date,
                payment_status=deposit_status,
                payment_method='CASH',
                transaction_reference=f"DEP-{int(datetime.utcnow().timestamp())}",
                notes="Initial security deposit recorded upon admission"
            )
            db.session.add(deposit_payment)

        # 2. Initial Admission Rent Obligation & Payment (Phase 6 requirement)
        adm_ob = PaymentObligation(
            resident_id=new_resident.id,
            branch_id=new_resident.branch_id,
            obligation_type=ObligationType.ADMISSION_RENT,
            title="Admission Rent Obligation",
            expected_amount=adm_due,
            due_date=parsed_admission_date,
            notes="Initial admission rent recorded upon onboarding"
        )
        db.session.add(adm_ob)
        db.session.flush()

        if admission_rent_str and admission_rent_status in (PaymentStatus.PAID, PaymentStatus.PARTIAL):
            adm_pay_amt = adm_due if admission_rent_status == PaymentStatus.PAID else (adm_due / 2)
            adm_payment = Payment(
                resident_id=new_resident.id,
                branch_id=new_resident.branch_id,
                obligation_id=adm_ob.id,
                payment_type=PaymentType.ADMISSION_RENT,
                amount=adm_pay_amt,
                payment_date=parsed_admission_date,
                payment_status=admission_rent_status,
                payment_method='CASH',
                transaction_reference=f"ADM-{int(datetime.utcnow().timestamp())}",
                notes="Admission rent payment recorded during onboarding"
            )
            db.session.add(adm_payment)

        db.session.commit()

        # Audit logging (never logging full Aadhaar)
        masked_info = f"ending in {last_four}" if last_four else "no Aadhaar provided"
        AuditService.log(
            action=AuditAction.RESIDENT_CREATE,
            entity_type='Resident',
            entity_id=new_resident.id,
            description=f"Resident '{full_name}' ({resident_code}) registered to branch '{target_branch.branch_name}' ({masked_info})."
        )

        flash(
            f"Resident '{full_name}' successfully registered! Assigned Resident ID: {resident_code}.",
            "success"
        )
        return redirect(url_for('residents.profile', resident_code=new_resident.resident_code))

    return render_template(
        'residents/add.html',
        branches=branches,
        today=date.today().strftime('%Y-%m-%d')
    )


@residents_bp.route('/<resident_code>')
@login_required
def profile(resident_code):
    """Detailed individual resident profile view."""
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    # Decrypt complete Aadhaar number strictly for authorized administrator profile view
    full_aadhaar = resident.get_decrypted_aadhaar() if resident.aadhaar_encrypted else None

    payments = resident.payments.order_by(Payment.payment_date.desc(), Payment.id.desc()).all()
    active_branches = Branch.query.filter_by(is_active=True).order_by(Branch.branch_name.asc()).all()
    stay_history = resident.stay_history.order_by(ResidentStayHistory.stay_number.desc()).all()

    return render_template(
        'residents/profile.html',
        resident=resident,
        full_aadhaar=full_aadhaar,
        payments=payments,
        stay_history=stay_history,
        retention=resident.retention,
        branch=resident.branch,
        active_branches=active_branches,
        today=date.today().strftime('%Y-%m-%d')
    )


@residents_bp.route('/<resident_code>/edit', methods=['GET', 'POST'])
@login_required
def edit(resident_code):
    """Edit resident personal details, branch assignment, admission date, and photograph."""
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        branch_id = request.form.get('branch_id')
        admission_date_str = request.form.get('admission_date', '').strip()
        aadhaar_number = request.form.get('aadhaar_number', '').strip()

        errors = []
        if not full_name or len(full_name) < 2:
            errors.append("Valid full legal name is required (minimum 2 characters).")

        # Branch validation
        target_branch = None
        if not branch_id:
            errors.append("Please select a branch.")
        else:
            try:
                target_branch = db.session.get(Branch, int(branch_id))
                if not target_branch:
                    errors.append("Selected branch does not exist.")
                elif not target_branch.is_active and target_branch.id != resident.branch_id:
                    errors.append("Cannot transfer resident to a deactivated branch.")
            except (ValueError, TypeError):
                errors.append("Invalid branch selection.")

        # Admission date validation
        parsed_date = None
        if not admission_date_str:
            errors.append("Admission date is required.")
        else:
            try:
                parsed_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append("Invalid admission date format. Use YYYY-MM-DD.")

        # Aadhaar validation and update if modified
        if aadhaar_number:
            clean_aadhaar = re.sub(r'[\s\-]', '', aadhaar_number)
            current_raw = resident.get_raw_aadhaar()
            # If changed from current
            if clean_aadhaar != current_raw:
                if not AadhaarSecurityService.validate_format(clean_aadhaar):
                    errors.append("Invalid Aadhaar format. Must be a 12-digit number (cannot start with 0 or 1).")
                else:
                    resident.aadhaar_encrypted = AadhaarSecurityService.encrypt_aadhaar(clean_aadhaar)
                    resident.aadhaar_last_four = AadhaarSecurityService.extract_last_four(clean_aadhaar)

        # Photograph replacement if provided
        photo_file = request.files.get('photograph')
        old_photo_path = resident.photograph_path
        new_photo_path = None
        if photo_file and photo_file.filename:
            is_valid_img, img_err = validate_image_upload(photo_file)
            if not is_valid_img:
                errors.append(f"Photograph error: {img_err}")
            else:
                # Upload and verify the new photograph first before modifying DB or deleting old
                try:
                    new_photo_path = StorageService.save_photograph(photo_file, prefix="res")
                    resident.photograph_path = new_photo_path
                except Exception as e:
                    errors.append(f"Photograph upload failed: {str(e)}")

        if errors:
            for err in errors:
                flash(err, "danger")
            return redirect(url_for('residents.profile', resident_code=resident.resident_code))

        # Apply updates
        resident.full_name = full_name
        resident.branch_id = target_branch.id
        resident.admission_date = parsed_date
        resident.updated_at = datetime.utcnow()
        db.session.commit()

        # Safely remove obsolete photograph only after commit succeeds
        if new_photo_path and old_photo_path and old_photo_path != new_photo_path:
            other_ref = Resident.query.filter(
                Resident.id != resident.id,
                Resident.photograph_path == old_photo_path
            ).first()
            if not other_ref:
                try:
                    StorageService.delete_photograph(old_photo_path)
                except Exception as e:
                    current_app.logger.warning(f"Could not delete old photograph '{old_photo_path}': {e}")

        AuditService.log(
            action=AuditAction.RESIDENT_UPDATE,
            entity_type='Resident',
            entity_id=resident.id,
            description=f"Administrator updated profile for resident '{resident.full_name}' ({resident.resident_code})."
        )

        flash(f"Resident '{resident.full_name}' details updated successfully!", "success")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    return redirect(url_for('residents.profile', resident_code=resident_code))


@residents_bp.route('/<resident_code>/update-photo', methods=['POST'])
@login_required
def update_photo(resident_code):
    """Directly replace a resident's photograph and remove the obsolete file."""
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        flash("Resident record not found.", "danger")
        return redirect(url_for('residents.index'))

    photo_file = request.files.get('photograph')
    if not photo_file or not photo_file.filename:
        flash("Please select an image file to upload.", "warning")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    is_valid_img, img_err = validate_image_upload(photo_file)
    if not is_valid_img:
        flash(f"Photograph upload error: {img_err}", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    old_photo = resident.photograph_path
    # 1. Upload and verify new image first
    try:
        new_photo = StorageService.save_photograph(photo_file, prefix="res")
    except Exception as e:
        flash(f"Failed to upload new photograph: {str(e)}", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    # 2. Update database reference
    resident.photograph_path = new_photo
    resident.updated_at = datetime.utcnow()
    db.session.commit()

    # 3. Safely delete obsolete image only after new photograph and DB commit succeed
    if old_photo and old_photo != new_photo:
        other_ref = Resident.query.filter(
            Resident.id != resident.id,
            Resident.photograph_path == old_photo
        ).first()
        if not other_ref:
            try:
                StorageService.delete_photograph(old_photo)
            except Exception as e:
                current_app.logger.warning(f"Could not delete old photograph '{old_photo}': {e}")

    AuditService.log(
        action=AuditAction.RESIDENT_UPDATE,
        entity_type='Resident',
        entity_id=resident.id,
        description=f"Replaced photograph for resident '{resident.full_name}' ({resident.resident_code})."
    )

    flash("Photograph replaced successfully!", "success")
    return redirect(url_for('residents.profile', resident_code=resident.resident_code))


@residents_bp.route('/leaving')
@login_required
def leaving():
    """
    Leaving residents view displaying residents currently in their 30-day notice/retention window.
    If not retained within 30 days, they automatically transfer to Previous Residents (LEFT).
    """
    # 1. Automatically rollover any leaving residents whose 30 days elapsed without retention
    Resident.check_and_transition_expired_leaving()

    search = request.args.get('search', '').strip()
    branch_id = request.args.get('branch', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Resident.query.options(db.joinedload(Resident.branch)).filter(
        Resident.resident_status == ResidentStatus.LEAVING
    ).join(Branch)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Resident.full_name.ilike(search_filter),
                Resident.resident_code.ilike(search_filter)
            )
        )

    if branch_id and branch_id != 'all':
        try:
            b_id = int(branch_id)
            query = query.filter(Resident.branch_id == b_id)
        except (ValueError, TypeError):
            pass

    query = query.order_by(Resident.notice_date.desc(), Resident.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    residents_list = pagination.items

    branches = Branch.query.order_by(Branch.branch_name.asc()).all()
    active_branches = [b for b in branches if b.is_active]

    return render_template(
        'residents/leaving.html',
        residents=residents_list,
        pagination=pagination,
        branches=branches,
        active_branches=active_branches,
        selected_branch=branch_id,
        search_query=search,
        total_count=pagination.total,
        today=date.today().strftime('%Y-%m-%d')
    )


@residents_bp.route('/<resident_code>/mark-leaving', methods=['POST'])
@login_required
def mark_leaving(resident_code):
    """
    Mark an active resident as LEAVING.
    Enters a 30-day timeframe in Leaving Residents section where they can be retained.
    If not retained within 30 days, they automatically transfer to Previous Residents.
    """
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    if resident.resident_status == ResidentStatus.LEAVING:
        flash(f"Resident '{resident.full_name}' is already in the Leaving Residents section.", "warning")
        return redirect(url_for('residents.leaving'))

    notice_date_str = request.form.get('notice_date', '').strip()
    leaving_date_str = request.form.get('leaving_date', '').strip()

    today = date.today()
    try:
        notice_date = datetime.strptime(notice_date_str, '%Y-%m-%d').date() if notice_date_str else today
    except ValueError:
        notice_date = today

    try:
        expected_leaving_date = datetime.strptime(leaving_date_str, '%Y-%m-%d').date() if leaving_date_str else (notice_date + timedelta(days=30))
    except ValueError:
        expected_leaving_date = notice_date + timedelta(days=30)

    resident.resident_status = ResidentStatus.LEAVING
    resident.notice_date = notice_date
    resident.leaving_date = expected_leaving_date
    resident.updated_at = datetime.utcnow()
    db.session.commit()

    AuditService.log(
        action=AuditAction.RESIDENT_DEPARTURE,
        entity_type='Resident',
        entity_id=resident.id,
        description=f"Marked resident '{resident.full_name}' ({resident.resident_code}) for leaving with 30-day retention timeframe."
    )

    flash(f"Resident '{resident.full_name}' is now marked for leaving and added to the Leaving Residents section with a 30-day retention window.", "warning")
    return redirect(url_for('residents.leaving'))


@residents_bp.route('/<resident_code>/retain', methods=['POST'], endpoint='retain')
@residents_bp.route('/<resident_code>/retain-resident', methods=['POST'], endpoint='retain_resident')
@login_required
def retain(resident_code):
    """
    Retain a resident from LEAVING status, restoring them to ACTIVE status.
    Cancels leaving notice.
    """
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    resident.resident_status = ResidentStatus.ACTIVE
    resident.notice_date = None
    resident.updated_at = datetime.utcnow()
    db.session.commit()

    AuditService.log(
        action=AuditAction.RESIDENT_REACTIVATE,
        entity_type='Resident',
        entity_id=resident.id,
        description=f"Retained resident '{resident.full_name}' ({resident.resident_code}) back to ACTIVE status."
    )

    flash(f"Resident '{resident.full_name}' has been successfully retained and restored to Active Residents!", "success")
    return redirect(url_for('residents.index'))


@residents_bp.route('/previous')
@login_required
def previous():
    """
    Previous residents view displaying left residents subject to 30-day retention policy.
    Connected to PostgreSQL.
    Supports search, branch filtering, retention urgency filtering, and leaving date ranges.
    """
    search = request.args.get('search', '').strip()
    branch_id = request.args.get('branch', 'all')
    urgency = request.args.get('urgency', 'ALL').strip().lower()
    from_date_str = request.args.get('from_date', '').strip()
    to_date_str = request.args.get('to_date', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Resident.query.options(db.joinedload(Resident.branch)).filter(Resident.resident_status == ResidentStatus.LEFT).join(Branch)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Resident.full_name.ilike(search_filter),
                Resident.resident_code.ilike(search_filter)
            )
        )

    if branch_id and branch_id != 'all':
        try:
            query = query.filter(Resident.branch_id == int(branch_id))
        except (ValueError, TypeError):
            pass

    # Date range filters on departure date
    if from_date_str:
        try:
            from_dt = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(Resident.leaving_date >= from_dt)
        except ValueError:
            pass

    if to_date_str:
        try:
            to_dt = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(Resident.leaving_date <= to_dt)
        except ValueError:
            pass

    today = date.today()
    # Urgency filter based on 1-year retention (365 days)
    if urgency == 'expired':
        # deadline < today => leaving_date + 365 < today => leaving_date < today - 365 days
        expired_cutoff = today - timedelta(days=365)
        query = query.filter(Resident.leaving_date < expired_cutoff)
    elif urgency == 'approaching':
        # 0 <= days_remaining <= 30 => today - 365 <= leaving_date <= today - 335
        cutoff_min = today - timedelta(days=365)
        cutoff_max = today - timedelta(days=335)
        query = query.filter(Resident.leaving_date >= cutoff_min, Resident.leaving_date <= cutoff_max)
    elif urgency in ('normal', 'safe'):
        # days_remaining > 30 => leaving_date > today - 335 days
        safe_cutoff = today - timedelta(days=335)
        query = query.filter(Resident.leaving_date > safe_cutoff)

    query = query.order_by(Resident.leaving_date.desc(), Resident.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    branches = Branch.query.order_by(Branch.branch_name.asc()).all()
    active_branches = [b for b in branches if b.is_active]

    return render_template(
        'residents/previous.html',
        residents=pagination.items,
        pagination=pagination,
        branches=branches,
        active_branches=active_branches,
        selected_branch=branch_id,
        selected_urgency=urgency,
        from_date=from_date_str,
        to_date=to_date_str,
        search_query=search,
        total_count=pagination.total,
        today=today.strftime('%Y-%m-%d')
    )


@residents_bp.route('/<resident_code>/departure', methods=['POST'])
@login_required
def departure(resident_code):
    """
    Mark an active resident as LEFT upon physical departure.
    Saves actual leaving date, calculates 30-day retention deadline,
    records stay history, preserves all financial records,
    and moves resident to Previous Residents.
    """
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    # Prevent duplicate departure submission
    if resident.resident_status == ResidentStatus.LEFT:
        flash(f"Resident '{resident.full_name}' is already marked as departed (Status: LEFT).", "warning")
        return redirect(url_for('residents.previous'))

    leaving_date_str = request.form.get('leaving_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not leaving_date_str:
        flash("Please provide the actual departure date.", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    try:
        leaving_date = datetime.strptime(leaving_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Invalid departure date format. Please use YYYY-MM-DD.", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    if resident.admission_date and leaving_date < resident.admission_date:
        flash(f"Departure date ({leaving_date.strftime('%d %b %Y')}) cannot be earlier than admission date ({resident.admission_date.strftime('%d %b %Y')}).", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    # Calculate 1-year retention deadline (365 days)
    retention_deadline = leaving_date + timedelta(days=365)
    outstanding_total = resident.total_financial_outstanding

    # Update resident status & departure date
    resident.resident_status = ResidentStatus.LEFT
    resident.leaving_date = leaving_date
    resident.notice_date = None
    resident.updated_at = datetime.utcnow()

    # Record or update historical stay record in ResidentStayHistory
    current_stay = resident.stay_history.filter_by(leaving_date=None).first()
    if current_stay:
        current_stay.leaving_date = leaving_date
        current_stay.notes = notes or current_stay.notes
        current_stay.updated_at = datetime.utcnow()
    else:
        stay_count = resident.stay_history.count()
        new_stay = ResidentStayHistory(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            admission_date=resident.admission_date,
            leaving_date=leaving_date,
            stay_number=stay_count + 1,
            notes=notes or "Resident departure recorded."
        )
        db.session.add(new_stay)

    db.session.commit()

    # Audit logging
    dues_note = f" (Outstanding dues: ₹{outstanding_total:,.2f})" if outstanding_total > 0 else " (All dues cleared)"
    AuditService.log(
        action=AuditAction.RESIDENT_DEPARTURE,
        entity_type='Resident',
        entity_id=resident.id,
        description=f"Resident '{resident.full_name}' ({resident.resident_code}) marked as LEFT on {leaving_date.strftime('%d %b %Y')}. 1-year retention active until {retention_deadline.strftime('%d %b %Y')}{dues_note}."
    )

    flash(
        f"Resident '{resident.full_name}' has been marked as departed. Record moved to Previous Residents (1-year retention active until {retention_deadline.strftime('%d %b %Y')}).",
        "success"
    )
    return redirect(url_for('residents.previous'))


@residents_bp.route('/<resident_code>/reactivate', methods=['POST'])
@login_required
def reactivate(resident_code):
    """
    Reactivate a returning resident who previously departed.
    Preserves entire previous stay history, admission/leaving dates,
    and all financial records while resetting status to ACTIVE.
    """
    resident = Resident.query.filter_by(resident_code=resident_code).first()
    if not resident:
        abort(404)

    if resident.resident_status == ResidentStatus.ACTIVE:
        flash(f"Resident '{resident.full_name}' is already ACTIVE.", "warning")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    new_admission_date_str = request.form.get('new_admission_date', '').strip()
    branch_id_raw = request.form.get('branch_id')
    notes = request.form.get('notes', '').strip()

    parsed_admission_date = date.today()
    if new_admission_date_str:
        try:
            parsed_admission_date = datetime.strptime(new_admission_date_str, '%Y-%m-%d').date()
        except ValueError:
            parsed_admission_date = date.today()

    if resident.leaving_date and parsed_admission_date < resident.leaving_date:
        flash(f"New admission date ({parsed_admission_date.strftime('%d %b %Y')}) cannot be earlier than previous departure date ({resident.leaving_date.strftime('%d %b %Y')}).", "danger")
        return redirect(url_for('residents.profile', resident_code=resident.resident_code))

    # Optional branch assignment
    target_branch_id = resident.branch_id
    if branch_id_raw:
        try:
            branch_obj = db.session.get(Branch, int(branch_id_raw))
            if branch_obj and branch_obj.is_active:
                target_branch_id = branch_obj.id
        except (ValueError, TypeError):
            pass

    # Ensure previous stay is closed in stay history
    prev_admission = resident.admission_date
    prev_departure = resident.leaving_date

    # If no stay history exists for the previous stay, create it
    existing_closed_stay = resident.stay_history.filter_by(
        admission_date=prev_admission,
        leaving_date=prev_departure
    ).first()
    if not existing_closed_stay and prev_departure:
        stay_count = resident.stay_history.count()
        closed_stay = ResidentStayHistory(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            admission_date=prev_admission,
            leaving_date=prev_departure,
            stay_number=stay_count + 1,
            notes="Previous stay archived upon reactivation."
        )
        db.session.add(closed_stay)
        db.session.flush()

    # Create new active stay record
    stay_count = resident.stay_history.count()
    new_stay = ResidentStayHistory(
        resident_id=resident.id,
        branch_id=target_branch_id,
        admission_date=parsed_admission_date,
        leaving_date=None,
        stay_number=stay_count + 1,
        notes=notes or "Returning resident reactivated."
    )
    db.session.add(new_stay)

    # Update resident to ACTIVE with new admission date and clear leaving date
    resident.resident_status = ResidentStatus.ACTIVE
    resident.admission_date = parsed_admission_date
    resident.leaving_date = None
    resident.branch_id = target_branch_id
    resident.updated_at = datetime.utcnow()

    db.session.commit()

    AuditService.log(
        action=AuditAction.RESIDENT_REACTIVATE,
        entity_type='Resident',
        entity_id=resident.id,
        description=f"Returning resident '{resident.full_name}' ({resident.resident_code}) reactivated to ACTIVE status with new admission date {parsed_admission_date.strftime('%d %b %Y')}. Previous stay history preserved."
    )

    flash(
        f"Resident '{resident.full_name}' ({resident.resident_code}) reactivated successfully and restored to Active Residents directory!",
        "success"
    )
    return redirect(url_for('residents.profile', resident_code=resident.resident_code))


@residents_bp.route('/photo/<path:filename>')
@login_required
def serve_photo(filename):
    """
    Serve resident photograph securely to authenticated administrators only.
    Resident photographs are stored outside app/static in private storage
    and require valid administrator authentication.
    """
    return StorageService.serve_file(filename)


def render_deposit_badge_html(resident_id: int, full_name: str, resident_code: str, status: str, amount: float = 0.0) -> str:
    """Helper to render dynamic HTML badge for security deposit status."""
    status_upper = status.upper()
    desktop_amount_str = f"₹ {amount:,.2f}" if amount > 0 else ""
    mobile_amount_str = f"₹ {amount:,.0f}" if amount > 0 else ""
    if status_upper == 'PAID':
        badge_class = 'badge-paid'
        desktop_label = f"Paid ({desktop_amount_str})" if desktop_amount_str else "Paid"
        mobile_label = (
            f'<span class="d-block">Paid <i class="bi bi-pencil-fill opacity-50" style="font-size: 0.55rem;"></i></span>'
            f'<span class="d-block font-monospace opacity-75" style="font-size: 0.625rem;">{mobile_amount_str}</span>'
        ) if mobile_amount_str else '<span>Paid <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'
    elif status_upper == 'PARTIAL':
        badge_class = 'badge-partial'
        desktop_label = "Partial"
        mobile_label = '<span>Partial <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'
    else:
        badge_class = 'badge-unpaid'
        desktop_label = "Unpaid"
        mobile_label = '<span>Unpaid <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'

    return (
        f'<button type="button" '
        f'class="badge-status badge-btn {badge_class} cursor-pointer" '
        f'data-quick-payment '
        f'data-resident-id="{resident_id}" '
        f'data-resident-name="{full_name}" '
        f'data-resident-code="{resident_code}" '
        f'data-payment-type="SECURITY_DEPOSIT" '
        f'data-type-label="Security Deposit" '
        f'data-current-status="{status_upper}" '
        f'data-current-amount="{amount}" '
        f'title="Click to update Security Deposit status">'
        f'<span class="d-none d-md-inline">{desktop_label} <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.65rem;"></i></span>'
        f'<span class="d-md-none text-center lh-1">{mobile_label}</span>'
        f'</button>'
    )


def render_rent_badge_html(resident_id: int, full_name: str, resident_code: str, status: str, amount: float = 0.0, outstanding: float = 0.0) -> str:
    """Helper to render dynamic HTML badge for rent payment status."""
    status_upper = status.upper()
    desktop_due_str = f"₹ {outstanding:,.2f}" if outstanding > 0 else ""
    mobile_due_str = f"₹ {outstanding:,.0f}" if outstanding > 0 else ""
    if status_upper == 'PAID':
        badge_class = 'badge-paid'
        desktop_label = "Paid"
        mobile_label = '<span>Paid <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'
    elif status_upper == 'PARTIAL':
        badge_class = 'badge-partial'
        desktop_label = f"Partial (Due: {desktop_due_str})" if desktop_due_str else "Partial"
        mobile_label = (
            f'<span class="d-block">Partial <i class="bi bi-pencil-fill opacity-50" style="font-size: 0.55rem;"></i></span>'
            f'<span class="d-block font-monospace opacity-75" style="font-size: 0.625rem;">Due: {mobile_due_str}</span>'
        ) if mobile_due_str else '<span>Partial <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'
    else:
        badge_class = 'badge-unpaid'
        desktop_label = f"Unpaid (Due: {desktop_due_str})" if desktop_due_str else "Unpaid"
        mobile_label = (
            f'<span class="d-block">Unpaid <i class="bi bi-pencil-fill opacity-50" style="font-size: 0.55rem;"></i></span>'
            f'<span class="d-block font-monospace opacity-75" style="font-size: 0.625rem;">Due: {mobile_due_str}</span>'
        ) if mobile_due_str else '<span>Unpaid <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.6rem;"></i></span>'

    return (
        f'<button type="button" '
        f'class="badge-status badge-btn {badge_class} cursor-pointer" '
        f'data-quick-payment '
        f'data-resident-id="{resident_id}" '
        f'data-resident-name="{full_name}" '
        f'data-resident-code="{resident_code}" '
        f'data-payment-type="RENT" '
        f'data-type-label="Monthly Rent" '
        f'data-current-status="{status_upper}" '
        f'data-current-amount="{amount}" '
        f'title="Click to update Monthly Rent status">'
        f'<span class="d-none d-md-inline">{desktop_label} <i class="bi bi-pencil-fill ms-1 opacity-50" style="font-size: 0.65rem;"></i></span>'
        f'<span class="d-md-none text-center lh-1">{mobile_label}</span>'
        f'</button>'
    )


@residents_bp.route('/quick-payment', methods=['POST'])
@login_required
def quick_payment():
    """
    Quick status update endpoint for Resident Directory.
    Allows changing resident's security deposit or rent status directly from table.
    - Validates inputs (amount > 0 for paid/partial, no negative values).
    - Prevents duplicate submissions.
    - Creates immutable transaction record in PostgreSQL.
    - When marked UNPAID: records a due/pending ledger record without fictitious money,
      preserving all previously recorded transactions.
    - Returns updated badge HTML for seamless in-place AJAX DOM replacement.
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({'success': False, 'message': 'Invalid request payload.'}), 400

    resident_id = data.get('resident_id')
    payment_type = (data.get('payment_type') or '').strip().upper()
    target_status = (data.get('status') or '').strip().upper()

    if not resident_id:
        return jsonify({'success': False, 'message': 'Resident identifier is required.'}), 400

    try:
        resident_id_int = int(resident_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid resident ID format.'}), 400

    resident = db.session.get(Resident, resident_id_int)
    if not resident:
        return jsonify({'success': False, 'message': 'Resident record not found.'}), 404

    if payment_type not in (PaymentType.SECURITY_DEPOSIT, PaymentType.RENT):
        return jsonify({'success': False, 'message': f"Invalid payment type '{payment_type}'."}), 400

    if target_status not in ('PAID', 'PARTIAL', 'UNPAID'):
        return jsonify({'success': False, 'message': f"Invalid payment status '{target_status}'. Must be PAID, PARTIAL, or UNPAID."}), 400

    # Parse payment date
    date_str = data.get('payment_date')
    if date_str:
        try:
            payment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            payment_date = date.today()
    else:
        payment_date = date.today()

    payment_method = data.get('payment_method')
    if payment_method:
        payment_method = str(payment_method).strip().upper()
        if payment_method not in PaymentMethod.CHOICES:
            payment_method = None

    tx_ref = (data.get('transaction_reference') or '').strip()
    if tx_ref:
        tx_ref = tx_ref[:100]
    else:
        tx_ref = None

    notes = (data.get('notes') or '').strip()
    if notes:
        notes = notes[:500]

    type_label = "Security Deposit" if payment_type == PaymentType.SECURITY_DEPOSIT else "Monthly Rent"

    if target_status == 'PAID':
        amount_raw = data.get('amount')
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Please provide a valid numeric payment amount.'}), 400

        if amount <= 0:
            return jsonify({'success': False, 'message': 'Payment amount must be greater than zero.'}), 400

        payment = Payment(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            payment_type=payment_type,
            amount=amount,
            payment_date=payment_date,
            payment_status=PaymentStatus.PAID,
            payment_method=payment_method or PaymentMethod.CASH,
            transaction_reference=tx_ref or f"REC-{int(datetime.utcnow().timestamp())}",
            notes=notes or f"{type_label} marked as PAID via quick-edit."
        )
        db.session.add(payment)
        db.session.commit()

        AuditService.log(
            action=AuditAction.PAYMENT_UPDATE,
            entity_type='Payment',
            entity_id=payment.id,
            description=f"Quick status update: Recorded payment of ₹{amount:,.2f} ({payment_type}) as PAID for '{resident.full_name}' ({resident.resident_code})."
        )

        badge_html = render_deposit_badge_html(resident.id, resident.full_name, resident.resident_code, 'PAID', amount) if payment_type == PaymentType.SECURITY_DEPOSIT else render_rent_badge_html(resident.id, resident.full_name, resident.resident_code, 'PAID', amount, 0.0)

        return jsonify({
            'success': True,
            'message': f"{type_label} for {resident.full_name} successfully marked as PAID (₹ {amount:,.2f}).",
            'resident_id': resident.id,
            'payment_type': payment_type,
            'status': 'PAID',
            'amount': amount,
            'badge_html': badge_html
        })

    elif target_status == 'PARTIAL':
        amount_raw = data.get('amount')
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Please provide a valid numeric partial payment amount.'}), 400

        if amount <= 0:
            return jsonify({'success': False, 'message': 'Partial payment amount must be greater than zero.'}), 400

        total_expected_raw = data.get('total_expected')
        balance_due = 0.0
        if total_expected_raw:
            try:
                total_expected = float(total_expected_raw)
                if total_expected > amount:
                    balance_due = total_expected - amount
            except (ValueError, TypeError):
                pass

        note_details = f"Partial payment of ₹{amount:,.2f} received."
        if balance_due > 0:
            note_details += f" Outstanding balance: ₹{balance_due:,.2f}."
        if notes:
            note_details = f"{notes} ({note_details})"

        payment = Payment(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            payment_type=payment_type,
            amount=amount,
            payment_date=payment_date,
            payment_status=PaymentStatus.PARTIAL,
            payment_method=payment_method or PaymentMethod.CASH,
            transaction_reference=tx_ref or f"PART-{int(datetime.utcnow().timestamp())}",
            notes=note_details
        )
        db.session.add(payment)
        db.session.commit()

        AuditService.log(
            action=AuditAction.PAYMENT_UPDATE,
            entity_type='Payment',
            entity_id=payment.id,
            description=f"Quick status update: Recorded partial payment of ₹{amount:,.2f} ({payment_type}) for '{resident.full_name}' ({resident.resident_code}). Balance: ₹{balance_due:,.2f}."
        )

        badge_html = render_deposit_badge_html(resident.id, resident.full_name, resident.resident_code, 'PARTIAL', amount) if payment_type == PaymentType.SECURITY_DEPOSIT else render_rent_badge_html(resident.id, resident.full_name, resident.resident_code, 'PARTIAL', amount, balance_due)

        return jsonify({
            'success': True,
            'message': f"{type_label} for {resident.full_name} marked as PARTIAL (Received: ₹ {amount:,.2f}, Balance: ₹ {balance_due:,.2f}).",
            'resident_id': resident.id,
            'payment_type': payment_type,
            'status': 'PARTIAL',
            'amount': amount,
            'balance_due': balance_due,
            'badge_html': badge_html
        })

    elif target_status == 'UNPAID':
        # Prompt requirement:
        # "When marking as UNPAID:
        # - Do not create a fictitious payment transaction.
        # - Preserve all previously recorded transactions."
        unpaid_note = notes or f"{type_label} marked as UNPAID by administrator on {date.today().strftime('%d %b %Y')}."
        payment = Payment(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            payment_type=payment_type,
            amount=0.00,
            payment_date=payment_date,
            payment_status=PaymentStatus.PENDING,
            payment_method=None,
            transaction_reference=None,
            notes=unpaid_note
        )
        db.session.add(payment)
        db.session.commit()

        AuditService.log(
            action=AuditAction.PAYMENT_UPDATE,
            entity_type='Payment',
            entity_id=payment.id,
            description=f"Quick status update: Marked {payment_type} as UNPAID for '{resident.full_name}' ({resident.resident_code}). No fictitious payment created."
        )

        badge_html = render_deposit_badge_html(resident.id, resident.full_name, resident.resident_code, 'UNPAID', 0.0) if payment_type == PaymentType.SECURITY_DEPOSIT else render_rent_badge_html(resident.id, resident.full_name, resident.resident_code, 'UNPAID', 0.0, 0.0)

        return jsonify({
            'success': True,
            'message': f"{type_label} for {resident.full_name} marked as UNPAID. Historical records preserved.",
            'resident_id': resident.id,
            'payment_type': payment_type,
            'status': 'UNPAID',
            'amount': 0.0,
            'badge_html': badge_html
        })
