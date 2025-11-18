"""Initialize gamification system with badges and test data."""
import sys
import os
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models import User, Badge, CrowdReport, Address
from app.gamification import GamificationService
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def init_badges(db):
    """Initialize default badges."""
    print("Initializing badges...")
    GamificationService.initialize_default_badges(db)
    print("✓ Badges initialized")


def create_test_users(db):
    """Create test users with varying levels of activity."""
    print("\nCreating test users...")

    test_users = [
        {"username": "alice_reporter", "email": "alice@example.com", "reports": 50, "verified": 35},
        {"username": "bob_active", "email": "bob@example.com", "reports": 30, "verified": 20},
        {"username": "charlie_newbie", "email": "charlie@example.com", "reports": 5, "verified": 2},
        {"username": "diana_champion", "email": "diana@example.com", "reports": 75, "verified": 60},
        {"username": "eve_casual", "email": "eve@example.com", "reports": 15, "verified": 10},
        {"username": "frank_beginner", "email": "frank@example.com", "reports": 3, "verified": 1},
        {"username": "grace_power", "email": "grace@example.com", "reports": 40, "verified": 25},
        {"username": "henry_top", "email": "henry@example.com", "reports": 90, "verified": 70},
        {"username": "iris_steady", "email": "iris@example.com", "reports": 20, "verified": 15},
        {"username": "jack_explorer", "email": "jack@example.com", "reports": 12, "verified": 8},
    ]

    created_users = []
    for user_data in test_users:
        # Check if user already exists
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if existing:
            print(f"  User {user_data['username']} already exists, skipping...")
            created_users.append(existing)
            continue

        # Create user
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            hashed_password=hash_password("password123"),
            total_points=0,
            total_reports=0,
            verified_reports=0,
            is_active=True,
            is_verified_reporter=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"  Created user: {user.username} (ID: {user.id})")
        created_users.append(user)

    return created_users, test_users


def create_test_reports(db, users, user_data_list):
    """Create test reports for users."""
    print("\nCreating test reports...")

    # Get some addresses to report on
    addresses = db.query(Address).limit(50).all()

    if not addresses:
        print("  No addresses found in database. Please run init_database.py first.")
        return

    total_reports_created = 0

    for user, user_data in zip(users, user_data_list):
        num_reports = user_data["reports"]
        num_verified = user_data["verified"]

        # Create reports
        for i in range(num_reports):
            # Pick a random address
            address = random.choice(addresses)

            # Create report
            report = CrowdReport(
                address_id=address.id,
                trash_day=random.choice(["MON", "TUE", "WED", "THU", "FRI"]),
                recycling_day=random.choice(["MON", "TUE", "WED", "THU", "FRI", None]),
                green_day=random.choice(["MON", "TUE", "WED", "THU", "FRI", None]),
                user_id=user.id,
                user_hash=f"hash_{user.id}",
                ip_address=f"192.168.1.{user.id}",
                is_verified=(i < num_verified),
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90))
            )
            db.add(report)
            total_reports_created += 1

        db.commit()

        # Award points for each report
        reports = db.query(CrowdReport).filter(CrowdReport.user_id == user.id).all()
        for report in reports:
            GamificationService.award_report_points(db, user.id, report.id)

            if report.is_verified:
                GamificationService.award_verification_points(db, user.id, report.id)

        # Check for badges
        GamificationService.check_and_award_badges(db, user.id)

        print(f"  Created {num_reports} reports for {user.username} ({num_verified} verified)")

    print(f"✓ Created {total_reports_created} total reports")


def print_leaderboard(db):
    """Print the current leaderboard."""
    print("\n" + "="*60)
    print("LEADERBOARD")
    print("="*60)

    leaderboard, total = GamificationService.get_leaderboard(db, limit=10)

    print(f"\nTotal Users: {total}\n")
    print(f"{'Rank':<6} {'Username':<20} {'Points':<10} {'Reports':<10} {'Verified':<10} {'Badges':<8}")
    print("-" * 60)

    for entry in leaderboard:
        print(f"{entry.rank:<6} {entry.username:<20} {entry.total_points:<10} "
              f"{entry.total_reports:<10} {entry.verified_reports:<10} {entry.badges_count:<8}")

    print("\n" + "="*60)


def main():
    """Main initialization function."""
    print("="*60)
    print("GAMIFICATION SYSTEM INITIALIZATION")
    print("="*60)

    db = SessionLocal()

    try:
        # Step 1: Initialize badges
        init_badges(db)

        # Step 2: Create test users
        users, user_data = create_test_users(db)

        # Step 3: Create test reports and award points
        create_test_reports(db, users, user_data)

        # Step 4: Print leaderboard
        print_leaderboard(db)

        print("\n✓ Gamification system initialized successfully!")
        print("\nYou can now:")
        print("  1. View the leaderboard at /leaderboard")
        print("  2. Check user stats at /users/{user_id}/stats")
        print("  3. View all badges at /badges")

    except Exception as e:
        print(f"\n✗ Error during initialization: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
