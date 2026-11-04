"""
Resident Stay History model for tracking admission and departure cycles across a resident's lifecycle.
Preserves historical admissions, leaving dates, and branch stays for returning/reactivated residents.
"""
from datetime import datetime
from app.extensions import db


class ResidentStayHistory(db.Model):
    """
    Tracks multiple admission and departure events for a resident.
    Ensures complete lifecycle auditing when residents depart and subsequently return.
    """
    __tablename__ = 'resident_stay_histories'

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
    admission_date = db.Column(db.Date, nullable=False, index=True)
    leaving_date = db.Column(db.Date, nullable=True, index=True)
    stay_number = db.Column(db.Integer, default=1, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    resident = db.relationship('Resident', back_populates='stay_history')
    branch = db.relationship('Branch')

    @property
    def is_current_stay(self) -> bool:
        """True if this record represents the resident's currently active stay."""
        return self.leaving_date is None

    @property
    def duration_days(self) -> int | None:
        """Total duration of this stay in days."""
        if self.leaving_date and self.admission_date:
            return (self.leaving_date - self.admission_date).days
        return None

    def __repr__(self):
        status = f"left on {self.leaving_date}" if self.leaving_date else "active"
        return f"<ResidentStayHistory resident_id={self.resident_id} stay_number={self.stay_number} ({status})>"

