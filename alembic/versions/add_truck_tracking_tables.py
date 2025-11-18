"""Add truck tracking tables

Revision ID: 2a8f7e1b3c9d
Revises: cf3d5b32a1e3
Create Date: 2025-11-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a8f7e1b3c9d'
down_revision: Union[str, None] = 'cf3d5b32a1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create trucks table
    op.create_table('trucks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('truck_number', sa.String(), nullable=False),
        sa.Column('license_plate', sa.String(), nullable=True),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),  # active, inactive, maintenance
        sa.Column('vehicle_type', sa.String(), nullable=True),  # trash, recycling, green
        sa.Column('capacity_cubic_yards', sa.Float(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trucks_id'), 'trucks', ['id'], unique=False)
    op.create_index(op.f('ix_trucks_truck_number'), 'trucks', ['truck_number'], unique=True)
    op.create_index(op.f('ix_trucks_city_id'), 'trucks', ['city_id'], unique=False)
    op.create_index(op.f('ix_trucks_status'), 'trucks', ['status'], unique=False)

    # Create truck_locations table for GPS trails
    op.create_table('truck_locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('truck_id', sa.Integer(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('speed_mph', sa.Float(), nullable=True),
        sa.Column('heading_degrees', sa.Float(), nullable=True),
        sa.Column('altitude_meters', sa.Float(), nullable=True),
        sa.Column('accuracy_meters', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['truck_id'], ['trucks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_truck_locations_id'), 'truck_locations', ['id'], unique=False)
    op.create_index(op.f('ix_truck_locations_truck_id'), 'truck_locations', ['truck_id'], unique=False)
    op.create_index(op.f('ix_truck_locations_timestamp'), 'truck_locations', ['timestamp'], unique=False)
    op.create_index('idx_truck_locations_truck_timestamp', 'truck_locations', ['truck_id', 'timestamp'], unique=False)

    # Create truck_routes table for daily route planning
    op.create_table('truck_routes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('truck_id', sa.Integer(), nullable=False),
        sa.Column('pickup_zone_id', sa.Integer(), nullable=True),
        sa.Column('route_date', sa.Date(), nullable=False),
        sa.Column('route_type', sa.String(), nullable=True),  # trash, recycling, green
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=True),  # planned, in_progress, completed, cancelled
        sa.Column('total_stops', sa.Integer(), nullable=True),
        sa.Column('completed_stops', sa.Integer(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['truck_id'], ['trucks.id'], ),
        sa.ForeignKeyConstraint(['pickup_zone_id'], ['pickup_zones.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_truck_routes_id'), 'truck_routes', ['id'], unique=False)
    op.create_index(op.f('ix_truck_routes_truck_id'), 'truck_routes', ['truck_id'], unique=False)
    op.create_index(op.f('ix_truck_routes_route_date'), 'truck_routes', ['route_date'], unique=False)
    op.create_index('idx_truck_routes_truck_date', 'truck_routes', ['truck_id', 'route_date'], unique=False)


def downgrade() -> None:
    # Drop truck_routes table
    op.drop_index('idx_truck_routes_truck_date', table_name='truck_routes')
    op.drop_index(op.f('ix_truck_routes_route_date'), table_name='truck_routes')
    op.drop_index(op.f('ix_truck_routes_truck_id'), table_name='truck_routes')
    op.drop_index(op.f('ix_truck_routes_id'), table_name='truck_routes')
    op.drop_table('truck_routes')

    # Drop truck_locations table
    op.drop_index('idx_truck_locations_truck_timestamp', table_name='truck_locations')
    op.drop_index(op.f('ix_truck_locations_timestamp'), table_name='truck_locations')
    op.drop_index(op.f('ix_truck_locations_truck_id'), table_name='truck_locations')
    op.drop_index(op.f('ix_truck_locations_id'), table_name='truck_locations')
    op.drop_table('truck_locations')

    # Drop trucks table
    op.drop_index(op.f('ix_trucks_status'), table_name='trucks')
    op.drop_index(op.f('ix_trucks_city_id'), table_name='trucks')
    op.drop_index(op.f('ix_trucks_truck_number'), table_name='trucks')
    op.drop_index(op.f('ix_trucks_id'), table_name='trucks')
    op.drop_table('trucks')
