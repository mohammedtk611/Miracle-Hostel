"""
Branch model representing individual hostel locations.
"""
from datetime import datetime
from app.extensions import db


class Branch(db.Model):
    """
    Branch model representing individual hostel branches.
    Deactivating a branch preserves all associated historical data and records.
    """
    __tablename__ = 'branches'

    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(120), nullable=False)
    branch_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    address = db.Column(db.Text, nullable=False)
    contact_number = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    total_beds = db.Column(db.Integer, default=20, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    # Deleting or deactivating branch must protect historical records (RESTRICT)
    residents = db.relationship(
        'Resident',
        back_populates='branch',
        lazy='dynamic',
        passive_deletes=False
    )
    payments = db.relationship(
        'Payment',
        back_populates='branch',
        lazy='dynamic',
        passive_deletes=False
    )
    obligations = db.relationship(
        'PaymentObligation',
        back_populates='branch',
        lazy='dynamic',
        passive_deletes=False
    )

    @property
    def active_residents_count(self) -> int:
        """Count currently active residents residing in this branch."""
        return self.residents.filter_by(resident_status='ACTIVE').count()

    @property
    def occupied_beds(self) -> int:
        """Number of currently occupied beds."""
        return self.active_residents_count

    @property
    def available_beds(self) -> int:
        """Number of free beds available for new resident admissions."""
        capacity = self.total_beds if self.total_beds is not None else 20
        return max(0, capacity - self.active_residents_count)

    @property
    def occupancy_rate(self) -> float:
        """Occupancy percentage (0.0 to 100.0)."""
        capacity = self.total_beds if self.total_beds is not None else 20
        if capacity <= 0:
            return 0.0
        return round((self.active_residents_count / capacity) * 100, 1)

    @property
    def total_residents_count(self) -> int:
        """Count total all-time residents registered under this branch."""
        return self.residents.count()

    def to_dict(self):
        return {
            'id': self.id,
            'branch_name': self.branch_name,
            'branch_code': self.branch_code,
            'address': self.address,
            'contact_number': self.contact_number,
            'is_active': self.is_active,
            'total_beds': self.total_beds or 20,
            'occupied_beds': self.occupied_beds,
            'available_beds': self.available_beds,
            'occupancy_rate': self.occupancy_rate,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None,
            'active_residents_count': self.active_residents_count,
            'total_residents_count': self.total_residents_count
        }

    def __repr__(self):
        return f"<Branch code='{self.branch_code}' name='{self.branch_name}' active={self.is_active}>"

