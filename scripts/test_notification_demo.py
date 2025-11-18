#!/usr/bin/env python3
"""
Demo script to test the TrashAlert notification system.

This script demonstrates:
1. Creating a user
2. Creating a subscription for an address
3. Sending a test SMS notification

Prerequisites:
- Database migration must be run first
- Environment variables must be set in .env:
  - TWILIO_ACCOUNT_SID
  - TWILIO_AUTH_TOKEN
  - TWILIO_PHONE_NUMBER
  - SENDGRID_API_KEY (optional, for email)
  - SENDGRID_FROM_EMAIL (optional)

Usage:
    python scripts/test_notification_demo.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import User, Address, AddressSubscription
from app.notification_service import get_notification_service
from app.utils import normalize_address


def main():
    """Run the notification demo."""
    print("=" * 80)
    print("TrashAlert Notification System Demo")
    print("=" * 80)
    print()

    # Load environment variables
    load_dotenv()

    # Check for required environment variables
    required_vars = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER"
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print()
        print("Please set these in your .env file and try again.")
        sys.exit(1)

    print("✓ Environment variables configured")
    print()

    # Create tables if they don't exist
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
    print()

    # Get database session
    db: Session = SessionLocal()

    try:
        # Step 1: Create a demo user
        print("Step 1: Creating demo user")
        print("-" * 40)

        demo_email = input("Enter email address for demo user: ").strip()
        demo_phone = input("Enter phone number for SMS (E.164 format, e.g., +15551234567): ").strip()
        demo_name = input("Enter display name (optional): ").strip() or "Demo User"

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == demo_email).first()
        if existing_user:
            print(f"✓ User already exists (ID: {existing_user.id})")
            user = existing_user
        else:
            user = User(
                email=demo_email,
                phone=demo_phone,
                display_name=demo_name,
                timezone="America/Los_Angeles"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✓ Created new user (ID: {user.id})")

        print()

        # Step 2: Create a demo subscription
        print("Step 2: Creating demo subscription")
        print("-" * 40)

        demo_address = input("Enter an address to subscribe to: ").strip()
        normalized = normalize_address(demo_address)

        # Find or create address
        address = db.query(Address).filter(Address.normalized_address == normalized).first()
        if not address:
            address = Address(
                normalized_address=normalized,
                official_trash_day="MON",  # Demo data
                official_recycling_day="WED",
                city_name="Demo City",
                state="CA"
            )
            db.add(address)
            db.flush()
            print(f"✓ Created new address (ID: {address.id})")
        else:
            print(f"✓ Found existing address (ID: {address.id})")

        # Check if subscription exists
        existing_sub = db.query(AddressSubscription).filter(
            AddressSubscription.user_id == user.id,
            AddressSubscription.address_id == address.id
        ).first()

        if existing_sub:
            print(f"✓ Subscription already exists (ID: {existing_sub.id})")
            subscription = existing_sub
        else:
            subscription = AddressSubscription(
                user_id=user.id,
                address_id=address.id,
                notify_trash=True,
                notify_recycling=True,
                notify_green=False,
                notify_email=True,
                notify_sms=True,
                days_before=1,
                notification_time="18:00"
            )
            db.add(subscription)
            db.commit()
            db.refresh(subscription)
            print(f"✓ Created new subscription (ID: {subscription.id})")

        print()

        # Step 3: Send test SMS notification
        print("Step 3: Sending test SMS notification")
        print("-" * 40)

        confirm = input(f"Send test SMS to {user.phone}? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Skipping SMS test")
        else:
            notification_service = get_notification_service()

            result = notification_service.send_trash_reminder_sms(
                phone=user.phone,
                address=address.normalized_address,
                pickup_type="trash",
                pickup_day="tomorrow (DEMO)"
            )

            print()
            if result.get("status") == "sent":
                print("✓ SMS SENT SUCCESSFULLY!")
                print(f"  Message SID: {result.get('external_id')}")
                print(f"  Sent to: {user.phone}")
                print()
                print("SUCCESS CRITERIA MET: Demo script successfully sent SMS reminder!")
            else:
                print("✗ SMS FAILED")
                print(f"  Error: {result.get('error')}")
                if result.get('error_code'):
                    print(f"  Error Code: {result.get('error_code')}")

        print()

        # Step 4: Test email notification (optional)
        print("Step 4: Sending test email notification (optional)")
        print("-" * 40)

        if not os.getenv("SENDGRID_API_KEY"):
            print("⚠ SendGrid API key not configured - skipping email test")
        else:
            confirm = input(f"Send test email to {user.email}? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Skipping email test")
            else:
                notification_service = get_notification_service()

                result = notification_service.send_trash_reminder_email(
                    email=user.email,
                    address=address.normalized_address,
                    pickup_type="trash",
                    pickup_day="tomorrow (DEMO)",
                    additional_info="This is a demo email from the TrashAlert notification system."
                )

                print()
                if result.get("status") == "sent":
                    print("✓ EMAIL SENT SUCCESSFULLY!")
                    print(f"  Message ID: {result.get('external_id')}")
                    print(f"  Sent to: {user.email}")
                else:
                    print("✗ EMAIL FAILED")
                    print(f"  Error: {result.get('error')}")

        print()
        print("=" * 80)
        print("Demo Complete!")
        print("=" * 80)
        print()
        print("Summary:")
        print(f"  User ID: {user.id}")
        print(f"  Email: {user.email}")
        print(f"  Phone: {user.phone}")
        print(f"  Subscription ID: {subscription.id}")
        print(f"  Address: {address.normalized_address}")
        print()
        print("You can now:")
        print("  1. Use the API to manage subscriptions")
        print("  2. Test the scheduler by waiting for scheduled notifications")
        print("  3. Use POST /api/notifications/test to send more test notifications")
        print()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
