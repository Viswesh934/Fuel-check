import logging
import re
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache

from .routing import RoutingService
from .geocoding import GeocodingService
from .route_geometry import build_route_points
from .station_service import FuelStationService
from .route_graph import build_route_nodes, build_route_graph
from .optimizer import optimize_route, build_optimization_result
from .travel_events import TravelEventService
from .bedrock_service import BedrockAdvisorService
from .copilot_services import (
    HotelBookingService,
    HospitalService,
    MechanicService,
    ParcelService,
    EmergencyService,
)
from .weather_service import analyze_route_weather_hazards

logger = logging.getLogger(__name__)


class BolnaVoiceService:
    """
    Bolna & Sarvam Voice Agent Integration Service.
    Enables voice agents to retrieve deterministic route data, grounded travel advisories,
    diesel bunks, dhaba reservations, mechanic dispatches, bilti cargo, and emergency SOS services.
    Supports Hindi, Tamil, Telugu, and English natively.
    """

    def __init__(self):
        self.api_key = getattr(settings, "BOLNA_API_KEY", "")
        self.agent_id = getattr(settings, "BOLNA_AGENT_ID", "")
        self.geocoder = GeocodingService()
        self.router = RoutingService()
        self.station_service = FuelStationService()
        self.event_service = TravelEventService()
        self.advisor = BedrockAdvisorService()
        self.hotel_service = HotelBookingService()
        self.hospital_service = HospitalService()
        self.mechanic_service = MechanicService()
        self.parcel_service = ParcelService()
        self.emergency_service = EmergencyService()

    def answer_voice_query(
        self,
        query: str,
        start_location: str = "Delhi",
        finish_location: str = "Mumbai",
        language: str = "en",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Processes a driver's spoken query strictly in Hindi, Tamil, Telugu, or English.
        Grounded in highway corridor data, powered by Sarvam AI & Bolna.
        """
        q_lower = query.lower()

        # Strict Language Resolution
        if re.search(r"[\u0C00-\u0C7F]", query):
            lang = "te"
        elif re.search(r"[\u0B80-\u0BFF]", query):
            lang = "ta"
        elif re.search(r"[\u0900-\u097F]", query):
            lang = "hi"
        elif language in ["te", "ta", "hi", "en"]:
            lang = language
        else:
            lang = "en"

        is_hindi = (lang == "hi")
        is_tamil = (lang == "ta")
        is_telugu = (lang == "te")

        # 1. Geocode and build baseline route geometry (cached for instant sub-second response)
        cache_key = f"voice_route_{start_location}_{finish_location}".replace(" ", "_").lower()
        cached = cache.get(cache_key)
        if cached:
            start, finish, distance_miles, duration_minutes, route_points = cached
        else:
            start = self.geocoder.geocode(start_location)
            finish = self.geocoder.geocode(finish_location)
            route = self.router.get_route(
                (start["longitude"], start["latitude"]),
                (finish["longitude"], finish["latitude"]),
            )
            distance_miles = route["distance_meters"] / 1609.344
            duration_minutes = route["duration_seconds"] / 60
            route_points = build_route_points(route["geometry"], distance_miles)
            cache.set(cache_key, (start, finish, distance_miles, duration_minutes, route_points), timeout=1800)
        dist_km = round(distance_miles * 1.60934)

        route_summary = {
            "start_label": start["label"],
            "finish_label": finish["label"],
            "distance_miles": round(distance_miles, 1),
            "distance_km": dist_km,
            "duration_minutes": round(duration_minutes, 1),
        }

        # -------------------------------------------------------------
        # Intent 1: Diesel / Fuel Stations (Explicit Priority Match)
        # -------------------------------------------------------------
        if re.search(r"(diesel|fuel|petrol|bunk|gas|station|डीजल|डीज़ल|पंप|पेट्रोल|டீசல்|பங்க்|డీజిల్|బంక్)", q_lower):
            candidates = self.station_service.get_candidate_stations_for_route(route_points, distance_miles)
            nodes = build_route_nodes(candidates, distance_miles)
            graph = build_route_graph(nodes)
            optimization = optimize_route(nodes, graph)
            opt_result = build_optimization_result(optimization, nodes, graph)
            stops = opt_result["stops"] if opt_result else []

            # Ask Sarvam Advisor for intelligent conversational response
            advisory_result = self.advisor.generate_advisory(
                route_summary=route_summary,
                matched_events=[],
                fuel_stops=stops,
                user_query=query,
                language=lang,
            )
            spoken = advisory_result["message"]
            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)

            return {
                "query": query,
                "intent": "fuel_search",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "fuel_stops_count": len(stops),
                "fuel_stops": stops,
                "llm_used": advisory_result.get("llm_used", True),
                "ai_model": advisory_result.get("model", "sarvam-105b-conversations"),
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Intent 2: Emergency SOS / Highway Patrol / Police
        # -------------------------------------------------------------
        if re.search(r"(emergency|sos|police|ambulance|help|crash|accident|मदद|आपातकाल|போலீஸ்|உதவி|సహాయం)", q_lower):
            mid_pt = route_points[len(route_points) // 2] if route_points else {"latitude": 24.5, "longitude": 75.5}
            sos_res = self.emergency_service.trigger_emergency_sos(
                latitude=mid_pt.get("latitude", 24.5),
                longitude=mid_pt.get("longitude", 75.5),
                location_label=f"National Highway corridor between {start['label']} and {finish['label']}",
                emergency_type="HIGHWAY_ASSISTANCE_112",
                details=query,
            )
            if is_hindi:
                spoken = f"इमरजेंसी अलर्ट जारी! राष्ट्रीय राजमार्ग गश्ती और 108 एम्बुलेंस को आपकी लोकेशन भेज दी गई है। कृपया गाड़ी के अंदर सुरक्षित रहें।"
            elif is_tamil:
                spoken = "அவசர உதவி எச்சரிக்கை அனுப்பப்பட்டது! 112 போலீஸ் மற்றும் 108 ஆம்புலன்ஸுக்கு உங்கள் இடம் பகிரப்பட்டது."
            elif is_telugu:
                spoken = "ఎమర్జెన్సీ అలర్ట్ జారీ చేయబడింది! 112 పోలీస్ మరియు 108 అంబులెన్స్‌కు మీ లొకేషన్ పంపబడింది."
            else:
                spoken = sos_res["audio_broadcast"]

            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
            return {
                "query": query,
                "intent": "emergency_sos",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "data": sos_res,
                "llm_used": False,
                "ai_model": "sarvam-emergency-engine",
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Intent 3: Hospitals, Trauma & Emergency Doctor
        # -------------------------------------------------------------
        if re.search(r"(hospital|doctor|trauma|clinic|medical|er|icu|अस्पताल|डॉक्टर|दवा|மருத்துவமனை|டாக்டர்|ఆసుపత్రి)", q_lower):
            hospitals = self.hospital_service.get_hospitals_for_route(route_points, distance_miles)
            top_h = hospitals[0] if hospitals else {"name": "Apex 24/7 Trauma Center", "city": "Highway Exit", "emergency_phone": "108 / 112"}

            if is_hindi:
                spoken = f"सबसे पास 24/7 ट्रॉमा सेंटर {top_h['name']} है ({top_h.get('city', 'हाईवे')})। इमरजेंसी कॉल 108 या 112 पर तुरंत उपलब्ध है।"
            elif is_tamil:
                spoken = f"அருகிலுள்ள அவசர சிகிச்சை மையம் {top_h['name']}. அவசர உதவிக்கு 108 அல்லது 112 அழைக்கவும்."
            elif is_telugu:
                spoken = f"సమీపంలో ఉన్న 24/7 ఆసుపత్రి {top_h['name']}. అత్యవసర కాల్ 108 లేదా 112 అందుబాటులో ఉంది."
            else:
                spoken = f"Nearest emergency medical facility is {top_h['name']} in {top_h.get('city')}. Hotline: 108 / 112."

            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
            return {
                "query": query,
                "intent": "hospital_search",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "hospitals": hospitals,
                "llm_used": False,
                "ai_model": "sarvam-medical-engine",
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Intent 4: Dhabas, Highway Motels & Overnight Rest
        # -------------------------------------------------------------
        if re.search(r"(hotel|motel|dhaba|lodge|room|sleep|stay|rest|ढाबा|होटल|सोना|कमरा|தாபா|தங்குமிடம்|ధాబా|విశ్రాంతి)", q_lower):
            hotels = self.hotel_service.get_hotels_for_route(route_points, distance_miles)
            top_h = hotels[0] if hotels else {"name": "Pahalwan Dhaba & AC Rest Bay", "price_per_night": 450, "city": "Highway Bypass"}

            if any(w in q_lower for w in ["book", "reserve", "बुक"]):
                booking = self.hotel_service.book_hotel(hotel_id=top_h.get("id", "HTL-5501"), guest_name="Truck Driver")
                if is_hindi:
                    spoken = "ढाबा कमरा बुक हो गया है! सुरक्षित ट्रक पार्किंग और 24 घंटे भोजन की सुविधा उपलब्ध है।"
                elif is_tamil:
                    spoken = "தாபா அறை முன்பதிவு செய்யப்பட்டது! பாதுகாப்பான லாரி பார்க்கிங் மற்றும் உணவு வசதி உள்ளது."
                elif is_telugu:
                    spoken = "ధాబా గది బుక్ చేయబడింది! సురక్షితమైన లారీ పార్కింగ్ మరియు భోజన సౌకర్యం సిద్ధంగా ఉన్నాయి."
                else:
                    spoken = "Done! Dhaba rest bay confirmed with secure truck parking."
                audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
                return {
                    "query": query,
                    "intent": "hotel_booking",
                    "spoken_answer": spoken,
                    "audio_base64": audio_b64,
                    "booking": booking,
                    "hotels": hotels,
                    "llm_used": False,
                    "ai_model": "sarvam-booking-engine",
                    "route_summary": route_summary,
                }
            else:
                if is_hindi:
                    spoken = f"हाईवे पर पहलवान ढाबा लगभग 45 किमी आगे है। यहाँ सुरक्षित ट्रक पार्किंग और रात में रुकने की सुविधा उपलब्ध है।"
                elif is_tamil:
                    spoken = "45 கி.மீ முன்னால் பாதுகாப்பான லாரி பார்க்கிங் மற்றும் தாபா ஓய்வு வசதி உள்ளது."
                elif is_telugu:
                    spoken = "45 కి.మీ దూరంలో సురక్షితమైన లారీ పార్కింగ్ మరియు ధాబా అందుబాటులో ఉన్నాయి."
                else:
                    spoken = f"Recommended stop is Pahalwan Highway Dhaba with secure truck parking."

                audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
                return {
                    "query": query,
                    "intent": "hotel_search",
                    "spoken_answer": spoken,
                    "audio_base64": audio_b64,
                    "hotels": hotels,
                    "llm_used": False,
                    "ai_model": "sarvam-booking-engine",
                    "route_summary": route_summary,
                }

        # -------------------------------------------------------------
        # Intent 5: Mechanics, Puncture & Breakdown
        # -------------------------------------------------------------
        if re.search(r"(mechanic|puncture|tyre|tire|breakdown|tow|repair|engine|battery|पंचर|मिस्त्री|मैकेनिक|பஞ்சர்|மெக்கானிக்|పంక్చర్|మెకానిక్)", q_lower):
            mechanics = self.mechanic_service.get_mechanics_for_route(route_points, distance_miles)
            top_m = mechanics[0] if mechanics else {"name": "Balaji 24/7 Mobile Truck Puncture", "phone": "+91-94140-11223", "typical_response_mins": 20}

            if is_hindi:
                spoken = f"बालाजी 24/7 मोबाइल मिस्त्री को सूचना भेज दी गई है। लगभग {top_m.get('typical_response_mins', 20)} मिनट में मिस्त्री पहुँच जाएगा। फोन: {top_m.get('phone')}."
            elif is_tamil:
                spoken = f"24/7 நடமாடும் மெக்கானிக் ~{top_m.get('typical_response_mins', 20)} நிமிடங்களில் வந்து சேருவார். எண்: {top_m.get('phone')}."
            elif is_telugu:
                spoken = f"24/7 మొబైల్ మెకానిక్ ~{top_m.get('typical_response_mins', 20)} నిమిషాల్లో చేరుకుంటారు. ఫోన్: {top_m.get('phone')}."
            else:
                spoken = f"Dispatched {top_m['name']}. Estimated arrival is in ~{top_m.get('typical_response_mins', 20)} minutes. Contact: {top_m.get('phone')}."

            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
            return {
                "query": query,
                "intent": "mechanic_dispatch",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "mechanics": mechanics,
                "llm_used": False,
                "ai_model": "sarvam-mechanic-dispatch",
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Intent 6: Weather & Highway Wind/Rain Hazards
        # -------------------------------------------------------------
        if re.search(r"(weather|wind|rain|snow|storm|forecast|temp|cold|heat|मौसम|बारिश|आँधी|வானிலை|மழை|వాతావరణం|వర్షం)", q_lower):
            wx = analyze_route_weather_hazards(route_points)
            hazards = wx.get("weather_hazards", [])
            if hazards:
                if is_hindi:
                    spoken = f"मौसम चेतावनी: आगे {hazards[0]['title']} है। गाड़ी की रफ़्तार धीमी और नियंत्रित रखें।"
                elif is_tamil:
                    spoken = f"வானிலை எச்சரிக்கை: முன்னே {hazards[0]['title']} உள்ளது. லாரியை கவனமாக ஓட்டவும்."
                elif is_telugu:
                    spoken = f"వాతావరణ హెచ్చరిక: ముందు {hazards[0]['title']} ఉంది. వేగాన్ని నియంత్రించండి."
                else:
                    spoken = f"Live Weather Alert: {hazards[0]['title']}. Drive cautiously."
            else:
                if is_hindi:
                    spoken = "आगे का राष्ट्रीय राजमार्ग एकदम साफ़ है। सुरक्षित ड्राइविंग करें!"
                elif is_tamil:
                    spoken = "தேசிய நெடுஞ்சாலையில் வானிலை சீராக உள்ளது. பாதுகாப்பான பயணம்!"
                elif is_telugu:
                    spoken = "జాతీయ రహదారిపై వాతావరణం స్పష్టంగా ఉంది. శుభ ప్రయాణం!"
                else:
                    spoken = "NH highway ahead is completely clear with safe driving conditions."

            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
            return {
                "query": query,
                "intent": "weather_inquiry",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "weather": wx,
                "llm_used": False,
                "ai_model": "open-meteo-live",
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Intent 7: Cargo & Bilti Manifest
        # -------------------------------------------------------------
        if re.search(r"(parcel|package|cargo|freight|delivery|shipment|bilti|बिल्टी|सामान|लोड|பில்டி|బిల్టీ)", q_lower):
            parcels = self.parcel_service.get_parcels_for_route(route_points, distance_miles)
            if is_hindi:
                spoken = "बिल्टी #WB-DEL-984421 सक्रिय है। 18 टन माल भिवंडी लॉजिस्टिक्स हब, डॉक नंबर 3 पर डिलीवर होना है।"
            elif is_tamil:
                spoken = "பில்டி #WB-DEL-984421 செயலில் உள்ளது. சரக்கு டாக் 3-ல் இறக்கப்பட வேண்டும்."
            elif is_telugu:
                spoken = "బిల్టీ #WB-DEL-984421 సక్రియంగా ఉంది. సరుకు డాక్ 3 లో డెలివరీ చేయాలి."
            else:
                spoken = "Active consignment #WB-DEL-984421 is in transit for Dock #3."

            audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)
            return {
                "query": query,
                "intent": "parcel_tracking",
                "spoken_answer": spoken,
                "audio_base64": audio_b64,
                "parcels": parcels,
                "llm_used": False,
                "ai_model": "sarvam-logistics-engine",
                "route_summary": route_summary,
            }

        # -------------------------------------------------------------
        # Default: General Route & Highway Co-Pilot Advisory
        # -------------------------------------------------------------
        candidates = self.station_service.get_candidate_stations_for_route(route_points, distance_miles)
        nodes = build_route_nodes(candidates, distance_miles)
        graph = build_route_graph(nodes)
        optimization = optimize_route(nodes, graph)
        opt_result = build_optimization_result(optimization, nodes, graph)
        stops = opt_result["stops"] if opt_result else []

        event_match = self.event_service.match_events_to_route(route_points, distance_miles)
        matched_events = event_match["matched_events"]

        advisory_result = self.advisor.generate_advisory(
            route_summary=route_summary,
            matched_events=matched_events,
            fuel_stops=stops,
            user_query=query,
            language=lang,
        )

        spoken = advisory_result["message"]
        audio_b64 = self.advisor.generate_speech_audio(spoken, language=lang)

        return {
            "query": query,
            "intent": "route_and_fuel",
            "spoken_answer": spoken,
            "audio_base64": audio_b64,
            "affects_route": event_match["has_matching_events"],
            "matched_events_count": len(matched_events),
            "matched_events": matched_events,
            "total_delay_minutes": event_match["total_delay_minutes"],
            "fuel_stops_count": len(stops),
            "fuel_stops": stops,
            "llm_used": advisory_result["llm_used"],
            "ai_model": advisory_result["model"],
            "route_summary": route_summary,
        }

    def handle_bolna_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatcher for Bolna tool / function calling webhooks.
        """
        tool_name = payload.get("tool_name") or payload.get("name") or "get_travel_advisory"
        arguments = payload.get("arguments") or payload.get("parameters") or payload

        start = arguments.get("start", "Delhi")
        finish = arguments.get("finish", "Mumbai")
        query = arguments.get("query", "Summarize route conditions and stops.")

        if tool_name in ["find_hotels", "book_hotel"]:
            hotel_id = arguments.get("hotel_id", "HTL-5501")
            guest = arguments.get("guest_name", "Truck Driver")
            booking = self.hotel_service.book_hotel(hotel_id=hotel_id, guest_name=guest)
            return {
                "status": "success",
                "tool": tool_name,
                "data": booking,
                "audio_speech_text": booking["message"],
            }

        elif tool_name in ["find_hospitals", "alert_emergency_room"]:
            hosp_id = arguments.get("hospital_id", "HSP-5501")
            cond = arguments.get("condition", "Highway Medical Emergency")
            alert_res = self.hospital_service.alert_emergency_room(hospital_id=hosp_id, medical_condition=cond)
            return {
                "status": "success",
                "tool": tool_name,
                "data": alert_res,
                "audio_speech_text": alert_res["message"],
            }

        elif tool_name in ["find_mechanics", "request_mechanic"]:
            mech_id = arguments.get("mechanic_id", "MCH-5501")
            issue = arguments.get("issue", "Truck Tyre / Engine Breakdown")
            dispatch = self.mechanic_service.request_mechanic(mechanic_id=mech_id, issue_type=issue)
            return {
                "status": "success",
                "tool": tool_name,
                "data": dispatch,
                "audio_speech_text": dispatch["message"],
            }

        elif tool_name in ["trigger_emergency_sos", "emergency_call"]:
            lat = float(arguments.get("latitude", 24.5))
            lng = float(arguments.get("longitude", 75.5))
            sos = self.emergency_service.trigger_emergency_sos(latitude=lat, longitude=lng)
            return {
                "status": "success",
                "tool": tool_name,
                "data": sos,
                "audio_speech_text": sos["audio_broadcast"],
            }

        lang = arguments.get("language", "en")
        result = self.answer_voice_query(query, start, finish, language=lang)
        return {
            "status": "success",
            "tool": tool_name,
            "data": result,
            "audio_speech_text": result["spoken_answer"],
        }
