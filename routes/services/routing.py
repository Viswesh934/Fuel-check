import logging
import requests
from django.conf import settings

from .route_geometry import haversine_distance

logger = logging.getLogger(__name__)


class RoutingService:
    OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"
    USER_AGENT = "FuelCheckTravelCopilot/2.0 (contact@fuelcheck.app)"

    def __init__(self):
        self.provider = getattr(settings, "ROUTING_PROVIDER", "osrm")
        self.mapbox_token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "")
        self.ors_api_key = getattr(settings, "ORS_API_KEY", "")

    def get_route(self, start, finish):
        start_lon, start_lat = start[0], start[1]
        finish_lon, finish_lat = finish[0], finish[1]

        # 0. AWS Routes V2 Commercial Truck Routing (if AWS_LOCATION_API_KEY is configured)
        import os
        aws_key = getattr(settings, "AWS_LOCATION_API_KEY", os.getenv("AWS_LOCATION_API_KEY", "")).strip()
        if aws_key:
            try:
                from .aws_location_service import calculate_single_truck_route
                return calculate_single_truck_route((start_lon, start_lat), (finish_lon, finish_lat))
            except Exception as e:
                logger.warning(f"AWS Routes V2 truck routing failed: {e}. Falling back to OSRM.")

        # 1. Mapbox Directions (if provider configured and token exists)
        if self.provider == "mapbox" and self.mapbox_token:
            try:
                return self._get_mapbox_route(start_lon, start_lat, finish_lon, finish_lat)
            except Exception as e:
                logger.warning(f"Mapbox routing failed: {e}. Falling back to OSRM.")

        # 2. Legacy OpenRouteService (if configured and key exists)
        if self.provider == "ors" and self.ors_api_key:
            try:
                return self._get_ors_route(start_lon, start_lat, finish_lon, finish_lat)
            except Exception as e:
                logger.warning(f"ORS routing failed: {e}. Falling back to OSRM.")

        # 3. OSRM (Default - Free, no API key required)
        try:
            return self._get_osrm_route(start_lon, start_lat, finish_lon, finish_lat)
        except Exception as e:
            logger.error(f"OSRM routing failed: {e}. Generating geographic fallback.")
            return self._get_fallback_route(start_lon, start_lat, finish_lon, finish_lat)

    def _get_osrm_route(self, start_lon, start_lat, finish_lon, finish_lat):
        url = f"{self.OSRM_BASE_URL}/{start_lon},{start_lat};{finish_lon},{finish_lat}"
        response = requests.get(
            url,
            params={
                "overview": "full",
                "geometries": "geojson",
            },
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"No driving route found between specified points: {data.get('message', 'Unknown error')}")

        route = data["routes"][0]
        return {
            "distance_meters": float(route["distance"]),
            "duration_seconds": float(route["duration"]),
            "geometry": route["geometry"],
        }

    def _get_mapbox_route(self, start_lon, start_lat, finish_lon, finish_lat):
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{finish_lon},{finish_lat}"
        response = requests.get(
            url,
            params={
                "access_token": self.mapbox_token,
                "geometries": "geojson",
                "overview": "full",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        route = data["routes"][0]
        return {
            "distance_meters": float(route["distance"]),
            "duration_seconds": float(route["duration"]),
            "geometry": route["geometry"],
        }

    def _get_ors_route(self, start_lon, start_lat, finish_lon, finish_lat):
        url = "https://api.heigit.org/openrouteservice/v2/directions/driving-car/geojson"
        response = requests.post(
            url,
            headers={
                "Authorization": self.ors_api_key,
                "Content-Type": "application/json",
                "Accept": "application/geo+json",
            },
            json={
                "coordinates": [[start_lon, start_lat], [finish_lon, finish_lat]],
                "instructions": False,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        route = data["features"][0]
        return {
            "distance_meters": float(route["properties"]["summary"]["distance"]),
            "duration_seconds": float(route["properties"]["summary"]["duration"]),
            "geometry": route["geometry"],
        }

    def _get_fallback_route(self, start_lon, start_lat, finish_lon, finish_lat):
        """
        Geographic straight-line interpolation with road curvature factor (1.2x)
        when external routing network is temporarily unreachable.
        """
        crow_miles = haversine_distance((start_lon, start_lat), (finish_lon, finish_lat))
        estimated_distance_miles = crow_miles * 1.2
        distance_meters = estimated_distance_miles * 1609.344
        # Assume average highway speed 60 mph -> 1 mile per minute
        duration_seconds = estimated_distance_miles * 60

        # Generate 20 intermediate points
        coords = []
        steps = 20
        for i in range(steps + 1):
            fraction = i / steps
            lon = start_lon + fraction * (finish_lon - start_lon)
            lat = start_lat + fraction * (finish_lat - start_lat)
            coords.append([round(lon, 6), round(lat, 6)])

        return {
            "distance_meters": distance_meters,
            "duration_seconds": duration_seconds,
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        }
