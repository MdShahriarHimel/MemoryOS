"""Webhook secret encryption at rest."""
from alembic import op
import sqlalchemy as sa

revision = "0005_webhook_secret_enc"
down_revision = "0004_idempotency"
branch_labels = None
depends_on = None


from app.db.migrate_util import column_exists


def upgrade() -> None:
    bind = op.get_bind()
    if not column_exists(bind, "webhooks", "secret_enc"):
        with op.batch_alter_table("webhooks") as batch:
            batch.add_column(sa.Column("secret_enc", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("webhooks") as batch:
        batch.drop_column("secret_enc")
