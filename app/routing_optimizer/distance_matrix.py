"""Distance matrix calculation for routing optimization.

This module calculates distance matrices between geographic coordinates
using geodesic (great-circle) distances.
"""

from typing import List, Tuple
from geopy.distance import geodesic
import numpy as np


class DistanceMatrixCalculator:
    """Calculate distance matrices for routing optimization."""

    @staticmethod
    def calculate_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        Calculate geodesic distance between two coordinates.

        Args:
            coord1: Tuple of (lat, lon) for first point
            coord2: Tuple of (lat, lon) for second point

        Returns:
            Distance in meters
        """
        return geodesic(coord1, coord2).meters

    @staticmethod
    def calculate_distance_km(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        Calculate geodesic distance between two coordinates in kilometers.

        Args:
            coord1: Tuple of (lat, lon) for first point
            coord2: Tuple of (lat, lon) for second point

        Returns:
            Distance in kilometers
        """
        return geodesic(coord1, coord2).kilometers

    def create_distance_matrix(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        Create a distance matrix from a list of coordinates.

        The matrix is symmetric with zeros on the diagonal.
        Distances are in meters (suitable for OR-Tools).

        Args:
            coordinates: List of (lat, lon) tuples

        Returns:
            2D numpy array where matrix[i][j] is the distance from point i to point j in meters
        """
        n = len(coordinates)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):  # Only calculate upper triangle
                dist = self.calculate_distance(coordinates[i], coordinates[j])
                matrix[i][j] = dist
                matrix[j][i] = dist  # Symmetric

        return matrix

    def create_distance_matrix_int(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> List[List[int]]:
        """
        Create a distance matrix with integer distances (for OR-Tools).

        OR-Tools requires integer distance matrices. This method rounds
        distances to the nearest meter.

        Args:
            coordinates: List of (lat, lon) tuples

        Returns:
            2D list where matrix[i][j] is the distance from point i to point j in meters (int)
        """
        n = len(coordinates)
        matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                dist = int(round(self.calculate_distance(coordinates[i], coordinates[j])))
                matrix[i][j] = dist
                matrix[j][i] = dist  # Symmetric

        return matrix

    def calculate_route_distance(
        self,
        coordinates: List[Tuple[float, float]],
        route_order: List[int]
    ) -> float:
        """
        Calculate total distance for a given route order.

        Args:
            coordinates: List of all (lat, lon) tuples
            route_order: List of indices representing the route order

        Returns:
            Total distance in kilometers
        """
        total_distance = 0.0

        for i in range(len(route_order) - 1):
            idx1 = route_order[i]
            idx2 = route_order[i + 1]
            total_distance += self.calculate_distance_km(
                coordinates[idx1],
                coordinates[idx2]
            )

        return total_distance

    def calculate_naive_route_distance(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> float:
        """
        Calculate distance for a naive route (original order, returning to start).

        Args:
            coordinates: List of (lat, lon) tuples in original order

        Returns:
            Total distance in kilometers
        """
        if len(coordinates) < 2:
            return 0.0

        total_distance = 0.0

        # Calculate path through all points in order
        for i in range(len(coordinates) - 1):
            total_distance += self.calculate_distance_km(coordinates[i], coordinates[i + 1])

        # Add return to start
        total_distance += self.calculate_distance_km(coordinates[-1], coordinates[0])

        return total_distance
