"""
Dashboard Service for Miracle Hostel Management Portal.
Provides PostgreSQL database-driven aggregations, metrics, and KPI calculations
supporting both consolidated system-wide views and branch-specific reporting.
"""
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Branch, Resident, Payment, ResidentStatus, PaymentType, PaymentStatus


class DashboardService:
    """Calculates real-time occupancy and financial metrics from PostgreSQL records."""

    @classmethod
    def get_dashboard_stats(cls, selected_branch: str | int = 'all') -> dict:
        """
        Compute KPI statistics based on the selected branch filter ('all' or numeric branch ID).
        Consolidated statistics include all branches (including deactivated branches for historical totals).
        """
        is_all_branches = True
        branch_name = "All Branches"
        branch_code = "ALL"
        target_branch_id = None

        if selected_branch and str(selected_branch).lower() != 'all':
            try:
                b_id = int(selected_branch)
                branch_obj = db.session.get(Branch, b_id)
                if branch_obj:
                    is_all_branches = False
                    branch_name = branch_obj.branch_name
                    branch_code = branch_obj.branch_code
                    target_branch_id = branch_obj.id
            except (ValueError, TypeError):
                pass

        # 1. Resident Counts
        res_query = Resident.query
        if target_branch_id:
            res_query = res_query.filter(Resident.branch_id == target_branch_id)

        total_residents = res_query.count()
        active_residents = res_query.filter(Resident.resident_status == ResidentStatus.ACTIVE).count()
        left_residents = res_query.filter(Resident.resident_status == ResidentStatus.LEFT).count()

        # 2. Financial Metrics via SQL Aggregation
        # Pending Security Deposits
        pending_dep_query = db.session.query(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.payment_type == PaymentType.SECURITY_DEPOSIT,
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL, PaymentStatus.UNPAID])
        )
        if target_branch_id:
            pending_dep_query = pending_dep_query.filter(Payment.branch_id == target_branch_id)
        pending_dep_count, pending_dep_amount = pending_dep_query.first()

        # Pending Monthly Rent
        pending_rent_query = db.session.query(
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.payment_type.in_([PaymentType.RENT, PaymentType.MONTHLY_RENT, PaymentType.ADMISSION_RENT]),
            Payment.payment_status.in_([PaymentStatus.PENDING, PaymentStatus.PARTIAL, PaymentStatus.UNPAID])
        )
        if target_branch_id:
            pending_rent_query = pending_rent_query.filter(Payment.branch_id == target_branch_id)
        pending_rent_count, pending_rent_amount = pending_rent_query.first()

        # Total Collections (Paid Payments)
        coll_query = db.session.query(
            func.coalesce(func.sum(Payment.amount), 0)
        ).filter(
            Payment.payment_status == PaymentStatus.PAID
        )
        if target_branch_id:
            coll_query = coll_query.filter(Payment.branch_id == target_branch_id)
        total_collection = coll_query.scalar() or 0

        return {
            'is_all_branches': is_all_branches,
            'branch_name': branch_name,
            'branch_code': branch_code,
            'branch_id': target_branch_id,
            'total_residents': total_residents,
            'active_residents': active_residents,
            'left_residents': left_residents,
            'pending_deposits_count': int(pending_dep_count or 0),
            'pending_deposits_amount': float(pending_dep_amount or 0.0),
            'pending_rent_count': int(pending_rent_count or 0),
            'pending_rent_amount': float(pending_rent_amount or 0.0),
            'total_collection': float(total_collection or 0.0)
        }

    @classmethod
    def get_recent_admissions(cls, selected_branch: str | int = 'all', limit: int = 5) -> list[dict]:
        """Retrieve recent resident admissions ordered by admission date descending."""
        q = Resident.query.options(joinedload(Resident.branch)).order_by(Resident.admission_date.desc(), Resident.id.desc())

        if selected_branch and str(selected_branch).lower() != 'all':
            try:
                b_id = int(selected_branch)
                q = q.filter(Resident.branch_id == b_id)
            except (ValueError, TypeError):
                pass

        residents = q.limit(limit).all()
        results = []
        for r in residents:
            deposit_record = r.payments.filter_by(payment_type=PaymentType.SECURITY_DEPOSIT).first()
            deposit_status = deposit_record.payment_status if deposit_record else 'PAID'
            results.append({
                'id': r.id,
                'resident_code': r.resident_code,
                'full_name': r.full_name,
                'photograph_path': r.photograph_path or '/static/images/avatars/avatar-1.svg',
                'branch_name': r.branch.branch_name if r.branch else 'N/A',
                'branch_code': r.branch.branch_code if r.branch else 'N/A',
                'admission_date': r.admission_date,
                'room_number': r.room_number,
                'deposit_status': deposit_status
            })
        return results

    @classmethod
    def get_recent_payments(cls, selected_branch: str | int = 'all', limit: int = 6) -> list[dict]:
        """Retrieve recent payment transactions ordered by payment date descending."""
        q = Payment.query.options(
            joinedload(Payment.resident),
            joinedload(Payment.branch)
        ).order_by(Payment.payment_date.desc(), Payment.id.desc())

        if selected_branch and str(selected_branch).lower() != 'all':
            try:
                b_id = int(selected_branch)
                q = q.filter(Payment.branch_id == b_id)
            except (ValueError, TypeError):
                pass

        payments = q.limit(limit).all()
        results = []
        for p in payments:
            results.append({
                'id': p.id,
                'payment_id': f"PAY-{p.id:05d}",
                'resident_name': p.resident_name,
                'resident_code': p.resident_code,
                'branch_name': p.branch_name,
                'payment_type': p.payment_type,
                'amount': float(p.amount),
                'payment_date': p.payment_date,
                'payment_method': p.payment_method or 'CASH',
                'transaction_reference': p.transaction_reference,
                'payment_status': p.payment_status
            })
        return results

    @classmethod
    def get_recent_departures(cls, selected_branch: str | int = 'all', limit: int = 5) -> list[dict]:
        """Retrieve recent resident departures ordered by leaving date descending."""
        q = Resident.query.options(joinedload(Resident.branch)).filter(
            Resident.resident_status == ResidentStatus.LEFT
        ).order_by(Resident.leaving_date.desc(), Resident.id.desc())

        if selected_branch and str(selected_branch).lower() != 'all':
            try:
                b_id = int(selected_branch)
                q = q.filter(Resident.branch_id == b_id)
            except (ValueError, TypeError):
                pass

        residents = q.limit(limit).all()
        results = []
        for r in residents:
            results.append({
                'id': r.id,
                'resident_code': r.resident_code,
                'full_name': r.full_name,
                'photograph_path': r.photograph_path or '/static/images/avatars/avatar-1.svg',
                'branch_name': r.branch.branch_name if r.branch else 'N/A',
                'branch_code': r.branch.branch_code if r.branch else 'N/A',
                'admission_date': r.admission_date,
                'leaving_date': r.leaving_date,
                'retention_deadline': r.retention_deadline,
                'remaining_retention_days': r.remaining_retention_days,
                'outstanding_balance': r.total_financial_outstanding
            })
        return results

    @classmethod
    def get_branch_distribution(cls) -> list[dict]:
        """Compute resident occupancy distribution across all branches."""
        branches = Branch.query.order_by(Branch.branch_name.asc()).all()
        total_active = Resident.query.filter_by(resident_status=ResidentStatus.ACTIVE).count()

        distribution = []
        for b in branches:
            active_cnt = b.active_residents_count
            total_cnt = b.total_residents_count
            pct = round((active_cnt / total_active * 100), 1) if total_active > 0 else 0.0
            distribution.append({
                'id': b.id,
                'branch_name': b.branch_name,
                'branch_code': b.branch_code,
                'is_active': b.is_active,
                'active_count': active_cnt,
                'total_count': total_cnt,
                'percentage': pct
            })
        return distribution

