"""Authentication utilities for JWT and password hashing."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.models import User, UserRole

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # 30 minutes
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days

# Security scheme
security = HTTPBearer()


# ============================================================================
# PASSWORD UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# JWT TOKEN UTILITIES
# ============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token (typically user_id, username, role)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Data to encode in the token (typically user_id)

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token from request
        db: Database session

    Returns:
        Current authenticated User object

    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials

    # Decode token
    payload = decode_token(token)

    # Verify token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user_id from token
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current active User object
    """
    return current_user


async def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current user.
    Returns None if no token is provided or token is invalid.
    Used for endpoints that work both authenticated and unauthenticated.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.replace("Bearer ", "")
        payload = decode_token(token)

        # Verify token type
        if payload.get("type") != "access":
            return None

        # Get user_id from token
        user_id: int = payload.get("sub")
        if user_id is None:
            return None

        # Get user from database
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        return user
    except:
        return None


# ============================================================================
# ROLE-BASED ACCESS CONTROL DEPENDENCIES
# ============================================================================

class RoleChecker:
    """
    Dependency class to check if user has required role(s).

    Usage:
        @app.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
        async def admin_endpoint():
            ...
    """

    def __init__(self, allowed_roles: list[str]):
        """
        Initialize role checker.

        Args:
            allowed_roles: List of allowed role names (e.g., ["admin", "city_partner"])
        """
        self.allowed_roles = [role.lower() for role in allowed_roles]

    async def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        """
        Check if current user has one of the allowed roles.

        Args:
            current_user: Current authenticated user

        Returns:
            User object if authorized

        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.role.value.lower() not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(self.allowed_roles)}"
            )
        return current_user


# Convenience dependencies for common role checks
require_admin = RoleChecker(["admin"])
require_city_partner_or_admin = RoleChecker(["city_partner", "admin"])
require_authenticated = RoleChecker(["user", "reporter", "city_partner", "admin"])


# ============================================================================
# AUTHENTICATION HELPERS
# ============================================================================

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user by username/email and password.

    Args:
        db: Database session
        username: Username or email
        password: Plain text password

    Returns:
        User object if authentication succeeds, None otherwise
    """
    # Try to find user by username or email
    user = db.query(User).filter(
        (User.username == username.lower()) | (User.email == username.lower())
    ).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def create_user_tokens(user: User) -> Dict[str, Any]:
    """
    Create access and refresh tokens for a user.

    Args:
        user: User object

    Returns:
        Dictionary with access_token, refresh_token, token_type, and expires_in
    """
    access_token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "role": user.role.value
        }
    )

    refresh_token = create_refresh_token(
        data={"sub": user.id}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    }
