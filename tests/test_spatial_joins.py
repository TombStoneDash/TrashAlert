"""
Tests for spatial join functionality.

Tests ensure that point-in-polygon assignment works correctly
for assigning addresses to subdivisions.
"""

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from src.spatial import (
    SpatialJoiner,
    create_point_from_coords,
    create_geodataframe_from_points,
    create_polygon_from_coords,
    create_geodataframe_from_polygons,
)


@pytest.fixture
def sample_polygons():
    """
    Create sample subdivision polygons for testing.

    Creates three polygons representing different subdivisions:
    - subdivision_a: Square from (0,0) to (10,10)
    - subdivision_b: Square from (10,0) to (20,10)
    - subdivision_c: Square from (0,10) to (10,20)
    """
    polygons = [
        Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),  # subdivision_a
        Polygon([(10, 0), (20, 0), (20, 10), (10, 10), (10, 0)]),  # subdivision_b
        Polygon([(0, 10), (10, 10), (10, 20), (0, 20), (0, 10)]),  # subdivision_c
    ]

    polygon_ids = ['subdivision_a', 'subdivision_b', 'subdivision_c']

    return create_geodataframe_from_polygons(polygons, polygon_ids)


@pytest.fixture
def sample_points():
    """
    Create sample address points for testing.

    Creates points that fall within and outside the sample polygons:
    - Point at (lon=5, lat=5) - in subdivision_a
    - Point at (lon=15, lat=5) - in subdivision_b
    - Point at (lon=5, lat=15) - in subdivision_c
    - Point at (lon=5, lat=5) - duplicate in subdivision_a
    - Point at (lon=25, lat=25) - outside all polygons
    """
    lats = [5, 5, 15, 5, 25]
    lons = [5, 15, 5, 5, 25]

    return create_geodataframe_from_points(lats, lons)


class TestCreatePointFromCoords:
    """Test creating Point objects from coordinates."""

    def test_create_point_basic(self):
        """Test basic point creation."""
        point = create_point_from_coords(37.7749, -122.4194)
        assert isinstance(point, Point)
        assert point.y == 37.7749  # latitude is y
        assert point.x == -122.4194  # longitude is x

    def test_create_point_zero_coords(self):
        """Test point at origin."""
        point = create_point_from_coords(0.0, 0.0)
        assert point.x == 0.0
        assert point.y == 0.0


class TestCreateGeoDataFrameFromPoints:
    """Test creating GeoDataFrame from point coordinates."""

    def test_create_gdf_single_point(self):
        """Test creating GeoDataFrame with a single point."""
        lats = [37.7749]
        lons = [-122.4194]

        gdf = create_geodataframe_from_points(lats, lons)

        assert len(gdf) == 1
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert gdf.crs.to_string() == "EPSG:4326"

    def test_create_gdf_multiple_points(self):
        """Test creating GeoDataFrame with multiple points."""
        lats = [37.7749, 34.0522, 40.7128]
        lons = [-122.4194, -118.2437, -74.0060]

        gdf = create_geodataframe_from_points(lats, lons)

        assert len(gdf) == 3
        assert 'lat' in gdf.columns
        assert 'lon' in gdf.columns

    def test_create_gdf_mismatched_lengths(self):
        """Test that mismatched coordinate lists raise an error."""
        lats = [37.7749, 34.0522]
        lons = [-122.4194]

        with pytest.raises(ValueError, match="must have the same length"):
            create_geodataframe_from_points(lats, lons)


class TestCreatePolygonFromCoords:
    """Test creating Polygon objects from coordinates."""

    def test_create_polygon_basic(self):
        """Test basic polygon creation."""
        coords = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        polygon = create_polygon_from_coords(coords)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid

    def test_create_polygon_too_few_vertices(self):
        """Test that polygons with too few vertices raise an error."""
        coords = [(0, 0), (10, 0)]

        with pytest.raises(ValueError, match="at least 3 vertices"):
            create_polygon_from_coords(coords)

    def test_create_polygon_triangle(self):
        """Test creating a triangular polygon."""
        coords = [(0, 0), (10, 0), (5, 10), (0, 0)]
        polygon = create_polygon_from_coords(coords)

        assert polygon.is_valid
        assert polygon.area > 0


class TestCreateGeoDataFrameFromPolygons:
    """Test creating GeoDataFrame from polygons."""

    def test_create_gdf_single_polygon(self):
        """Test creating GeoDataFrame with a single polygon."""
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        polygons = [polygon]
        ids = ['subdivision_a']

        gdf = create_geodataframe_from_polygons(polygons, ids)

        assert len(gdf) == 1
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert 'subdivision_id' in gdf.columns

    def test_create_gdf_multiple_polygons(self):
        """Test creating GeoDataFrame with multiple polygons."""
        polygons = [
            Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
            Polygon([(10, 0), (20, 0), (20, 10), (10, 10), (10, 0)]),
        ]
        ids = ['subdivision_a', 'subdivision_b']

        gdf = create_geodataframe_from_polygons(polygons, ids)

        assert len(gdf) == 2

    def test_create_gdf_mismatched_lengths(self):
        """Test that mismatched lists raise an error."""
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        polygons = [polygon]
        ids = ['subdivision_a', 'subdivision_b']

        with pytest.raises(ValueError, match="must have the same length"):
            create_geodataframe_from_polygons(polygons, ids)


class TestSpatialJoinerPointInPolygon:
    """Test point-in-polygon assignment."""

    def test_point_in_polygon_basic(self, sample_polygons, sample_points):
        """Test that points are correctly assigned to polygons."""
        joiner = SpatialJoiner(sample_polygons)
        joined = joiner.assign_points_to_polygons(sample_points)

        # Check that we have assignments
        assert 'subdivision_id' in joined.columns

        # First point: lat=5, lon=5 should be in subdivision_a
        # Note: Due to potential indexing differences, we check by geometry
        point_5_5 = joined[
            (joined['lat'] == 5) & (joined['lon'] == 5)
        ]['subdivision_id'].iloc[0]
        assert point_5_5 == 'subdivision_a'

        # Second point: lat=5, lon=15 should be in subdivision_b
        point_5_15_b = joined[
            (joined['lat'] == 5) & (joined['lon'] == 15)
        ]['subdivision_id'].iloc[0]
        assert point_5_15_b == 'subdivision_b'

        # Third point: lat=15, lon=5 should be in subdivision_c
        point_15_5 = joined[
            (joined['lat'] == 15) & (joined['lon'] == 5)
        ]['subdivision_id'].iloc[0]
        assert point_15_5 == 'subdivision_c'

    def test_duplicate_points_same_subdivision(self, sample_polygons):
        """Test that duplicate points in the same polygon get same subdivision_id."""
        # Create two identical points at (5, 5), both in subdivision_a
        lats = [5, 5]
        lons = [5, 5]
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(sample_polygons)
        joined = joiner.assign_points_to_polygons(points)

        # Both points should have the same subdivision_id
        subdivision_ids = joined['subdivision_id'].unique()
        assert len(subdivision_ids) == 1
        assert subdivision_ids[0] == 'subdivision_a'

    def test_point_outside_all_polygons(self, sample_polygons):
        """Test that points outside all polygons have null subdivision_id."""
        # Point at (25, 25) is outside all polygons
        lats = [25]
        lons = [25]
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(sample_polygons)
        joined = joiner.assign_points_to_polygons(points)

        # Should have null subdivision_id
        assert pd.isna(joined['subdivision_id'].iloc[0])

    def test_get_polygon_for_single_point(self, sample_polygons):
        """Test getting polygon for a single point."""
        joiner = SpatialJoiner(sample_polygons)

        # Point (lon=5, lat=5) should be in subdivision_a
        result = joiner.get_polygon_for_point(lat=5, lon=5)
        assert result == 'subdivision_a'

        # Point (lon=15, lat=5) should be in subdivision_b
        result = joiner.get_polygon_for_point(lat=5, lon=15)
        assert result == 'subdivision_b'

        # Point outside should return None
        result = joiner.get_polygon_for_point(lat=25, lon=25)
        assert result is None


class TestSpatialJoinerCounting:
    """Test counting points per polygon."""

    def test_count_points_per_polygon(self, sample_polygons, sample_points):
        """Test counting how many points fall in each polygon."""
        joiner = SpatialJoiner(sample_polygons)
        counts = joiner.count_points_per_polygon(sample_points)

        # Should have counts for each subdivision
        assert 'subdivision_id' in counts.columns
        assert 'point_count' in counts.columns

        # subdivision_a should have 2 points (two at 5,5)
        sub_a_count = counts[
            counts['subdivision_id'] == 'subdivision_a'
        ]['point_count'].iloc[0]
        assert sub_a_count == 2

    def test_count_with_no_points(self, sample_polygons):
        """Test counting when there are no points."""
        # Create empty points GeoDataFrame
        lats = []
        lons = []
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(sample_polygons)
        counts = joiner.count_points_per_polygon(points)

        # Should return empty DataFrame
        assert len(counts) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_point_on_polygon_boundary(self):
        """Test points exactly on polygon boundaries."""
        # Create a simple square polygon
        polygon = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
        polygons = create_geodataframe_from_polygons([polygon], ['subdivision_a'])

        # Point exactly on the boundary (edge at x=10)
        lats = [5]
        lons = [10]
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(polygons)
        joined = joiner.assign_points_to_polygons(points)

        # Behavior may vary; just ensure no crash
        assert joined is not None

    def test_many_points_in_single_polygon(self):
        """Test assigning many points to a single polygon."""
        polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
        polygons = create_geodataframe_from_polygons([polygon], ['subdivision_a'])

        # Create 99 points within the polygon (avoiding boundary at 100)
        lats = [i for i in range(1, 100)]
        lons = [i for i in range(1, 100)]
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(polygons)
        joined = joiner.assign_points_to_polygons(points)

        # All points should be in subdivision_a
        assert (joined['subdivision_id'] == 'subdivision_a').all()

    def test_overlapping_polygons(self):
        """Test behavior with overlapping polygons."""
        # Create two overlapping polygons
        polygons = [
            Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
            Polygon([(5, 5), (15, 5), (15, 15), (5, 15), (5, 5)]),
        ]
        ids = ['subdivision_a', 'subdivision_b']
        polygon_gdf = create_geodataframe_from_polygons(polygons, ids)

        # Point in overlap region (7, 7)
        lats = [7]
        lons = [7]
        points = create_geodataframe_from_points(lats, lons)

        joiner = SpatialJoiner(polygon_gdf)
        joined = joiner.assign_points_to_polygons(points)

        # Should be assigned to one of the polygons (behavior may vary)
        assert joined['subdivision_id'].iloc[0] in ['subdivision_a', 'subdivision_b']
