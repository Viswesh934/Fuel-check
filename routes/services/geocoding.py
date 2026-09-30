import requests
from django.conf import settings


class GeocodingService:
    BASE_URL = "https://api.heigit.org/pelias/v1/search"

    def __init__(self):
        self.api_key = settings.ORS_API_KEY

    def geocode(self, location):

        response = requests.get(
            self.BASE_URL,
            headers={
                "Authorization": self.api_key,
                "Accept": "application/json",
            },
            params={
                "text": location,
                "size": 1,
            },
            timeout=10,
        )


        response.raise_for_status()

        data = response.json()

        features = data.get("features", [])

        if not features:
            raise ValueError(
                f"Location not found: {location}"
            )

        feature = features[0]

        coordinates = feature["geometry"]["coordinates"]

        return {
            "longitude": coordinates[0],
            "latitude": coordinates[1],
            "label": feature["properties"].get(
                "label",
                location,
            ),
        }