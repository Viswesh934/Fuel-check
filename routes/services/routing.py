import requests
from django.conf import settings


class RoutingService:
    BASE_URL = (
        "https://api.heigit.org/"
        "openrouteservice/v2/directions/driving-car/geojson"
    )

    def __init__(self):
        self.api_key = settings.ORS_API_KEY

    def get_route(self, start, finish):
        coordinates = [
            list(start),
            list(finish),
        ]

        response = requests.post(
            self.BASE_URL,
            headers={
                "Authorization": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/geo+json",
            },
            json={
                "coordinates": coordinates,
                "instructions": False,
            },
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        route = data["features"][0]

        return {
            "distance_meters": route["properties"]["summary"]["distance"],
            "duration_seconds": route["properties"]["summary"]["duration"],
            "geometry": route["geometry"],
        }