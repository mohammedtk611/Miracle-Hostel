"""
Payment Obligation model representing financial dues and billing obligations.
Tracks expected amounts, amounts received, outstanding balances, and dynamically
calculated financial statuses for Security Deposits, Admission Rent, Monthly Rent,
and Other Charges.
"""
from datetime import datetime, date
from app.extensions import db


class ObligationType:
    SECURITY_DEPOSIT = 'SECURITY_DEPOSIT'
    ADMISSION_RENT = 'ADMISSION_RENT'
    MONTHLY_RENT = 'MONTHLY_RENT'
    OTHER_CHARGES = 'OTHER_CHARGES'
    CHOICES = [SECURITY_DEPOSIT, ADMISSION_RENT, MONTHLY_RENT, OTHER_CHARGES]


class PaymentObligation(db.Model):
    """
    Payment Obligation model.
    Represents an expected payment requirement (e.g., monthly rent for a specific cycle,
    initial security deposit, admission rent, or miscellaneous charges).
    Maintains financial truth by computing outstanding balances against actual payments.
    """
    __tablename__ = 'payment_obligations'

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(
        db.Integer,
        db.ForeignKey('residents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey('branches.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    obligation_type = db.Column(db.String(30), nullable=False, index=True)
    billing_month = db.Column(db.String(20), nullable=True, index=True)  # Format: YYYY-MM
    title = db.Column(db.String(120), nullable=False)
    expected_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0.00)
    due_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    resident = db.relationship('Resident', back_populates='obligations')
    branch = db.relationship('Branch', back_populates='obligations')
    payments = db.relationship(
        'Payment',
        back_populates='obligation',
        cascade='all, delete-orphan',
        order_by='Payment.payment_date.desc()'
    )

    @property
    def total_amount_received(self) -> float:
        """Calculate total amount received from verified payment transactions."""
        return sum(
            float(p.amount) for p in self.payments
            if p.payment_status in ('PAID', 'PARTIAL') and float(p.amount) > 0
        )

    @property
    def outstanding_amount(self) -> float:
        """
        Outstanding Amount = max(0, Expected Amount - Total Amount Received).
        Guarantees non-negative balance.
        """
        expected = float(self.expected_amount) if self.expected_amount is not None else 0.0
        received = self.total_amount_received
        return max(0.0, round(expected - received, 2))

    @property
    def status(self) -> str:
        """
        Financial status rules:
        - PAID: Outstanding amount is zero.
        - PARTIAL: Some amount has been received but a balance remains.
        - UNPAID: No amount has been received.
        """
        received = self.total_amount_received
        expected = float(self.expected_amount) if self.expected_amount is not None else 0.0
        if expected <= 0:
            return 'PAID' if received > 0 else 'UNPAID'
        if received >= expected:
            return 'PAID'
        elif received > 0:
            return 'PARTIAL'
        else:
            return 'UNPAID'

    def to_dict(self):
        return {
            'id': self.id,
            'resident_id': self.resident_id,
            'resident_name': self.resident.full_name if self.resident else None,
            'resident_code': self.resident.resident_code if self.resident else None,
            'branch_id': self.branch_id,
            'branch_name': self.branch.branch_name if self.branch else None,
            'obligation_type': self.obligation_type,
            'billing_month': self.billing_month,
            'title': self.title,
            'expected_amount': float(self.expected_amount) if self.expected_amount else 0.0,
            'total_amount_received': self.total_amount_received,
            'outstanding_amount': self.outstanding_amount,
            'due_date': self.due_date.strftime('%Y-%m-%d') if self.due_date else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None
        }

    def __repr__(self):
        return f"<PaymentObligation id={self.id} resident_id={self.resident_id} type='{self.obligation_type}' expected={self.expected_amount} status='{self.status}'>"

