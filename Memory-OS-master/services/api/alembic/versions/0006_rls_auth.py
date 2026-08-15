"""RLS on auth tables (users, organizations, refresh_sessions).

Revision ID: 0006_rls_auth
Revises: 0005_webhook_secret_enc
"""
from alembic import op

revision = "0006_rls_auth"
down_revision = "0005_webhook_secret_enc"
branch_labels = None
depends_on = None


def _enable_rls(table: str, using_expr: str, check_expr: str | None = None) -> None:
    check = check_expr or using_expr
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for suffix, cmd in (
        ("select", "FOR SELECT USING"),
        ("insert", "FOR INSERT WITH CHECK"),
        ("update", "FOR UPDATE USING"),
        ("delete", "FOR DELETE USING"),
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON {table}")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {table} FOR SELECT USING ({using_expr})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_insert ON {table} FOR INSERT WITH CHECK ({check})"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_update ON {table}
        FOR UPDATE USING ({using_expr}) WITH CHECK ({check})
        """
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_delete ON {table} FOR DELETE USING ({using_expr})"
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    tenant = "current_setting('app.current_tenant', true)"
    _enable_rls("organizations", f"id = {tenant}")
    _enable_rls("users", f"organization_id = {tenant}")
    _enable_rls("refresh_sessions", f"tenant_id = {tenant}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in ("refresh_sessions", "users", "organizations"):
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
