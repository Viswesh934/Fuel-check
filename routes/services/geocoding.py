import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# Built-in fast cache / fallback coordinates for common transit hubs & test cities
FALLBACK_LOCATIONS = {
    "chicago, il": {"longitude": -87.6298, "latitude": 41.8781, "label": "Chicago, IL, USA"},
    "chicago": {"longitude": -87.6298, "latitude": 41.8781, "label": "Chicago, IL, USA"},
    "little rock, ar": {"longitude": -92.2896, "latitude": 34.7465, "label": "Little Rock, AR, USA"},
    "little rock": {"longitude": -92.2896, "latitude": 34.7465, "label": "Little Rock, AR, USA"},
    "new york, ny": {"longitude": -74.0060, "latitude": 40.7128, "label": "New York, NY, USA"},
    "new york": {"longitude": -74.0060, "latitude": 40.7128, "label": "New York, NY, USA"},
    "houston, tx": {"longitude": -95.3698, "latitude": 29.7604, "label": "Houston, TX, USA"},
    "houston": {"longitude": -95.3698, "latitude": 29.7604, "label": "Houston, TX, USA"},
    "st. louis, mo": {"longitude": -90.1994, "latitude": 38.6270, "label": "St. Louis, MO, USA"},
    "st. louis": {"longitude": -90.1994, "latitude": 38.6270, "label": "St. Louis, MO, USA"},
    "milwaukee, wi": {"longitude": -87.9065, "latitude": 43.0389, "label": "Milwaukee, WI, USA"},
    "atlanta, ga": {"longitude": -84.3880, "latitude": 33.7490, "label": "Atlanta, GA, USA"},
    "dallas, tx": {"longitude": -96.7970, "latitude": 32.7767, "label": "Dallas, TX, USA"},
}


class GeocodingService:
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "FuelCheckTravelCopilot/2.0 (contact@fuelcheck.app)"

    def __init__(self):
        self.provider = getattr(settings, "GEOCODING_PROVIDER", "nominatim")
        self.mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "")

    def geocode(self, location: str):
        if not location or not location.strip():
            raise ValueError("Location query cannot be blank.")

        query = location.strip()
        normalized_query = query.lower()

        # Check local fallback cache first for instant resolution
        if normalized_query in FALLBACK_LOCATIONS:
            return dict(FALLBACK_LOCATIONS[normalized_query])

        # 0. AWS Places V2 Geocoding (if AWS_LOCATION_API_KEY is configured)
        import os
        aws_key = getattr(settings, "AWS_LOCATION_API_KEY", os.getenv("AWS_LOCATION_API_KEY", "")).strip()
        if aws_key:
            try:
                from .aws_location_service import geocode_place
                lon, lat = geocode_place(query)
                is_india = (68.0 <= lon <= 97.0 and 8.0 <= lat <= 37.0)
                label = f"{query}, India" if is_india else f"{query}"
                return {"longitude": lon, "latitude": lat, "label": label}
            except Exception as e:
                logger.warning(f"AWS Places V2 geocoding failed: {e}. Falling back.")

        # 1. Mapbox Geocoding (if token is provided)
        if self.provider == "mapbox" and self.mapbox_token:
            try:
                return self._geocode_mapbox(query)
            except Exception as e:
                logger.warning(f"Mapbox geocoding failed: {e}. Falling back to Nominatim.")

        # 2. Nominatim OpenStreetMap Geocoding (Default, 100% free, no API key needed)
        try:
            return self._geocode_nominatim(query)
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Nominatim lookup error for '{query}': {e}")

        # Check partial fallback match
        for key, val in FALLBACK_LOCATIONS.items():
            if key in normalized_query or normalized_query in key:
                return dict(val)

        raise ValueError(f"Location not found: {location}")

    def _geocode_nominatim(self, query: str):
        response = requests.get(
            self.NOMINATIM_URL,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "us,ca",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise ValueError(f"Location not found: {query}")

        data = response.json()
        if not data or not isinstance(data, list):
            raise ValueError(f"Location not found: {query}")

        item = data[0]
        return {
            "longitude": float(item["lon"]),
            "latitude": float(item["lat"]),
            "label": item.get("display_name", query),
        }

    def _geocode_mapbox(self, query: str):
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
        response = requests.get(
            url,
            params={
                "access_token": self.mapbox_token,
                "limit": 1,
                "country": "US,CA",
            },
            timeout=10,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
            raise ValueError(f"Location not found: {query}")

        center = features[0]["center"]
        return {
            "longitude": float(center[0]),
            "latitude": float(center[1]),
            "label": features[0].get("place_name", query),
        }
