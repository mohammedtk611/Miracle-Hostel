"""
Dashboard routes for Miracle Hostel.
Protected with Flask-Login administrator session requirement.
Powered by real PostgreSQL database queries and aggregations.
"""
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.extensions import db
from app.models.branch import Branch
from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main administrative dashboard view with real-time PostgreSQL metrics."""
    # Selected branch filter from query params ('all' or branch numeric ID)
    selected_branch = request.args.get('branch', 'all')
    
    # Calculate statistics based on selected branch or consolidated
    stats = DashboardService.get_dashboard_stats(selected_branch)
    recent_admissions = DashboardService.get_recent_admissions(selected_branch, limit=5)
    recent_departures = DashboardService.get_recent_departures(selected_branch, limit=5)
    recent_payments = DashboardService.get_recent_payments(selected_branch, limit=6)
    branch_distribution = DashboardService.get_branch_distribution()
    all_branches = Branch.query.order_by(Branch.branch_name.asc()).all()
    active_branches = [b for b in all_branches if b.is_active]

    current_branch_obj = None
    if selected_branch != 'all':
        try:
            current_branch_obj = db.session.get(Branch, int(selected_branch))
        except (ValueError, TypeError):
            current_branch_obj = None

    return render_template(
        'dashboard/index.html',
        stats=stats,
        recent_admissions=recent_admissions,
        recent_departures=recent_departures,
        recent_payments=recent_payments,
        branch_distribution=branch_distribution,
        all_branches=all_branches,
        active_branches=active_branches,
        selected_branch=selected_branch,
        current_branch_obj=current_branch_obj
    )
