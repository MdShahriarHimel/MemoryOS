"""RLS hardening, usage metering, audit log enrichment.

Enables row-level security on all tenant-scoped tables when running on
PostgreSQL. Adds usage_meters for billing-grade metering and extends
audit_logs with structured detail payloads.

Revision ID: 0002_rls_metering_audit
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_rls_metering_audit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Tables that carry tenant_id and must be isolated at the DB layer.
_TENANT_TABLES = (
    "memories",
    "memory_embeddings",
    "memory_versions",
    "memory_provenance",
    "memory_conflicts",
    "sessions",
    "session_events",
    "api_keys",
    "audit_logs",
    "webhooks",
    "webhook_deliveries",
    "analytics_events",
    "graph_nodes",
    "graph_edges",
    "agents",
    "usage_meters",
)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    from sqlalchemy import inspect

    insp = inspect(bind)
    audit_cols = {c["name"] for c in insp.get_columns("audit_logs")}

    # Extend audit_logs with structured detail (portable JSON).
    if "details" not in audit_cols:
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(sa.Column("details", sa.JSON(), nullable=True, server_default="{}"))

    if "usage_meters" not in insp.get_table_names():
        op.create_table(
            "usage_meters",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("metric", sa.String(60), nullable=False, index=True),
            sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=True, server_default="{}"),
            sa.UniqueConstraint("tenant_id", "metric", "window_start", name="uq_usage_meter_window"),
        )

    if not is_pg:
        return

    # Session variable used by RLS policies: SET app.current_tenant = '<uuid>';
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_select ON {table}
                FOR SELECT
                USING (tenant_id = current_setting('app.current_tenant', true))
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_insert ON {table}
                FOR INSERT
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true))
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_update ON {table}
                FOR UPDATE
                USING (tenant_id = current_setting('app.current_tenant', true))
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true))
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_delete ON {table}
                FOR DELETE
                USING (tenant_id = current_setting('app.current_tenant', true))
            """
        )

    # Bypass role for migrations / superuser operations.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'memoryos_bypass') THEN
                CREATE ROLE memoryos_bypass BYPASSRLS;
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        for table in _TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_insert ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_update ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_delete ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("usage_meters")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("details")
