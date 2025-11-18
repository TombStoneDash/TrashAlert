"""Metrics collection and aggregation for observability."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, Any
import time

from app.models import RequestMetrics, Address, CrowdReport, CrowdConsensus
from app.logging_config import app_logger


class MetricsManager:
    """
    Manager for collecting and querying API metrics.

    Provides methods to:
    - Record API requests with timing and city information
    - Query metrics aggregated by city
    - Get overall statistics
    """

    @staticmethod
    def record_request(
        db: Session,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        city: Optional[str] = None,
        error_message: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Record an API request metric.

        Args:
            db: Database session
            endpoint: API endpoint (e.g., "/lookup", "/report")
            method: HTTP method (GET, POST)
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
            city: City from the request (if applicable)
            error_message: Error message if request failed
            user_agent: User agent string
            ip_address: Client IP address
        """
        try:
            metric = RequestMetrics(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time_ms=response_time_ms,
                city=city,
                error_message=error_message,
                user_agent=user_agent,
                ip_address=ip_address
            )
            db.add(metric)
            db.commit()

            app_logger.debug(
                f"Recorded metric: {method} {endpoint} - {status_code} - "
                f"{response_time_ms:.2f}ms - City: {city or 'N/A'}"
            )
        except Exception as e:
            app_logger.error(f"Failed to record metric: {e}", exc_info=True)
            db.rollback()

    @staticmethod
    def get_lookup_stats_by_city(db: Session) -> Dict[str, int]:
        """
        Get number of /lookup calls per city.

        Returns:
            Dictionary mapping city name to lookup count
        """
        results = (
            db.query(
                RequestMetrics.city,
                func.count(RequestMetrics.id).label('count')
            )
            .filter(
                RequestMetrics.endpoint == '/lookup',
                RequestMetrics.city.isnot(None)
            )
            .group_by(RequestMetrics.city)
            .all()
        )

        return {city: count for city, count in results}

    @staticmethod
    def get_report_stats_by_city(db: Session) -> Dict[str, int]:
        """
        Get number of /report submissions per city.

        Returns:
            Dictionary mapping city name to report count
        """
        results = (
            db.query(
                RequestMetrics.city,
                func.count(RequestMetrics.id).label('count')
            )
            .filter(
                RequestMetrics.endpoint == '/report',
                RequestMetrics.city.isnot(None)
            )
            .group_by(RequestMetrics.city)
            .all()
        )

        return {city: count for city, count in results}

    @staticmethod
    def get_overall_stats(db: Session) -> Dict[str, Any]:
        """
        Get overall API statistics.

        Returns:
            Dictionary with comprehensive statistics including:
            - Total lookups and reports
            - Average response times
            - Error rates
            - Per-city breakdowns
        """
        # Total requests by endpoint
        total_lookups = (
            db.query(func.count(RequestMetrics.id))
            .filter(RequestMetrics.endpoint == '/lookup')
            .scalar() or 0
        )

        total_reports = (
            db.query(func.count(RequestMetrics.id))
            .filter(RequestMetrics.endpoint == '/report')
            .scalar() or 0
        )

        # Average response times
        avg_lookup_time = (
            db.query(func.avg(RequestMetrics.response_time_ms))
            .filter(RequestMetrics.endpoint == '/lookup')
            .scalar() or 0.0
        )

        avg_report_time = (
            db.query(func.avg(RequestMetrics.response_time_ms))
            .filter(RequestMetrics.endpoint == '/report')
            .scalar() or 0.0
        )

        # Error counts (status code >= 400)
        total_errors = (
            db.query(func.count(RequestMetrics.id))
            .filter(RequestMetrics.status_code >= 400)
            .scalar() or 0
        )

        # Per-city breakdowns
        lookup_by_city = MetricsManager.get_lookup_stats_by_city(db)
        report_by_city = MetricsManager.get_report_stats_by_city(db)

        # Database statistics
        total_addresses = db.query(func.count(Address.id)).scalar() or 0
        total_crowd_reports = db.query(func.count(CrowdReport.id)).scalar() or 0
        total_consensus = db.query(func.count(CrowdConsensus.id)).scalar() or 0
        verified_consensus = (
            db.query(func.count(CrowdConsensus.id))
            .filter(CrowdConsensus.is_verified == True)
            .scalar() or 0
        )

        return {
            'api_metrics': {
                'total_lookups': total_lookups,
                'total_reports': total_reports,
                'total_errors': total_errors,
                'avg_lookup_time_ms': round(avg_lookup_time, 2),
                'avg_report_time_ms': round(avg_report_time, 2),
            },
            'lookup_by_city': lookup_by_city,
            'report_by_city': report_by_city,
            'database_stats': {
                'total_addresses': total_addresses,
                'total_crowd_reports': total_crowd_reports,
                'total_consensus': total_consensus,
                'verified_consensus': verified_consensus,
            }
        }

    @staticmethod
    def get_endpoint_stats(db: Session, endpoint: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific endpoint.

        Args:
            endpoint: Endpoint path (e.g., "/lookup", "/report")

        Returns:
            Dictionary with endpoint-specific statistics
        """
        total_requests = (
            db.query(func.count(RequestMetrics.id))
            .filter(RequestMetrics.endpoint == endpoint)
            .scalar() or 0
        )

        avg_response_time = (
            db.query(func.avg(RequestMetrics.response_time_ms))
            .filter(RequestMetrics.endpoint == endpoint)
            .scalar() or 0.0
        )

        min_response_time = (
            db.query(func.min(RequestMetrics.response_time_ms))
            .filter(RequestMetrics.endpoint == endpoint)
            .scalar() or 0.0
        )

        max_response_time = (
            db.query(func.max(RequestMetrics.response_time_ms))
            .filter(RequestMetrics.endpoint == endpoint)
            .scalar() or 0.0
        )

        error_count = (
            db.query(func.count(RequestMetrics.id))
            .filter(
                RequestMetrics.endpoint == endpoint,
                RequestMetrics.status_code >= 400
            )
            .scalar() or 0
        )

        success_rate = 0.0
        if total_requests > 0:
            success_rate = ((total_requests - error_count) / total_requests) * 100

        return {
            'endpoint': endpoint,
            'total_requests': total_requests,
            'avg_response_time_ms': round(avg_response_time, 2),
            'min_response_time_ms': round(min_response_time, 2),
            'max_response_time_ms': round(max_response_time, 2),
            'error_count': error_count,
            'success_rate': round(success_rate, 2)
        }
