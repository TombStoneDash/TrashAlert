# Role-Based Access Control (RBAC) Implementation

## Overview

TrashAlert API now implements comprehensive JWT-based authentication and role-based access control (RBAC) to secure endpoints and manage user permissions.

## Authentication

### JWT Authentication

The API uses JSON Web Tokens (JWT) for authentication:

- **Access Token**: Short-lived token (30 minutes) for API requests
- **Refresh Token**: Long-lived token (7 days) for obtaining new access tokens
- **Token Type**: Bearer token passed in Authorization header

### Security Features

- Passwords hashed with bcrypt
- Strong password requirements (min 8 chars, uppercase, lowercase, digit)
- Token expiration and validation
- Active user verification
- Secure token signing with configurable secret key

## User Roles

The system supports four distinct roles with different permission levels:

### 1. User (`user`)
**Default role for new registrations**

**Permissions:**
- Submit trash pickup reports
- Look up trash schedules
- View public statistics
- Update own profile

**Use Case:** Regular citizens contributing crowdsourced data

### 2. Reporter (`reporter`)
**Enhanced user role**

**Permissions:**
- All `user` permissions
- Same as user role (reserved for future enhancements)

**Use Case:** Verified community reporters or frequent contributors

### 3. City Partner (`city_partner`)
**Municipal partner role**

**Permissions:**
- All `user` permissions
- View detailed reports for addresses
- Verify/unverify crowdsourced reports
- List all reports with filters

**Use Case:** City officials validating crowdsourced data

### 4. Admin (`admin`)
**Full system access**

**Permissions:**
- All `city_partner` permissions
- List all users
- Change user roles
- View sensitive data (IP addresses)
- Full system administration

**Use Case:** System administrators and platform maintainers

## API Endpoints

### Public Endpoints (No Authentication Required)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/stats` | GET | Database statistics |
| `/lookup` | GET | Look up trash schedule |
| `/auth/register` | POST | User registration |
| `/auth/login` | POST | User login |

### Authenticated Endpoints

#### All Authenticated Users (user, reporter, city_partner, admin)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/me` | GET | Get current user info |
| `/auth/refresh` | POST | Refresh access token |
| `/report` | POST | Submit trash pickup report |

#### City Partners & Admins Only

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/reports/{address_id}` | GET | Get all reports for address |
| `/admin/reports` | GET | List all reports with filters |
| `/admin/reports/{report_id}/verify` | PATCH | Verify/unverify a report |

#### Admins Only

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/users` | GET | List all users |
| `/auth/users/{user_id}/role` | PATCH | Update user role |

## Usage Examples

### 1. Register a New User

```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "full_name": "John Doe"
  }'
```

**Response:**
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "role": "user",
  "full_name": "John Doe",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-01-15T10:30:00Z",
  "last_login_at": null
}
```

### 2. Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "password": "SecurePass123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 3. Submit a Report (Authenticated)

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, San Diego, CA 92101",
    "trash_day": "MON",
    "recycling_day": "THU"
  }'
```

### 4. View Reports (City Partner or Admin)

```bash
curl -X GET "http://localhost:8000/admin/reports/1" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Verify a Report (City Partner or Admin)

```bash
curl -X PATCH "http://localhost:8000/admin/reports/123/verify" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_verified": true
  }'
```

### 6. Update User Role (Admin Only)

```bash
curl -X PATCH "http://localhost:8000/auth/users/1/role" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "city_partner"
  }'
```

### 7. Refresh Access Token

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# JWT Secret Key - Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
JWT_SECRET_KEY=your-secret-key-here

# Token expiration times
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Generating a Secure Secret Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Security Best Practices

1. **Secret Key Management**
   - Never commit JWT_SECRET_KEY to version control
   - Use different keys for development and production
   - Rotate keys periodically in production

2. **Password Requirements**
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one lowercase letter
   - At least one digit
   - Passwords are hashed with bcrypt

3. **Token Security**
   - Access tokens expire after 30 minutes
   - Refresh tokens expire after 7 days
   - Tokens are validated on every request
   - Invalid tokens return 401 Unauthorized

4. **Role Management**
   - Only admins can change user roles
   - Admins cannot demote themselves
   - Role checks happen at endpoint level

## Testing

Run RBAC tests:

```bash
# Run all auth tests
pytest tests/test_auth.py -v

# Run specific test class
pytest tests/test_auth.py::TestRBAC -v

# Run with coverage
pytest tests/test_auth.py --cov=app.auth --cov=app.routers.auth
```

## Database Schema

### User Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    full_name VARCHAR,
    city_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    last_login_at TIMESTAMP
);
```

### Enhanced CrowdReport Table

Reports are now linked to authenticated users:

```sql
ALTER TABLE crowd_reports ADD COLUMN user_id INTEGER;
ALTER TABLE crowd_reports ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE crowd_reports ADD COLUMN verified_by_user_id INTEGER;
ALTER TABLE crowd_reports ADD COLUMN verified_at TIMESTAMP;
```

## Migration Guide

### For Existing Deployments

1. **Update Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   ```bash
   # Generate secret key
   python -c "import secrets; print(secrets.token_urlsafe(32))"

   # Add to .env
   echo "JWT_SECRET_KEY=<generated-key>" >> .env
   ```

3. **Database Migration**
   The new User table and CrowdReport columns will be created automatically on startup.

4. **Create Admin User**
   ```bash
   # Register first user via API
   curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "admin",
       "email": "admin@example.com",
       "password": "AdminPass123"
     }'

   # Manually update role in database
   sqlite3 trashalert.db "UPDATE users SET role='admin' WHERE username='admin';"
   ```

### Backward Compatibility

- Existing `/lookup` and `/stats` endpoints remain public
- `/report` now requires authentication (breaking change)
- `user_hash` field in reports is retained for backward compatibility
- Reports without `user_id` (legacy) are still supported

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 201 | Created (registration) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid credentials/token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 422 | Unprocessable Entity (validation error) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |

## Support

For issues or questions about RBAC implementation:
- Open an issue on GitHub
- Check the API documentation at `/docs`
- Review test cases in `tests/test_auth.py`
