"""RLS + tenant_quotas table.

Revision ID: 0007_tenant_quotas
Revises: 0006_rls_auth
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_tenant_quotas"
down_revision = "0006_rls_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.migrate_util import table_exists

    bind = op.get_bind()
    if not table_exists(bind, "tenant_quotas"):
        op.create_table(
            "tenant_quotas",
            sa.Column("tenant_id", sa.String(36), primary_key=True),
            sa.Column("limits", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE tenant_quotas ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_quotas FORCE ROW LEVEL SECURITY")
    tenant = "current_setting('app.current_tenant', true)"
    for suffix, clause in (
        ("select", f"FOR SELECT USING (tenant_id = {tenant})"),
        ("insert", f"FOR INSERT WITH CHECK (tenant_id = {tenant})"),
        ("update", f"FOR UPDATE USING (tenant_id = {tenant}) WITH CHECK (tenant_id = {tenant})"),
        ("delete", f"FOR DELETE USING (tenant_id = {tenant})"),
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON tenant_quotas")
        op.execute(f"CREATE POLICY tenant_isolation_{suffix} ON tenant_quotas {clause}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for suffix in ("select", "insert", "update", "delete"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON tenant_quotas")
    op.drop_table("tenant_quotas")
