#!/usr/bin/env python3
"""
GPS Simulator - Generates simulated GPS data for truck tracking.

This script simulates trucks moving through a city and sends their GPS
coordinates to the TrashAlert API for testing the GPS tracking system.
"""

import asyncio
import random
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Truck, City, TruckLocation

# Configuration
API_BASE_URL = "http://localhost:8000"
UPDATE_INTERVAL = 5  # seconds between GPS updates
NUM_TRUCKS = 3  # number of simulated trucks

# San Francisco area coordinates for simulation
SF_CENTER = (37.7749, -122.4194)
SF_BOUNDS = {
    'min_lat': 37.7000,
    'max_lat': 37.8100,
    'min_lon': -122.5200,
    'max_lon': -122.3500
}


class TruckSimulator:
    """Simulates a truck moving through a city."""

    def __init__(self, truck_id: int, truck_number: str, start_lat: float, start_lon: float):
        self.truck_id = truck_id
        self.truck_number = truck_number
        self.lat = start_lat
        self.lon = start_lon
        self.speed_mph = 0.0
        self.heading_degrees = random.uniform(0, 360)

    def update_position(self):
        """Update truck position simulating realistic movement."""
        # Simulate speed variation (0-30 mph)
        self.speed_mph = max(0, min(30, self.speed_mph + random.uniform(-5, 5)))

        # Occasionally change direction
        if random.random() < 0.2:  # 20% chance to turn
            self.heading_degrees = (self.heading_degrees + random.uniform(-45, 45)) % 360

        # Convert speed to degrees per second (very rough approximation)
        # 1 mph ≈ 0.000004 degrees latitude per second
        speed_deg_per_sec = (self.speed_mph * 0.000004) * UPDATE_INTERVAL

        # Update position based on heading
        import math
        heading_rad = math.radians(self.heading_degrees)

        lat_change = speed_deg_per_sec * math.cos(heading_rad)
        lon_change = speed_deg_per_sec * math.sin(heading_rad)

        self.lat += lat_change
        self.lon += lon_change

        # Keep within SF bounds
        self.lat = max(SF_BOUNDS['min_lat'], min(SF_BOUNDS['max_lat'], self.lat))
        self.lon = max(SF_BOUNDS['min_lon'], min(SF_BOUNDS['max_lon'], self.lon))

    def get_location_data(self):
        """Get current location as API payload."""
        return {
            "truck_id": self.truck_id,
            "lat": self.lat,
            "lon": self.lon,
            "speed_mph": round(self.speed_mph, 2),
            "heading_degrees": round(self.heading_degrees, 2),
            "altitude_meters": round(random.uniform(0, 100), 2),
            "accuracy_meters": round(random.uniform(5, 15), 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def ensure_test_trucks(db: Session):
    """Create test trucks in the database if they don't exist."""
    # Get or create SF city
    city = db.query(City).filter(City.slug == "san-francisco").first()
    if not city:
        city = City(
            slug="san-francisco",
            name="San Francisco",
            state="CA",
            timezone="America/Los_Angeles",
            enabled=True
        )
        db.add(city)
        db.commit()
        db.refresh(city)
        print(f"✓ Created city: {city.name}")

    # Create test trucks
    trucks = []
    vehicle_types = ["trash", "recycling", "green"]

    for i in range(NUM_TRUCKS):
        truck_number = f"TEST-{i+1:03d}"
        truck = db.query(Truck).filter(Truck.truck_number == truck_number).first()

        if not truck:
            truck = Truck(
                truck_number=truck_number,
                license_plate=f"CA-{random.randint(1000, 9999)}",
                city_id=city.id,
                status="active",
                vehicle_type=vehicle_types[i % len(vehicle_types)],
                capacity_cubic_yards=random.choice([10.0, 15.0, 20.0, 25.0])
            )
            db.add(truck)
            db.commit()
            db.refresh(truck)
            print(f"✓ Created truck: {truck.truck_number}")

        trucks.append(truck)

    return trucks


async def send_gps_update(client: httpx.AsyncClient, location_data: dict):
    """Send GPS location update to API."""
    try:
        response = await client.post(
            f"{API_BASE_URL}/gps/truck-location",
            json=location_data,
            timeout=5.0
        )
        if response.status_code == 201:
            print(f"✓ Truck #{location_data['truck_id']:2d}: "
                  f"{location_data['lat']:.6f}, {location_data['lon']:.6f} "
                  f"@ {location_data['speed_mph']:.1f} mph")
        else:
            print(f"✗ Error for truck {location_data['truck_id']}: {response.status_code}")
    except Exception as e:
        print(f"✗ Exception sending update: {e}")


async def run_simulation():
    """Main simulation loop."""
    print("\n" + "="*70)
    print("GPS TRUCK TRACKING SIMULATOR")
    print("="*70)
    print(f"\nConfiguration:")
    print(f"  API URL: {API_BASE_URL}")
    print(f"  Update interval: {UPDATE_INTERVAL}s")
    print(f"  Number of trucks: {NUM_TRUCKS}")
    print(f"  Area: San Francisco")
    print("\n" + "="*70 + "\n")

    # Initialize database and trucks
    db = SessionLocal()
    try:
        trucks = ensure_test_trucks(db)
        print(f"\n✓ {len(trucks)} trucks ready for simulation\n")
    finally:
        db.close()

    # Create simulators with random starting positions
    simulators = []
    for truck in trucks:
        start_lat = random.uniform(SF_BOUNDS['min_lat'], SF_BOUNDS['max_lat'])
        start_lon = random.uniform(SF_BOUNDS['min_lon'], SF_BOUNDS['max_lon'])
        sim = TruckSimulator(truck.id, truck.truck_number, start_lat, start_lon)
        simulators.append(sim)

    print("Starting GPS simulation... (Press Ctrl+C to stop)\n")

    # Main simulation loop
    async with httpx.AsyncClient() as client:
        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"\n--- Update #{iteration} at {datetime.now().strftime('%H:%M:%S')} ---")

                # Update all trucks
                tasks = []
                for sim in simulators:
                    sim.update_position()
                    location_data = sim.get_location_data()
                    tasks.append(send_gps_update(client, location_data))

                # Send all updates in parallel
                await asyncio.gather(*tasks)

                # Wait for next update
                await asyncio.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nSimulation stopped by user.")
            print(f"Total updates sent: {iteration * len(simulators)}")
            print("\nGoodbye!\n")


def main():
    """Entry point for the simulator."""
    try:
        asyncio.run(run_simulation())
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
