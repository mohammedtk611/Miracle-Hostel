"""
UI and formatting helper utilities for Miracle Hostel.
"""
from datetime import datetime, date, timedelta


def format_currency(amount) -> str:
    """Format numeric values into standard Indian Rupee notation."""
    if amount is None:
        return "₹ 0"
    try:
        val = float(amount)
        # Format with Indian-style grouping or standard comma notation
        if val.is_integer():
            return f"₹ {int(val):,}"
        return f"₹ {val:,.2f}"
    except (ValueError, TypeError):
        return f"₹ {amount}"


def format_date(dt_value, fmt="%d %b %Y") -> str:
    """Format date or datetime into readable string (e.g. 15 Oct 2024)."""
    if not dt_value:
        return "—"
    if isinstance(dt_value, str):
        try:
            dt_value = datetime.strptime(dt_value, "%Y-%m-%d").date()
        except ValueError:
            return dt_value
    if isinstance(dt_value, (datetime, date)):
        return dt_value.strftime(fmt)
    return str(dt_value)


def calculate_retention_info(leaving_date, retention_days=365) -> dict:
    """
    Calculate retention status metrics for left residents (default: 365 days / 1 year):
    - retention_deadline
    - days_remaining
    - urgency_level ('normal', 'approaching', 'expired')
    - badge_class
    - label
    """
    if not leaving_date:
        return {
            'deadline': None,
            'days_remaining': None,
            'urgency': 'unknown',
            'badge_class': 'badge-secondary',
            'label': 'Not Specified'
        }

    if isinstance(leaving_date, str):
        try:
            leaving_date = datetime.strptime(leaving_date, "%Y-%m-%d").date()
        except ValueError:
            return {
                'deadline': None,
                'days_remaining': None,
                'urgency': 'unknown',
                'badge_class': 'badge-secondary',
                'label': str(leaving_date)
            }

    deadline = leaving_date + timedelta(days=retention_days)
    today = date.today()
    days_remaining = (deadline - today).days

    if days_remaining < 0:
        return {
            'deadline': deadline,
            'days_remaining': days_remaining,
            'urgency': 'expired',
            'badge_class': 'badge-danger',
            'label': f'Eligible for Deletion ({abs(days_remaining)}d overdue)'
        }
    elif days_remaining <= 30:
        return {
            'deadline': deadline,
            'days_remaining': days_remaining,
            'urgency': 'approaching',
            'badge_class': 'badge-warning',
            'label': f'Approaching 1-Year Deadline ({days_remaining}d left)'
        }
    else:
        return {
            'deadline': deadline,
            'days_remaining': days_remaining,
            'urgency': 'normal',
            'badge_class': 'badge-success',
            'label': f'{days_remaining} days remaining'
        }

