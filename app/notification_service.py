"""Notification service for sending SMS and email reminders."""
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via SMS and email."""

    def __init__(self):
        """Initialize notification service with Twilio and SendGrid clients."""
        # Twilio configuration
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

        # SendGrid configuration
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.sendgrid_from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@trashalert.app")

        # Initialize clients if credentials are available
        self.twilio_client = None
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                self.twilio_client = TwilioClient(
                    self.twilio_account_sid,
                    self.twilio_auth_token
                )
                logger.info("Twilio client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        else:
            logger.warning("Twilio credentials not found - SMS notifications disabled")

        self.sendgrid_client = None
        if self.sendgrid_api_key:
            try:
                self.sendgrid_client = SendGridAPIClient(self.sendgrid_api_key)
                logger.info("SendGrid client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize SendGrid client: {e}")
        else:
            logger.warning("SendGrid API key not found - email notifications disabled")

    def send_sms(
        self,
        to_phone: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send SMS notification via Twilio.

        Args:
            to_phone: Recipient phone number (E.164 format recommended)
            message: Message body
            **kwargs: Additional Twilio message parameters

        Returns:
            Dict with status and message_id or error details
        """
        if not self.twilio_client:
            logger.error("SMS sending attempted but Twilio client not initialized")
            return {
                "status": "failed",
                "error": "Twilio client not initialized - check credentials"
            }

        try:
            # Ensure phone number has country code
            if not to_phone.startswith('+'):
                to_phone = f"+1{to_phone}"  # Default to US

            # Send SMS via Twilio
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone_number,
                to=to_phone,
                **kwargs
            )

            logger.info(f"SMS sent successfully to {to_phone}, SID: {message_obj.sid}")
            return {
                "status": "sent",
                "external_id": message_obj.sid,
                "sent_at": datetime.utcnow()
            }

        except TwilioRestException as e:
            logger.error(f"Twilio error sending SMS to {to_phone}: {e.msg}")
            return {
                "status": "failed",
                "error": f"Twilio error: {e.msg}",
                "error_code": e.code
            }
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_phone}: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send email notification via SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML email body
            text_content: Plain text email body (optional)
            **kwargs: Additional SendGrid parameters

        Returns:
            Dict with status and message_id or error details
        """
        if not self.sendgrid_client:
            logger.error("Email sending attempted but SendGrid client not initialized")
            return {
                "status": "failed",
                "error": "SendGrid client not initialized - check API key"
            }

        try:
            # Create email message
            message = Mail(
                from_email=self.sendgrid_from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )

            # Add plain text content if provided
            if text_content:
                message.plain_text_content = text_content

            # Send email via SendGrid
            response = self.sendgrid_client.send(message)

            logger.info(f"Email sent successfully to {to_email}, status code: {response.status_code}")
            return {
                "status": "sent",
                "external_id": response.headers.get('X-Message-Id'),
                "sent_at": datetime.utcnow(),
                "status_code": response.status_code
            }

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def send_trash_reminder_sms(
        self,
        phone: str,
        address: str,
        pickup_type: str,
        pickup_day: str
    ) -> Dict[str, Any]:
        """
        Send trash pickup reminder via SMS.

        Args:
            phone: Recipient phone number
            address: Address for the pickup
            pickup_type: Type of pickup (trash, recycling, green)
            pickup_day: Day of pickup (e.g., "Monday", "tomorrow")

        Returns:
            Dict with status and message_id or error details
        """
        message = (
            f"TrashAlert Reminder: {pickup_type.capitalize()} pickup "
            f"for {address} is scheduled for {pickup_day}. "
            f"Don't forget to put your bin out!"
        )

        return self.send_sms(phone, message)

    def send_trash_reminder_email(
        self,
        email: str,
        address: str,
        pickup_type: str,
        pickup_day: str,
        additional_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send trash pickup reminder via email.

        Args:
            email: Recipient email address
            address: Address for the pickup
            pickup_type: Type of pickup (trash, recycling, green)
            pickup_day: Day of pickup (e.g., "Monday", "tomorrow")
            additional_info: Additional information to include in email

        Returns:
            Dict with status and message_id or error details
        """
        subject = f"TrashAlert Reminder: {pickup_type.capitalize()} pickup {pickup_day}"

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .footer {{ background-color: #f1f1f1; padding: 10px; text-align: center; font-size: 12px; }}
                .highlight {{ color: #4CAF50; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>TrashAlert Reminder</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>This is a reminder that your <span class="highlight">{pickup_type}</span> pickup
                at <strong>{address}</strong> is scheduled for <span class="highlight">{pickup_day}</span>.</p>
                <p>Please remember to put your bin out before your scheduled pickup time.</p>
                {f"<p><em>{additional_info}</em></p>" if additional_info else ""}
            </div>
            <div class="footer">
                <p>You're receiving this because you subscribed to TrashAlert notifications.</p>
                <p>To manage your subscriptions, visit your TrashAlert account settings.</p>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        TrashAlert Reminder

        Hello,

        This is a reminder that your {pickup_type} pickup at {address} is scheduled for {pickup_day}.

        Please remember to put your bin out before your scheduled pickup time.

        {additional_info if additional_info else ""}

        ---
        You're receiving this because you subscribed to TrashAlert notifications.
        To manage your subscriptions, visit your TrashAlert account settings.
        """

        return self.send_email(email, subject, html_content, text_content)


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the singleton NotificationService instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
