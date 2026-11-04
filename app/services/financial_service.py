"""
Financial Management Service for Miracle Hostel.
Handles:
- Creation and tracking of payment obligations (Security Deposit, Admission Rent, Monthly Rent, Other Charges)
- Transaction recording with strict validation, duplicate prevention, and balance updating
- Branch-wise and consolidated KPI aggregations using efficient SQLAlchemy queries
- Payment history retrieval and filtering
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func, or_, and_
from app.extensions import db
from app.models.branch import Branch
from app.models.resident import Resident, ResidentStatus
from app.models.payment import Payment, PaymentType, PaymentStatus, PaymentMethod
from app.models.payment_obligation import PaymentObligation, ObligationType
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService


class FinancialService:
    """Service providing core financial and accounting operations."""

    @staticmethod
    def create_obligation(
        resident_id: int,
        obligation_type: str,
        expected_amount: float,
        title: str = None,
        due_date: date = None,
        billing_month: str = None,
        notes: str = None
    ) -> PaymentObligation:
        """
        Create a new financial obligation for a resident.
        Prevents duplicate monthly obligations for the same resident and billing month.
        """
        resident = db.session.get(Resident, resident_id)
        if not resident:
            raise ValueError(f"Resident with ID {resident_id} not found.")

        if expected_amount < 0:
            raise ValueError("Expected amount cannot be negative.")

        if not title:
            title = f"{obligation_type.replace('_', ' ').title()} Obligation"

        if due_date is None:
            due_date = date.today()

        # Duplicate monthly obligation protection
        if obligation_type == ObligationType.MONTHLY_RENT and billing_month:
            existing = PaymentObligation.query.filter_by(
                resident_id=resident.id,
                obligation_type=ObligationType.MONTHLY_RENT,
                billing_month=billing_month
            ).first()
            if existing:
                raise ValueError(
                    f"Monthly rent obligation for billing month '{billing_month}' already exists for {resident.full_name}."
                )

        obligation = PaymentObligation(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            obligation_type=obligation_type,
            billing_month=billing_month,
            title=title,
            expected_amount=round(Decimal(str(expected_amount)), 2),
            due_date=due_date,
            notes=notes
        )
        db.session.add(obligation)
        db.session.commit()

        AuditService.log(
            action=AuditAction.PAYMENT_CREATE,
            entity_type='PaymentObligation',
            entity_id=obligation.id,
            description=f"Generated obligation '{title}' of ₹{expected_amount:,.2f} for resident '{resident.full_name}' ({resident.resident_code})."
        )
        return obligation

    @staticmethod
    def record_payment(
        resident_id: int,
        payment_type: str,
        amount: float,
        payment_date: date = None,
        payment_method: str = PaymentMethod.CASH,
        transaction_reference: str = None,
        notes: str = None,
        obligation_id: int = None,
        target_status: str = None
    ) -> Payment:
        """
        Record a monetary transaction in PostgreSQL.
        - Requires positive payment amounts only.
        - Never overwrites historical payments.
        - Links to obligation when available.
        - Uses transactional safety.
        """
        resident = db.session.get(Resident, resident_id)
        if not resident:
            raise ValueError(f"Resident ID #{resident_id} does not exist.")

        try:
            amount_val = float(amount)
        except (ValueError, TypeError):
            raise ValueError("Invalid payment amount.")

        if amount_val <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        if payment_date is None:
            payment_date = date.today()

        # Sanitize payment method
        valid_methods = [PaymentMethod.CASH, PaymentMethod.UPI, PaymentMethod.BANK_TRANSFER, PaymentMethod.CHEQUE]
        clean_method = (payment_method or PaymentMethod.CASH).strip().upper()
        if clean_method not in valid_methods:
            clean_method = PaymentMethod.CASH

        # Normalize payment category
        cat = payment_type.strip().upper()
        if cat == 'RENT':
            cat = PaymentType.MONTHLY_RENT
        elif cat not in PaymentType.CHOICES:
            cat = PaymentType.MONTHLY_RENT

        # Find or link matching obligation if not explicitly provided
        obligation = None
        if obligation_id:
            obligation = db.session.get(PaymentObligation, obligation_id)
        elif cat in (PaymentType.SECURITY_DEPOSIT, ObligationType.SECURITY_DEPOSIT):
            obligation = resident.obligations.filter_by(obligation_type=ObligationType.SECURITY_DEPOSIT).first()
        elif cat in (PaymentType.ADMISSION_RENT, ObligationType.ADMISSION_RENT):
            obligation = resident.obligations.filter_by(obligation_type=ObligationType.ADMISSION_RENT).first()
        elif cat in (PaymentType.MONTHLY_RENT, ObligationType.MONTHLY_RENT):
            # Look for latest unsettled monthly rent obligation
            unsettled_rent = [
                ob for ob in resident.obligations.filter_by(obligation_type=ObligationType.MONTHLY_RENT).order_by(PaymentObligation.due_date.asc()).all()
                if ob.status in ('UNPAID', 'PARTIAL')
            ]
            if unsettled_rent:
                obligation = unsettled_rent[0]

        # Check overpayment against obligation
        note_text = notes or ""
        if obligation and obligation.expected_amount:
            remaining = obligation.outstanding_amount
            if amount_val > remaining and remaining > 0:
                advance_amt = round(amount_val - remaining, 2)
                advance_msg = f"Includes advance payment of ₹{advance_amt:,.2f} recorded toward future balance."
                note_text = f"{note_text} ({advance_msg})" if note_text else advance_msg

        # Status resolution
        if target_status and target_status.upper() in (PaymentStatus.PAID, PaymentStatus.PARTIAL):
            p_status = target_status.upper()
        elif obligation:
            rec_after = obligation.total_amount_received + amount_val
            exp = float(obligation.expected_amount)
            p_status = PaymentStatus.PAID if rec_after >= exp else PaymentStatus.PARTIAL
        else:
            p_status = PaymentStatus.PAID

        # Clean strings
        clean_ref = (transaction_reference or '').strip()[:100] or None
        clean_notes = note_text.strip()[:500] or None

        # Execute database transaction
        payment = Payment(
            resident_id=resident.id,
            branch_id=resident.branch_id,
            obligation_id=obligation.id if obligation else None,
            payment_type=cat,
            amount=round(Decimal(str(amount_val)), 2),
            payment_date=payment_date,
            payment_status=p_status,
            payment_method=clean_method,
            transaction_reference=clean_ref or f"TX-{int(datetime.utcnow().timestamp())}",
            notes=clean_notes,
            anonymized_resident_code=resident.resident_code
        )
        db.session.add(payment)
        db.session.commit()

        AuditService.log(
            action=AuditAction.PAYMENT_CREATE,
            entity_type='Payment',
            entity_id=payment.id,
            description=f"Recorded payment of ₹{amount_val:,.2f} ({cat}) for resident '{resident.full_name}' ({resident.resident_code}) via {clean_method}."
        )
        return payment

    @staticmethod
    def get_financial_dashboard_stats(
        branch_id: str | int = 'all',
        from_date: date = None,
        to_date: date = None
    ) -> dict:
        """
        Aggregate financial statistics from PostgreSQL:
        - Total amount collected
        - Total security deposits collected
        - Total rent collected (including monthly rent and admission rent)
        - Total outstanding rent
        - Total outstanding deposits
        - Filter by branch and date range
        """
        q_pay = Payment.query.filter(
            Payment.payment_status.in_([PaymentStatus.PAID, PaymentStatus.PARTIAL]),
            Payment.amount > 0
        )

        b_id_int = None
        if branch_id and str(branch_id).lower() != 'all':
            try:
                b_id_int = int(branch_id)
                q_pay = q_pay.filter(Payment.branch_id == b_id_int)
            except (ValueError, TypeError):
                pass

        if from_date:
            q_pay = q_pay.filter(Payment.payment_date >= from_date)
        if to_date:
            q_pay = q_pay.filter(Payment.payment_date <= to_date)

        # 1. Total Amount Collected
        total_collected = q_pay.with_entities(func.coalesce(func.sum(Payment.amount), 0.0)).scalar()
        total_collected = float(total_collected)

        # 2. Total Security Deposits Collected
        total_deposits = q_pay.filter(
            Payment.payment_type == PaymentType.SECURITY_DEPOSIT
        ).with_entities(func.coalesce(func.sum(Payment.amount), 0.0)).scalar()
        total_deposits = float(total_deposits)

        # 3. Total Rent Collected (Monthly Rent + Admission Rent + legacy RENT)
        total_rent = q_pay.filter(
            Payment.payment_type.in_([PaymentType.MONTHLY_RENT, PaymentType.ADMISSION_RENT, 'RENT'])
        ).with_entities(func.coalesce(func.sum(Payment.amount), 0.0)).scalar()
        total_rent = float(total_rent)

        # 4 & 5. Outstanding Rent & Deposits Calculation across Active Residents
        q_res = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE)
        if b_id_int:
            q_res = q_res.filter(Resident.branch_id == b_id_int)

        active_residents = q_res.all()
        pending_rent_amount = sum(r.outstanding_rent for r in active_residents)
        pending_deposits_amount = sum(r.deposit_outstanding for r in active_residents)

        pending_rent_count = sum(1 for r in active_residents if r.outstanding_rent > 0)
        pending_deposits_count = sum(1 for r in active_residents if r.deposit_outstanding > 0)

        return {
            'total_amount_collected': round(total_collected, 2),
            'total_deposits_collected': round(total_deposits, 2),
            'total_rent_collected': round(total_rent, 2),
            'pending_rent_amount': round(pending_rent_amount, 2),
            'pending_deposits_amount': round(pending_deposits_amount, 2),
            'pending_rent_count': pending_rent_count,
            'pending_deposits_count': pending_deposits_count
        }

    @staticmethod
    def get_payment_transactions(
        branch_id: str | int = 'all',
        payment_type: str = 'ALL',
        status: str = 'ALL',
        from_date: date = None,
        to_date: date = None,
        search: str = None,
        page: int = 1,
        per_page: int = 15
    ):
        """Retrieve paginated payment transactions from PostgreSQL with full filtering."""
        query = Payment.query.options(
            db.joinedload(Payment.resident),
            db.joinedload(Payment.branch)
        ).outerjoin(Resident).join(Branch)

        # Branch filter
        if branch_id and str(branch_id).lower() != 'all':
            try:
                b_id = int(branch_id)
                query = query.filter(Payment.branch_id == b_id)
            except (ValueError, TypeError):
                pass

        # Payment category filter
        if payment_type and payment_type.upper() != 'ALL':
            cat = payment_type.upper()
            if cat in ('RENT', 'MONTHLY_RENT'):
                query = query.filter(Payment.payment_type.in_(['RENT', 'MONTHLY_RENT']))
            else:
                query = query.filter(Payment.payment_type == cat)

        # Status filter
        if status and status.upper() != 'ALL':
            st = status.upper()
            if st in ('PENDING', 'UNPAID'):
                query = query.filter(Payment.payment_status.in_(['PENDING', 'UNPAID']))
            else:
                query = query.filter(Payment.payment_status == st)

        # Date range filter
        if from_date:
            query = query.filter(Payment.payment_date >= from_date)
        if to_date:
            query = query.filter(Payment.payment_date <= to_date)

        # Search filter (Resident Name, Resident ID, Transaction Ref, or Payment ID)
        if search:
            s_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Resident.full_name.ilike(s_term),
                    Resident.resident_code.ilike(s_term),
                    Payment.anonymized_resident_code.ilike(s_term),
                    Payment.transaction_reference.ilike(s_term),
                    func.cast(Payment.id, db.String).ilike(s_term)
                )
            )

        query = query.order_by(Payment.payment_date.desc(), Payment.id.desc())
        return query.paginate(page=page, per_page=per_page, error_out=False)
