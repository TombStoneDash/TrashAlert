# TrashAlert Gamification Module

This document describes the gamification features added to TrashAlert to encourage user participation and reward contributors.

## Overview

The gamification system includes:
- **Points System**: Users earn points for submitting and getting reports verified
- **Badges**: Achievement badges awarded automatically based on user activity
- **Leaderboard**: Public ranking of top contributors
- **Email Notifications**: Automatic badge award emails (placeholder for SMTP integration)

## Features

### 1. Points System

Users earn points through the following activities:

| Action | Points |
|--------|--------|
| Submit a report | 10 points |
| Report gets verified | 50 points (bonus) |

Points are tracked in the `point_history` table for full transparency.

### 2. Badges

Badges are automatically awarded when users meet certain criteria:

#### Verified Reporter
- **Requirement**: 5 verified reports
- **Tier**: Silver (2)
- **Description**: Earned after 5 verified reports

#### Power User - Bronze
- **Requirement**: 10 total reports
- **Tier**: Bronze (1)
- **Description**: Submitted 10 reports

#### Power User - Silver
- **Requirement**: 25 total reports
- **Tier**: Silver (2)
- **Description**: Submitted 25 reports

#### Power User - Gold
- **Requirement**: 50 total reports
- **Tier**: Gold (3)
- **Description**: Submitted 50 reports

### 3. Leaderboard

The leaderboard displays:
- User rank based on total points
- Total reports submitted
- Verified reports count
- Badges earned
- Verified Reporter status

Access the leaderboard at: `GET /leaderboard`

### 4. User Statistics

Detailed user statistics available at: `GET /users/{user_id}/stats`

Returns:
- Total points
- Total reports
- Verified reports
- All earned badges
- Recent point history
- Current leaderboard rank

## Database Schema

### New Tables

#### `users`
Stores user information and gamification stats:
- `id`: Primary key
- `email`: Unique email address
- `username`: Unique username
- `hashed_password`: Bcrypt hashed password
- `total_points`: Accumulated points
- `total_reports`: Count of all reports
- `verified_reports`: Count of verified reports
- `is_verified_reporter`: Badge status flag
- Timestamps: `created_at`, `updated_at`, `last_login`

#### `badges`
Badge definitions:
- `id`: Primary key
- `slug`: Unique identifier
- `name`: Display name
- `description`: Badge description
- `icon`: Icon name/URL
- `requirement_type`: Criteria type (verified_reports, total_reports, power_user)
- `requirement_value`: Threshold to earn
- `color`: Display color (hex)
- `tier`: Badge tier (1=bronze, 2=silver, 3=gold)

#### `user_badges`
Tracks badge awards:
- `id`: Primary key
- `user_id`: Foreign key to users
- `badge_id`: Foreign key to badges
- `earned_at`: Timestamp of award
- `email_sent`: Email notification status
- `email_sent_at`: Timestamp of email

#### `point_history`
Transaction log for points:
- `id`: Primary key
- `user_id`: Foreign key to users
- `points`: Points awarded (can be negative)
- `action`: Action type (report_submitted, report_verified, bonus)
- `description`: Human-readable description
- `report_id`: Foreign key to crowd_reports (optional)
- `created_at`: Timestamp

### Modified Tables

#### `crowd_reports`
Added fields:
- `user_id`: Foreign key to users (optional, for registered users)
- `is_verified`: Boolean flag for verification status

## API Endpoints

### GET /leaderboard
Get the leaderboard with top users.

**Query Parameters:**
- `limit` (optional): Max entries to return (default: 100)
- `offset` (optional): Pagination offset (default: 0)
- `user_id` (optional): Include specific user's rank

**Response:**
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "user_id": 4,
      "username": "diana_champion",
      "total_points": 3350,
      "total_reports": 75,
      "verified_reports": 60,
      "is_verified_reporter": true,
      "badges_count": 4
    }
  ],
  "total_users": 10,
  "current_user_rank": null
}
```

### GET /users/{user_id}/stats
Get detailed statistics for a specific user.

**Response:**
```json
{
  "user_id": 1,
  "username": "alice_reporter",
  "email": "alice@example.com",
  "total_points": 2250,
  "total_reports": 50,
  "verified_reports": 35,
  "is_verified_reporter": true,
  "badges": [
    {
      "id": 1,
      "badge": {
        "id": 1,
        "slug": "verified-reporter",
        "name": "Verified Reporter",
        "description": "Earned after 5 verified reports",
        "icon": "shield-check",
        "color": "#3b82f6",
        "tier": 2,
        "requirement_type": "verified_reports",
        "requirement_value": 5
      },
      "earned_at": "2025-11-18T20:00:00"
    }
  ],
  "recent_points": [
    {
      "points": 50,
      "action": "report_verified",
      "description": "Bonus points for verified report",
      "created_at": "2025-11-18T19:30:00"
    }
  ],
  "rank": 3
}
```

### GET /badges
Get all available badge definitions.

**Response:**
```json
{
  "badges": [
    {
      "id": 1,
      "slug": "verified-reporter",
      "name": "Verified Reporter",
      "description": "Earned after 5 verified reports",
      "icon": "shield-check",
      "color": "#3b82f6",
      "tier": 2,
      "requirement_type": "verified_reports",
      "requirement_value": 5
    }
  ]
}
```

## Frontend Dashboard

### Leaderboard Page

Access at: `/leaderboard` in the admin dashboard

Features:
- Real-time leaderboard with top 100 users
- Visual ranking indicators (trophies for top 3)
- Statistics cards showing total users, active players, badges, and verified reporters
- Badge showcase displaying all available badges
- Color-coded rank badges
- Responsive design with Tailwind CSS

### Navigation

The Leaderboard link has been added to the sidebar navigation with a Trophy icon.

## Setup & Initialization

### 1. Run Database Migration

```bash
# Apply the gamification migration
alembic upgrade head
```

This creates the new tables: `users`, `badges`, `user_badges`, and `point_history`.

### 2. Initialize Badges and Test Data

```bash
# Run the initialization script
python scripts/init_gamification.py
```

This script:
1. Creates default badge definitions
2. Creates 10 test users with varying activity levels
3. Generates test reports (linked to users)
4. Awards points and badges automatically
5. Displays the leaderboard

Test users created:
- `henry_top` - 90 reports, 70 verified (top performer)
- `diana_champion` - 75 reports, 60 verified
- `alice_reporter` - 50 reports, 35 verified
- `grace_power` - 40 reports, 25 verified
- `bob_active` - 30 reports, 20 verified
- `iris_steady` - 20 reports, 15 verified
- `eve_casual` - 15 reports, 10 verified
- `jack_explorer` - 12 reports, 8 verified
- `charlie_newbie` - 5 reports, 2 verified
- `frank_beginner` - 3 reports, 1 verified

All test users have password: `password123`

## Service Layer

### GamificationService

Located in `app/gamification.py`, provides:

#### Methods:
- `award_points()`: Award points to a user
- `award_report_points()`: Award points for report submission
- `award_verification_points()`: Award bonus points for verified reports
- `check_and_award_badges()`: Check and award eligible badges
- `get_leaderboard()`: Get ranked user list
- `get_user_rank()`: Get a user's current rank
- `get_user_badges()`: Get all badges earned by a user
- `get_recent_point_history()`: Get recent point transactions
- `send_badge_email()`: Send badge notification email (placeholder)
- `initialize_default_badges()`: Create default badge definitions

## Email Notifications

Email notifications for badge awards are implemented as a placeholder in the `send_badge_email()` method.

To enable actual emails, integrate an SMTP service:

### Options:
1. **SMTP Server**: Use Python's `smtplib` with Gmail, SendGrid, or AWS SES
2. **Email Service API**: SendGrid, Mailgun, or AWS SES API
3. **Background Tasks**: Use Celery + Redis for async email sending

### Implementation Example:

```python
import smtplib
from email.mime.text import MIMEText

def send_badge_email(user_email, badge_name):
    msg = MIMEText(f"Congratulations! You earned the {badge_name} badge!")
    msg['Subject'] = f'New Badge Earned: {badge_name}'
    msg['From'] = 'noreply@trashalert.com'
    msg['To'] = user_email

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('your_email@gmail.com', 'your_password')
        server.send_message(msg)
```

## Testing

### Manual Testing

1. Start the API:
```bash
uvicorn app.main:app --reload
```

2. Access endpoints:
- Leaderboard: http://localhost:8000/leaderboard
- Badges: http://localhost:8000/badges
- User Stats: http://localhost:8000/users/1/stats

3. Access the admin dashboard:
```bash
cd frontend/admin-dashboard
npm install
npm run dev
```

Navigate to http://localhost:5173/leaderboard

### Automated Testing

Add tests in `tests/test_gamification.py`:

```python
def test_award_points(db):
    user = create_test_user(db)
    GamificationService.award_points(db, user.id, 100, "test", "Test points")

    user = db.query(User).filter(User.id == user.id).first()
    assert user.total_points == 100

def test_badge_award(db):
    user = create_test_user(db)
    user.verified_reports = 5
    db.commit()

    badges = GamificationService.check_and_award_badges(db, user.id)
    assert len(badges) > 0
```

## Future Enhancements

### Potential Features:
1. **Streak Bonuses**: Award bonus points for consecutive days of reporting
2. **Seasonal Challenges**: Time-limited achievement events
3. **Team Competitions**: Neighborhood or city-based team rankings
4. **Social Features**: Share achievements on social media
5. **Reward Redemption**: Exchange points for rewards or recognition
6. **Admin Dashboard**: Badge management and custom badge creation
7. **Notifications**: Real-time notifications for points and badges
8. **Analytics**: Detailed user engagement analytics

## Troubleshooting

### Common Issues:

**Migration fails:**
```bash
# Check current migration status
alembic current

# If needed, reset and rerun
alembic downgrade base
alembic upgrade head
```

**Test data not appearing:**
```bash
# Ensure addresses exist first
python scripts/init_database.py

# Then run gamification init
python scripts/init_gamification.py
```

**Frontend not showing leaderboard:**
- Check API is running: http://localhost:8000/leaderboard
- Check CORS settings in `main.py`
- Verify API_BASE_URL in frontend `.env` file

## Credits

Gamification module implemented as part of TrashAlert enhancement initiative to increase user engagement and data quality through community incentivization.
