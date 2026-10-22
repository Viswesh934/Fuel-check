import json
import logging
from typing import List, Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class BedrockAdvisorService:
    """
    AWS Bedrock Travel Co-Pilot Advisor.
    Strictly conditional AI invocation:
    - No matching conditions on route = NO LLM call (zero cost).
    - AI is invoked only when events affect the route or traveler asks conversational questions.
    - Grounded strictly in Fuel Check's deterministic backend data.
    """

    def __init__(self):
        self.access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        self.secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        self.region = getattr(settings, "AWS_DEFAULT_REGION", "us-east-1")
        self.model_id = getattr(settings, "BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key)

    def generate_advisory(
        self,
        route_summary: Dict[str, Any],
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
        user_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates conversational travel advisory or answers user questions.
        Enforces the cost-conscious principle:
        If no events match and no explicit user query exists, skips Bedrock completely!
        """
        # RULE: No matching condition and no user query -> NO LLM CALL
        if not matched_events and not user_query:
            return {
                "message": "Clear conditions ahead. No road closures or weather hazards detected along your route.",
                "llm_used": False,
                "model": "deterministic-rules",
            }

        # Build grounded context from Fuel Check backend truth
        context_str = self._build_grounding_context(route_summary, matched_events, fuel_stops)

        # Attempt Bedrock invocation if credentials are configured
        if self.is_configured():
            try:
                advisory_text = self._invoke_bedrock(context_str, user_query)
                return {
                    "message": advisory_text,
                    "llm_used": True,
                    "model": self.model_id,
                }
            except Exception as e:
                logger.warning(f"AWS Bedrock invocation failed ({e}). Falling back to deterministic advisor.")

        # Deterministic grounded fallback (100% reliable without AWS credentials)
        return {
            "message": self._generate_deterministic_advisory(matched_events, fuel_stops, user_query),
            "llm_used": False,
            "model": "deterministic-grounded-fallback",
        }

    def _build_grounding_context(
        self,
        route_summary: Dict[str, Any],
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
    ) -> str:
        stops_desc = ", ".join(
            [f"{s['name']} (Mile {s['route_mile']}, ${s['price_per_gallon']:.2f}/gal)" for s in fuel_stops]
        ) or "None (direct trip on single tank)"

        events_desc = []
        for e in matched_events:
            events_desc.append(
                f"- [{e['severity']}] {e['title']} at Mile {e.get('route_mile', 'N/A')} ({e.get('corridor', 'Highway')}). "
                f"Expected delay: {e.get('estimated_delay_minutes', 0)} mins. Details: {e['description']}. "
                f"Action: {e['recommended_action']}"
            )
        events_str = "\n".join(events_desc) if events_desc else "No active hazards along route."

        return (
            f"Trip: {route_summary.get('start_label', 'Start')} to {route_summary.get('finish_label', 'Destination')}\n"
            f"Total Distance: {route_summary.get('distance_miles', 0)} miles, Drive Time: {route_summary.get('duration_minutes', 0)} mins.\n"
            f"Optimal Fuel Stops: {stops_desc}\n"
            f"Active Travel Events on Route:\n{events_str}\n"
        )

    def _invoke_bedrock(self, context_str: str, user_query: Optional[str]) -> str:
        import boto3

        client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

        system_prompt = (
            "You are the Fuel Check Travel Awareness Co-Pilot. You assist drivers by providing clear, "
            "practical, audio-friendly travel briefings. You must only reference the provided route facts and events. "
            "Keep advice concise (under 3 sentences) suitable for hands-free voice readouts."
        )

        prompt_question = user_query if user_query else "Summarize what the events mean for my journey and fuel stops."
        full_prompt = f"{system_prompt}\n\nFacts:\n{context_str}\n\nDriver Question: {prompt_question}\nCo-Pilot Response:"

        # Formatting payload for Amazon Nova / Claude models
        if "nova" in self.model_id.lower():
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": full_prompt}],
                    }
                ],
                "inferenceConfig": {"max_new_tokens": 150, "temperature": 0.2},
            }
        else:
            # Standard Anthropic Claude on Bedrock format
            payload = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 150,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": full_prompt}],
            }

        response = client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )

        resp_body = json.loads(response["body"].read().decode("utf-8"))

        if "nova" in self.model_id.lower():
            return resp_body["output"]["message"]["content"][0]["text"].strip()
        elif "content" in resp_body:
            return resp_body["content"][0]["text"].strip()
        elif "completion" in resp_body:
            return resp_body["completion"].strip()

        return str(resp_body)

    def _generate_deterministic_advisory(
        self,
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
        user_query: Optional[str],
    ) -> str:
        """
        Deterministic, grounded response generator when Bedrock is in zero-cost mode or credentials unconfigured.
        """
        if not matched_events:
            return "Good news! No road closures or weather hazards were detected on your route. Have a safe drive!"

        primary_event = matched_events[0]
        event_title = primary_event.get("title", "Road incident")
        event_mile = primary_event.get("route_mile", "along route")
        delay = primary_event.get("estimated_delay_minutes", 15)
        action = primary_event.get("recommended_action", "Proceed with caution.")

        advisory = (
            f"Heads up! {event_title} affects your route near Mile {event_mile}, "
            f"with an estimated delay of ~{delay} minutes. {action}"
        )

        if fuel_stops:
            advisory += f" Your planned refuel at {fuel_stops[0]['name']} remains reachable."

        return advisory
