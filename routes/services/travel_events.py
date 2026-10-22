import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from .station_projection import project_point_to_segment
from .route_geometry import haversine_distance

logger = logging.getLogger(__name__)


@dataclass
class TravelEvent:
    id: str
    type: str  # ROAD_CLOSURE, WEATHER_HAZARD, CONSTRUCTION, TRAFFIC_DISRUPTION
    severity: str  # CRITICAL, WARNING, ADVISORY
    title: str
    description: str
    latitude: float
    longitude: float
    corridor: str
    source: str  # "SIMULATED" or "LIVE_VERIFIED"
    is_simulated: bool
    estimated_delay_minutes: int
    recommended_action: str
    impact_radius_miles: float = 15.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Realistic simulated travel events along major US travel corridors
# Every simulated fixture is explicitly and permanently labeled source: "SIMULATED"
DEMO_TRAVEL_EVENTS: List[TravelEvent] = [
    TravelEvent(
        id="SIM-CLOSURE-5501",
        type="ROAD_CLOSURE",
        severity="WARNING",
        title="I-55 Southbound Bridge Reconstruction & Lane Closure",
        description="Single-lane restriction between Mile Marker 98 and 104 due to deck repairs. Expect slow speeds.",
        latitude=38.6270,
        longitude=-90.1994,
        corridor="I-55 (St. Louis Metro / Mississippi Crossing)",
        source="SIMULATED",
        is_simulated=True,
        estimated_delay_minutes=35,
        recommended_action="Stay in left lane. Consider refueling before congestion zone.",
        impact_radius_miles=15.0,
    ),
    TravelEvent(
        id="SIM-WEATHER-4002",
        type="WEATHER_HAZARD",
        severity="WARNING",
        title="Severe Thunderstorm & Flash Flood Advisory",
        description="Heavy downpours reducing highway visibility under 1/4 mile with localized ponding on I-40 East/West.",
        latitude=35.1495,
        longitude=-90.0490,
        corridor="I-40 (Memphis / Arkansas Corridor)",
        source="SIMULATED",
        is_simulated=True,
        estimated_delay_minutes=25,
        recommended_action="Reduce speed to 45 mph, turn on low beams, avoid standing water on shoulders.",
        impact_radius_miles=25.0,
    ),
    TravelEvent(
        id="SIM-WEATHER-8003",
        type="WEATHER_HAZARD",
        severity="CRITICAL",
        title="I-80 High Wind & Lake Effect Snow Squall",
        description="Wind gusts exceeding 50 mph with sudden whiteout conditions. Commercial empty trailers prohibited.",
        latitude=41.4993,
        longitude=-81.6944,
        corridor="I-80 (Northern Ohio / Lake Erie Corridor)",
        source="SIMULATED",
        is_simulated=True,
        estimated_delay_minutes=60,
        recommended_action="Commercial haulers reduce speed or park at nearest travel plaza until squall passes.",
        impact_radius_miles=20.0,
    ),
    TravelEvent(
        id="SIM-DISRUPT-1004",
        type="TRAFFIC_DISRUPTION",
        severity="ADVISORY",
        title="I-10 Commercial Vehicle Inspection Queue",
        description="State highway weigh station open with traffic spilling onto right travel lane.",
        latitude=30.0800,
        longitude=-94.1265,
        corridor="I-10 (Beaumont / Houston East Corridor)",
        source="SIMULATED",
        is_simulated=True,
        estimated_delay_minutes=15,
        recommended_action="Use center and left lanes to bypass truck inspection backup.",
        impact_radius_miles=10.0,
    ),
    # Control/Irrelevant fixture: located in Montana, will NOT match Midwest or South routes
    TravelEvent(
        id="SIM-OFFROUTE-9005",
        type="WEATHER_HAZARD",
        severity="ADVISORY",
        title="I-90 Rocky Mountain Snow Chain Requirement",
        description="Pass elevation freezing fog. Commercial traction tire chains required.",
        latitude=47.4240,
        longitude=-121.4130,
        corridor="I-90 (Washington / Montana)",
        source="SIMULATED",
        is_simulated=True,
        estimated_delay_minutes=45,
        recommended_action="Chains required on drive axles.",
        impact_radius_miles=15.0,
    ),
]


class TravelEventService:
    """
    Evaluates travel events along the route using normal deterministic code.
    Matching is strictly spatial and mathematical (NO LLM is invoked for route matching).
    """

    def __init__(self):
        self.events = list(DEMO_TRAVEL_EVENTS)

    def get_all_events(self) -> List[TravelEvent]:
        return list(self.events)

    def match_events_to_route(
        self,
        route_points: List[dict],
        total_distance_miles: float,
        default_tolerance_miles: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Deterministic route-aware event matcher.
        Determines whether each travel event intersects or lies near the calculated route polyline.

        Returns:
            {
                "has_matching_events": bool,
                "matched_events": List[dict],
                "all_events": List[dict],
                "total_delay_minutes": int
            }
        """
        matched_events = []
        all_event_results = []
        total_delay = 0

        if not route_points or len(route_points) < 2:
            return {
                "has_matching_events": False,
                "matched_events": [],
                "all_events": [e.to_dict() for e in self.events],
                "total_delay_minutes": 0,
            }

        for event in self.events:
            tolerance = max(default_tolerance_miles, event.impact_radius_miles)
            event_point = (event.longitude, event.latitude)

            best_distance = float("inf")
            best_route_mile = None

            # Project event coordinates onto route polyline segments
            for index in range(len(route_points) - 1):
                current = route_points[index]
                next_point = route_points[index + 1]

                segment_start = (current["longitude"], current["latitude"])
                segment_end = (next_point["longitude"], next_point["latitude"])

                fraction, dist = project_point_to_segment(
                    event_point,
                    segment_start,
                    segment_end,
                )

                if dist < best_distance:
                    best_distance = dist
                    seg_len = haversine_distance(segment_start, segment_end)
                    best_route_mile = current["mile"] + fraction * seg_len

            affects_route = best_distance <= tolerance

            event_dict = event.to_dict()
            event_dict["distance_to_route_miles"] = round(best_distance, 1)
            event_dict["affects_route"] = affects_route

            if affects_route and best_route_mile is not None:
                # Ensure route mile does not exceed total distance
                route_mile = max(0.0, min(total_distance_miles, best_route_mile))
                event_dict["route_mile"] = round(route_mile, 1)
                matched_events.append(event_dict)
                total_delay += event.estimated_delay_minutes
            else:
                event_dict["route_mile"] = None

            all_event_results.append(event_dict)

        # Sort matched events sequentially by route mile marker
        matched_events.sort(key=lambda x: x["route_mile"])

        return {
            "has_matching_events": len(matched_events) > 0,
            "matched_events": matched_events,
            "all_events": all_event_results,
            "total_delay_minutes": total_delay,
        }
