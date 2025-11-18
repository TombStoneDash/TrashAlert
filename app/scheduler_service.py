"""Scheduler service for sending daily trash pickup reminders."""
import logging
from datetime import datetime, timedelta
from typing import List
import pytz

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AddressSubscription, User, Address, NotificationLog, AddressPickupInfo
from app.notification_service import get_notification_service

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler for sending daily trash pickup reminders."""

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = BackgroundScheduler()
        self.notification_service = get_notification_service()

    def start(self):
        """Start the scheduler with daily reminder job."""
        # Schedule daily reminder job to run at multiple times throughout the day
        # to catch different user notification time preferences
        for hour in range(6, 22):  # Run every hour from 6 AM to 9 PM
            self.scheduler.add_job(
                func=self.send_daily_reminders,
                trigger=CronTrigger(hour=hour, minute=0),
                id=f'daily_reminders_{hour:02d}00',
                name=f'Send daily reminders at {hour:02d}:00',
                replace_existing=True
            )

        self.scheduler.start()
        logger.info("Reminder scheduler started successfully")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Reminder scheduler stopped")

    def send_daily_reminders(self):
        """
        Send reminders to all users whose notification time matches current hour.
        This runs every hour to check for users who want notifications at this time.
        """
        db = SessionLocal()
        try:
            current_time = datetime.now(pytz.UTC)
            logger.info(f"Running daily reminders job at {current_time}")

            # Get all active subscriptions
            subscriptions = db.query(AddressSubscription).filter(
                AddressSubscription.is_active == True
            ).all()

            logger.info(f"Found {len(subscriptions)} active subscriptions")

            for subscription in subscriptions:
                try:
                    self._process_subscription(db, subscription, current_time)
                except Exception as e:
                    logger.error(f"Error processing subscription {subscription.id}: {e}")
                    continue

            db.commit()
            logger.info("Daily reminders job completed")

        except Exception as e:
            logger.error(f"Error in send_daily_reminders: {e}")
            db.rollback()
        finally:
            db.close()

    def _process_subscription(
        self,
        db: Session,
        subscription: AddressSubscription,
        current_time: datetime
    ):
        """
        Process a single subscription and send reminders if needed.

        Args:
            db: Database session
            subscription: AddressSubscription to process
            current_time: Current UTC time
        """
        # Get user and address details
        user = db.query(User).filter(User.id == subscription.user_id).first()
        if not user or not user.is_active:
            return

        address = db.query(Address).filter(Address.id == subscription.address_id).first()
        if not address:
            logger.warning(f"Address {subscription.address_id} not found for subscription {subscription.id}")
            return

        # Get user's timezone
        user_tz = pytz.timezone(user.timezone)
        user_time = current_time.astimezone(user_tz)

        # Parse notification time (HH:MM format)
        try:
            notification_hour, notification_minute = map(int, subscription.notification_time.split(':'))
        except (ValueError, AttributeError):
            notification_hour, notification_minute = 18, 0  # Default to 6 PM

        # Check if current hour matches notification hour
        if user_time.hour != notification_hour:
            return

        # Calculate target pickup date (days_before from today)
        target_date = user_time.date() + timedelta(days=subscription.days_before)
        target_day_of_week = target_date.strftime('%A').upper()[:3]  # MON, TUE, etc.

        # Get pickup information for the address
        pickup_info = db.query(AddressPickupInfo).filter(
            AddressPickupInfo.address_id == address.id
        ).first()

        # Fallback to address official days if no pickup_info
        trash_day = pickup_info.trash_day_of_week if pickup_info else address.official_trash_day
        recycling_day = pickup_info.recycling_day_of_week if pickup_info else address.official_recycling_day
        green_day = pickup_info.green_day_of_week if pickup_info else address.official_green_day

        # Determine which reminders to send
        reminders_to_send = []

        if subscription.notify_trash and trash_day and trash_day.upper() == target_day_of_week:
            reminders_to_send.append(("trash", trash_day))

        if subscription.notify_recycling and recycling_day and recycling_day.upper() == target_day_of_week:
            reminders_to_send.append(("recycling", recycling_day))

        if subscription.notify_green and green_day and green_day.upper() == target_day_of_week:
            reminders_to_send.append(("green", green_day))

        # Send reminders
        for pickup_type, pickup_day in reminders_to_send:
            # Format pickup day string
            if subscription.days_before == 0:
                pickup_day_str = "today"
            elif subscription.days_before == 1:
                pickup_day_str = "tomorrow"
            else:
                pickup_day_str = target_date.strftime('%A, %B %d')

            # Send SMS if enabled
            if subscription.notify_sms and user.phone:
                self._send_sms_reminder(
                    db=db,
                    user=user,
                    subscription=subscription,
                    address=address,
                    pickup_type=pickup_type,
                    pickup_day_str=pickup_day_str
                )

            # Send email if enabled
            if subscription.notify_email and user.email:
                self._send_email_reminder(
                    db=db,
                    user=user,
                    subscription=subscription,
                    address=address,
                    pickup_type=pickup_type,
                    pickup_day_str=pickup_day_str
                )

    def _send_sms_reminder(
        self,
        db: Session,
        user: User,
        subscription: AddressSubscription,
        address: Address,
        pickup_type: str,
        pickup_day_str: str
    ):
        """Send SMS reminder and log the notification."""
        try:
            result = self.notification_service.send_trash_reminder_sms(
                phone=user.phone,
                address=address.normalized_address,
                pickup_type=pickup_type,
                pickup_day=pickup_day_str
            )

            # Log notification
            log = NotificationLog(
                user_id=user.id,
                subscription_id=subscription.id,
                notification_type=pickup_type,
                channel="sms",
                recipient=user.phone,
                message_body=f"{pickup_type} reminder for {address.normalized_address}",
                status=result.get("status", "unknown"),
                external_id=result.get("external_id"),
                error_message=result.get("error"),
                scheduled_for=datetime.utcnow(),
                sent_at=result.get("sent_at")
            )
            db.add(log)

            logger.info(f"SMS reminder sent to {user.phone} for {pickup_type} at {address.normalized_address}")

        except Exception as e:
            logger.error(f"Failed to send SMS reminder: {e}")

    def _send_email_reminder(
        self,
        db: Session,
        user: User,
        subscription: AddressSubscription,
        address: Address,
        pickup_type: str,
        pickup_day_str: str
    ):
        """Send email reminder and log the notification."""
        try:
            result = self.notification_service.send_trash_reminder_email(
                email=user.email,
                address=address.normalized_address,
                pickup_type=pickup_type,
                pickup_day=pickup_day_str
            )

            # Log notification
            log = NotificationLog(
                user_id=user.id,
                subscription_id=subscription.id,
                notification_type=pickup_type,
                channel="email",
                recipient=user.email,
                subject=f"TrashAlert: {pickup_type} pickup {pickup_day_str}",
                message_body=f"{pickup_type} reminder for {address.normalized_address}",
                status=result.get("status", "unknown"),
                external_id=result.get("external_id"),
                error_message=result.get("error"),
                scheduled_for=datetime.utcnow(),
                sent_at=result.get("sent_at")
            )
            db.add(log)

            logger.info(f"Email reminder sent to {user.email} for {pickup_type} at {address.normalized_address}")

        except Exception as e:
            logger.error(f"Failed to send email reminder: {e}")


# Singleton instance
_scheduler: ReminderScheduler = None


def get_scheduler() -> ReminderScheduler:
    """Get or create the singleton ReminderScheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler()
    return _scheduler
