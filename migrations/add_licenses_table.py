from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Enum as SQLEnum
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'licenses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('license_key', sa.String(), nullable=False),
        sa.Column('tier', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('max_meetings_per_month', sa.Integer(), nullable=False),
        sa.Column('max_file_size_mb', sa.Integer(), nullable=False),
        sa.Column('meetings_used_this_month', sa.Integer(), default=0),
        sa.Column('last_reset_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('gumroad_order_id', sa.String(), nullable=True),
        sa.Column('gumroad_product_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_licenses_license_key', 'licenses', ['license_key'], unique=True)

def downgrade():
    op.drop_index('ix_licenses_license_key', table_name='licenses')
    op.drop_table('licenses')