"""Add prediction models and cache tables

Revision ID: add_prediction_models
Revises: cf3d5b32a1e3
Create Date: 2025-11-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_prediction_models'
down_revision = 'cf3d5b32a1e3'
branch_labels = None
depends_on = None


def upgrade():
    """Create prediction_models and prediction_cache tables."""
    # Create prediction_models table
    op.create_table(
        'prediction_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_type', sa.String(), nullable=False),
        sa.Column('version', sa.String(), nullable=False),
        sa.Column('model_data', sa.Text(), nullable=False),
        sa.Column('training_samples', sa.Integer(), default=0),
        sa.Column('training_accuracy', sa.Float()),
        sa.Column('training_features', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prediction_models_id', 'prediction_models', ['id'])
    op.create_index('ix_prediction_models_model_type', 'prediction_models', ['model_type'])
    op.create_index('ix_prediction_models_is_active', 'prediction_models', ['is_active'])
    op.create_index('idx_model_type_active', 'prediction_models', ['model_type', 'is_active'])

    # Create prediction_cache table
    op.create_table(
        'prediction_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('address_id', sa.Integer(), nullable=False),
        sa.Column('prediction_type', sa.String(), nullable=False),
        sa.Column('prediction_result', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float()),
        sa.Column('model_version', sa.String()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['address_id'], ['addresses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_prediction_cache_id', 'prediction_cache', ['id'])
    op.create_index('ix_prediction_cache_address_id', 'prediction_cache', ['address_id'])
    op.create_index('ix_prediction_cache_prediction_type', 'prediction_cache', ['prediction_type'])
    op.create_index('ix_prediction_cache_expires_at', 'prediction_cache', ['expires_at'])
    op.create_index('idx_prediction_cache_lookup', 'prediction_cache', ['address_id', 'prediction_type', 'expires_at'])


def downgrade():
    """Drop prediction_models and prediction_cache tables."""
    op.drop_index('idx_prediction_cache_lookup', table_name='prediction_cache')
    op.drop_index('ix_prediction_cache_expires_at', table_name='prediction_cache')
    op.drop_index('ix_prediction_cache_prediction_type', table_name='prediction_cache')
    op.drop_index('ix_prediction_cache_address_id', table_name='prediction_cache')
    op.drop_index('ix_prediction_cache_id', table_name='prediction_cache')
    op.drop_table('prediction_cache')

    op.drop_index('idx_model_type_active', table_name='prediction_models')
    op.drop_index('ix_prediction_models_is_active', table_name='prediction_models')
    op.drop_index('ix_prediction_models_model_type', table_name='prediction_models')
    op.drop_index('ix_prediction_models_id', table_name='prediction_models')
    op.drop_table('prediction_models')
