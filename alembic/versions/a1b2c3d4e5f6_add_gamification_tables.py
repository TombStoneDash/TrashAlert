"""Add gamification tables

Revision ID: a1b2c3d4e5f6
Revises: cf3d5b32a1e3
Create Date: 2025-11-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'cf3d5b32a1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('total_points', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_reports', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('verified_reports', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('is_verified_reporter', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_total_points'), 'users', ['total_points'], unique=False)
    op.create_index(op.f('ix_users_is_verified_reporter'), 'users', ['is_verified_reporter'], unique=False)

    # Create badges table
    op.create_table('badges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(), nullable=True),
        sa.Column('requirement_type', sa.String(), nullable=False),
        sa.Column('requirement_value', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('tier', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_badges_id'), 'badges', ['id'], unique=False)
    op.create_index(op.f('ix_badges_slug'), 'badges', ['slug'], unique=True)

    # Create user_badges table
    op.create_table('user_badges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('badge_id', sa.Integer(), nullable=False),
        sa.Column('earned_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['badge_id'], ['badges.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_badges_id'), 'user_badges', ['id'], unique=False)
    op.create_index(op.f('ix_user_badges_user_id'), 'user_badges', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_badges_badge_id'), 'user_badges', ['badge_id'], unique=False)
    op.create_index(op.f('ix_user_badges_earned_at'), 'user_badges', ['earned_at'], unique=False)
    op.create_index('idx_user_badge_unique', 'user_badges', ['user_id', 'badge_id'], unique=True)

    # Create point_history table
    op.create_table('point_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['report_id'], ['crowd_reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_point_history_id'), 'point_history', ['id'], unique=False)
    op.create_index(op.f('ix_point_history_user_id'), 'point_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_point_history_report_id'), 'point_history', ['report_id'], unique=False)
    op.create_index(op.f('ix_point_history_created_at'), 'point_history', ['created_at'], unique=False)
    op.create_index('idx_user_created', 'point_history', ['user_id', 'created_at'], unique=False)

    # Add user_id and is_verified columns to crowd_reports table
    op.add_column('crowd_reports', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('crowd_reports', sa.Column('is_verified', sa.Boolean(), nullable=True, server_default='0'))
    op.create_foreign_key('fk_crowd_reports_user_id', 'crowd_reports', 'users', ['user_id'], ['id'])
    op.create_index(op.f('ix_crowd_reports_user_id'), 'crowd_reports', ['user_id'], unique=False)
    op.create_index(op.f('ix_crowd_reports_is_verified'), 'crowd_reports', ['is_verified'], unique=False)


def downgrade() -> None:
    # Remove columns from crowd_reports
    op.drop_index(op.f('ix_crowd_reports_is_verified'), table_name='crowd_reports')
    op.drop_index(op.f('ix_crowd_reports_user_id'), table_name='crowd_reports')
    op.drop_constraint('fk_crowd_reports_user_id', 'crowd_reports', type_='foreignkey')
    op.drop_column('crowd_reports', 'is_verified')
    op.drop_column('crowd_reports', 'user_id')

    # Drop point_history table
    op.drop_index('idx_user_created', table_name='point_history')
    op.drop_index(op.f('ix_point_history_created_at'), table_name='point_history')
    op.drop_index(op.f('ix_point_history_report_id'), table_name='point_history')
    op.drop_index(op.f('ix_point_history_user_id'), table_name='point_history')
    op.drop_index(op.f('ix_point_history_id'), table_name='point_history')
    op.drop_table('point_history')

    # Drop user_badges table
    op.drop_index('idx_user_badge_unique', table_name='user_badges')
    op.drop_index(op.f('ix_user_badges_earned_at'), table_name='user_badges')
    op.drop_index(op.f('ix_user_badges_badge_id'), table_name='user_badges')
    op.drop_index(op.f('ix_user_badges_user_id'), table_name='user_badges')
    op.drop_index(op.f('ix_user_badges_id'), table_name='user_badges')
    op.drop_table('user_badges')

    # Drop badges table
    op.drop_index(op.f('ix_badges_slug'), table_name='badges')
    op.drop_index(op.f('ix_badges_id'), table_name='badges')
    op.drop_table('badges')

    # Drop users table
    op.drop_index(op.f('ix_users_is_verified_reporter'), table_name='users')
    op.drop_index(op.f('ix_users_total_points'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
