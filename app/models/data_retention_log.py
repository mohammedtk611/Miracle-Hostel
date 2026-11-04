"""
DataRetentionLog model for tracking automated and manual retention purges.
Records retention cleanup execution history without retaining deleted personal data.
"""
from datetime import datetime
from app.extensions import db


class RetentionLogStatus:
    SUCCESS = 'SUCCESS'
    PARTIAL = 'PARTIAL'
    FAILED = 'FAILED'
    NO_OP = 'NO_OP'
    CHOICES = [SUCCESS, PARTIAL, FAILED, NO_OP]


class DataRetentionLog(db.Model):
    """
    DataRetentionLog model.
    Maintains an immutable record of data retention purges.
    Strictly prohibits recording full names, plaintext/encrypted Aadhaar numbers,
    or photographs of purged residents.
    """
    __tablename__ = 'data_retention_logs'

    id = db.Column(db.Integer, primary_key=True)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    records_identified = db.Column(db.Integer, default=0, nullable=False)
    records_purged = db.Column(db.Integer, default=0, nullable=False)
    records_failed = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default=RetentionLogStatus.SUCCESS, nullable=False, index=True)
    details = db.Column(db.Text, nullable=True)
    failure_reason = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'executed_at': self.executed_at.strftime('%Y-%m-%d %H:%M:%S') if self.executed_at else None,
            'records_identified': self.records_identified,
            'records_purged': self.records_purged,
            'records_failed': self.records_failed,
            'status': self.status,
            'details': self.details,
            'failure_reason': self.failure_reason
        }

    def __repr__(self):
        return f"<DataRetentionLog id={self.id} status='{self.status}' purged={self.records_purged} at='{self.executed_at}'>"

