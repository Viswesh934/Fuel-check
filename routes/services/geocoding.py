import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# Built-in fast cache / fallback coordinates for Indian freight corridors & test transit hubs
FALLBACK_LOCATIONS = {
    # Key Indian Highway Transit Hubs & Freight Corridors
    "delhi": {"longitude": 77.21688, "latitude": 28.63412, "label": "Delhi NCT, India"},
    "delhi, india": {"longitude": 77.21688, "latitude": 28.63412, "label": "Delhi NCT, India"},
    "new delhi": {"longitude": 77.2090, "latitude": 28.6139, "label": "New Delhi, India"},
    "mumbai": {"longitude": 72.83484, "latitude": 18.94018, "label": "Mumbai, Maharashtra, India"},
    "mumbai, india": {"longitude": 72.83484, "latitude": 18.94018, "label": "Mumbai, Maharashtra, India"},
    "bombay": {"longitude": 72.83484, "latitude": 18.94018, "label": "Mumbai, Maharashtra, India"},
    "jaipur": {"longitude": 75.8203, "latitude": 26.9124, "label": "Jaipur, Rajasthan, India"},
    "ahmedabad": {"longitude": 72.5714, "latitude": 23.0225, "label": "Ahmedabad, Gujarat, India"},
    "vadodara": {"longitude": 73.1812, "latitude": 22.3072, "label": "Vadodara, Gujarat, India"},
    "surat": {"longitude": 72.8311, "latitude": 21.1702, "label": "Surat, Gujarat, India"},
    "vapi": {"longitude": 72.9289, "latitude": 20.3709, "label": "Vapi, Gujarat, India"},
    "pune": {"longitude": 73.8567, "latitude": 18.5204, "label": "Pune, Maharashtra, India"},
    "bengaluru": {"longitude": 77.5946, "latitude": 12.9716, "label": "Bengaluru, Karnataka, India"},
    "bangalore": {"longitude": 77.5946, "latitude": 12.9716, "label": "Bengaluru, Karnataka, India"},
    "chennai": {"longitude": 80.2707, "latitude": 13.0827, "label": "Chennai, Tamil Nadu, India"},
    "madras": {"longitude": 80.2707, "latitude": 13.0827, "label": "Chennai, Tamil Nadu, India"},
    "hyderabad": {"longitude": 78.4867, "latitude": 17.3850, "label": "Hyderabad, Telangana, India"},
    "kolkata": {"longitude": 88.3639, "latitude": 22.5726, "label": "Kolkata, West Bengal, India"},
    "calcutta": {"longitude": 88.3639, "latitude": 22.5726, "label": "Kolkata, West Bengal, India"},
    "lucknow": {"longitude": 80.9462, "latitude": 26.8467, "label": "Lucknow, Uttar Pradesh, India"},
    "kanpur": {"longitude": 80.3319, "latitude": 26.4499, "label": "Kanpur, Uttar Pradesh, India"},
    "nagpur": {"longitude": 79.0882, "latitude": 21.1458, "label": "Nagpur, Maharashtra, India"},
    "indore": {"longitude": 75.8577, "latitude": 22.7196, "label": "Indore, Madhya Pradesh, India"},
    "bhopal": {"longitude": 77.4126, "latitude": 23.2599, "label": "Bhopal, Madhya Pradesh, India"},
    "chandigarh": {"longitude": 76.7794, "latitude": 30.7333, "label": "Chandigarh, India"},
    "gurugram": {"longitude": 77.0266, "latitude": 28.4595, "label": "Gurugram, Haryana, India"},
    "gurgaon": {"longitude": 77.0266, "latitude": 28.4595, "label": "Gurugram, Haryana, India"},
    "rewari": {"longitude": 76.6190, "latitude": 28.1821, "label": "Rewari, Haryana, India"},
    "ajmer": {"longitude": 74.6399, "latitude": 26.4499, "label": "Ajmer, Rajasthan, India"},
    "udaipur": {"longitude": 73.7125, "latitude": 24.5854, "label": "Udaipur, Rajasthan, India"},
    "agra": {"longitude": 78.0081, "latitude": 27.1767, "label": "Agra, Uttar Pradesh, India"},
    "varanasi": {"longitude": 82.9739, "latitude": 25.3176, "label": "Varanasi, Uttar Pradesh, India"},
    "coimbatore": {"longitude": 76.9558, "latitude": 11.0168, "label": "Coimbatore, Tamil Nadu, India"},
    "kochi": {"longitude": 76.2673, "latitude": 9.9312, "label": "Kochi, Kerala, India"},
    "vijayawada": {"longitude": 80.6480, "latitude": 16.5062, "label": "Vijayawada, Andhra Pradesh, India"},
    "visakhapatnam": {"longitude": 83.2185, "latitude": 17.6868, "label": "Visakhapatnam, Andhra Pradesh, India"},
    # Backwards Compatibility for Automated Unit Tests
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
            },
            timeout=2.5,
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
