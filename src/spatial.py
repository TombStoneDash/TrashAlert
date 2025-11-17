"""
Spatial join utilities for TrashAlert.

This module provides functions for performing spatial operations like
point-in-polygon matching to assign addresses to subdivisions.
"""

from typing import List, Optional, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely import prepare


class SpatialJoiner:
    """
    Handles spatial join operations between points (addresses) and polygons (subdivisions).
    """

    def __init__(self, polygons: gpd.GeoDataFrame):
        """
        Initialize the spatial joiner with subdivision polygons.

        Args:
            polygons: GeoDataFrame containing polygon geometries with subdivision_id
        """
        self.polygons = polygons.copy()

        # Prepare geometries for faster spatial queries
        for idx in self.polygons.index:
            prepare(self.polygons.loc[idx, 'geometry'])

    def assign_points_to_polygons(
        self,
        points: gpd.GeoDataFrame,
        polygon_id_column: str = 'subdivision_id'
    ) -> gpd.GeoDataFrame:
        """
        Assign each point to the polygon it falls within.

        Args:
            points: GeoDataFrame containing point geometries
            polygon_id_column: Column name in polygons GeoDataFrame for the ID

        Returns:
            GeoDataFrame with points joined to their containing polygons
        """
        # Perform spatial join
        joined = gpd.sjoin(
            points,
            self.polygons[[polygon_id_column, 'geometry']],
            how='left',
            predicate='within'
        )

        return joined

    def get_polygon_for_point(
        self,
        lat: float,
        lon: float,
        polygon_id_column: str = 'subdivision_id'
    ) -> Optional[str]:
        """
        Find which polygon contains a given point.

        Args:
            lat: Latitude of the point
            lon: Longitude of the point
            polygon_id_column: Column name for the polygon ID

        Returns:
            Polygon ID if point is within a polygon, None otherwise
        """
        point = Point(lon, lat)

        for idx, row in self.polygons.iterrows():
            if row['geometry'].contains(point):
                return row[polygon_id_column]

        return None

    def count_points_per_polygon(
        self,
        points: gpd.GeoDataFrame,
        polygon_id_column: str = 'subdivision_id'
    ) -> pd.DataFrame:
        """
        Count how many points fall within each polygon.

        Args:
            points: GeoDataFrame containing point geometries
            polygon_id_column: Column name for the polygon ID

        Returns:
            DataFrame with polygon IDs and point counts
        """
        joined = self.assign_points_to_polygons(points, polygon_id_column)

        counts = joined[polygon_id_column].value_counts().reset_index()
        counts.columns = [polygon_id_column, 'point_count']

        return counts


def create_point_from_coords(lat: float, lon: float) -> Point:
    """
    Create a Shapely Point from latitude and longitude.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Shapely Point object (lon, lat order for geographic coordinates)
    """
    return Point(lon, lat)


def create_geodataframe_from_points(
    lats: List[float],
    lons: List[float],
    crs: str = "EPSG:4326"
) -> gpd.GeoDataFrame:
    """
    Create a GeoDataFrame from lists of latitude and longitude coordinates.

    Args:
        lats: List of latitudes
        lons: List of longitudes
        crs: Coordinate reference system (default: WGS84)

    Returns:
        GeoDataFrame with Point geometries
    """
    if len(lats) != len(lons):
        raise ValueError("lats and lons must have the same length")

    geometry = [Point(lon, lat) for lat, lon in zip(lats, lons)]

    gdf = gpd.GeoDataFrame(
        {'lat': lats, 'lon': lons},
        geometry=geometry,
        crs=crs
    )

    return gdf


def create_polygon_from_coords(coords: List[Tuple[float, float]]) -> Polygon:
    """
    Create a Shapely Polygon from a list of coordinate tuples.

    Args:
        coords: List of (lon, lat) tuples forming the polygon boundary

    Returns:
        Shapely Polygon object
    """
    if len(coords) < 3:
        raise ValueError("A polygon must have at least 3 vertices")

    return Polygon(coords)


def create_geodataframe_from_polygons(
    polygons: List[Polygon],
    polygon_ids: List[str],
    crs: str = "EPSG:4326"
) -> gpd.GeoDataFrame:
    """
    Create a GeoDataFrame from a list of Shapely Polygons.

    Args:
        polygons: List of Shapely Polygon objects
        polygon_ids: List of IDs for each polygon
        crs: Coordinate reference system (default: WGS84)

    Returns:
        GeoDataFrame with Polygon geometries
    """
    if len(polygons) != len(polygon_ids):
        raise ValueError("polygons and polygon_ids must have the same length")

    gdf = gpd.GeoDataFrame(
        {'subdivision_id': polygon_ids},
        geometry=polygons,
        crs=crs
    )

    return gdf
