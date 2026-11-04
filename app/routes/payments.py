"""
Payment management routes for Miracle Hostel.
Phase 6: Complete Financial & Payment Management with PostgreSQL persistence.
Features:
- Live aggregated financial KPIs (Total Collected, Deposits Collected, Rent Collected, Pending Rent, Pending Deposits)
- Consolidated and individual branch financial reporting
- Multidimensional filtering (Branch, Payment Category, Payment Status, Date Range, Resident Search)
- Server-side database pagination for immutable transaction ledgers
- Transaction recording with strict validation, duplicate prevention, and balance updating
- Manual monthly rent obligation generation
- Protected with Flask-Login administrator session requirement and CSRF protection
"""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.extensions import db
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentMethod
from app.models.payment_obligation import PaymentObligation, ObligationType
from app.services.financial_service import FinancialService

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


@payments_bp.route('', methods=['GET', 'POST'])
@payments_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    Central Payment Management Dashboard:
    - Displays financial KPIs aggregated directly from PostgreSQL
    - Displays paginated, filtered transaction ledger
    - Handles Record New Payment modal submissions
    """
    if request.method == 'POST':
        resident_id_raw = request.form.get('resident_id')
        payment_type = request.form.get('payment_type', PaymentType.MONTHLY_RENT).strip()
        amount_raw = request.form.get('amount')
        payment_method = request.form.get('payment_method', PaymentMethod.UPI).strip()
        payment_date_str = request.form.get('payment_date', '').strip()
        tx_ref = request.form.get('transaction_reference', '').strip()
        notes = request.form.get('notes', '').strip()
        obligation_id_raw = request.form.get('obligation_id')

        # 1. Resident validation
        if not resident_id_raw:
            flash("Please select a resident for this payment.", "danger")
            return redirect(url_for('payments.index'))

        try:
            resident_id = int(resident_id_raw)
        except (ValueError, TypeError):
            flash("Invalid resident ID format.", "danger")
            return redirect(url_for('payments.index'))

        resident = db.session.get(Resident, resident_id)
        if not resident:
            flash(f"Resident #{resident_id} not found.", "danger")
            return redirect(url_for('payments.index'))

        # 2. Amount validation
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            flash("Please enter a valid numeric payment amount.", "danger")
            return redirect(url_for('payments.index'))

        if amount <= 0:
            flash("Payment amount must be greater than zero.", "danger")
            return redirect(url_for('payments.index'))

        # 3. Payment date parsing
        parsed_date = date.today()
        if payment_date_str:
            try:
                parsed_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()
            except ValueError:
                parsed_date = date.today()

        obligation_id = None
        if obligation_id_raw:
            try:
                obligation_id = int(obligation_id_raw)
            except (ValueError, TypeError):
                obligation_id = None

        try:
            payment = FinancialService.record_payment(
                resident_id=resident.id,
                payment_type=payment_type,
                amount=amount,
                payment_date=parsed_date,
                payment_method=payment_method,
                transaction_reference=tx_ref,
                notes=notes,
                obligation_id=obligation_id
            )
            flash(
                f"Payment of ₹ {amount:,.2f} ({payment.payment_type}) successfully recorded for {resident.full_name}! (Ref: {payment.transaction_reference}).",
                "success"
            )
        except Exception as e:
            flash(f"Error recording payment: {str(e)}", "danger")

        return redirect(url_for('payments.index'))

    # GET: Filter and Pagination parameters
    search = request.args.get('search', '').strip()
    branch_id = request.args.get('branch', 'all')
    payment_type = request.args.get('type', 'ALL').strip().upper()
    status = request.args.get('status', 'ALL').strip().upper()
    from_date_str = request.args.get('from_date', '').strip()
    to_date_str = request.args.get('to_date', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15

    from_date = None
    if from_date_str:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        except ValueError:
            from_date = None

    to_date = None
    if to_date_str:
        try:
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        except ValueError:
            to_date = None

    # Retrieve PostgreSQL aggregated financial statistics
    stats = FinancialService.get_financial_dashboard_stats(
        branch_id=branch_id,
        from_date=from_date,
        to_date=to_date
    )

    # Retrieve PostgreSQL paginated transactions
    pagination = FinancialService.get_payment_transactions(
        branch_id=branch_id,
        payment_type=payment_type,
        status=status,
        from_date=from_date,
        to_date=to_date,
        search=search,
        page=page,
        per_page=per_page
    )

    branches = Branch.query.order_by(Branch.branch_name.asc()).all()
    active_residents = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).order_by(Resident.full_name.asc()).all()

    return render_template(
        'payments/index.html',
        payments=pagination.items,
        pagination=pagination,
        branches=branches,
        active_residents=active_residents,
        stats=stats,
        selected_branch=branch_id,
        selected_type=payment_type,
        selected_status=status,
        search_query=search,
        from_date=from_date_str,
        to_date=to_date_str,
        today=date.today().strftime('%Y-%m-%d')
    )


@payments_bp.route('/obligations/generate', methods=['POST'])
@login_required
def generate_obligation():
    """
    Endpoint for administrators to manually generate monthly rent obligations.
    Validates amounts and prevents duplicate monthly obligations.
    """
    resident_id_raw = request.form.get('resident_id')
    obligation_type = request.form.get('obligation_type', ObligationType.MONTHLY_RENT).strip()
    billing_month = request.form.get('billing_month', '').strip()  # e.g. YYYY-MM
    title = request.form.get('title', '').strip()
    amount_raw = request.form.get('expected_amount')
    due_date_str = request.form.get('due_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not resident_id_raw:
        flash("Please select a resident.", "danger")
        return redirect(url_for('payments.index'))

    try:
        resident_id = int(resident_id_raw)
    except (ValueError, TypeError):
        flash("Invalid resident ID.", "danger")
        return redirect(url_for('payments.index'))

    resident = db.session.get(Resident, resident_id)
    if not resident:
        flash(f"Resident #{resident_id} not found.", "danger")
        return redirect(url_for('payments.index'))

    try:
        expected_amount = float(amount_raw)
        if expected_amount < 0:
            raise ValueError()
    except (ValueError, TypeError):
        flash("Expected amount must be a valid non-negative number.", "danger")
        return redirect(url_for('payments.index'))

    due_date = date.today()
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            due_date = date.today()

    if not title:
        title = f"{obligation_type.replace('_', ' ').title()} - {billing_month or due_date.strftime('%B %Y')}"

    try:
        ob = FinancialService.create_obligation(
            resident_id=resident.id,
            obligation_type=obligation_type,
            expected_amount=expected_amount,
            title=title,
            due_date=due_date,
            billing_month=billing_month or None,
            notes=notes or None
        )
        flash(f"Obligation '{ob.title}' for ₹ {expected_amount:,.2f} generated successfully for {resident.full_name}!", "success")
    except ValueError as ve:
        flash(str(ve), "warning")
    except Exception as e:
        flash(f"Failed to generate obligation: {str(e)}", "danger")

    # If redirected from resident profile
    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('payments.index'))
