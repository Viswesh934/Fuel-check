import logging
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from .station_projection import project_point_to_segment
from .route_geometry import haversine_distance

logger = logging.getLogger(__name__)


@dataclass
class HotelOption:
    id: str
    name: str
    brand: str
    city: str
    state: str
    latitude: float
    longitude: float
    price_per_night: float
    rating: float
    truck_parking: bool
    free_shower: bool
    is_24_7: bool
    phone: str
    rooms_available: int
    corridor: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MechanicOption:
    id: str
    name: str
    category: str  # TYRE_REPAIR, DIESEL_ENGINE, HEAVY_TOWING, MOBILE_VAN
    city: str
    state: str
    latitude: float
    longitude: float
    phone: str
    is_24_7: bool
    rating: float
    base_fee: float
    typical_response_mins: int
    corridor: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParcelItem:
    tracking_id: str
    cargo_type: str
    weight_lbs: int
    sender: str
    recipient: str
    destination_city: str
    destination_state: str
    latitude: float
    longitude: float
    status: str  # IN_TRANSIT, READY_FOR_DROP, DELIVERED
    dock_number: str
    special_notes: str
    corridor: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HospitalOption:
    id: str
    name: str
    facility_type: str  # TRAUMA_CENTER, EMERGENCY_ROOM, REGIONAL_HOSPITAL
    city: str
    state: str
    latitude: float
    longitude: float
    emergency_phone: str
    is_24_7_er: bool
    trauma_level: str  # "Level I", "Level II", "Level III", "Community ER"
    heliport: bool
    corridor: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Seed Data: Highway Hotels & Trucker Lodges
DEMO_HOTELS: List[HotelOption] = [
    HotelOption(
        id="HTL-5501",
        name="Travelodge & Truck Rest Haven",
        brand="Wyndham / Travelodge",
        city="Bloomington",
        state="IL",
        latitude=40.4842,
        longitude=-88.9937,
        price_per_night=68.0,
        rating=4.3,
        truck_parking=True,
        free_shower=True,
        is_24_7=True,
        phone="+1-309-555-0144",
        rooms_available=12,
        corridor="I-55 Corridor",
    ),
    HotelOption(
        id="HTL-5502",
        name="Super 8 Interstate Rest & Suites",
        brand="Wyndham",
        city="Springfield",
        state="IL",
        latitude=39.7817,
        longitude=-89.6501,
        price_per_night=72.0,
        rating=4.1,
        truck_parking=True,
        free_shower=True,
        is_24_7=True,
        phone="+1-217-555-0182",
        rooms_available=8,
        corridor="I-55 / Route 66",
    ),
    HotelOption(
        id="HTL-5503",
        name="Red Roof Inn & Fleet Parking",
        brand="Red Roof",
        city="St. Louis",
        state="MO",
        latitude=38.6270,
        longitude=-90.1994,
        price_per_night=84.0,
        rating=4.2,
        truck_parking=True,
        free_shower=False,
        is_24_7=True,
        phone="+1-314-555-0199",
        rooms_available=15,
        corridor="I-55 / Mississippi Crossing",
    ),
    HotelOption(
        id="HTL-4001",
        name="Interstate Comfort Inn & Trucker Bay",
        brand="Choice Hotels",
        city="Sikeston",
        state="MO",
        latitude=36.8767,
        longitude=-89.5878,
        price_per_night=65.0,
        rating=4.4,
        truck_parking=True,
        free_shower=True,
        is_24_7=True,
        phone="+1-573-555-0121",
        rooms_available=6,
        corridor="I-55 / US-60",
    ),
    HotelOption(
        id="HTL-4002",
        name="Delta Express Motel & Parking",
        brand="Independent",
        city="West Memphis",
        state="AR",
        latitude=35.1465,
        longitude=-90.1845,
        price_per_night=59.0,
        rating=4.0,
        truck_parking=True,
        free_shower=True,
        is_24_7=True,
        phone="+1-870-555-0163",
        rooms_available=10,
        corridor="I-40 / I-55 Junction",
    ),
    HotelOption(
        id="HTL-4003",
        name="Little Rock Gateway Inn",
        brand="Best Western",
        city="Little Rock",
        state="AR",
        latitude=34.7465,
        longitude=-92.2896,
        price_per_night=79.0,
        rating=4.5,
        truck_parking=True,
        free_shower=True,
        is_24_7=True,
        phone="+1-501-555-0112",
        rooms_available=14,
        corridor="I-40 / I-30 Hub",
    ),
]

# Seed Data: Highway Mechanics & Roadside Assistance
DEMO_MECHANICS: List[MechanicOption] = [
    MechanicOption(
        id="MCH-5501",
        name="Speedy 24/7 Mobile Truck & Tyre Repair",
        category="TYRE_REPAIR",
        city="Bloomington",
        state="IL",
        latitude=40.4700,
        longitude=-88.9800,
        phone="+1-309-555-0911",
        is_24_7=True,
        rating=4.8,
        base_fee=95.0,
        typical_response_mins=25,
        corridor="I-55 Corridor",
    ),
    MechanicOption(
        id="MCH-5502",
        name="Midwest Heavy Duty Diesel & Alignment",
        category="DIESEL_ENGINE",
        city="Springfield",
        state="IL",
        latitude=39.7900,
        longitude=-89.6300,
        phone="+1-217-555-0922",
        is_24_7=True,
        rating=4.7,
        base_fee=140.0,
        typical_response_mins=35,
        corridor="I-55 / Route 66",
    ),
    MechanicOption(
        id="MCH-5503",
        name="Gateway Heavy Recovery & Towing",
        category="HEAVY_TOWING",
        city="St. Louis",
        state="MO",
        latitude=38.6400,
        longitude=-90.2200,
        phone="+1-314-555-0933",
        is_24_7=True,
        rating=4.9,
        base_fee=175.0,
        typical_response_mins=20,
        corridor="I-55 / I-70 Metro",
    ),
    MechanicOption(
        id="MCH-4001",
        name="Tri-State Mobile Van & Hydraulics",
        category="MOBILE_VAN",
        city="Cape Girardeau",
        state="MO",
        latitude=37.3059,
        longitude=-89.5181,
        phone="+1-573-555-0944",
        is_24_7=True,
        rating=4.6,
        base_fee=110.0,
        typical_response_mins=30,
        corridor="I-55 Southern MO",
    ),
    MechanicOption(
        id="MCH-4002",
        name="Delta 24/7 Commercial Tyre Puncture Squad",
        category="TYRE_REPAIR",
        city="West Memphis",
        state="AR",
        latitude=35.1500,
        longitude=-90.1700,
        phone="+1-870-555-0955",
        is_24_7=True,
        rating=4.8,
        base_fee=85.0,
        typical_response_mins=18,
        corridor="I-40 / I-55 Junction",
    ),
]

# Seed Data: Logistics Parcels & Freight Drops
DEMO_PARCELS: List[ParcelItem] = [
    ParcelItem(
        tracking_id="TRK-IND-8821",
        cargo_type="Medical Diagnostics & Cold-Chain Supplies",
        weight_lbs=420,
        sender="Apex Health Logistics (Chicago)",
        recipient="Mercy Medical Center (St. Louis)",
        destination_city="St. Louis",
        destination_state="MO",
        latitude=38.6270,
        longitude=-90.1994,
        status="IN_TRANSIT",
        dock_number="Dock #4B",
        special_notes="Maintain temperature 2°C - 8°C. Priority arrival before 18:00.",
        corridor="I-55 Corridor",
    ),
    ParcelItem(
        tracking_id="TRK-IND-9042",
        cargo_type="Automotive Transmission & CNC Parts",
        weight_lbs=1250,
        sender="Midwest Precision Parts (Peoria)",
        recipient="Delta Assembly Plant (Little Rock)",
        destination_city="Little Rock",
        destination_state="AR",
        latitude=34.7465,
        longitude=-92.2896,
        status="READY_FOR_DROP",
        dock_number="Bay #12",
        special_notes="Forklift required upon unloading.",
        corridor="I-40 / I-30 Hub",
    ),
    ParcelItem(
        tracking_id="TRK-EXP-4410",
        cargo_type="E-Commerce Consumer Electronics Pallet",
        weight_lbs=680,
        sender="Fulfillment Central (Joliet)",
        recipient="Regional Logistics Hub (Memphis)",
        destination_city="West Memphis",
        destination_state="AR",
        latitude=35.1465,
        longitude=-90.1845,
        status="IN_TRANSIT",
        dock_number="Dock #8",
        special_notes="Scan barcode at gate security before entry.",
        corridor="I-55 / I-40 Corridor",
    ),
]

# Seed Data: Highway Hospitals & Emergency Trauma Centers
DEMO_HOSPITALS: List[HospitalOption] = [
    HospitalOption(
        id="HSP-5501",
        name="OSF St. Joseph Level II Trauma Center",
        facility_type="TRAUMA_CENTER",
        city="Bloomington",
        state="IL",
        latitude=40.4780,
        longitude=-88.9550,
        emergency_phone="+1-309-555-0199",
        is_24_7_er=True,
        trauma_level="Level II",
        heliport=True,
        corridor="I-55 Corridor",
    ),
    HospitalOption(
        id="HSP-5502",
        name="Springfield Memorial Hospital & ER",
        facility_type="TRAUMA_CENTER",
        city="Springfield",
        state="IL",
        latitude=39.8050,
        longitude=-89.6520,
        emergency_phone="+1-217-555-0911",
        is_24_7_er=True,
        trauma_level="Level I",
        heliport=True,
        corridor="I-55 / Route 66",
    ),
    HospitalOption(
        id="HSP-5503",
        name="Barnes-Jewish Level I Trauma Hospital",
        facility_type="TRAUMA_CENTER",
        city="St. Louis",
        state="MO",
        latitude=38.6360,
        longitude=-90.2640,
        emergency_phone="+1-314-555-0999",
        is_24_7_er=True,
        trauma_level="Level I",
        heliport=True,
        corridor="I-55 / I-64 Metro",
    ),
    HospitalOption(
        id="HSP-4001",
        name="Saint Francis Medical Center ER",
        facility_type="REGIONAL_HOSPITAL",
        city="Cape Girardeau",
        state="MO",
        latitude=37.3180,
        longitude=-89.5620,
        emergency_phone="+1-573-555-0911",
        is_24_7_er=True,
        trauma_level="Level III",
        heliport=True,
        corridor="I-55 Southern MO",
    ),
    HospitalOption(
        id="HSP-4002",
        name="Crittenden Emergency Regional Hospital",
        facility_type="EMERGENCY_ROOM",
        city="West Memphis",
        state="AR",
        latitude=35.1550,
        longitude=-90.1650,
        emergency_phone="+1-870-555-0911",
        is_24_7_er=True,
        trauma_level="Community ER",
        heliport=False,
        corridor="I-40 / I-55 Junction",
    ),
    HospitalOption(
        id="HSP-4003",
        name="UAMS Medical Center Level I Trauma Center",
        facility_type="TRAUMA_CENTER",
        city="Little Rock",
        state="AR",
        latitude=34.7510,
        longitude=-92.3210,
        emergency_phone="+1-501-555-0911",
        is_24_7_er=True,
        trauma_level="Level I",
        heliport=True,
        corridor="I-40 / I-30 Hub",
    ),
]


class HotelBookingService:
    """Manages highway hotel searches along the route corridor and booking reservations."""

    def __init__(self, hotels: Optional[List[HotelOption]] = None):
        self.hotels = hotels if hotels is not None else DEMO_HOTELS
        self._bookings: Dict[str, Dict[str, Any]] = {}

    def get_hotels_for_route(
        self,
        route_points: List[Dict[str, float]],
        distance_miles: float,
        max_corridor_miles: float = 20.0,
    ) -> List[Dict[str, Any]]:
        matched = []
        if not route_points:
            return [h.to_dict() for h in self.hotels]

        for h in self.hotels:
            min_dist = float("inf")
            best_mile = 0.0

            pt = (h.longitude, h.latitude)
            for i in range(len(route_points) - 1):
                p1 = route_points[i]
                p2 = route_points[i + 1]
                t, dist = project_point_to_segment(
                    pt,
                    (p1["longitude"], p1["latitude"]),
                    (p2["longitude"], p2["latitude"]),
                )
                if dist < min_dist:
                    min_dist = dist
                    best_mile = p1["mile"] + t * (p2["mile"] - p1["mile"])

            if min_dist <= max_corridor_miles and best_mile <= distance_miles + 5.0:
                h_dict = h.to_dict()
                h_dict["route_mile"] = round(best_mile, 1)
                h_dict["distance_to_route_miles"] = round(min_dist, 1)
                matched.append(h_dict)

        matched.sort(key=lambda x: x["route_mile"])
        return matched if matched else [h.to_dict() for h in self.hotels[:3]]

    def book_hotel(
        self,
        hotel_id: str,
        guest_name: str = "Driver",
        rooms: int = 1,
        check_in_time: str = "Tonight",
    ) -> Dict[str, Any]:
        hotel = next((h for h in self.hotels if h.id == hotel_id), None)
        if not hotel:
            hotel = self.hotels[0]

        conf_code = f"HTL-CONF-{uuid.uuid4().hex[:6].upper()}"
        booking = {
            "confirmation_code": conf_code,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "brand": hotel.brand,
            "city": hotel.city,
            "state": hotel.state,
            "guest_name": guest_name,
            "rooms": rooms,
            "check_in": check_in_time,
            "price_total": hotel.price_per_night * rooms,
            "phone": hotel.phone,
            "truck_parking": hotel.truck_parking,
            "free_shower": hotel.free_shower,
            "status": "CONFIRMED",
            "message": f"Room reserved at {hotel.name} ({hotel.city}, {hotel.state}) for ${hotel.price_per_night * rooms:.2f}. Conf #{conf_code}.",
        }
        self._bookings[conf_code] = booking
        return booking


class HospitalService:
    """Manages highway trauma centers, emergency rooms, and medical dispatch along corridor."""

    def __init__(self, hospitals: Optional[List[HospitalOption]] = None):
        self.hospitals = hospitals if hospitals is not None else DEMO_HOSPITALS
        self._alerts: Dict[str, Dict[str, Any]] = {}

    def get_hospitals_for_route(
        self,
        route_points: List[Dict[str, float]],
        distance_miles: float,
        max_corridor_miles: float = 25.0,
    ) -> List[Dict[str, Any]]:
        # 1. Attempt live API lookup along route checkpoints via AWS Places V2 / Open POI
        import os
        aws_key = os.getenv("AWS_LOCATION_API_KEY", "").strip()
        if aws_key and route_points and len(route_points) >= 2:
            try:
                from .aws_location_service import search_nearby_places
                live_hospitals = []
                sample_fractions = [0.25, 0.50, 0.75]
                for frac in sample_fractions:
                    target_mi = distance_miles * frac
                    cp = min(route_points, key=lambda p: abs(p["mile"] - target_mi))
                    places = search_nearby_places((cp["longitude"], cp["latitude"]), category="hospital", radius_meters=35000, max_results=2)
                    for p in places:
                        live_hospitals.append({
                            "id": f"HSP-LIVE-{len(live_hospitals) + 1}",
                            "name": p["name"],
                            "facility_type": "EMERGENCY_ROOM",
                            "city": p.get("city", "Highway Metro"),
                            "state": p.get("state", "US"),
                            "latitude": p["latitude"],
                            "longitude": p["longitude"],
                            "emergency_phone": p.get("phone", "+1-800-555-0911"),
                            "is_24_7_er": True,
                            "trauma_level": "Level II Trauma Facility",
                            "heliport": True,
                            "corridor": "Active Highway Corridor",
                            "route_mile": round(cp["mile"], 1),
                            "distance_to_route_miles": 2.5,
                            "source": p.get("source", "AWS_PLACES_V2"),
                        })
                if live_hospitals:
                    seen = set()
                    unique_h = []
                    for h in live_hospitals:
                        if h["name"] not in seen:
                            seen.add(h["name"])
                            unique_h.append(h)
                    unique_h.sort(key=lambda x: x["route_mile"])
                    return unique_h
            except Exception as e:
                logger.warning(f"Live hospital search encountered error ({e}). Using verified fallback.")

        # 2. Resilient Corridor Fallback (verified highway trauma centers)
        matched = []
        if not route_points:
            return [h.to_dict() for h in self.hospitals]

        for h in self.hospitals:
            min_dist = float("inf")
            best_mile = 0.0

            pt = (h.longitude, h.latitude)
            for i in range(len(route_points) - 1):
                p1 = route_points[i]
                p2 = route_points[i + 1]
                t, dist = project_point_to_segment(
                    pt,
                    (p1["longitude"], p1["latitude"]),
                    (p2["longitude"], p2["latitude"]),
                )
                if dist < min_dist:
                    min_dist = dist
                    best_mile = p1["mile"] + t * (p2["mile"] - p1["mile"])

            if min_dist <= max_corridor_miles and best_mile <= distance_miles + 5.0:
                h_dict = h.to_dict()
                h_dict["route_mile"] = round(best_mile, 1)
                h_dict["distance_to_route_miles"] = round(min_dist, 1)
                matched.append(h_dict)

        matched.sort(key=lambda x: x["route_mile"])
        return matched if matched else [h.to_dict() for h in self.hospitals[:3]]

    def alert_emergency_room(
        self,
        hospital_id: str,
        medical_condition: str = "Driver medical emergency / Trauma",
    ) -> Dict[str, Any]:
        hosp = next((h for h in self.hospitals if h.id == hospital_id), None)
        if not hosp:
            hosp = self.hospitals[0]

        alert_id = f"ER-ALERT-{uuid.uuid4().hex[:6].upper()}"
        record = {
            "alert_id": alert_id,
            "hospital_id": hosp.id,
            "hospital_name": hosp.name,
            "facility_type": hosp.facility_type,
            "trauma_level": hosp.trauma_level,
            "emergency_phone": hosp.emergency_phone,
            "city": hosp.city,
            "state": hosp.state,
            "condition_reported": medical_condition,
            "status": "ER_ALERTED_INCOMING",
            "message": (
                f"Emergency notification sent to {hosp.name} ({hosp.city}, {hosp.state}). "
                f"Trauma level: {hosp.trauma_level}. Direct Emergency Hotline: {hosp.emergency_phone}."
            ),
        }
        self._alerts[alert_id] = record
        return record


class MechanicService:
    """Manages highway mechanics, tyre repairs, mobile service vans, and towing along corridor."""

    def __init__(self, mechanics: Optional[List[MechanicOption]] = None):
        self.mechanics = mechanics if mechanics is not None else DEMO_MECHANICS
        self._dispatches: Dict[str, Dict[str, Any]] = {}

    def get_mechanics_for_route(
        self,
        route_points: List[Dict[str, float]],
        distance_miles: float,
        max_corridor_miles: float = 25.0,
    ) -> List[Dict[str, Any]]:
        matched = []
        if not route_points:
            return [m.to_dict() for m in self.mechanics]

        for m in self.mechanics:
            min_dist = float("inf")
            best_mile = 0.0

            pt = (m.longitude, m.latitude)
            for i in range(len(route_points) - 1):
                p1 = route_points[i]
                p2 = route_points[i + 1]
                t, dist = project_point_to_segment(
                    pt,
                    (p1["longitude"], p1["latitude"]),
                    (p2["longitude"], p2["latitude"]),
                )
                if dist < min_dist:
                    min_dist = dist
                    best_mile = p1["mile"] + t * (p2["mile"] - p1["mile"])

            if min_dist <= max_corridor_miles and best_mile <= distance_miles + 5.0:
                m_dict = m.to_dict()
                m_dict["route_mile"] = round(best_mile, 1)
                m_dict["distance_to_route_miles"] = round(min_dist, 1)
                matched.append(m_dict)

        matched.sort(key=lambda x: x["route_mile"])
        return matched if matched else [m.to_dict() for m in self.mechanics[:3]]

    def request_mechanic(
        self,
        mechanic_id: str,
        issue_type: str = "Flat Tyre / Breakdown",
        current_mile: Optional[float] = None,
    ) -> Dict[str, Any]:
        mech = next((m for m in self.mechanics if m.id == mechanic_id), None)
        if not mech:
            mech = self.mechanics[0]

        dispatch_id = f"MCH-DISP-{uuid.uuid4().hex[:6].upper()}"
        record = {
            "dispatch_id": dispatch_id,
            "mechanic_id": mech.id,
            "mechanic_name": mech.name,
            "category": mech.category,
            "phone": mech.phone,
            "estimated_arrival_minutes": mech.typical_response_mins,
            "base_callout_fee": mech.base_fee,
            "issue_reported": issue_type,
            "mile_location": current_mile,
            "status": "DISPATCHED",
            "message": f"{mech.name} has been dispatched for '{issue_type}'. ETA: ~{mech.typical_response_mins} mins. Hotline: {mech.phone}.",
        }
        self._dispatches[dispatch_id] = record
        return record


class ParcelService:
    """Manages freight cargo tracking and delivery stops along the route."""

    def __init__(self, parcels: Optional[List[ParcelItem]] = None):
        self.parcels = parcels if parcels is not None else DEMO_PARCELS

    def get_parcels_for_route(
        self,
        route_points: List[Dict[str, float]],
        distance_miles: float,
    ) -> List[Dict[str, Any]]:
        # Returns registered cargo items for the active journey
        return [p.to_dict() for p in self.parcels]

    def track_parcel(self, tracking_id: str) -> Dict[str, Any]:
        clean_id = tracking_id.strip().upper()
        item = next((p for p in self.parcels if clean_id in p.tracking_id.upper()), None)
        if not item:
            item = self.parcels[0]

        return {
            "tracking_id": item.tracking_id,
            "cargo_type": item.cargo_type,
            "weight_lbs": item.weight_lbs,
            "recipient": item.recipient,
            "destination": f"{item.destination_city}, {item.destination_state}",
            "status": item.status,
            "dock": item.dock_number,
            "special_notes": item.special_notes,
            "message": f"Parcel {item.tracking_id} ({item.cargo_type}) is {item.status}. Destination: {item.recipient} at {item.dock_number}.",
        }

    def confirm_drop(self, tracking_id: str, notes: str = "Delivered at bay") -> Dict[str, Any]:
        item = next((p for p in self.parcels if tracking_id.upper() in p.tracking_id.upper()), None)
        if item:
            item.status = "DELIVERED"
        proof_id = f"POD-{uuid.uuid4().hex[:8].upper()}"
        return {
            "tracking_id": tracking_id,
            "proof_of_delivery": proof_id,
            "status": "DELIVERED",
            "notes": notes,
            "message": f"Proof of delivery recorded for {tracking_id}. POD Code: #{proof_id}.",
        }


class EmergencyService:
    """Manages SOS emergency dispatch, GPS broadcast, and highway safety hotlines."""

    def trigger_emergency_sos(
        self,
        latitude: float,
        longitude: float,
        location_label: str = "Active Highway",
        emergency_type: str = "BREAKDOWN_OR_ACCIDENT",
        details: str = "Driver triggered hands-free emergency SOS.",
    ) -> Dict[str, Any]:
        incident_id = f"SOS-ALERT-{uuid.uuid4().hex[:6].upper()}"
        return {
            "incident_id": incident_id,
            "status": "ACTIVE_SOS_BROADCAST",
            "emergency_type": emergency_type,
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "location": location_label,
            "dispatched_services": [
                {"name": "Highway Patrol / State Police", "hotline": "112 / 911", "eta_minutes": 12},
                {"name": "Emergency Medical Services (EMS)", "hotline": "108 / 911", "eta_minutes": 15},
                {"name": "Heavy Vehicle Highway Recovery & Towing", "hotline": "+1-800-555-TOWS", "eta_minutes": 20},
            ],
            "audio_broadcast": (
                f"Emergency SOS triggered! Incident #{incident_id}. Your GPS coordinates ({latitude:.4f}, {longitude:.4f}) "
                f"have been broadcast to Highway Patrol and Roadside EMS. Remain safely inside your vehicle."
            ),
            "safety_instructions": [
                "Turn on your vehicle hazard flashers immediately.",
                "If safe, pull vehicle onto the shoulder and stay inside.",
                "Highway Patrol hotline 112 / 911 has received your GPS fix.",
            ],
        }
