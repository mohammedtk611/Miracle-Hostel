"""
Services package export.
"""
from app.services.aadhaar_service import AadhaarSecurityService
from app.services.mock_data import (
    get_branches,
    get_branch_by_id,
    get_residents,
    get_resident_by_code,
    get_resident_by_id,
    get_resident_payments,
    get_previous_residents,
    get_payments,
    get_dashboard_stats,
    get_recent_admissions,
    get_recent_payments,
    get_branch_distribution,
)

__all__ = [
    'AadhaarSecurityService',
    'get_branches',
    'get_branch_by_id',
    'get_residents',
    'get_resident_by_code',
    'get_resident_by_id',
    'get_resident_payments',
    'get_previous_residents',
    'get_payments',
    'get_dashboard_stats',
    'get_recent_admissions',
    'get_recent_payments',
    'get_branch_distribution',
]

