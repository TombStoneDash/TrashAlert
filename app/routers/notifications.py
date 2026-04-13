"""Tenant notification signup — email capture per address for weekly reminders."""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["notifications"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SIGNUPS_PATH = DATA_DIR / "notification_signups.json"


class NotificationSignup(BaseModel):
    email: str = Field(..., description="Tenant email address")
    address: str = Field(..., description="Street address for reminders")
    city: str = Field("san_diego", description="City slug")


def _load_signups() -> list[dict]:
    if SIGNUPS_PATH.exists():
        return json.loads(SIGNUPS_PATH.read_text(encoding="utf-8"))
    return []


def _save_signups(signups: list[dict]):
    SIGNUPS_PATH.write_text(
        json.dumps(signups, indent=2),
        encoding="utf-8",
    )


@router.post("/notifications/signup")
async def signup_for_reminders(req: NotificationSignup):
    """Sign up for weekly pickup reminders for a specific address.

    Stores the email + address pair. In production, this would trigger
    a weekly cron job that sends reminders the day before pickup.
    """
    signups = _load_signups()

    # Check for duplicate
    for s in signups:
        if s["email"] == req.email and s["address"].upper() == req.address.upper():
            return {"status": "already_subscribed", "message": "You're already signed up for this address."}

    signups.append({
        "email": req.email,
        "address": req.address,
        "city": req.city,
        "created_at": datetime.utcnow().isoformat(),
    })

    _save_signups(signups)
    logger.info(f"New notification signup: {req.email} for {req.address}")

    return {
        "status": "subscribed",
        "message": f"You'll receive weekly pickup reminders for {req.address}.",
    }


@router.get("/notifications/count")
async def signup_count():
    """Return total notification signups (for admin dashboard)."""
    signups = _load_signups()
    return {"total_signups": len(signups)}
