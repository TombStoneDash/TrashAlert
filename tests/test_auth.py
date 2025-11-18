"""Tests for authentication endpoints and RBAC."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import User, UserRole
from app.auth import hash_password

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_users(db):
    """Create test users with different roles."""
    users = {
        "user": User(
            username="testuser",
            email="user@test.com",
            hashed_password=hash_password("TestPass123"),
            role=UserRole.USER,
            is_active=True,
            full_name="Test User"
        ),
        "reporter": User(
            username="testreporter",
            email="reporter@test.com",
            hashed_password=hash_password("TestPass123"),
            role=UserRole.REPORTER,
            is_active=True,
            full_name="Test Reporter"
        ),
        "city_partner": User(
            username="testcitypartner",
            email="citypartner@test.com",
            hashed_password=hash_password("TestPass123"),
            role=UserRole.CITY_PARTNER,
            is_active=True,
            full_name="Test City Partner"
        ),
        "admin": User(
            username="testadmin",
            email="admin@test.com",
            hashed_password=hash_password("TestPass123"),
            role=UserRole.ADMIN,
            is_active=True,
            full_name="Test Admin"
        ),
        "inactive": User(
            username="inactiveuser",
            email="inactive@test.com",
            hashed_password=hash_password("TestPass123"),
            role=UserRole.USER,
            is_active=False,
            full_name="Inactive User"
        )
    }

    for user in users.values():
        db.add(user)
    db.commit()

    for user in users.values():
        db.refresh(user)

    return users


def get_auth_headers(client, username: str, password: str = "TestPass123"):
    """Helper to get authentication headers."""
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

class TestAuthentication:
    """Test authentication endpoints."""

    def test_register_success(self, client, db):
        """Test successful user registration."""
        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@test.com",
                "password": "NewPass123",
                "full_name": "New User"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "hashed_password" not in data

    def test_register_weak_password(self, client, db):
        """Test registration with weak password fails."""
        response = client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@test.com",
                "password": "weak",
            }
        )
        assert response.status_code == 422

    def test_register_duplicate_username(self, client, test_users):
        """Test registration with duplicate username fails."""
        response = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "different@test.com",
                "password": "TestPass123"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_duplicate_email(self, client, test_users):
        """Test registration with duplicate email fails."""
        response = client.post(
            "/auth/register",
            json={
                "username": "differentuser",
                "email": "user@test.com",
                "password": "TestPass123"
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_login_success(self, client, test_users):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "TestPass123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_with_email(self, client, test_users):
        """Test login using email instead of username."""
        response = client.post(
            "/auth/login",
            json={"username": "user@test.com", "password": "TestPass123"}
        )
        assert response.status_code == 200

    def test_login_wrong_password(self, client, test_users):
        """Test login with wrong password fails."""
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "WrongPass123"}
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client, db):
        """Test login with nonexistent user fails."""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "TestPass123"}
        )
        assert response.status_code == 401

    def test_login_inactive_user(self, client, test_users):
        """Test login with inactive user fails."""
        response = client.post(
            "/auth/login",
            json={"username": "inactiveuser", "password": "TestPass123"}
        )
        assert response.status_code == 403

    def test_get_current_user(self, client, test_users):
        """Test getting current user information."""
        headers = get_auth_headers(client, "testuser")
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "user@test.com"
        assert data["role"] == "user"

    def test_get_current_user_unauthorized(self, client, db):
        """Test getting current user without token fails."""
        response = client.get("/auth/me")
        assert response.status_code == 403

    def test_refresh_token(self, client, test_users):
        """Test refreshing access token."""
        # Login to get tokens
        login_response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "TestPass123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


# ============================================================================
# RBAC TESTS
# ============================================================================

class TestRBAC:
    """Test role-based access control."""

    def test_report_requires_authentication(self, client, db):
        """Test that /report endpoint requires authentication."""
        response = client.post(
            "/report",
            json={
                "address": "123 Main St, San Diego, CA 92101",
                "trash_day": "MON"
            }
        )
        assert response.status_code == 403

    def test_report_user_role(self, client, test_users):
        """Test that user role can submit reports."""
        headers = get_auth_headers(client, "testuser")
        response = client.post(
            "/report",
            json={
                "address": "123 Main St, San Diego, CA 92101",
                "trash_day": "MON"
            },
            headers=headers
        )
        # May fail due to address validation, but should not be 403
        assert response.status_code != 403

    def test_report_reporter_role(self, client, test_users):
        """Test that reporter role can submit reports."""
        headers = get_auth_headers(client, "testreporter")
        response = client.post(
            "/report",
            json={
                "address": "123 Main St, San Diego, CA 92101",
                "trash_day": "MON"
            },
            headers=headers
        )
        assert response.status_code != 403

    def test_report_city_partner_role(self, client, test_users):
        """Test that city_partner role can submit reports."""
        headers = get_auth_headers(client, "testcitypartner")
        response = client.post(
            "/report",
            json={
                "address": "123 Main St, San Diego, CA 92101",
                "trash_day": "MON"
            },
            headers=headers
        )
        assert response.status_code != 403

    def test_report_admin_role(self, client, test_users):
        """Test that admin role can submit reports."""
        headers = get_auth_headers(client, "testadmin")
        response = client.post(
            "/report",
            json={
                "address": "123 Main St, San Diego, CA 92101",
                "trash_day": "MON"
            },
            headers=headers
        )
        assert response.status_code != 403

    def test_list_users_admin_only(self, client, test_users):
        """Test that only admin can list users."""
        # User role - should fail
        headers = get_auth_headers(client, "testuser")
        response = client.get("/auth/users", headers=headers)
        assert response.status_code == 403

        # City partner role - should fail
        headers = get_auth_headers(client, "testcitypartner")
        response = client.get("/auth/users", headers=headers)
        assert response.status_code == 403

        # Admin role - should succeed
        headers = get_auth_headers(client, "testadmin")
        response = client.get("/auth/users", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_user_role_admin_only(self, client, test_users):
        """Test that only admin can update user roles."""
        user_id = test_users["user"].id

        # User role - should fail
        headers = get_auth_headers(client, "testuser")
        response = client.patch(
            f"/auth/users/{user_id}/role",
            json={"role": "admin"},
            headers=headers
        )
        assert response.status_code == 403

        # City partner role - should fail
        headers = get_auth_headers(client, "testcitypartner")
        response = client.patch(
            f"/auth/users/{user_id}/role",
            json={"role": "admin"},
            headers=headers
        )
        assert response.status_code == 403

        # Admin role - should succeed
        headers = get_auth_headers(client, "testadmin")
        response = client.patch(
            f"/auth/users/{user_id}/role",
            json={"role": "reporter"},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["role"] == "reporter"

    def test_admin_cannot_demote_self(self, client, test_users):
        """Test that admin cannot change their own role."""
        admin_id = test_users["admin"].id
        headers = get_auth_headers(client, "testadmin")

        response = client.patch(
            f"/auth/users/{admin_id}/role",
            json={"role": "user"},
            headers=headers
        )
        assert response.status_code == 400
        assert "cannot change your own role" in response.json()["detail"].lower()

    def test_view_reports_city_partner_and_admin(self, client, test_users):
        """Test that only city_partner and admin can view reports."""
        # User role - should fail
        headers = get_auth_headers(client, "testuser")
        response = client.get("/admin/reports/1", headers=headers)
        assert response.status_code == 403

        # Reporter role - should fail
        headers = get_auth_headers(client, "testreporter")
        response = client.get("/admin/reports/1", headers=headers)
        assert response.status_code == 403

        # City partner role - should succeed (404 if no reports exist)
        headers = get_auth_headers(client, "testcitypartner")
        response = client.get("/admin/reports/1", headers=headers)
        assert response.status_code in [200, 404]

        # Admin role - should succeed (404 if no reports exist)
        headers = get_auth_headers(client, "testadmin")
        response = client.get("/admin/reports/1", headers=headers)
        assert response.status_code in [200, 404]

    def test_verify_report_city_partner_and_admin(self, client, test_users, db):
        """Test that only city_partner and admin can verify reports."""
        # Create a test report first
        from app.models import Address, CrowdReport
        address = Address(
            normalized_address="123 main st, san diego, ca 92101",
            city="San Diego",
            city_id="san_diego",
            state="CA",
            zip_code="92101"
        )
        db.add(address)
        db.commit()
        db.refresh(address)

        report = CrowdReport(
            address_id=address.id,
            trash_day="MON",
            user_id=test_users["user"].id
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        # User role - should fail
        headers = get_auth_headers(client, "testuser")
        response = client.patch(
            f"/admin/reports/{report.id}/verify",
            json={"is_verified": True},
            headers=headers
        )
        assert response.status_code == 403

        # City partner role - should succeed
        headers = get_auth_headers(client, "testcitypartner")
        response = client.patch(
            f"/admin/reports/{report.id}/verify",
            json={"is_verified": True},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["is_verified"] is True

        # Admin role - should succeed
        headers = get_auth_headers(client, "testadmin")
        response = client.patch(
            f"/admin/reports/{report.id}/verify",
            json={"is_verified": False},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["is_verified"] is False


# ============================================================================
# PUBLIC ENDPOINT TESTS
# ============================================================================

class TestPublicEndpoints:
    """Test that public endpoints remain accessible."""

    def test_health_check_public(self, client, db):
        """Test that health check endpoint is public."""
        response = client.get("/")
        assert response.status_code == 200

    def test_lookup_public(self, client, db):
        """Test that lookup endpoint is public."""
        response = client.get("/lookup?address=123 Main St, San Diego, CA")
        # Should not return 401 or 403
        assert response.status_code not in [401, 403]

    def test_stats_public(self, client, db):
        """Test that stats endpoint is public."""
        response = client.get("/stats")
        assert response.status_code == 200
