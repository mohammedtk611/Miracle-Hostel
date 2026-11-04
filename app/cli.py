"""
Flask CLI Commands for Miracle Hostel Management Portal.
Provides command-line administrative tasks including automated 30-day data retention cleanup.
"""
import click
from flask import current_app
from app.services.retention_service import RetentionService


def register_cli_commands(app):
    """Register all custom CLI commands on the Flask application instance."""

    @app.cli.command("cleanup-expired-residents")
    @click.option(
        "--days",
        default=None,
        type=int,
        help="Override retention threshold days (defaults to config RESIDENT_RETENTION_DAYS, e.g. 30)."
    )
    def cleanup_expired_residents(days):
        """
        Permanently delete resident records whose 30-day retention deadline has passed.
        
        Usage:
            flask cleanup-expired-residents
            flask cleanup-expired-residents --days 30
        """
        click.echo("[Miracle Hostel] Connecting to database and checking data retention rules...")
        result = RetentionService.run_retention_cleanup(retention_days=days)

        if result['status'] == 'NO_OP':
            click.echo(f"[Miracle Hostel] {result['message']}")
        elif result['status'] == 'SUCCESS':
            click.secho(f"[Miracle Hostel] SUCCESS: {result['message']}", fg="green")
            if result['purged_codes']:
                click.echo(f"[Miracle Hostel] Purged resident codes: {', '.join(result['purged_codes'])}")
        elif result['status'] == 'PARTIAL':
            click.secho(f"[Miracle Hostel] WARNING: {result['message']}", fg="yellow")
            if result['failed_codes']:
                click.secho(f"[Miracle Hostel] Failed resident codes: {', '.join(result['failed_codes'])}", fg="red")
        else:
            click.secho(f"[Miracle Hostel] FAILURE: {result['message']}", fg="red")
            if result['failed_codes']:
                click.secho(f"[Miracle Hostel] Failed resident codes: {', '.join(result['failed_codes'])}", fg="red")
            raise click.ClickException(result['message'])

