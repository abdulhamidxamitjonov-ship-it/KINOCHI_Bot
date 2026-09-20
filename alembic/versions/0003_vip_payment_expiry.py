from alembic import op
import sqlalchemy as sa

revision = '0003_vip_payment_expiry'
down_revision = '0002_metadata_protection'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('vip_payments', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column('vip_payments', 'expires_at')
