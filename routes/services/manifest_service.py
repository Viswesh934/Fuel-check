"""
Trip Manifest & Driver Waybill ("Bilti") Service

Aggregates route details, diesel stops, state VAT arbitrage strategy,
emergency contacts, and road/weather hazards into a structured dispatch
waybill for commercial transport operators and drivers.
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid


class TripManifestService:
    """
    Generates structured digital and printable dispatch waybills (Bilti)
    for long-haul commercial truck operations.
    """

    def generate_manifest(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transforms optimized route response data into an actionable driver manifest.
        """
        route = route_data.get("route", {})
        fuel = route_data.get("fuel", {})
        fuel_stops = route_data.get("fuel_stops", [])
        fuel_strategy = route_data.get("live_fuel_strategy", {})
        travel_events = route_data.get("travel_events", {})
        amenities = route_data.get("copilot_amenities", {})

        manifest_id = f"BLT-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        start_label = route.get("start", {}).get("label", "Origin")
        finish_label = route.get("finish", {}).get("label", "Destination")
        dist_miles = route.get("distance_miles", 0.0)
        dist_km = round(dist_miles * 1.60934, 1)
        duration_hrs = round(route.get("duration_minutes", 0.0) / 60.0, 1)

        consumed_gallons = fuel.get("consumed_gallons", 0.0)
        consumed_liters = round(consumed_gallons * 3.78541, 1)
        total_cost_usd = fuel.get("total_cost", 0.0)
        # Approximate INR conversion at default highway benchmark
        total_cost_inr = round(consumed_liters * 90.75, 2)

        # Emergency Contacts extraction
        hospitals = amenities.get("hospitals", [])
        mechanics = amenities.get("mechanics", [])

        primary_hospital = hospitals[0] if hospitals else {
            "name": "District Civil Emergency Hospital",
            "phone": "108 / 112",
            "city": "En-route Corridor",
        }
        primary_mechanic = mechanics[0] if mechanics else {
            "name": "NH Highway Breakdown & Tyre Care",
            "phone": "1033 (NHAI Emergency)",
            "city": "En-route Highway",
        }

        # Format Stops
        stops_summary: List[Dict[str, Any]] = []
        for s in fuel_stops:
            stops_summary.append({
                "station_name": s.get("name", "Highway Fuel Station"),
                "city": s.get("city", "Highway"),
                "state": s.get("state", "IN"),
                "route_mile": s.get("route_mile", 0.0),
                "price_per_unit": s.get("retail_price") or s.get("price_per_liter", 0.0),
                "gallons_to_buy": s.get("gallons_to_buy", 0.0),
                "estimated_liters": round(s.get("gallons_to_buy", 0.0) * 3.78541, 1),
            })

        # Weather / Hazard Summary
        active_alerts = travel_events.get("active_route_alerts", [])
        alerts_summary = [
            {
                "type": a.get("type", "HAZARD"),
                "title": a.get("title", "Road Caution"),
                "severity": a.get("severity", "INFO"),
                "mile": a.get("route_mile", 0.0),
                "recommendation": a.get("recommended_action", "Drive with caution."),
            }
            for a in active_alerts
        ]

        # Plain-Text Printable Waybill Summary
        text_waybill = self._build_text_waybill(
            manifest_id=manifest_id,
            generated_at=generated_at,
            start_label=start_label,
            finish_label=finish_label,
            dist_km=dist_km,
            dist_miles=dist_miles,
            duration_hrs=duration_hrs,
            consumed_liters=consumed_liters,
            total_cost_inr=total_cost_inr,
            fuel_strategy=fuel_strategy,
            stops_summary=stops_summary,
            primary_hospital=primary_hospital,
            primary_mechanic=primary_mechanic,
            alerts_summary=alerts_summary,
        )

        return {
            "status": "success",
            "manifest_id": manifest_id,
            "generated_at": generated_at,
            "corridor": {
                "start": start_label,
                "finish": finish_label,
                "distance_km": dist_km,
                "distance_miles": dist_miles,
                "drive_time_hours": duration_hrs,
            },
            "fuel_manifest": {
                "consumed_liters": consumed_liters,
                "estimated_cost_inr": total_cost_inr,
                "stops": stops_summary,
                "tax_savings_strategy": fuel_strategy.get("advisory", "Refuel in low-VAT border zones."),
            },
            "emergency_dispatch": {
                "national_emergency": "112",
                "nhai_highway_helpline": "1033",
                "trauma_care": primary_hospital,
                "roadside_mechanic": primary_mechanic,
            },
            "hazard_advisories": alerts_summary,
            "printable_waybill": text_waybill,
        }

    def _build_text_waybill(
        self,
        manifest_id: str,
        generated_at: str,
        start_label: str,
        finish_label: str,
        dist_km: float,
        dist_miles: float,
        duration_hrs: float,
        consumed_liters: float,
        total_cost_inr: float,
        fuel_strategy: Dict[str, Any],
        stops_summary: List[Dict[str, Any]],
        primary_hospital: Dict[str, Any],
        primary_mechanic: Dict[str, Any],
        alerts_summary: List[Dict[str, Any]],
    ) -> str:
        lines = [
            "=" * 60,
            "     FUEL-CHECK COMMERCIAL WAYBILL & DISPATCH MANIFEST",
            f" Manifest ID : {manifest_id}",
            f" Date/Time   : {generated_at}",
            "=" * 60,
            f" CORRIDOR    : {start_label} -> {finish_label}",
            f" DISTANCE    : {dist_km} km ({dist_miles} miles)",
            f" DRIVE TIME  : ~{duration_hrs} hours",
            f" DIESEL EST. : {consumed_liters} Liters (approx. ₹{total_cost_inr:,.2f})",
            "-" * 60,
            " OPTIMAL REFUELING STOPS & VAT ARBITRAGE:",
        ]

        if stops_summary:
            for idx, stop in enumerate(stops_summary, 1):
                lines.append(
                    f"  {idx}. {stop['station_name']} ({stop['city']}, {stop['state']})"
                )
                lines.append(
                    f"     At Mile {stop['route_mile']} | Fill: ~{stop['estimated_liters']} L @ {stop['price_per_unit']}/unit"
                )
        else:
            lines.append("  * Single tank corridor; no en-route refueling required.")

        if fuel_strategy.get("advisory"):
            lines.append(f"  Note: {fuel_strategy['advisory']}")

        lines.extend([
            "-" * 60,
            " EMERGENCY CONTACTS & DISPATCH HELPLINES:",
            "  * National Emergency Police/Ambulance: 112",
            "  * NHAI Highway Helpline (24x7): 1033",
            f"  * Nearest Trauma Care: {primary_hospital.get('name', 'Civil Hospital')} (Ph: {primary_hospital.get('phone', '108')})",
            f"  * Nearest Highway Mechanic: {primary_mechanic.get('name', 'Puncture/Tow')} (Ph: {primary_mechanic.get('phone', '1033')})",
            "-" * 60,
            " ACTIVE HIGHWAY & WEATHER HAZARDS:",
        ])

        if alerts_summary:
            for a in alerts_summary:
                lines.append(f"  * [{a['severity']}] {a['title']}: {a['recommendation']}")
        else:
            lines.append("  * Highway corridor is clear. Drive safely!")

        lines.extend([
            "=" * 60,
            "           SAFE JOURNEY - COMPLIANT LOGISTICS DISPATCH",
            "=" * 60,
        ])
        return "\n".join(lines)
