"""Authentication endpoints router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
    UserUpdateRoleRequest
)
from app.auth import (
    hash_password,
    authenticate_user,
    create_user_tokens,
    decode_token,
    get_current_user,
    require_admin
)
from app.logging_config import app_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user.

    Creates a new user account with default 'user' role.

    Args:
        user_data: User registration data (username, email, password)
        db: Database session

    Returns:
        Created user information

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    new_user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=UserRole.USER,
        is_active=True,
        is_verified=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    app_logger.info(f"New user registered: {new_user.username} (ID: {new_user.id})")

    return new_user


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login and receive access and refresh tokens.

    Accepts username or email for login.

    Args:
        login_data: Login credentials (username/email and password)
        db: Database session

    Returns:
        JWT access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = authenticate_user(db, login_data.username, login_data.password)

    if not user:
        app_logger.warning(f"Failed login attempt for: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support."
        )

    # Update last login time
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Create tokens
    tokens = create_user_tokens(user)

    app_logger.info(f"User logged in: {user.username} (ID: {user.id})")

    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Args:
        refresh_data: Refresh token
        db: Database session

    Returns:
        New JWT access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Decode refresh token
    payload = decode_token(refresh_data.refresh_token)

    # Verify token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    # Get user
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Create new tokens
    tokens = create_user_tokens(user)

    app_logger.info(f"Token refreshed for user: {user.username} (ID: {user.id})")

    return TokenResponse(**tokens)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user from token

    Returns:
        Current user information
    """
    return current_user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    List all users (admin only).

    Args:
        skip: Number of users to skip (pagination)
        limit: Maximum number of users to return
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        List of users
    """
    users = db.query(User).offset(skip).limit(limit).all()
    app_logger.info(f"Admin {current_user.username} listed users")
    return users


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_data: UserUpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a user's role (admin only).

    Args:
        user_id: ID of user to update
        role_data: New role data
        db: Database session
        current_user: Current authenticated admin user

    Returns:
        Updated user information

    Raises:
        HTTPException: If user not found or invalid role
    """
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent self-demotion
    if user.id == current_user.id and role_data.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )

    # Update role
    old_role = user.role.value
    user.role = UserRole(role_data.role)
    db.commit()
    db.refresh(user)

    app_logger.info(
        f"Admin {current_user.username} changed role of user {user.username} "
        f"from {old_role} to {role_data.role}"
    )

    return user
