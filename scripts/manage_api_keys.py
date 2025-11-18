#!/usr/bin/env python3
"""CLI utility for managing TrashAlert API keys.

Usage:
    python scripts/manage_api_keys.py create --name "iOS App v1.0" --description "Production iOS app"
    python scripts/manage_api_keys.py list
    python scripts/manage_api_keys.py revoke --prefix "ta_abc123"
    python scripts/manage_api_keys.py stats --prefix "ta_abc123"
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.api_key_auth import create_api_key, validate_api_key, hash_api_key
from app.models import ApiKey, ApiKeyUsage


def create_key(
    name: str,
    description: Optional[str] = None,
    scopes: Optional[str] = None,
    rpm: int = 30,
    rph: int = 500,
    expires_days: Optional[int] = None
):
    """Create a new API key."""
    db = SessionLocal()
    try:
        # Parse scopes
        scope_list = None
        if scopes:
            scope_list = [s.strip() for s in scopes.split(",")]

        # Create key
        full_key, api_key_record = create_api_key(
            db=db,
            name=name,
            description=description,
            scopes=scope_list,
            rate_limit_per_minute=rpm,
            rate_limit_per_hour=rph,
            expires_in_days=expires_days,
            created_by="CLI"
        )

        print("=" * 80)
        print("API KEY CREATED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nAPI Key: {full_key}")
        print("\n⚠️  IMPORTANT: Save this key now! It won't be shown again.")
        print("=" * 80)
        print(f"\nKey Details:")
        print(f"  ID: {api_key_record.id}")
        print(f"  Prefix: {api_key_record.key_prefix}")
        print(f"  Name: {api_key_record.name}")
        print(f"  Description: {api_key_record.description or 'N/A'}")
        print(f"  Scopes: {', '.join(api_key_record.scopes or [])}")
        print(f"  Rate Limits: {rpm}/min, {rph}/hour")
        if api_key_record.expires_at:
            print(f"  Expires: {api_key_record.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            print(f"  Expires: Never")
        print(f"  Created: {api_key_record.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 80)

    finally:
        db.close()


def list_keys():
    """List all API keys."""
    db = SessionLocal()
    try:
        keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()

        if not keys:
            print("No API keys found.")
            return

        print("=" * 120)
        print(f"{'ID':<5} {'Prefix':<12} {'Name':<25} {'Active':<8} {'Scopes':<30} {'Requests':<10} {'Last Used':<20}")
        print("=" * 120)

        for key in keys:
            active = "✓" if key.is_active else "✗"
            scopes = ", ".join(key.scopes or [])[:28] + "..." if key.scopes and len(", ".join(key.scopes)) > 30 else ", ".join(key.scopes or [])
            last_used = key.last_used_at.strftime("%Y-%m-%d %H:%M") if key.last_used_at else "Never"

            print(f"{key.id:<5} {key.key_prefix:<12} {key.name:<25} {active:<8} {scopes:<30} {key.total_requests:<10} {last_used:<20}")

        print("=" * 120)

    finally:
        db.close()


def revoke_key(prefix: str):
    """Revoke an API key by prefix."""
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_prefix == prefix).first()

        if not key:
            print(f"❌ No API key found with prefix: {prefix}")
            return

        key.is_active = False
        db.commit()

        print(f"✓ API key revoked: {key.name} ({key.key_prefix})")

    finally:
        db.close()


def activate_key(prefix: str):
    """Activate a revoked API key."""
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_prefix == prefix).first()

        if not key:
            print(f"❌ No API key found with prefix: {prefix}")
            return

        key.is_active = True
        db.commit()

        print(f"✓ API key activated: {key.name} ({key.key_prefix})")

    finally:
        db.close()


def show_stats(prefix: str):
    """Show usage statistics for an API key."""
    db = SessionLocal()
    try:
        key = db.query(ApiKey).filter(ApiKey.key_prefix == prefix).first()

        if not key:
            print(f"❌ No API key found with prefix: {prefix}")
            return

        print("=" * 80)
        print(f"API KEY STATISTICS: {key.name}")
        print("=" * 80)
        print(f"\nKey Details:")
        print(f"  ID: {key.id}")
        print(f"  Prefix: {key.key_prefix}")
        print(f"  Active: {'Yes' if key.is_active else 'No'}")
        print(f"  Total Requests: {key.total_requests or 0}")
        print(f"  Last Used: {key.last_used_at.strftime('%Y-%m-%d %H:%M:%S UTC') if key.last_used_at else 'Never'}")
        print(f"  Created: {key.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        # Recent usage
        recent_usage = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key.id
        ).order_by(ApiKeyUsage.created_at.desc()).limit(10).all()

        if recent_usage:
            print(f"\nRecent Usage (last 10 requests):")
            print(f"  {'Endpoint':<20} {'Method':<8} {'Status':<8} {'Time (ms)':<12} {'Timestamp':<20}")
            print(f"  {'-' * 75}")
            for usage in recent_usage:
                timestamp = usage.created_at.strftime("%Y-%m-%d %H:%M:%S") if usage.created_at else "N/A"
                print(f"  {usage.endpoint:<20} {usage.method:<8} {usage.status_code:<8} {usage.response_time_ms:<12.2f} {timestamp:<20}")

        # Endpoint breakdown
        from sqlalchemy import func
        endpoint_stats = db.query(
            ApiKeyUsage.endpoint,
            func.count(ApiKeyUsage.id).label('count'),
            func.avg(ApiKeyUsage.response_time_ms).label('avg_time')
        ).filter(
            ApiKeyUsage.api_key_id == key.id
        ).group_by(ApiKeyUsage.endpoint).all()

        if endpoint_stats:
            print(f"\nEndpoint Breakdown:")
            print(f"  {'Endpoint':<20} {'Requests':<12} {'Avg Time (ms)':<15}")
            print(f"  {'-' * 50}")
            for endpoint, count, avg_time in endpoint_stats:
                print(f"  {endpoint:<20} {count:<12} {avg_time:<15.2f}")

        print("=" * 80)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Manage TrashAlert API keys")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new API key")
    create_parser.add_argument("--name", required=True, help="Name for the API key")
    create_parser.add_argument("--description", help="Description of the API key")
    create_parser.add_argument("--scopes", help="Comma-separated scopes (default: mobile:lookup,mobile:report)")
    create_parser.add_argument("--rpm", type=int, default=30, help="Requests per minute (default: 30)")
    create_parser.add_argument("--rph", type=int, default=500, help="Requests per hour (default: 500)")
    create_parser.add_argument("--expires-days", type=int, help="Days until expiration (default: never)")

    # List command
    list_parser = subparsers.add_parser("list", help="List all API keys")

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("--prefix", required=True, help="API key prefix (e.g., ta_abc123)")

    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate a revoked API key")
    activate_parser.add_argument("--prefix", required=True, help="API key prefix (e.g., ta_abc123)")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show API key usage statistics")
    stats_parser.add_argument("--prefix", required=True, help="API key prefix (e.g., ta_abc123)")

    args = parser.parse_args()

    if args.command == "create":
        create_key(
            name=args.name,
            description=args.description,
            scopes=args.scopes,
            rpm=args.rpm,
            rph=args.rph,
            expires_days=args.expires_days
        )
    elif args.command == "list":
        list_keys()
    elif args.command == "revoke":
        revoke_key(args.prefix)
    elif args.command == "activate":
        activate_key(args.prefix)
    elif args.command == "stats":
        show_stats(args.prefix)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
