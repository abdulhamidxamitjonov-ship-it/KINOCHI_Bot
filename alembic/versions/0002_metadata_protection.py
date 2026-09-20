from alembic import op
import sqlalchemy as sa
revision="0002_metadata_protection"; down_revision="0001_initial"; branch_labels=None; depends_on=None

def upgrade():
    op.add_column("movies", sa.Column("metadata_text", sa.Text))
    op.add_column("movies", sa.Column("metadata_entities", sa.JSON))
    op.add_column("series", sa.Column("metadata_text", sa.Text))
    op.add_column("series", sa.Column("metadata_entities", sa.JSON))

def downgrade():
    op.drop_column("series","metadata_entities"); op.drop_column("series","metadata_text")
    op.drop_column("movies","metadata_entities"); op.drop_column("movies","metadata_text")
