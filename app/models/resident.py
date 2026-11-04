"""
Resident model representing hostel residents.
"""
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.payment_obligation import PaymentObligation
from app.models.payment import Payment


class ResidentStatus:
    ACTIVE = 'ACTIVE'
    LEFT = 'LEFT'
    CHOICES = [ACTIVE, LEFT]


class Resident(db.Model):
    """
    Resident model.
    Aadhaar information is encrypted at rest.
    Only the last four digits are stored separately for safe display and searching.
    When a resident leaves, their status transitions to LEFT and their record moves
    to previous residents under a 30-day retention policy.
    """
    __tablename__ = 'residents'

    id = db.Column(db.Integer, primary_key=True)
    resident_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    branch_id = db.Column(
        db.Integer,
        db.ForeignKey('branches.id', ondelete='RESTRICT'),
        nullable=False,
        index=True
    )
    full_name = db.Column(db.String(150), nullable=False, index=True)
    photograph_path = db.Column(db.String(300), nullable=True)
    
    # Secure Aadhaar Storage
    # Full Aadhaar is stored strictly as ciphertext (AES-256)
    aadhaar_encrypted = db.Column(db.Text, nullable=True)
    # Stored plaintext last 4 digits for verification & UI display (e.g. XXXX-XXXX-4589)
    aadhaar_last_four = db.Column(db.String(4), nullable=True, index=True)

    admission_date = db.Column(db.Date, nullable=False, index=True)
    leaving_date = db.Column(db.Date, nullable=True, index=True)
    notice_date = db.Column(db.Date, nullable=True, index=True)
    resident_status = db.Column(
        db.String(20),
        default=ResidentStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Financial Agreed Baseline Fields
    monthly_rent_amount = db.Column(db.Numeric(10, 2), default=8500.00, nullable=True)
    security_deposit_due = db.Column(db.Numeric(10, 2), default=12000.00, nullable=True)
    admission_rent_due = db.Column(db.Numeric(10, 2), default=8500.00, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    branch = db.relationship('Branch', back_populates='residents')
    payments = db.relationship(
        'Payment',
        back_populates='resident',
        cascade='save-update, merge',
        passive_deletes=True,
        lazy='dynamic',
        order_by='Payment.payment_date.desc()'
    )
    obligations = db.relationship(
        'PaymentObligation',
        back_populates='resident',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='PaymentObligation.due_date.desc()'
    )
    stay_history = db.relationship(
        'ResidentStayHistory',
        back_populates='resident',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='ResidentStayHistory.stay_number.asc()'
    )

    @classmethod
    def generate_unique_code(cls) -> str:
        """
        Generate a unique resident identifier: MHL-{YEAR}-{SEQ:03d}.
        Guaranteed unique, preventing manual identifier tampering.
        """
        current_year = date.today().year
        prefix = f"MHL-{current_year}-"
        latest = cls.query.filter(cls.resident_code.like(f"{prefix}%"))\
            .order_by(cls.id.desc()).first()
        next_seq = 1
        if latest and latest.resident_code:
            try:
                num_part = latest.resident_code.split('-')[-1]
                next_seq = int(num_part) + 1
            except (ValueError, IndexError):
                next_seq = cls.query.count() + 1
        else:
            next_seq = cls.query.count() + 1

        code = f"{prefix}{next_seq:03d}"
        while cls.query.filter_by(resident_code=code).first():
            next_seq += 1
            code = f"{prefix}{next_seq:03d}"
        return code

    @property
    def room_number(self) -> str:
        """Deterministic room and bed allocation representation."""
        bed_letter = 'A' if (self.id or 1) % 2 == 1 else 'B'
        room_num = ((self.id or 1) % 15) + 101
        return f"Room {room_num} - Bed {bed_letter}"

    @property
    def masked_aadhaar(self) -> str:
        """Return masked Aadhaar string for UI displays."""
        if self.aadhaar_last_four and self.aadhaar_last_four not in ('', 'N/A'):
            return f"XXXX-XXXX-{self.aadhaar_last_four}"
        return "Not Provided"

    def get_decrypted_aadhaar(self) -> str:
        """
        Decrypt and return the full 12-digit Aadhaar number for authorized administrator operations.
        Formatted as 'XXXX XXXX XXXX'.
        """
        if not self.aadhaar_encrypted:
            return "Not Provided"
        from app.services.aadhaar_service import AadhaarSecurityService
        decrypted = AadhaarSecurityService.decrypt_aadhaar(self.aadhaar_encrypted)
        if decrypted and decrypted != "DECRYPTION_ERROR" and len(decrypted) == 12:
            return f"{decrypted[:4]} {decrypted[4:8]} {decrypted[8:]}"
        return decrypted or "Not Provided"

    def get_raw_aadhaar(self) -> str:
        """Return raw 12-digit plaintext Aadhaar without spaces for form inputs."""
        if not self.aadhaar_encrypted:
            return ""
        from app.services.aadhaar_service import AadhaarSecurityService
        decrypted = AadhaarSecurityService.decrypt_aadhaar(self.aadhaar_encrypted)
        return decrypted if decrypted != "DECRYPTION_ERROR" else ""

    # -------------------------------------------------------------------------
    # FINANCIAL OBLIGATIONS & BALANCE COMPUTATION
    # -------------------------------------------------------------------------
    @property
    def deposit_due(self) -> float:
        """Expected security deposit obligation amount."""
        ob = self.obligations.filter_by(obligation_type='SECURITY_DEPOSIT').first()
        if ob and ob.expected_amount is not None:
            return float(ob.expected_amount)
        return float(self.security_deposit_due) if self.security_deposit_due is not None else 12000.00

    @property
    def deposit_received(self) -> float:
        """Total verified security deposit amount received."""
        dep_payments = self.payments.filter_by(payment_type='SECURITY_DEPOSIT').all()
        return sum(float(p.amount) for p in dep_payments if p.payment_status in ('PAID', 'PARTIAL') and float(p.amount) > 0)

    @property
    def deposit_outstanding(self) -> float:
        """Deposit Outstanding Balance = max(0, Due - Received)."""
        ob = self.obligations.filter_by(obligation_type='SECURITY_DEPOSIT').first()
        if ob:
            return ob.outstanding_amount
        return max(0.0, round(self.deposit_due - self.deposit_received, 2))

    @property
    def deposit_status(self) -> str:
        """
        Security deposit status reflecting actual amount paid against expected due:
        - PAID: Outstanding amount is zero.
        - PARTIAL: Some amount has been received but a balance remains.
        - UNPAID: No amount has been received.
        """
        ob = self.obligations.filter_by(obligation_type='SECURITY_DEPOSIT').first()
        if ob:
            return ob.status
        rec = self.deposit_received
        due = self.deposit_due
        if due <= 0 and rec <= 0:
            latest = self.payments.filter_by(payment_type='SECURITY_DEPOSIT').order_by(
                db.desc('payment_date'), db.desc('id')
            ).first()
            return latest.payment_status if latest else 'UNPAID'
        if rec >= due and due > 0:
            return 'PAID'
        elif rec > 0:
            return 'PARTIAL'
        else:
            # Fallback to latest payment record status if present
            latest = self.payments.filter_by(payment_type='SECURITY_DEPOSIT').order_by(
                db.desc('payment_date'), db.desc('id')
            ).first()
            return latest.payment_status if latest else 'UNPAID'

    @property
    def security_deposit_amount(self) -> float:
        """Security deposit amount from latest payment record or agreed due."""
        dep = self.payments.filter_by(payment_type='SECURITY_DEPOSIT').order_by(
            db.desc('payment_date'), db.desc('id')
        ).first()
        if dep and float(dep.amount) > 0:
            return float(dep.amount)
        return self.deposit_due

    @property
    def security_deposit(self) -> float:
        """Alias for security deposit amount."""
        return self.security_deposit_amount

    # Admission Rent
    @property
    def admission_rent_expected(self) -> float:
        """Expected admission rent amount."""
        ob = self.obligations.filter_by(obligation_type='ADMISSION_RENT').first()
        if ob and ob.expected_amount is not None:
            return float(ob.expected_amount)
        return float(self.admission_rent_due) if self.admission_rent_due is not None else 8500.00

    @property
    def admission_rent_received(self) -> float:
        """Total verified admission rent received."""
        adm_payments = self.payments.filter_by(payment_type='ADMISSION_RENT').all()
        return sum(float(p.amount) for p in adm_payments if p.payment_status in ('PAID', 'PARTIAL') and float(p.amount) > 0)

    @property
    def admission_rent_outstanding(self) -> float:
        """Remaining admission rent balance."""
        ob = self.obligations.filter_by(obligation_type='ADMISSION_RENT').first()
        if ob:
            return ob.outstanding_amount
        return max(0.0, round(self.admission_rent_expected - self.admission_rent_received, 2))

    @property
    def admission_rent_status(self) -> str:
        """Admission rent status (PAID, PARTIAL, UNPAID)."""
        ob = self.obligations.filter_by(obligation_type='ADMISSION_RENT').first()
        if ob:
            return ob.status
        rec = self.admission_rent_received
        exp = self.admission_rent_expected
        if rec >= exp and exp > 0:
            return 'PAID'
        elif rec > 0:
            return 'PARTIAL'
        else:
            return 'UNPAID'

    # Monthly Rent
    @property
    def total_rent_paid(self) -> float:
        """Calculate total sum of verified paid rent transactions across all cycles."""
        rent_payments = [
            p for p in self.payments.all()
            if p.payment_type in ('RENT', 'MONTHLY_RENT', 'ADMISSION_RENT')
            and p.payment_status in ('PAID', 'PARTIAL') and float(p.amount) > 0
        ]
        return sum(float(p.amount) for p in rent_payments)

    @property
    def outstanding_rent(self) -> float:
        """Calculate outstanding rent amount across all obligations."""
        obs = self.obligations.filter(
            db.or_(
                PaymentObligation.obligation_type == 'MONTHLY_RENT',
                PaymentObligation.obligation_type == 'ADMISSION_RENT'
            )
        ).all()
        if obs:
            return sum(ob.outstanding_amount for ob in obs)

        # Fallback to latest payment record if no obligations
        latest_rent = self.payments.filter(
            db.or_(
                Payment.payment_type == 'RENT',
                Payment.payment_type == 'MONTHLY_RENT',
                Payment.payment_type == 'ADMISSION_RENT'
            )
        ).order_by(db.desc('payment_date'), db.desc('id')).first()
        if latest_rent and latest_rent.payment_status in ('PENDING', 'PARTIAL', 'UNPAID'):
            return float(latest_rent.amount)
        return 0.0

    @property
    def rent_status(self) -> str:
        """Determine current rent status from payment history or latest obligation."""
        # 1. If explicit monthly rent obligation exists, use latest obligation's status
        latest_ob = self.obligations.filter_by(obligation_type='MONTHLY_RENT').order_by(
            db.desc('due_date'), db.desc('id')
        ).first()
        if latest_ob:
            return latest_ob.status

        # 2. Check latest rent payment record
        latest_rent = self.payments.filter(
            db.or_(
                Payment.payment_type == 'RENT',
                Payment.payment_type == 'MONTHLY_RENT'
            )
        ).order_by(db.desc('payment_date'), db.desc('id')).first()
        if latest_rent:
            return latest_rent.payment_status
        return 'UNPAID'

    @property
    def total_financial_received(self) -> float:
        """Total monetary amount received from this resident across all categories."""
        return sum(
            float(p.amount) for p in self.payments.all()
            if p.payment_status in ('PAID', 'PARTIAL') and float(p.amount) > 0
        )

    @property
    def total_financial_outstanding(self) -> float:
        """Total balance due from this resident across all obligations."""
        return round(self.deposit_outstanding + self.outstanding_rent, 2)

    @property
    def branch_name(self) -> str:
        """Name of assigned branch."""
        return self.branch.branch_name if self.branch else "N/A"

    @property
    def branch_code(self) -> str:
        """Code of assigned branch."""
        return self.branch.branch_code if self.branch else "N/A"

    @property
    def phone_number(self) -> str:
        """Formatted resident contact phone placeholder."""
        return "+91 98400 " + f"{self.id:05d}"

    @property
    def emergency_contact(self) -> str:
        """Formatted emergency contact placeholder."""
        return "+91 98401 00000 (Family)"

    @property
    def security_deposit(self) -> float:
        """Alias for security deposit amount."""
        return self.security_deposit_amount

    @property
    def retention(self) -> dict | None:
        """Calculate retention metrics and status for departed resident."""
        from app.utils.helpers import calculate_retention_info
        if self.resident_status == ResidentStatus.LEFT and self.leaving_date:
            return calculate_retention_info(self.leaving_date)
        return None

    @property
    def retention_deadline(self) -> date | None:
        """Calculate the 30-day retention deadline after departure."""
        if self.resident_status == ResidentStatus.LEFT and self.leaving_date:
            return self.leaving_date + timedelta(days=30)
        return None

    @property
    def remaining_retention_days(self) -> int | None:
        """
        Calculate remaining days until permanent deletion eligibility.
        Returns a negative number if deadline has passed.
        """
        if self.retention_deadline:
            delta = self.retention_deadline - date.today()
            return delta.days
        return None

    @property
    def is_leaving_soon(self) -> bool:
        """
        True if resident is active but has given notice or is scheduled to leave
        this month or next month (within notice period).
        """
        if self.resident_status != ResidentStatus.ACTIVE:
            return False
        target_date = self.notice_date or self.leaving_date
        if not target_date:
            return False
        today = date.today()
        # Scheduled to leave between today and end of next month (~45 days)
        return today <= target_date <= (today + timedelta(days=45))

    @property
    def is_eligible_for_deletion(self) -> bool:
        """True if the resident has left and the 30-day retention period has elapsed."""
        if self.resident_status == ResidentStatus.LEFT and self.leaving_date:
            return date.today() >= self.retention_deadline
        return False

    @property
    def security_deposit_payment(self):
        """Retrieve latest security deposit payment record."""
        return self.payments.filter_by(payment_type='SECURITY_DEPOSIT').first()

    @property
    def rent_payments(self):
        """Retrieve rent payment records."""
        return self.payments.filter_by(payment_type='RENT').all()

    def to_dict(self):
        return {
            'id': self.id,
            'resident_code': self.resident_code,
            'branch_id': self.branch_id,
            'branch_name': self.branch.branch_name if self.branch else None,
            'full_name': self.full_name,
            'photograph_path': self.photograph_path,
            'masked_aadhaar': self.masked_aadhaar,
            'aadhaar_last_four': self.aadhaar_last_four,
            'admission_date': self.admission_date.strftime('%Y-%m-%d') if self.admission_date else None,
            'leaving_date': self.leaving_date.strftime('%Y-%m-%d') if self.leaving_date else None,
            'resident_status': self.resident_status,
            'retention_deadline': self.retention_deadline.strftime('%Y-%m-%d') if self.retention_deadline else None,
            'remaining_retention_days': self.remaining_retention_days,
            'is_eligible_for_deletion': self.is_eligible_for_deletion
        }

    def __repr__(self):
        return f"<Resident code='{self.resident_code}' name='{self.full_name}' status={self.resident_status}>"

