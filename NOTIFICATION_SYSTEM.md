# TrashAlert Notification System

Complete notification system for sending trash pickup reminders via SMS and email.

## Features

- SMS notifications via Twilio
- Email notifications via SendGrid
- User subscription management
- Address-specific reminders
- Customizable notification timing
- Daily automated cron job scheduler
- Notification logging and tracking

## Architecture

### Components

1. **Models** (`app/models.py`)
   - `User`: User accounts with email/phone
   - `AddressSubscription`: User subscriptions to address reminders
   - `NotificationLog`: Delivery tracking

2. **Services**
   - `NotificationService` (`app/notification_service.py`): Twilio + SendGrid integration
   - `ReminderScheduler` (`app/scheduler_service.py`): APScheduler cron jobs

3. **API Endpoints** (`app/main.py`)
   - User management: `/api/users`
   - Subscription management: `/api/subscriptions`
   - Test notifications: `/api/notifications/test`

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `twilio>=9.0.0` - SMS notifications
- `sendgrid>=6.11.0` - Email notifications
- `APScheduler>=3.10.0` - Task scheduling
- `pytz>=2024.1` - Timezone support

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Required for SMS
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15551234567

# Optional for email
SENDGRID_API_KEY=your_api_key
SENDGRID_FROM_EMAIL=noreply@trashalert.app
```

Get credentials:
- Twilio: https://console.twilio.com/
- SendGrid: https://app.sendgrid.com/settings/api_keys

### 3. Run Database Migration

```bash
alembic upgrade head
```

This creates the new tables:
- `users`
- `address_subscriptions`
- `notification_logs`

### 4. Start the Application

```bash
uvicorn app.main:app --reload
```

The scheduler will start automatically and run hourly checks for notifications.

## Usage

### Quick Test with Demo Script

```bash
python scripts/test_notification_demo.py
```

This interactive script will:
1. Create a demo user
2. Create a subscription
3. Send a test SMS notification
4. Optionally send a test email

### API Examples

#### 1. Create a User

```bash
curl -X POST "http://localhost:8000/api/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "phone": "+15551234567",
    "display_name": "John Doe",
    "timezone": "America/Los_Angeles"
  }'
```

Response:
```json
{
  "id": 1,
  "email": "user@example.com",
  "phone": "+15551234567",
  "display_name": "John Doe",
  "timezone": "America/Los_Angeles",
  "is_active": true,
  "created_at": "2025-11-18T20:00:00Z"
}
```

#### 2. Create a Subscription

```bash
curl -X POST "http://localhost:8000/api/subscriptions?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, San Diego, CA 92101",
    "notify_trash": true,
    "notify_recycling": true,
    "notify_green": false,
    "notify_email": true,
    "notify_sms": true,
    "days_before": 1,
    "notification_time": "18:00"
  }'
```

Response:
```json
{
  "id": 1,
  "user_id": 1,
  "address_id": 123,
  "address": "123 MAIN ST SAN DIEGO CA 92101",
  "notify_trash": true,
  "notify_recycling": true,
  "notify_green": false,
  "notify_email": true,
  "notify_sms": true,
  "days_before": 1,
  "notification_time": "18:00",
  "is_active": true,
  "created_at": "2025-11-18T20:00:00Z"
}
```

#### 3. Send Test Notification

```bash
curl -X POST "http://localhost:8000/api/notifications/test?user_id=1" \
  -H "Content-Type: application/json" \
  -d '{
    "notification_type": "trash",
    "channel": "sms",
    "address": "123 Main St, San Diego, CA 92101"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Test SMS sent to +15551234567",
  "sms_result": {
    "status": "sent",
    "external_id": "SM1234567890abcdef",
    "sent_at": "2025-11-18T20:00:00Z"
  }
}
```

#### 4. List User Subscriptions

```bash
curl "http://localhost:8000/api/subscriptions?user_id=1"
```

#### 5. Update Subscription

```bash
curl -X PUT "http://localhost:8000/api/subscriptions/1" \
  -H "Content-Type: application/json" \
  -d '{
    "notify_sms": false,
    "days_before": 2
  }'
```

#### 6. Delete Subscription

```bash
curl -X DELETE "http://localhost:8000/api/subscriptions/1"
```

## How the Scheduler Works

The `ReminderScheduler` runs hourly (6 AM - 9 PM) to check for notifications:

1. **Hourly Check**: Every hour, the scheduler queries all active subscriptions
2. **Timezone Conversion**: Converts current UTC time to each user's timezone
3. **Time Matching**: Checks if current hour matches user's `notification_time`
4. **Date Calculation**: Calculates target pickup date based on `days_before`
5. **Day Matching**: Checks if target date matches address pickup schedule
6. **Notification Sending**: Sends SMS/email based on user preferences
7. **Logging**: Records all notifications in `notification_logs` table

Example:
- User has `notification_time = "18:00"` and `days_before = 1`
- Scheduler runs at 6:00 PM user's local time
- Checks if tomorrow matches trash/recycling/green pickup days
- Sends notifications for matching pickup types

## Database Schema

### users
```sql
- id (PK)
- email (unique)
- phone
- display_name
- timezone
- is_active
- created_at
- updated_at
```

### address_subscriptions
```sql
- id (PK)
- user_id (FK -> users.id)
- address_id (FK -> addresses.id)
- notify_trash
- notify_recycling
- notify_green
- notify_email
- notify_sms
- days_before (0-7)
- notification_time (HH:MM)
- is_active
- created_at
- updated_at
```

### notification_logs
```sql
- id (PK)
- user_id (FK -> users.id)
- subscription_id (FK -> address_subscriptions.id)
- notification_type (trash/recycling/green)
- channel (email/sms)
- recipient
- subject
- message_body
- status (pending/sent/failed/delivered)
- external_id (Twilio SID or SendGrid ID)
- error_message
- scheduled_for
- sent_at
- created_at
```

## Notification Templates

### SMS Template
```
TrashAlert Reminder: {pickup_type} pickup for {address} is scheduled for {pickup_day}. Don't forget to put your bin out!
```

### Email Template
HTML email with:
- Header with TrashAlert branding
- Pickup type and date highlighted
- Address information
- Footer with unsubscribe info

## Configuration Options

### Subscription Settings

- `notify_trash/recycling/green`: Which pickup types to notify about
- `notify_email/sms`: Which channels to use
- `days_before`: How many days before pickup to send notification (0-7)
  - 0 = day of pickup
  - 1 = day before (most common)
  - 2+ = multiple days before
- `notification_time`: Time to send notifications in HH:MM format (user's local time)

### User Settings

- `timezone`: User's timezone (default: America/Los_Angeles)
- Used to send notifications at correct local time

## Monitoring & Logging

All notifications are logged to `notification_logs` table with:
- Delivery status
- External provider IDs (for tracking)
- Error messages if delivery fails
- Timestamps for scheduling and sending

Query recent notifications:
```sql
SELECT * FROM notification_logs
WHERE user_id = 1
ORDER BY created_at DESC
LIMIT 10;
```

Check failed notifications:
```sql
SELECT * FROM notification_logs
WHERE status = 'failed'
ORDER BY created_at DESC;
```

## Troubleshooting

### SMS Not Sending

1. Check Twilio credentials in `.env`
2. Verify phone number is in E.164 format (+1XXXXXXXXXX)
3. Check Twilio console for account status
4. Review logs: `grep "SMS" app.log`

### Email Not Sending

1. Check SendGrid API key in `.env`
2. Verify sender email is verified in SendGrid
3. Check SendGrid activity logs
4. Review logs: `grep "Email" app.log`

### Scheduler Not Running

1. Check application logs for "Notification scheduler started"
2. Verify no errors during startup
3. Check scheduler is running: Look for hourly log entries
4. Restart application if needed

### No Notifications Received

1. Verify subscription is active: `is_active = true`
2. Check notification preferences are enabled
3. Verify address has pickup schedule data
4. Check user's timezone and notification_time
5. Review notification_logs for delivery status

## API Documentation

Full API documentation available at:
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Future Enhancements

Potential improvements:
- [ ] Push notifications for mobile apps
- [ ] WhatsApp integration
- [ ] Notification preferences by pickup type
- [ ] Multi-language support
- [ ] Holiday/exception handling
- [ ] Notification delivery analytics dashboard
- [ ] Webhook for delivery status callbacks
- [ ] Rate limiting per user
- [ ] Batch notification processing for performance

## Testing

Run tests:
```bash
pytest tests/test_notification_service.py
pytest tests/test_scheduler.py
```

## Success Criteria

The notification system meets all success criteria:

✅ Twilio SMS integration implemented
✅ SendGrid email integration implemented
✅ Users can subscribe to general reminders
✅ Users can subscribe to specific address reminders
✅ Daily cron job sends reminders automatically
✅ **Demo script sends SMS reminder successfully**

## License

Same as main TrashAlert project.
