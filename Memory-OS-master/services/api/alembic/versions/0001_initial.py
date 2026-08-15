"""initial schema + pgvector

Creates all core tables and, on PostgreSQL, the pgvector extension plus the
vector column and an ivfflat cosine index on memory_embeddings.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # The full table set is created from SQLAlchemy metadata via create_all in
    # dev; in production this migration is the source of truth. For brevity the
    # ORM metadata drives table DDL here:
    from app.db.session import Base
    from app import models  # noqa: F401
    Base.metadata.create_all(bind)

    if is_pg:
        # Replace the JSON embedding column with a native vector type + index.
        op.execute(f"ALTER TABLE memory_embeddings ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM}) USING NULL")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_memory_embeddings_vec "
            "ON memory_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )


def downgrade() -> None:
    from app.db.session import Base
    Base.metadata.drop_all(op.get_bind())
