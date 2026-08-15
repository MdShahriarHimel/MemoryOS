"""v0.3 canonical memory fields, provenance lineage, benchmark runs.

Revision ID: 0003_v03_canonical_memory
Revises: 0002_rls_metering_audit
"""
from alembic import op
import sqlalchemy as sa

from app.db.migrate_util import column_exists, index_exists, table_exists

revision = "0003_v03_canonical_memory"
down_revision = "0002_rls_metering_audit"
branch_labels = None
depends_on = None

_TENANT_TABLES = ("benchmark_runs",)


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    from sqlalchemy import inspect as sa_inspect

    mem_cols = {c["name"] for c in sa_inspect(bind).get_columns("memories")}
    with op.batch_alter_table("memories") as batch:
        if "subject" not in mem_cols:
            batch.add_column(sa.Column("subject", sa.String(200), nullable=True))
        if "predicate" not in mem_cols:
            batch.add_column(sa.Column("predicate", sa.String(200), nullable=True))
        if "object_value" not in mem_cols:
            batch.add_column(sa.Column("object_value", sa.String(500), nullable=True))
        if "normalized_content" not in mem_cols:
            batch.add_column(sa.Column("normalized_content", sa.Text(), nullable=True))
        if "contradiction_status" not in mem_cols:
            batch.add_column(
                sa.Column("contradiction_status", sa.String(30), nullable=False, server_default="none")
            )
        if "decay_score" not in mem_cols:
            batch.add_column(
                sa.Column("decay_score", sa.Float(), nullable=False, server_default="1.0")
            )
        if "superseded_by_memory_id" not in mem_cols:
            batch.add_column(sa.Column("superseded_by_memory_id", sa.String(36), nullable=True))

    if not index_exists(bind, "ix_memory_subject_predicate"):
        op.create_index("ix_memory_subject_predicate", "memories", ["tenant_id", "subject", "predicate"])

    prov_cols = {c["name"] for c in sa_inspect(bind).get_columns("memory_provenance")}
    with op.batch_alter_table("memory_provenance") as batch:
        if "derived_from" not in prov_cols:
            batch.add_column(sa.Column("derived_from", sa.JSON(), nullable=True, server_default="[]"))
        if "supersedes_refs" not in prov_cols:
            batch.add_column(sa.Column("supersedes_refs", sa.JSON(), nullable=True, server_default="[]"))
        if "observed_at" not in prov_cols:
            batch.add_column(sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True))
        if "extracted_at" not in prov_cols:
            batch.add_column(sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True))
        if "extraction_confidence" not in prov_cols:
            batch.add_column(sa.Column("extraction_confidence", sa.Float(), nullable=True))

    if not table_exists(bind, "benchmark_runs"):
        op.create_table(
            "benchmark_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), nullable=False, index=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("config", sa.JSON(), nullable=True, server_default="{}"),
            sa.Column("results", sa.JSON(), nullable=True, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not is_pg:
        return

    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        for action in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{action.lower()} ON {table}")
            check = (
                "WITH CHECK (tenant_id = current_setting('app.current_tenant', true))"
                if action in ("INSERT", "UPDATE")
                else "USING (tenant_id = current_setting('app.current_tenant', true))"
            )
            op.execute(
                f"""
                CREATE POLICY tenant_isolation_{action.lower()} ON {table}
                    FOR {action}
                    {check}
                """
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        for table in _TENANT_TABLES:
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_delete ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_update ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_insert ON {table}")
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {table}")

    if table_exists(bind, "benchmark_runs"):
        op.drop_table("benchmark_runs")
    if index_exists(bind, "ix_memory_subject_predicate"):
        op.drop_index("ix_memory_subject_predicate", "memories")

    with op.batch_alter_table("memory_provenance") as batch:
        for col in (
            "extraction_confidence", "extracted_at", "observed_at",
            "supersedes_refs", "derived_from",
        ):
            if column_exists(bind, "memory_provenance", col):
                batch.drop_column(col)

    with op.batch_alter_table("memories") as batch:
        for col in (
            "superseded_by_memory_id", "decay_score", "contradiction_status",
            "normalized_content", "object_value", "predicate", "subject",
        ):
            if column_exists(bind, "memories", col):
                batch.drop_column(col)
