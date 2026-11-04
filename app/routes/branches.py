"""
Branch management routes for Miracle Hostel.
Protected with Flask-Login administrator session requirement.
Complete PostgreSQL integration with Add, Edit, Deactivate/Activate, Search,
and Active Resident Safeguards.
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import or_, func
from app.extensions import db
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService

branches_bp = Blueprint('branches', __name__, url_prefix='/branches')


@branches_bp.route('', methods=['GET', 'POST'])
@branches_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """Branch management view with Add, Edit, and Deactivate/Activate operations."""
    if request.method == 'POST':
        action = request.form.get('action')

        # -------------------------------------------------------------
        # 1. ADD BRANCH
        # -------------------------------------------------------------
        if action == 'add':
            branch_name = request.form.get('branch_name', '').strip()
            branch_code = request.form.get('branch_code', '').strip().upper()
            address = request.form.get('address', '').strip()
            contact_number = request.form.get('contact_number', '').strip()

            # Validation
            if not branch_name or not branch_code or not address or not contact_number:
                flash("All branch fields (Name, Code, Address, Contact Number) are required.", "danger")
                return redirect(url_for('branches.index'))

            # Check uniqueness of branch code
            existing = Branch.query.filter(func.lower(Branch.branch_code) == branch_code.lower()).first()
            if existing:
                flash(f"Branch code '{branch_code}' already exists. Branch codes must be unique.", "danger")
                return redirect(url_for('branches.index'))

            # Create and save in PostgreSQL
            total_beds_raw = request.form.get('total_beds', '20').strip()
            try:
                total_beds = max(1, int(total_beds_raw))
            except (ValueError, TypeError):
                total_beds = 20

            new_branch = Branch(
                branch_name=branch_name,
                branch_code=branch_code,
                address=address,
                contact_number=contact_number,
                total_beds=total_beds,
                is_active=True
            )
            db.session.add(new_branch)
            db.session.commit()

            AuditService.log(
                action=AuditAction.BRANCH_CREATE,
                entity_type='Branch',
                entity_id=new_branch.id,
                description=f"Hostel branch '{branch_name}' ({branch_code}) created and activated."
            )
            flash(f"Branch '{branch_name}' ({branch_code}) successfully created and activated!", "success")
            return redirect(url_for('branches.index'))

        # -------------------------------------------------------------
        # 2. EDIT BRANCH
        # -------------------------------------------------------------
        elif action == 'edit':
            branch_id = request.form.get('branch_id')
            branch_name = request.form.get('branch_name', '').strip()
            branch_code = request.form.get('branch_code', '').strip().upper()
            address = request.form.get('address', '').strip()
            contact_number = request.form.get('contact_number', '').strip()

            if not branch_id or not branch_name or not branch_code or not address or not contact_number:
                flash("All fields are required to update branch details.", "danger")
                return redirect(url_for('branches.index'))

            try:
                branch = db.session.get(Branch, int(branch_id))
            except (ValueError, TypeError):
                branch = None

            if not branch:
                flash("Branch record not found.", "danger")
                return redirect(url_for('branches.index'))

            # Check uniqueness of branch_code if modified
            if branch_code.lower() != branch.branch_code.lower():
                duplicate = Branch.query.filter(
                    func.lower(Branch.branch_code) == branch_code.lower(),
                    Branch.id != branch.id
                ).first()
                if duplicate:
                    flash(f"Branch code '{branch_code}' is already assigned to another branch.", "danger")
                    return redirect(url_for('branches.index'))

            branch.branch_name = branch_name
            branch.branch_code = branch_code
            branch.address = address
            branch.contact_number = contact_number
            total_beds_raw = request.form.get('total_beds', '').strip()
            if total_beds_raw:
                try:
                    branch.total_beds = max(1, int(total_beds_raw))
                except (ValueError, TypeError):
                    pass
            branch.updated_at = datetime.utcnow()
            db.session.commit()

            AuditService.log(
                action=AuditAction.BRANCH_UPDATE,
                entity_type='Branch',
                entity_id=branch.id,
                description=f"Branch details for '{branch_name}' ({branch_code}) updated."
            )
            flash(f"Branch '{branch.branch_name}' updated successfully!", "success")
            return redirect(url_for('branches.index'))

        # -------------------------------------------------------------
        # 3. DEACTIVATE / ACTIVATE BRANCH
        # -------------------------------------------------------------
        elif action == 'toggle_status':
            branch_id = request.form.get('branch_id')
            new_status = request.form.get('new_status')

            try:
                branch = db.session.get(Branch, int(branch_id))
            except (ValueError, TypeError):
                branch = None

            if not branch:
                flash("Branch record not found.", "danger")
                return redirect(url_for('branches.index'))

            if new_status == 'deactivate':
                # CRITICAL SAFEGUARD: Prevent accidental deactivation if active residents exist
                active_count = branch.residents.filter_by(resident_status=ResidentStatus.ACTIVE).count()
                if active_count > 0:
                    flash(
                        f"Cannot deactivate branch '{branch.branch_name}'. It still has {active_count} active resident(s). "
                        "All active residents must be transferred or marked as LEFT before deactivating the branch.",
                        "danger"
                    )
                    return redirect(url_for('branches.index'))

                branch.is_active = False
                branch.updated_at = datetime.utcnow()
                db.session.commit()

                AuditService.log(
                    action=AuditAction.BRANCH_DEACTIVATE,
                    entity_type='Branch',
                    entity_id=branch.id,
                    description=f"Branch '{branch.branch_name}' ({branch.branch_code}) deactivated. Historical records preserved."
                )
                flash(
                    f"Branch '{branch.branch_name}' deactivated successfully. Historical residents and financial records remain fully preserved.",
                    "warning"
                )
            else:
                branch.is_active = True
                branch.updated_at = datetime.utcnow()
                db.session.commit()

                AuditService.log(
                    action=AuditAction.BRANCH_ACTIVATE,
                    entity_type='Branch',
                    entity_id=branch.id,
                    description=f"Branch '{branch.branch_name}' ({branch.branch_code}) reactivated."
                )
                flash(f"Branch '{branch.branch_name}' reactivated successfully! Now accepting new resident admissions.", "success")

            return redirect(url_for('branches.index'))

    # -----------------------------------------------------------------
    # GET: DIRECTORY VIEW WITH SEARCH & FILTER
    # -----------------------------------------------------------------
    search_query = request.args.get('search', '').strip()
    selected_status = request.args.get('status', 'all').lower()

    query = Branch.query

    # Search filter
    if search_query:
        search_filter = f"%{search_query}%"
        query = query.filter(
            or_(
                Branch.branch_name.ilike(search_filter),
                Branch.branch_code.ilike(search_filter),
                Branch.address.ilike(search_filter)
            )
        )

    # Active/Inactive filter
    if selected_status == 'active':
        query = query.filter(Branch.is_active.is_(True))
    elif selected_status == 'inactive':
        query = query.filter(Branch.is_active.is_(False))

    branches_list = query.order_by(Branch.created_at.desc()).all()

    # System-wide metrics for top KPI cards
    active_count = Branch.query.filter_by(is_active=True).count()
    inactive_count = Branch.query.filter_by(is_active=False).count()
    total_capacity = Resident.query.count()
    total_system_beds = db.session.query(func.coalesce(func.sum(Branch.total_beds), 0)).filter(Branch.is_active.is_(True)).scalar() or 0
    total_occupied_beds = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).count()
    total_available_beds = max(0, total_system_beds - total_occupied_beds)

    return render_template(
        'branches/index.html',
        branches=branches_list,
        active_count=active_count,
        inactive_count=inactive_count,
        total_capacity=total_capacity,
        total_system_beds=total_system_beds,
        total_available_beds=total_available_beds,
        search_query=search_query,
        selected_status=selected_status
    )
