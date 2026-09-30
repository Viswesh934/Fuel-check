from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from routes.services.routing import RoutingService
from routes.services.geocoding import GeocodingService
from routes.services.route_geometry import build_route_points
from routes.services.station_projection import find_candidate_stations
from routes.services.route_graph import (
    build_route_nodes,
    build_route_graph,
)
from routes.services.optimizer import (
    optimize_route,
    build_optimization_result,
)
from .models import FuelStation
from .serializers import OptimizeRouteSerializer


class HealthView(APIView):
    def get(self, request):
        return Response({
            "status": "ok"
        })


class OptimizeRouteView(APIView):

    def post(self, request):

        serializer = OptimizeRouteSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        start_location = serializer.validated_data["start"]
        finish_location = serializer.validated_data["finish"]

        try:
            # 1. Geocode user locations
            geocoder = GeocodingService()

            start = geocoder.geocode(
                start_location
            )

            finish = geocoder.geocode(
                finish_location
            )

            # 2. Get route
            router = RoutingService()

            route = router.get_route(
                (
                    start["longitude"],
                    start["latitude"],
                ),
                (
                    finish["longitude"],
                    finish["latitude"],
                ),
            )

            distance_miles = (
                route["distance_meters"] / 1609.344
            )

            # 3. Convert route geometry
            route_points = build_route_points(
                route["geometry"],
                distance_miles,
            )

            # 4. Find fuel stations near route
            stations = FuelStation.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False,
            )

            candidates = find_candidate_stations(
                stations,
                route_points,
                tolerance_miles=5.0,
            )

            # 5. Build reachability graph
            nodes = build_route_nodes(
                candidates,
                distance_miles,
            )

            graph = build_route_graph(nodes)

            # 6. Find cheapest reachable path
            optimization = optimize_route(
                nodes,
                graph,
            )

            # 7. Format result
            optimization_result = (
                build_optimization_result(
                    optimization,
                    nodes,
                    graph,
                )
            )

            # 8. No feasible route
            if optimization_result is None:
                return Response(
                    {
                        "error": "No feasible fuel-stop plan exists for this route.",
                        "route": {
                            "distance_miles": round(distance_miles, 2),
                            "duration_minutes": round(
                                route["duration_seconds"] / 60,
                                2,
                            ),
                        },
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            fuel_consumed = distance_miles / 10

            return Response({
                "start": start,
                "finish": finish,

                "route": {
                    "distance_miles": round(distance_miles, 2),
                    "duration_minutes": round(
                        route["duration_seconds"] / 60,
                        2,
                    ),
                    "geometry": route["geometry"],
                },

                "fuel": {
                    "mpg": 10,
                    "max_range_miles": 500,
                    "consumed_gallons": round(fuel_consumed, 2),
                    "starting_fuel_gallons": 50,
                    "modeled_purchased_gallons": round(
                        optimization_result[
                            "total_gallons_purchased"
                        ],
                        2,
                    ),
                    "total_cost": round(
                        optimization_result[
                            "total_cost"
                        ],
                        2,
                    ),
                },

                "fuel_stops": (
                    optimization_result["stops"]
                ),

                "legs": (
                    optimization_result["legs"]
                ),
            })

        except ValueError as exc:
            return Response(
                {
                    "error": str(exc)
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            return Response(
                {
                    "error": "Unable to calculate route."
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )