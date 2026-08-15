"""Revision 0004 — idempotency keys table + RLS."""
from alembic import op
import sqlalchemy as sa

revision = "0004_idempotency"
down_revision = "0003_v03_canonical_memory"
branch_labels = None
depends_on = None


from app.db.migrate_util import index_exists, table_exists


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if not table_exists(bind, "idempotency_keys"):
        op.create_table(
            "idempotency_keys",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False, index=True),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("path", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("response_body", sa.JSON(), nullable=True, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    from app.db.migrate_util import index_exists
    if not index_exists(bind, "ix_idempotency_tenant_key_path"):
        op.create_index(
            "ix_idempotency_tenant_key_path",
            "idempotency_keys",
            ["tenant_id", "idempotency_key", "method", "path"],
        )

    if not is_pg:
        return

    op.execute("ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE idempotency_keys FORCE ROW LEVEL SECURITY")
    for suffix, clause in (
        ("select", "FOR SELECT USING (tenant_id = current_setting('app.current_tenant', true))"),
        ("insert", "FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant', true))"),
        ("update", "FOR UPDATE USING (tenant_id = current_setting('app.current_tenant', true))"),
        ("delete", "FOR DELETE USING (tenant_id = current_setting('app.current_tenant', true))"),
    ):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{suffix} ON idempotency_keys")
        op.execute(f"CREATE POLICY tenant_isolation_{suffix} ON idempotency_keys {clause}")


def downgrade() -> None:
    op.drop_index("ix_idempotency_tenant_key_path", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
