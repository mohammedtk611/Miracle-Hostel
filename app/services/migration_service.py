"""
Database migration and schema upgrade service for Miracle Hostel.
Safely adds new columns and tables for Phase 6, Phase 7, and Phase 8
without destroying existing records.
"""
from sqlalchemy import inspect, text
from app.extensions import db


class MigrationService:
    @staticmethod
    def migrate_schema():
        """Ensure all required tables and columns exist across all phases."""
        engine = db.engine
        inspector = inspect(engine)
        dialect = engine.dialect.name

        # 1. Create any missing tables (e.g. resident_stay_histories, data_retention_logs)
        db.create_all()

        # Refresh inspector
        inspector = inspect(engine)

        # 2. Check and add missing columns to payments
        if 'payments' in inspector.get_table_names():
            payment_cols = {c['name']: c for c in inspector.get_columns('payments')}
            with engine.connect() as conn:
                if 'updated_at' not in payment_cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN updated_at DATETIME"))
                    conn.commit()
                if 'obligation_id' not in payment_cols:
                    conn.execute(text("ALTER TABLE payments ADD COLUMN obligation_id INTEGER REFERENCES payment_obligations(id) ON DELETE SET NULL"))
                    conn.commit()

                # Phase 8: Ensure resident_id is nullable and anonymized_resident_code exists
                if 'anonymized_resident_code' not in payment_cols:
                    try:
                        conn.execute(text("ALTER TABLE payments ADD COLUMN anonymized_resident_code VARCHAR(50)"))
                        conn.commit()
                    except Exception:
                        pass

                # If resident_id is still NOT NULL, alter in PostgreSQL or SQLite
                res_col = payment_cols.get('resident_id')
                if res_col and not res_col.get('nullable', True):
                    if dialect == 'postgresql':
                        conn.execute(text("ALTER TABLE payments ALTER COLUMN resident_id DROP NOT NULL"))
                        conn.commit()
                    elif dialect == 'sqlite':
                        conn.execute(text("PRAGMA foreign_keys=OFF;"))
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS payments_migration_tmp (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                resident_id INTEGER REFERENCES residents(id) ON DELETE SET NULL,
                                branch_id INTEGER NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
                                obligation_id INTEGER REFERENCES payment_obligations(id) ON DELETE SET NULL,
                                payment_type VARCHAR(30) NOT NULL,
                                amount NUMERIC(10, 2) NOT NULL,
                                payment_date DATE NOT NULL,
                                payment_status VARCHAR(20) NOT NULL,
                                payment_method VARCHAR(30),
                                transaction_reference VARCHAR(100),
                                notes TEXT,
                                anonymized_resident_code VARCHAR(50),
                                created_at DATETIME NOT NULL,
                                updated_at DATETIME
                            )
                        """))
                        conn.execute(text("""
                            INSERT INTO payments_migration_tmp (id, resident_id, branch_id, obligation_id, payment_type, amount, payment_date, payment_status, payment_method, transaction_reference, notes, created_at, updated_at)
                            SELECT id, resident_id, branch_id, obligation_id, payment_type, amount, payment_date, payment_status, payment_method, transaction_reference, notes, created_at, COALESCE(updated_at, created_at) FROM payments;
                        """))
                        conn.execute(text("DROP TABLE payments;"))
                        conn.execute(text("ALTER TABLE payments_migration_tmp RENAME TO payments;"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_resident_id ON payments (resident_id);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_branch_id ON payments (branch_id);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_obligation_id ON payments (obligation_id);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_payment_type ON payments (payment_type);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_payment_date ON payments (payment_date);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_payment_status ON payments (payment_status);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_transaction_reference ON payments (transaction_reference);"))
                        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_anonymized_resident_code ON payments (anonymized_resident_code);"))
                        conn.commit()
                        conn.execute(text("PRAGMA foreign_keys=ON;"))

                # Backfill anonymized resident codes for existing payments
                try:
                    conn.execute(text("""
                        UPDATE payments 
                        SET anonymized_resident_code = (
                            SELECT resident_code FROM residents WHERE residents.id = payments.resident_id
                        )
                        WHERE (anonymized_resident_code IS NULL OR anonymized_resident_code = '') 
                          AND resident_id IS NOT NULL;
                    """))
                    conn.commit()
                except Exception:
                    pass

        # 3. Check and add missing columns to residents
        if 'residents' in inspector.get_table_names():
            resident_cols = {c['name'] for c in inspector.get_columns('residents')}
            with engine.connect() as conn:
                if 'monthly_rent_amount' not in resident_cols:
                    conn.execute(text("ALTER TABLE residents ADD COLUMN monthly_rent_amount NUMERIC(10, 2) DEFAULT 8500.00"))
                    conn.commit()
                if 'security_deposit_due' not in resident_cols:
                    conn.execute(text("ALTER TABLE residents ADD COLUMN security_deposit_due NUMERIC(10, 2) DEFAULT 12000.00"))
                    conn.commit()
                if 'admission_rent_due' not in resident_cols:
                    conn.execute(text("ALTER TABLE residents ADD COLUMN admission_rent_due NUMERIC(10, 2) DEFAULT 8500.00"))
                    conn.commit()
                if 'notice_date' not in resident_cols:
                    conn.execute(text("ALTER TABLE residents ADD COLUMN notice_date DATE"))
                    conn.commit()

                # Clean up any inconsistent leaving_date for active residents with no active notice
                conn.execute(text("UPDATE residents SET leaving_date = NULL WHERE resident_status = 'ACTIVE' AND notice_date IS NULL AND leaving_date IS NOT NULL"))
                conn.commit()

        # 4. Check and add missing columns to branches
        if 'branches' in inspector.get_table_names():
            branch_cols = {c['name'] for c in inspector.get_columns('branches')}
            with engine.connect() as conn:
                if 'total_beds' not in branch_cols:
                    conn.execute(text("ALTER TABLE branches ADD COLUMN total_beds INTEGER DEFAULT 20 NOT NULL"))
                    conn.commit()

