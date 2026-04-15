"""Add collection_zones table with PostGIS support

Revision ID: b3c7d9e1f4a2
Revises: a1b2c3d4e5f6
Create Date: 2026-04-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c7d9e1f4a2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension (safe to call if already enabled)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Create collection_zones table
    op.create_table('collection_zones',
        sa.Column('zone_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('zone_name', sa.String(length=200), nullable=False),
        sa.Column('collection_day', sa.String(length=20), nullable=True),
        sa.Column('estimated_addresses', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('zone_id'),
    )

    # Add PostGIS geometry column for the polygon boundary
    op.execute("""
        ALTER TABLE collection_zones
        ADD COLUMN geom geometry(Polygon, 4326)
    """)

    # Create spatial index on the geometry column
    op.execute("""
        CREATE INDEX idx_collection_zones_geom
        ON collection_zones USING GIST (geom)
    """)

    # Index on city for fast filtering
    op.create_index('idx_collection_zones_city', 'collection_zones', ['city'])

    # Create an RPC function for point-in-zone lookup via PostGIS ST_Contains
    op.execute("""
        CREATE OR REPLACE FUNCTION lookup_zone(p_lat double precision, p_lng double precision)
        RETURNS TABLE(
            zone_id integer,
            city varchar,
            zone_name varchar,
            collection_day varchar,
            estimated_addresses integer,
            source_url text
        )
        LANGUAGE sql STABLE
        AS $$
            SELECT
                cz.zone_id,
                cz.city,
                cz.zone_name,
                cz.collection_day,
                cz.estimated_addresses,
                cz.source_url
            FROM collection_zones cz
            WHERE ST_Contains(cz.geom, ST_SetSRID(ST_Point(p_lng, p_lat), 4326))
        $$;
    """)

    # Create a function to get total estimated addresses from zones
    op.execute("""
        CREATE OR REPLACE FUNCTION zone_coverage_stats()
        RETURNS TABLE(
            total_zones bigint,
            total_estimated_addresses bigint,
            cities_with_zones bigint
        )
        LANGUAGE sql STABLE
        AS $$
            SELECT
                COUNT(*)::bigint AS total_zones,
                COALESCE(SUM(estimated_addresses), 0)::bigint AS total_estimated_addresses,
                COUNT(DISTINCT city)::bigint AS cities_with_zones
            FROM collection_zones
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS zone_coverage_stats()")
    op.execute("DROP FUNCTION IF EXISTS lookup_zone(double precision, double precision)")
    op.drop_index('idx_collection_zones_city', table_name='collection_zones')
    op.drop_table('collection_zones')
