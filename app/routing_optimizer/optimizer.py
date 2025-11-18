"""Route optimization using Google OR-Tools.

This module provides the core route optimization logic using the
OR-Tools Vehicle Routing Problem (VRP) solver.
"""

from typing import List, Tuple, Optional, Dict
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import logging

from app.routing_optimizer.distance_matrix import DistanceMatrixCalculator
from app.routing_optimizer.schemas import RouteStop, RouteStatistics

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """Optimize routes using OR-Tools VRP solver."""

    def __init__(self):
        """Initialize the route optimizer."""
        self.distance_calculator = DistanceMatrixCalculator()

    def optimize(
        self,
        coordinates: List[Tuple[float, float]],
        depot_index: int = 0,
        use_time_windows: bool = False,
        time_limit_seconds: int = 30
    ) -> Dict:
        """
        Optimize a route through the given coordinates.

        Args:
            coordinates: List of (lat, lon) tuples representing pickup points
            depot_index: Index of the depot (start/end point), default is first coordinate
            use_time_windows: Enable time window constraints (experimental)
            time_limit_seconds: Maximum time to spend on optimization

        Returns:
            Dictionary with:
                - optimized_order: List of indices in optimized order
                - total_distance_km: Total route distance in kilometers
                - total_distance_miles: Total route distance in miles
                - success: Whether optimization succeeded
                - message: Status message
        """
        if not coordinates or len(coordinates) < 2:
            return {
                "success": False,
                "message": "Need at least 2 coordinates to optimize",
                "optimized_order": [],
                "total_distance_km": 0.0,
                "total_distance_miles": 0.0
            }

        try:
            logger.info(f"Starting route optimization for {len(coordinates)} stops")

            # Create distance matrix
            distance_matrix = self.distance_calculator.create_distance_matrix_int(coordinates)

            # Create the routing index manager
            manager = pywrapcp.RoutingIndexManager(
                len(distance_matrix),
                1,  # Number of vehicles (1 for single route)
                depot_index
            )

            # Create routing model
            routing = pywrapcp.RoutingModel(manager)

            # Create and register distance callback
            def distance_callback(from_index, to_index):
                """Returns the distance between the two nodes."""
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return distance_matrix[from_node][to_node]

            transit_callback_index = routing.RegisterTransitCallback(distance_callback)

            # Define cost of each arc
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

            # Optional: Add time window constraints
            if use_time_windows:
                self._add_time_window_constraints(
                    routing,
                    manager,
                    distance_matrix,
                    transit_callback_index
                )

            # Set search parameters
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.seconds = time_limit_seconds

            logger.info("Solving VRP...")

            # Solve the problem
            solution = routing.SolveWithParameters(search_parameters)

            if solution:
                logger.info("Solution found!")
                return self._extract_solution(
                    routing,
                    manager,
                    solution,
                    coordinates,
                    depot_index
                )
            else:
                logger.warning("No solution found")
                return {
                    "success": False,
                    "message": "No solution found within time limit",
                    "optimized_order": list(range(len(coordinates))),
                    "total_distance_km": 0.0,
                    "total_distance_miles": 0.0
                }

        except Exception as e:
            logger.error(f"Optimization error: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Optimization error: {str(e)}",
                "optimized_order": list(range(len(coordinates))),
                "total_distance_km": 0.0,
                "total_distance_miles": 0.0
            }

    def _add_time_window_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        distance_matrix: List[List[int]],
        transit_callback_index: int
    ):
        """
        Add time window constraints to the routing model.

        This is a basic implementation assuming:
        - Average speed of 40 km/h (25 mph) in urban areas
        - 5 minutes per stop for service time
        - 8-hour working day (480 minutes)

        Args:
            routing: OR-Tools routing model
            manager: OR-Tools index manager
            distance_matrix: Distance matrix in meters
            transit_callback_index: Index of the transit callback
        """
        # Time conversion: meters to minutes at 40 km/h
        # 40 km/h = 40000 m/h = 666.67 m/min
        SPEED_METERS_PER_MINUTE = 666.67
        SERVICE_TIME_MINUTES = 5

        def time_callback(from_index, to_index):
            """Returns the travel time between two nodes."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            distance = distance_matrix[from_node][to_node]
            travel_time = int(distance / SPEED_METERS_PER_MINUTE)
            return travel_time + SERVICE_TIME_MINUTES

        time_callback_index = routing.RegisterTransitCallback(time_callback)

        # Add time dimension
        routing.AddDimension(
            time_callback_index,
            30,  # Allow waiting time (slack) of 30 minutes
            480,  # Maximum time per vehicle (8 hours = 480 minutes)
            False,  # Don't force start cumul to zero
            'Time'
        )

        time_dimension = routing.GetDimensionOrDie('Time')

        # Set time windows (simplified: all stops available 8am-5pm)
        # In a real implementation, you'd set specific windows per location
        for location_idx in range(len(distance_matrix)):
            if location_idx == 0:  # Depot
                time_dimension.CumulVar(manager.NodeToIndex(location_idx)).SetRange(0, 480)
            else:
                index = manager.NodeToIndex(location_idx)
                time_dimension.CumulVar(index).SetRange(0, 480)

    def _extract_solution(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        solution,
        coordinates: List[Tuple[float, float]],
        depot_index: int
    ) -> Dict:
        """
        Extract the solution from OR-Tools solver.

        Args:
            routing: OR-Tools routing model
            manager: OR-Tools index manager
            solution: Solution object from solver
            coordinates: Original list of coordinates
            depot_index: Index of the depot

        Returns:
            Dictionary with solution details
        """
        # Extract route
        optimized_order = []
        index = routing.Start(0)  # Vehicle 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            optimized_order.append(node_index)
            index = solution.Value(routing.NextVar(index))

        # Add final depot
        optimized_order.append(manager.IndexToNode(index))

        # Calculate total distance
        total_distance_km = self.distance_calculator.calculate_route_distance(
            coordinates,
            optimized_order
        )

        # Convert to miles
        total_distance_miles = total_distance_km * 0.621371

        logger.info(
            f"Optimized route: {len(optimized_order)} stops, "
            f"{total_distance_km:.2f} km ({total_distance_miles:.2f} miles)"
        )

        return {
            "success": True,
            "message": "Route optimized successfully",
            "optimized_order": optimized_order,
            "total_distance_km": round(total_distance_km, 2),
            "total_distance_miles": round(total_distance_miles, 2)
        }

    def create_route_stops(
        self,
        coordinates: List[Tuple[float, float]],
        optimized_order: List[int],
        address_ids: Optional[List[int]] = None,
        addresses: Optional[List[str]] = None
    ) -> List[RouteStop]:
        """
        Create RouteStop objects from optimized order.

        Args:
            coordinates: Original list of coordinates
            optimized_order: List of indices in optimized order
            address_ids: Optional list of address IDs
            addresses: Optional list of address strings

        Returns:
            List of RouteStop objects in optimized order
        """
        route_stops = []

        for sequence, idx in enumerate(optimized_order):
            lat, lon = coordinates[idx]

            route_stop = RouteStop(
                address_id=address_ids[idx] if address_ids and idx < len(address_ids) else None,
                address=addresses[idx] if addresses and idx < len(addresses) else None,
                lat=lat,
                lon=lon,
                sequence=sequence
            )
            route_stops.append(route_stop)

        return route_stops

    def calculate_distance_reduction(
        self,
        coordinates: List[Tuple[float, float]],
        optimized_distance_km: float
    ) -> float:
        """
        Calculate percentage reduction vs naive route.

        Args:
            coordinates: List of coordinates
            optimized_distance_km: Distance of optimized route in km

        Returns:
            Percentage reduction (e.g., 25.5 for 25.5% reduction)
        """
        naive_distance_km = self.distance_calculator.calculate_naive_route_distance(
            coordinates
        )

        if naive_distance_km == 0:
            return 0.0

        reduction = ((naive_distance_km - optimized_distance_km) / naive_distance_km) * 100
        return round(reduction, 2)
