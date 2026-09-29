# routes/services/routing.py

import requests
from django.conf import settings


class RoutingService:
    BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

    def __init__(self):
        self.api_key = settings.ORS_API_KEY

    def get_route(self, start, finish):
        """
        start  = (longitude, latitude)
        finish = (longitude, latitude)

        Returns:
            distance_meters
            duration_seconds
            geometry
        """

        coordinates = [
            list(start),
            list(finish),
        ]

        response = requests.post(
            self.BASE_URL,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "coordinates": coordinates,
                "instructions": False,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        route = data["routes"][0]

        return {
            "distance_meters": route["summary"]["distance"],
            "duration_seconds": route["summary"]["duration"],
            "geometry": route["geometry"],
        }