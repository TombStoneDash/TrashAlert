"""Add notification system

Revision ID: a7b4c8d9e2f1
Revises: cf3d5b32a1e3
Create Date: 2025-11-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b4c8d9e2f1'
down_revision: Union[str, None] = 'cf3d5b32a1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('display_name', sa.String(), nullable=True),
    sa.Column('timezone', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)

    # Create address_subscriptions table
    op.create_table('address_subscriptions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('address_id', sa.Integer(), nullable=False),
    sa.Column('notify_trash', sa.Boolean(), nullable=True),
    sa.Column('notify_recycling', sa.Boolean(), nullable=True),
    sa.Column('notify_green', sa.Boolean(), nullable=True),
    sa.Column('notify_email', sa.Boolean(), nullable=True),
    sa.Column('notify_sms', sa.Boolean(), nullable=True),
    sa.Column('days_before', sa.Integer(), nullable=True),
    sa.Column('notification_time', sa.String(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['address_id'], ['addresses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_address_subscriptions_id'), 'address_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_address_subscriptions_user_id'), 'address_subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_address_subscriptions_address_id'), 'address_subscriptions', ['address_id'], unique=False)
    op.create_index(op.f('ix_address_subscriptions_is_active'), 'address_subscriptions', ['is_active'], unique=False)
    op.create_index('idx_user_address', 'address_subscriptions', ['user_id', 'address_id'], unique=False)
    op.create_index('idx_active_subscriptions', 'address_subscriptions', ['is_active', 'user_id'], unique=False)

    # Create notification_logs table
    op.create_table('notification_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('subscription_id', sa.Integer(), nullable=True),
    sa.Column('notification_type', sa.String(), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('recipient', sa.String(), nullable=False),
    sa.Column('subject', sa.String(), nullable=True),
    sa.Column('message_body', sa.Text(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('external_id', sa.String(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['subscription_id'], ['address_subscriptions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_logs_id'), 'notification_logs', ['id'], unique=False)
    op.create_index(op.f('ix_notification_logs_user_id'), 'notification_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_logs_subscription_id'), 'notification_logs', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_notification_logs_notification_type'), 'notification_logs', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notification_logs_channel'), 'notification_logs', ['channel'], unique=False)
    op.create_index(op.f('ix_notification_logs_status'), 'notification_logs', ['status'], unique=False)
    op.create_index(op.f('ix_notification_logs_scheduled_for'), 'notification_logs', ['scheduled_for'], unique=False)
    op.create_index(op.f('ix_notification_logs_created_at'), 'notification_logs', ['created_at'], unique=False)
    op.create_index('idx_notification_status_scheduled', 'notification_logs', ['status', 'scheduled_for'], unique=False)
    op.create_index('idx_user_created', 'notification_logs', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop notification_logs table and indexes
    op.drop_index('idx_user_created', table_name='notification_logs')
    op.drop_index('idx_notification_status_scheduled', table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_created_at'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_scheduled_for'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_status'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_channel'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_notification_type'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_subscription_id'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_user_id'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_id'), table_name='notification_logs')
    op.drop_table('notification_logs')

    # Drop address_subscriptions table and indexes
    op.drop_index('idx_active_subscriptions', table_name='address_subscriptions')
    op.drop_index('idx_user_address', table_name='address_subscriptions')
    op.drop_index(op.f('ix_address_subscriptions_is_active'), table_name='address_subscriptions')
    op.drop_index(op.f('ix_address_subscriptions_address_id'), table_name='address_subscriptions')
    op.drop_index(op.f('ix_address_subscriptions_user_id'), table_name='address_subscriptions')
    op.drop_index(op.f('ix_address_subscriptions_id'), table_name='address_subscriptions')
    op.drop_table('address_subscriptions')

    # Drop users table and indexes
    op.drop_index(op.f('ix_users_is_active'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
