"""Gamification service for points, badges, and leaderboards."""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime
import logging

from app.models import User, Badge, UserBadge, PointHistory, CrowdReport
from app.schemas import LeaderboardEntry, UserBadgeSchema, BadgeSchema

logger = logging.getLogger(__name__)


class GamificationService:
    """Service for managing gamification features."""

    # Point values
    POINTS_PER_REPORT = 10
    POINTS_PER_VERIFIED_REPORT = 50

    @staticmethod
    def award_points(
        db: Session,
        user_id: int,
        points: int,
        action: str,
        description: Optional[str] = None,
        report_id: Optional[int] = None
    ) -> None:
        """Award points to a user and log the transaction."""
        # Create point history record
        point_record = PointHistory(
            user_id=user_id,
            points=points,
            action=action,
            description=description,
            report_id=report_id
        )
        db.add(point_record)

        # Update user's total points
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_points = (user.total_points or 0) + points
            db.commit()
            logger.info(f"Awarded {points} points to user {user_id} for {action}")

    @staticmethod
    def award_report_points(db: Session, user_id: int, report_id: int) -> None:
        """Award points for submitting a report."""
        GamificationService.award_points(
            db=db,
            user_id=user_id,
            points=GamificationService.POINTS_PER_REPORT,
            action="report_submitted",
            description="Points for submitting a trash pickup report",
            report_id=report_id
        )

        # Update user's total reports count
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_reports = (user.total_reports or 0) + 1
            db.commit()

        # Check for badge eligibility
        GamificationService.check_and_award_badges(db, user_id)

    @staticmethod
    def award_verification_points(db: Session, user_id: int, report_id: int) -> None:
        """Award additional points when a user's report gets verified."""
        GamificationService.award_points(
            db=db,
            user_id=user_id,
            points=GamificationService.POINTS_PER_VERIFIED_REPORT,
            action="report_verified",
            description="Bonus points for verified report",
            report_id=report_id
        )

        # Update user's verified reports count
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.verified_reports = (user.verified_reports or 0) + 1
            db.commit()

        # Check for badge eligibility
        GamificationService.check_and_award_badges(db, user_id)

    @staticmethod
    def check_and_award_badges(db: Session, user_id: int) -> List[Badge]:
        """Check if user qualifies for any badges and award them."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        newly_awarded = []

        # Get all badges
        all_badges = db.query(Badge).all()

        for badge in all_badges:
            # Check if user already has this badge
            existing = db.query(UserBadge).filter(
                UserBadge.user_id == user_id,
                UserBadge.badge_id == badge.id
            ).first()

            if existing:
                continue

            # Check if user qualifies
            qualifies = False

            if badge.requirement_type == "total_reports":
                qualifies = user.total_reports >= badge.requirement_value
            elif badge.requirement_type == "verified_reports":
                qualifies = user.verified_reports >= badge.requirement_value
            elif badge.requirement_type == "power_user":
                # Power user: 20+ verified reports
                qualifies = user.verified_reports >= badge.requirement_value

            if qualifies:
                # Award the badge
                user_badge = UserBadge(
                    user_id=user_id,
                    badge_id=badge.id
                )
                db.add(user_badge)

                # Update verified reporter status if applicable
                if badge.requirement_type == "verified_reporter":
                    user.is_verified_reporter = True

                newly_awarded.append(badge)
                logger.info(f"Awarded badge '{badge.name}' to user {user_id}")

        if newly_awarded:
            db.commit()

        return newly_awarded

    @staticmethod
    def get_leaderboard(
        db: Session,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[LeaderboardEntry], int]:
        """Get the leaderboard with user rankings."""
        # Query users ordered by points, with badge counts
        query = db.query(
            User.id,
            User.username,
            User.total_points,
            User.total_reports,
            User.verified_reports,
            User.is_verified_reporter,
            func.count(UserBadge.id).label('badges_count')
        ).outerjoin(UserBadge).group_by(User.id).order_by(
            desc(User.total_points),
            desc(User.verified_reports)
        )

        total_users = query.count()
        users = query.limit(limit).offset(offset).all()

        leaderboard = []
        for idx, user_data in enumerate(users, start=offset + 1):
            entry = LeaderboardEntry(
                rank=idx,
                user_id=user_data.id,
                username=user_data.username,
                total_points=user_data.total_points or 0,
                total_reports=user_data.total_reports or 0,
                verified_reports=user_data.verified_reports or 0,
                is_verified_reporter=user_data.is_verified_reporter or False,
                badges_count=user_data.badges_count
            )
            leaderboard.append(entry)

        return leaderboard, total_users

    @staticmethod
    def get_user_rank(db: Session, user_id: int) -> Optional[int]:
        """Get a user's current rank on the leaderboard."""
        # Count users with more points
        higher_ranked = db.query(User).filter(
            User.total_points > db.query(User.total_points).filter(User.id == user_id).scalar_subquery()
        ).count()

        return higher_ranked + 1

    @staticmethod
    def get_user_badges(db: Session, user_id: int) -> List[UserBadgeSchema]:
        """Get all badges earned by a user."""
        user_badges = db.query(UserBadge).filter(
            UserBadge.user_id == user_id
        ).order_by(desc(UserBadge.earned_at)).all()

        result = []
        for ub in user_badges:
            badge = db.query(Badge).filter(Badge.id == ub.badge_id).first()
            if badge:
                badge_schema = BadgeSchema(
                    id=badge.id,
                    slug=badge.slug,
                    name=badge.name,
                    description=badge.description,
                    icon=badge.icon,
                    color=badge.color,
                    tier=badge.tier,
                    requirement_type=badge.requirement_type,
                    requirement_value=badge.requirement_value
                )
                result.append(UserBadgeSchema(
                    id=ub.id,
                    badge=badge_schema,
                    earned_at=ub.earned_at.isoformat() if ub.earned_at else ""
                ))

        return result

    @staticmethod
    def get_recent_point_history(db: Session, user_id: int, limit: int = 10) -> List[dict]:
        """Get recent point transactions for a user."""
        history = db.query(PointHistory).filter(
            PointHistory.user_id == user_id
        ).order_by(desc(PointHistory.created_at)).limit(limit).all()

        return [
            {
                "points": h.points,
                "action": h.action,
                "description": h.description,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in history
        ]

    @staticmethod
    def send_badge_email(db: Session, user_id: int, badge_id: int) -> bool:
        """
        Send email notification for a newly earned badge.

        Note: This is a placeholder. Actual email sending would require
        an SMTP service or email API (e.g., SendGrid, AWS SES).
        """
        user = db.query(User).filter(User.id == user_id).first()
        badge = db.query(Badge).filter(Badge.id == badge_id).first()

        if not user or not badge:
            return False

        # Get the user_badge record
        user_badge = db.query(UserBadge).filter(
            UserBadge.user_id == user_id,
            UserBadge.badge_id == badge_id
        ).first()

        if not user_badge:
            return False

        # TODO: Implement actual email sending
        # For now, just log it
        logger.info(f"Email notification: User {user.email} earned badge '{badge.name}'")

        # Mark as sent
        user_badge.email_sent = True
        user_badge.email_sent_at = datetime.utcnow()
        db.commit()

        return True

    @staticmethod
    def initialize_default_badges(db: Session) -> None:
        """Initialize default badge definitions."""
        default_badges = [
            {
                "slug": "verified-reporter",
                "name": "Verified Reporter",
                "description": "Earned after 5 verified reports",
                "icon": "shield-check",
                "requirement_type": "verified_reports",
                "requirement_value": 5,
                "color": "#3b82f6",
                "tier": 2
            },
            {
                "slug": "power-user-bronze",
                "name": "Power User - Bronze",
                "description": "Submitted 10 reports",
                "icon": "trophy",
                "requirement_type": "total_reports",
                "requirement_value": 10,
                "color": "#cd7f32",
                "tier": 1
            },
            {
                "slug": "power-user-silver",
                "name": "Power User - Silver",
                "description": "Submitted 25 reports",
                "icon": "trophy",
                "requirement_type": "total_reports",
                "requirement_value": 25,
                "color": "#c0c0c0",
                "tier": 2
            },
            {
                "slug": "power-user-gold",
                "name": "Power User - Gold",
                "description": "Submitted 50 reports",
                "icon": "trophy",
                "requirement_type": "total_reports",
                "requirement_value": 50,
                "color": "#ffd700",
                "tier": 3
            }
        ]

        for badge_data in default_badges:
            # Check if badge already exists
            existing = db.query(Badge).filter(Badge.slug == badge_data["slug"]).first()
            if not existing:
                badge = Badge(**badge_data)
                db.add(badge)

        db.commit()
        logger.info("Default badges initialized")
