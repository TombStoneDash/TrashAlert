#!/usr/bin/env python3
"""
Example script demonstrating AI schedule classifier usage.

This script shows how to use the AI-powered schedule classifier
both programmatically and via the REST API.
"""

import os
import sys
import json
import requests
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def classify_via_api(text: str, context: Optional[dict] = None, api_url: str = "http://localhost:8000"):
    """
    Classify schedule text using the REST API.

    Args:
        text: Natural language schedule description
        context: Optional context (city, year, etc.)
        api_url: Base URL of the API

    Returns:
        API response as dictionary
    """
    endpoint = f"{api_url}/ai-classify"

    payload = {"text": text}
    if context:
        payload["context"] = context

    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling API: {e}")
        return None


def classify_programmatically(text: str, context: Optional[dict] = None):
    """
    Classify schedule text programmatically (direct function call).

    Args:
        text: Natural language schedule description
        context: Optional context

    Returns:
        List of ClassifiedSchedule objects
    """
    try:
        from app.ai_classifier import classify_schedule_text

        schedules = classify_schedule_text(text, context)
        return [schedule.to_dict() for schedule in schedules]
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure OPENAI_API_KEY environment variable is set")
        return None
    except Exception as e:
        print(f"Classification error: {e}")
        return None


def print_schedule(schedule: dict):
    """Pretty print a schedule object."""
    print(f"\n📅 Schedule:")
    print(f"   Collection Type: {schedule['collection_type']}")
    print(f"   Pickup Day: {schedule['pickup_day']}")
    print(f"   Frequency: {schedule['frequency']}")
    print(f"   Confidence: {schedule['confidence']:.2%}")

    if schedule['exceptions']:
        print(f"   Exceptions:")
        for exc in schedule['exceptions']:
            print(f"      - {exc['reason']} on {exc['exception_date']}")
            if exc['rescheduled_date']:
                print(f"        Rescheduled to: {exc['rescheduled_date']}")
            elif exc['is_cancelled']:
                print(f"        Status: Cancelled")


def main():
    """Run example classifications."""
    print("=" * 70)
    print("AI Schedule Classifier - Example Usage")
    print("=" * 70)

    # Example inputs
    examples = [
        {
            "text": "Trash pickup is every Monday",
            "description": "Simple weekly trash",
        },
        {
            "text": "Recycling on Wednesdays every other week",
            "description": "Biweekly recycling",
        },
        {
            "text": "Garbage on Tuesdays, recycling every other Friday, yard waste on Wednesdays",
            "description": "Multiple collection types",
            "context": {"city": "San Diego"}
        },
        {
            "text": "Garbage collection Thursday mornings, no pickup on Christmas, moved to Friday",
            "description": "Schedule with holiday exception",
        },
        {
            "text": "I think it's Tuesday or maybe Wednesday for trash, not really sure",
            "description": "Uncertain classification",
        }
    ]

    # Try API first, fallback to programmatic
    use_api = True
    api_url = os.getenv("API_URL", "http://localhost:8000")

    # Test API availability
    try:
        response = requests.get(f"{api_url}/", timeout=2)
        if response.status_code != 200:
            print(f"\n⚠️  API not available at {api_url}, using programmatic approach\n")
            use_api = False
    except requests.exceptions.RequestException:
        print(f"\n⚠️  API not available at {api_url}, using programmatic approach\n")
        use_api = False

    # Process examples
    for i, example in enumerate(examples, 1):
        print(f"\n{'=' * 70}")
        print(f"Example {i}: {example['description']}")
        print(f"{'=' * 70}")
        print(f"\n💬 Input: \"{example['text']}\"")

        context = example.get("context")
        if context:
            print(f"📍 Context: {context}")

        # Classify
        if use_api:
            result = classify_via_api(example["text"], context, api_url)
            if result and result.get("success"):
                schedules = result["schedules"]
                cached = result.get("cached", False)
                print(f"\n✅ Classification successful (cached: {cached})")
            else:
                print(f"\n❌ Classification failed")
                if result and result.get("error"):
                    print(f"   Error: {result['error']}")
                continue
        else:
            schedules = classify_programmatically(example["text"], context)
            if not schedules:
                print(f"\n❌ Classification failed")
                continue
            print(f"\n✅ Classification successful")

        # Display results
        print(f"\n📊 Found {len(schedules)} schedule(s):")
        for schedule in schedules:
            print_schedule(schedule)

    # Show cache statistics
    if use_api:
        print(f"\n{'=' * 70}")
        print("Cache Statistics")
        print(f"{'=' * 70}")

        try:
            response = requests.get(f"{api_url}/stats", timeout=5)
            if response.status_code == 200:
                stats = response.json()
                cache_stats = stats.get("ai_cache_stats", {})

                if cache_stats:
                    print(f"\n📈 Cache Performance:")
                    print(f"   Total Requests: {cache_stats.get('total_requests', 0)}")
                    print(f"   Memory Hits: {cache_stats.get('memory_hits', 0)}")
                    print(f"   DB Hits: {cache_stats.get('db_hits', 0)}")
                    print(f"   Misses: {cache_stats.get('misses', 0)}")
                    print(f"   Hit Rate: {cache_stats.get('hit_rate', 0):.1%}")
                    print(f"   Memory Cache Size: {cache_stats.get('memory_cache_size', 0)}")
        except Exception as e:
            print(f"\n⚠️  Could not fetch cache statistics: {e}")

    # Show popular phrases
    if use_api:
        print(f"\n{'=' * 70}")
        print("Popular Phrases")
        print(f"{'=' * 70}")

        try:
            response = requests.get(f"{api_url}/ai-classify/popular?limit=5", timeout=5)
            if response.status_code == 200:
                result = response.json()
                popular = result.get("popular_phrases", [])

                if popular:
                    print(f"\n🔥 Top {len(popular)} most popular phrases:")
                    for i, phrase in enumerate(popular, 1):
                        print(f"\n   {i}. \"{phrase['text'][:60]}...\"")
                        print(f"      Hits: {phrase['hit_count']}")
                        print(f"      Avg Confidence: {phrase['confidence_avg']:.2%}")
                else:
                    print("\n   No cached phrases yet")
        except Exception as e:
            print(f"\n⚠️  Could not fetch popular phrases: {e}")

    print(f"\n{'=' * 70}")
    print("Example completed!")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    # Check for API key if not using API
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set!")
        print("Set it with: export OPENAI_API_KEY='sk-...'")
        print("\nThe programmatic approach will fail without it.")
        print("You can still try the API approach if the server is running.\n")

    main()
