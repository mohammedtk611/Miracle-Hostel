"""
Payment model representing monetary transactions for residents.
"""
from datetime import datetime
from app.extensions import db


class PaymentType:
    SECURITY_DEPOSIT = 'SECURITY_DEPOSIT'
    ADMISSION_RENT = 'ADMISSION_RENT'
    MONTHLY_RENT = 'MONTHLY_RENT'
    OTHER_CHARGES = 'OTHER_CHARGES'
    RENT = 'RENT'  # Backward compatibility alias
    CHOICES = [SECURITY_DEPOSIT, ADMISSION_RENT, MONTHLY_RENT, OTHER_CHARGES, RENT]


class PaymentStatus:
    PAID = 'PAID'
    PARTIAL = 'PARTIAL'
    UNPAID = 'UNPAID'
    PENDING = 'PENDING'  # Backward compatibility alias
    CHOICES = [PAID, PARTIAL, UNPAID, PENDING]


class PaymentMethod:
    CASH = 'CASH'
    UPI = 'UPI'
    BANK_TRANSFER = 'BANK_TRANSFER'
    CHEQUE = 'CHEQUE'
    CHOICES = [CASH, UPI, BANK_TRANSFER, CHEQUE]


class Payment(db.Model):
    """
    Payment model.
    Tracks all individual monetary transactions for security deposits, admission rent,
    monthly rent, and other charges.
    Multiple payment records per resident are retained immutably without overwriting history.
    """
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(
        db.Integer,
        db.ForeignKey('residents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey('branches.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    obligation_id = db.Column(
        db.Integer,
        db.ForeignKey('payment_obligations.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    payment_type = db.Column(db.String(30), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, index=True)
    payment_status = db.Column(
        db.String(20),
        default=PaymentStatus.PAID,
        nullable=False,
        index=True
    )
    payment_method = db.Column(db.String(30), nullable=True)
    transaction_reference = db.Column(db.String(100), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    anonymized_resident_code = db.Column(db.String(50), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    resident = db.relationship('Resident', back_populates='payments')
    branch = db.relationship('Branch', back_populates='payments')
    obligation = db.relationship('PaymentObligation', back_populates='payments')

    @property
    def payment_id(self) -> str:
        """Formatted payment identifier string."""
        return f"PAY-{self.id:05d}"

    @property
    def resident_name(self) -> str:
        """Resident name or placeholder for deleted records."""
        return self.resident.full_name if self.resident else "[Deleted Resident]"

    @property
    def resident_code(self) -> str:
        """Resident unique code or anonymized code for purged records."""
        if self.resident:
            return self.resident.resident_code
        return self.anonymized_resident_code or "ANON-PURGED"

    @property
    def branch_name(self) -> str:
        """Name of the assigned hostel branch."""
        return self.branch.branch_name if self.branch else "N/A"

    def to_dict(self):
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'resident_id': self.resident_id,
            'resident_name': self.resident_name,
            'resident_code': self.resident_code,
            'anonymized_resident_code': self.anonymized_resident_code,
            'branch_id': self.branch_id,
            'branch_name': self.branch_name,
            'obligation_id': self.obligation_id,
            'payment_type': self.payment_type,
            'amount': float(self.amount) if self.amount is not None else 0.0,
            'payment_date': self.payment_date.strftime('%Y-%m-%d') if self.payment_date else None,
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
            'transaction_reference': self.transaction_reference,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None
        }

    def __repr__(self):
        return f"<Payment id={self.id} resident_id={self.resident_id} type='{self.payment_type}' amount={self.amount} status='{self.payment_status}'>"


