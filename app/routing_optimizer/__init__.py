"""Routing optimizer module for TrashAlert.

This module provides route optimization capabilities using Google OR-Tools
to optimize trash collection routes.
"""

from app.routing_optimizer.optimizer import RouteOptimizer
from app.routing_optimizer.schemas import (
    OptimizeRouteRequest,
    OptimizeRouteResponse,
    RouteStop,
    RouteStatistics
)

__all__ = [
    "RouteOptimizer",
    "OptimizeRouteRequest",
    "OptimizeRouteResponse",
    "RouteStop",
    "RouteStatistics"
]
