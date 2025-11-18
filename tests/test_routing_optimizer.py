"""Unit tests for routing optimizer module."""

import pytest
from app.routing_optimizer import RouteOptimizer
from app.routing_optimizer.distance_matrix import DistanceMatrixCalculator
from app.routing_optimizer.schemas import RouteStop


class TestDistanceMatrixCalculator:
    """Test DistanceMatrixCalculator class."""

    def test_calculate_distance(self):
        """Test distance calculation between two points."""
        calc = DistanceMatrixCalculator()

        # San Diego (32.7157, -117.1611) to Los Angeles (34.0522, -118.2437)
        # Approximately 180 km
        san_diego = (32.7157, -117.1611)
        los_angeles = (34.0522, -118.2437)

        distance_m = calc.calculate_distance(san_diego, los_angeles)
        distance_km = calc.calculate_distance_km(san_diego, los_angeles)

        # Distance should be approximately 180 km
        assert 170000 < distance_m < 190000
        assert 170 < distance_km < 190

    def test_distance_matrix_symmetry(self):
        """Test that distance matrix is symmetric."""
        calc = DistanceMatrixCalculator()

        coords = [
            (32.7157, -117.1611),  # San Diego
            (34.0522, -118.2437),  # Los Angeles
            (37.7749, -122.4194)   # San Francisco
        ]

        matrix = calc.create_distance_matrix(coords)

        # Check symmetry
        assert matrix[0][1] == matrix[1][0]
        assert matrix[0][2] == matrix[2][0]
        assert matrix[1][2] == matrix[2][1]

        # Check diagonal is zero
        assert matrix[0][0] == 0
        assert matrix[1][1] == 0
        assert matrix[2][2] == 0

    def test_distance_matrix_int(self):
        """Test integer distance matrix creation."""
        calc = DistanceMatrixCalculator()

        coords = [
            (32.7157, -117.1611),
            (32.7257, -117.1711),
            (32.7357, -117.1811)
        ]

        matrix = calc.create_distance_matrix_int(coords)

        # Check that all values are integers
        for row in matrix:
            for val in row:
                assert isinstance(val, int)

        # Check symmetry
        assert matrix[0][1] == matrix[1][0]

    def test_calculate_route_distance(self):
        """Test route distance calculation."""
        calc = DistanceMatrixCalculator()

        coords = [
            (32.0, -117.0),
            (32.1, -117.0),
            (32.2, -117.0)
        ]

        route_order = [0, 1, 2]

        distance = calc.calculate_route_distance(coords, route_order)

        # Should be positive
        assert distance > 0

    def test_naive_route_distance(self):
        """Test naive route distance calculation."""
        calc = DistanceMatrixCalculator()

        coords = [
            (32.0, -117.0),
            (32.1, -117.0),
            (32.2, -117.0)
        ]

        distance = calc.calculate_naive_route_distance(coords)

        # Should include return to start
        assert distance > 0


class TestRouteOptimizer:
    """Test RouteOptimizer class."""

    def test_optimize_simple_route(self):
        """Test optimization of a simple route."""
        optimizer = RouteOptimizer()

        # Create a simple square of points
        coords = [
            (32.0, -117.0),  # Bottom left
            (32.1, -117.0),  # Top left
            (32.1, -117.1),  # Top right
            (32.0, -117.1)   # Bottom right
        ]

        result = optimizer.optimize(coords, depot_index=0)

        assert result["success"] is True
        assert "optimized_order" in result
        assert len(result["optimized_order"]) == len(coords) + 1  # Includes return to depot
        assert result["total_distance_km"] > 0
        assert result["total_distance_miles"] > 0

    def test_optimize_insufficient_points(self):
        """Test optimization with insufficient points."""
        optimizer = RouteOptimizer()

        # Only one point
        coords = [(32.0, -117.0)]

        result = optimizer.optimize(coords)

        assert result["success"] is False
        assert "Need at least 2 coordinates" in result["message"]

    def test_optimize_empty_list(self):
        """Test optimization with empty coordinate list."""
        optimizer = RouteOptimizer()

        result = optimizer.optimize([])

        assert result["success"] is False

    def test_create_route_stops(self):
        """Test creation of RouteStop objects."""
        optimizer = RouteOptimizer()

        coords = [
            (32.0, -117.0),
            (32.1, -117.0),
            (32.2, -117.0)
        ]

        optimized_order = [0, 2, 1, 0]
        address_ids = [1, 2, 3]
        addresses = ["123 Main St", "456 Oak Ave", "789 Pine Rd"]

        route_stops = optimizer.create_route_stops(
            coords,
            optimized_order,
            address_ids,
            addresses
        )

        assert len(route_stops) == len(optimized_order)
        assert all(isinstance(stop, RouteStop) for stop in route_stops)
        assert route_stops[0].sequence == 0
        assert route_stops[1].sequence == 1

    def test_calculate_distance_reduction(self):
        """Test distance reduction calculation."""
        optimizer = RouteOptimizer()

        coords = [
            (32.0, -117.0),
            (32.1, -117.0),
            (32.2, -117.0),
            (32.3, -117.0)
        ]

        # Assume optimized distance is 20 km
        optimized_distance = 20.0

        reduction = optimizer.calculate_distance_reduction(coords, optimized_distance)

        # Should return a percentage
        assert isinstance(reduction, float)
        # Reduction could be positive (improvement) or negative (worse)
        # For this test, we just check it's a valid number
        assert -100 < reduction < 100

    def test_optimize_with_time_windows(self):
        """Test optimization with time windows enabled."""
        optimizer = RouteOptimizer()

        coords = [
            (32.0, -117.0),
            (32.1, -117.0),
            (32.2, -117.0),
            (32.3, -117.0)
        ]

        result = optimizer.optimize(
            coords,
            depot_index=0,
            use_time_windows=True
        )

        # Should still succeed with time windows
        assert result["success"] is True
        assert result["total_distance_km"] > 0


class TestRouteOptimizerIntegration:
    """Integration tests for the full routing workflow."""

    def test_full_optimization_workflow(self):
        """Test the complete optimization workflow."""
        optimizer = RouteOptimizer()

        # Create a realistic set of coordinates (El Centro area)
        coords = [
            (32.792, -115.563),  # El Centro downtown
            (32.795, -115.570),  # West El Centro
            (32.788, -115.556),  # East El Centro
            (32.800, -115.565),  # North El Centro
            (32.785, -115.560),  # South El Centro
        ]

        address_ids = [1, 2, 3, 4, 5]
        addresses = [
            "100 Main St, El Centro, CA",
            "200 West St, El Centro, CA",
            "300 East St, El Centro, CA",
            "400 North St, El Centro, CA",
            "500 South St, El Centro, CA"
        ]

        # Run optimization
        result = optimizer.optimize(coords, depot_index=0)

        assert result["success"] is True

        # Create route stops
        route_stops = optimizer.create_route_stops(
            coords,
            result["optimized_order"],
            address_ids,
            addresses
        )

        # Verify route stops
        assert len(route_stops) == len(coords) + 1  # Includes return to depot
        assert route_stops[0].lat == coords[0][0]  # Starts at depot
        assert route_stops[-1].lat == coords[0][0]  # Returns to depot

        # Calculate reduction
        reduction = optimizer.calculate_distance_reduction(
            coords,
            result["total_distance_km"]
        )

        # Reduction should be calculable
        assert isinstance(reduction, float)

        # Stats should make sense
        assert result["total_distance_km"] > 0
        assert result["total_distance_miles"] > 0
        assert result["total_distance_miles"] == pytest.approx(
            result["total_distance_km"] * 0.621371,
            rel=0.01
        )
