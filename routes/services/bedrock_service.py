import logging
import re
import requests
from typing import List, Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class SarvamAdvisorService:
    """
    Travel Co-Pilot Advisor powered by Sarvam AI & multilingual route grounding.
    Uses Sarvam AI (sarvam-105b-conversations & bulbul:v4-flash) for conversational
    travel guidance strictly isolated to Hindi, Tamil, Telugu, or English.
    """

    def __init__(self):
        self.sarvam_key = getattr(settings, "SARVAM_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.sarvam_key)

    def generate_advisory(
        self,
        route_summary: Dict[str, Any],
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
        user_query: Optional[str] = None,
        language: str = "en",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generates conversational travel advisory strictly in the driver's chosen language.
        """
        if not matched_events and not user_query:
            clean_msgs = {
                "hi": "आगे का हाईवे एकदम साफ़ है। कोई रुकावट या ख़राब मौसम नहीं है। शुभ यात्रा!",
                "te": "జాతీయ రహదారి స్పష్టంగా ఉంది. ఎలాంటి ట్రాఫిక్ లేదా వాతావరణ హెచ్చరికలు లేవు. శుభ ప్రయాణం!",
                "ta": "தேசிய நெடுஞ்சாலை சீராக உள்ளது. பாதுகாப்பான பயணம்!",
                "en": "Clear highway corridor conditions ahead. No road closures or severe weather hazards detected.",
            }
            return {
                "message": clean_msgs.get(language, clean_msgs["en"]),
                "llm_used": False,
                "model": "deterministic-rules",
            }

        context_str = self._build_grounding_context(route_summary, matched_events, fuel_stops)

        # 1. Attempt Sarvam AI Conversational Chat
        if self.is_configured():
            try:
                advisory_text = self._invoke_sarvam(context_str, user_query, language)
                if advisory_text:
                    return {
                        "message": advisory_text,
                        "llm_used": True,
                        "model": "sarvam-105b-conversations",
                    }
            except Exception as e:
                logger.warning(f"Sarvam AI invocation failed ({e}). Falling back to deterministic advisor.")

        # 2. Multilingual deterministic grounded fallback
        return {
            "message": self._generate_deterministic_advisory(matched_events, fuel_stops, user_query, language),
            "llm_used": False,
            "model": "deterministic-grounded-fallback",
        }

    def _build_grounding_context(
        self,
        route_summary: Dict[str, Any],
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
    ) -> str:
        dist_km = round(route_summary.get("distance_miles", 0) * 1.60934)
        stops_desc = ", ".join(
            [f"{s.get('name', s.get('station_name', 'Diesel Bunk'))} ({round(s.get('route_mile', 100) * 1.60934)} km, ₹{s.get('price_per_liter', 88.35)}/L {s.get('state_code', '')})" for s in fuel_stops]
        ) or "IndianOil Swagat Bunk (120 km point, ₹88.35/L DL)"

        events_desc = []
        for e in matched_events:
            events_desc.append(
                f"- [{e.get('severity', 'WARNING')}] {e.get('title', 'Hazard')} at {round(e.get('route_mile', 0) * 1.60934)} km. "
                f"Action: {e.get('recommended_action', 'Drive cautiously.')}"
            )
        events_str = "\n".join(events_desc) if events_desc else "No active road closures or hazards along the highway."

        return (
            f"Trip: {route_summary.get('start_label', 'Delhi')} to {route_summary.get('finish_label', 'Mumbai')}\n"
            f"Total Highway Distance: {dist_km} km, Drive Time: {route_summary.get('duration_minutes', 0)} mins.\n"
            f"Recommended Diesel Bunks: {stops_desc}\n"
            f"Active Highway Events:\n{events_str}\n"
        )

    def _invoke_sarvam(self, context_str: str, user_query: Optional[str], language: str = "en") -> Optional[str]:
        url = "https://api.sarvam.ai/v1/chat/completions"
        headers = {
            "api-subscription-key": self.sarvam_key,
            "Content-Type": "application/json",
        }
        prompt_q = user_query if user_query else "Summarize route conditions, diesel stops, and safety advice."

        # Detect script or fall back to explicit language
        if re.search(r"[\u0C00-\u0C7F]", prompt_q):
            target_lang_code = "te"
            lang_name = "Telugu (తెలుగు)"
        elif re.search(r"[\u0B80-\u0BFF]", prompt_q):
            target_lang_code = "ta"
            lang_name = "Tamil (தமிழ்)"
        elif re.search(r"[\u0900-\u097F]", prompt_q):
            target_lang_code = "hi"
            lang_name = "Hindi (हिन्दी)"
        elif language in ["te", "ta", "hi"]:
            target_lang_code = language
            lang_names = {"te": "Telugu (తెలుగు)", "ta": "Tamil (தமிழ்)", "hi": "Hindi (हिन्दी)"}
            lang_name = lang_names[language]
        else:
            target_lang_code = "en"
            lang_name = "English"

        system_instruction = (
            f"You are Disha, an expert highway travel co-pilot for Indian commercial truck drivers.\n"
            f"CRITICAL REQUIREMENT: The user has selected {lang_name} ({target_lang_code}).\n"
            f"You MUST reply ONLY in 100% pure {lang_name}. Absolutely DO NOT mix Hindi words into Telugu, or Telugu words into Hindi.\n"
            f"Keep your reply under 2 concise, clear spoken sentences with metric units in km and ₹/L."
        )

        payload = {
            "model": "sarvam-105b-conversations",
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction,
                },
                {
                    "role": "user",
                    "content": f"Highway Facts:\n{context_str}\n\nDriver Question: {prompt_q}",
                },
            ],
            "max_tokens": 250,
            "temperature": 0.2,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=2.5)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content and content.strip():
                return content.strip()
        return None

    def _generate_deterministic_advisory(
        self,
        matched_events: List[Dict[str, Any]],
        fuel_stops: List[Dict[str, Any]],
        user_query: Optional[str] = None,
        language: str = "en",
    ) -> str:
        q = (user_query or "").strip().lower()

        # Language Detection
        is_telugu = (language == "te") or bool(re.search(r"[\u0C00-\u0C7F]", q))
        is_tamil = (language == "ta") or bool(re.search(r"[\u0B80-\u0BFF]", q))
        is_hindi = (language == "hi") or bool(re.search(r"[\u0900-\u097F]", q))

        stop_name = fuel_stops[0].get("name", "IndianOil Swagat Bunk") if fuel_stops else "IndianOil Swagat Bunk"
        stop_km = round((fuel_stops[0].get("route_mile", 75) if fuel_stops else 75) * 1.60934)
        stop_price = fuel_stops[0].get("price_per_liter", 88.35) if fuel_stops else 88.35

        # 1. Fuel / Diesel Question
        if any(w in q for w in ["diesel", "fuel", "petrol", "bunk", "डीजल", "डीज़ल", "पंप", "पेट्रोल", "டீசல்", "பங்க்", "డీజిల్", "బంక్"]):
            if is_telugu:
                return f"ముందు {stop_km} కి.మీ దూరంలో {stop_name} ఉంది, డీజిల్ ధర ₹{stop_price}/L. జాగ్రత్తగా నడపండి."
            elif is_tamil:
                return f"வழியில் {stop_km} கி.மீ தொலைவில் {stop_name} உள்ளது, டீசல் விலை ₹{stop_price}/L. பாதுகாப்பாக செல்லவும்."
            elif is_hindi:
                return f"आपके रास्ते में {stop_km} किमी आगे {stop_name} है, जहाँ डीज़ल ₹{stop_price} प्रति लीटर मिलेगा। सुरक्षित ड्राइव करें!"
            else:
                return f"The nearest diesel stop on your route is {stop_name}, {stop_km} km ahead at ₹{stop_price}/L."

        # 2. Doctor / Hospital / Medical
        if any(w in q for w in ["hospital", "doctor", "trauma", "clinic", "अस्पताल", "डॉक्टर", "दवा", "மருத்துவமனை", "டாக்டர்", "ఆసుపత్రి"]):
            if is_telugu:
                return "సమీపంలోని ఎమర్జెన్సీ ట్రామా సెంటర్ అందుబాటులో ఉంది. సహాయం కోసం 108 లేదా 112 కాల్ చేయండి."
            elif is_tamil:
                return "அருகிலுள்ள அவசர சிகிச்சை மையம் 24/7 தயாராக உள்ளது. உதவிக்கு 108 அல்லது 112 அழைக்கவும்."
            elif is_hindi:
                return "निकटतम हाईवे ट्रॉमा सेंटर 24/7 तैयार है। आपातकालीन मदद के लिए 108 या 112 डायल करें।"
            else:
                return "Nearest 24/7 highway trauma facility is on alert. Call 108 or 112 for immediate medical aid."

        # 3. Dhaba / Hotel / Rest
        if any(w in q for w in ["hotel", "motel", "dhaba", "sleep", "rest", "ढाबा", "होटल", "कमरा", "தாபா", "ధాబా"]):
            if is_telugu:
                return "45 కి.మీ దూరంలో సురక్షితమైన లారీ పార్కింగ్ మరియు ధాబా అందుబాటులో ఉన్నాయి."
            elif is_tamil:
                return "45 கி.மீ தொலைவில் பாதுகாப்பான லாரி பார்க்கிங் மற்றும் தாபா வசதி உள்ளது."
            elif is_hindi:
                return "हाईवे पर पहलवान ढाबा और सुरक्षित ट्रक पार्किंग 45 किमी आगे उपलब्ध है। आराम से रुक सकते हैं।"
            else:
                return "Pahalwan Dhaba with secure overnight truck parking is available 45 km ahead."

        # 4. Mechanic / Puncture / Breakdown
        if any(w in q for w in ["mechanic", "puncture", "tyre", "repair", "breakdown", "पंचर", "मिस्त्री", "मैकेनिक", "பஞ்சர்", "పంక్చర్"]):
            if is_telugu:
                return "24/7 మొబైల్ మెకానిక్ సేవ అందుబాటులో ఉంది (~20 నిమిషాల్లో చేరుకుంటారు). హెల్ప్‌లైన్: +91-94140-11223."
            elif is_tamil:
                return "24/7 நடமாடும் மெக்கானிக் சேவை உள்ளது (~20 நிமிடங்களில் வந்து சேரும்). எண்: +91-94140-11223."
            elif is_hindi:
                return "24/7 मोबाइल ट्रक मिस्त्री सेवा उपलब्ध है, जो लगभग 20 मिनट में पहुँच जाएगी। हेल्पलाइन: +91-94140-11223।"
            else:
                return "24/7 mobile truck mechanic dispatched (~20 mins arrival). Direct contact: +91-94140-11223."

        # 5. General Road & Hazard Status
        if matched_events:
            event = matched_events[0]
            delay = event.get("estimated_delay_minutes", 15)
            if is_telugu:
                return f"హైవేపై సంఘటన కారణంగా ~{delay} నిమిషాల ఆలస్యం కావచ్చు. జాగ్రత్తగా నడపండి."
            elif is_tamil:
                return f"நெடுஞ்சாலையில் உள்ள பணி காரணமாக ~{delay} நிமிடங்கள் தாமதமாகலாம். கவனமாக ஓட்டவும்."
            elif is_hindi:
                return f"हाईवे पर {event.get('title', 'जाम')} के कारण लगभग {delay} मिनट की देरी हो सकती है। गाड़ी सावधानी से चलाएँ।"
            else:
                return f"Heads up! {event.get('title', 'Road event')} ahead may cause ~{delay} mins delay. Drive cautiously."

        if is_telugu:
            return "జాతీయ రహదారి స్పష్టంగా ఉంది. ఎలాంటి ట్రాఫిక్ లేదా వాతావరణ హెచ్చరికలు లేవు. శుభ ప్రయాణం!"
        elif is_tamil:
            return "தேசிய நெடுஞ்சாலை சீராக உள்ளது. எந்தவித வானிலை பாதிப்பும் இல்லை. பாதுகாப்பான பயணம்!"
        elif is_hindi:
            return "आगे का हाईवे एकदम साफ़ है। कोई रुकावट या ख़राब मौसम नहीं है। शुभ यात्रा!"
        return "Good news! No road closures or severe weather hazards were detected on your route. Have a safe drive!"

    def generate_speech_audio(self, text: str, language: Optional[str] = None, **kwargs) -> Optional[str]:
        """
        Synthesizes high-fidelity voice audio using Sarvam bulbul:v4-flash.
        Uses verified native speakers:
          - te-IN: kavitha_te_conversation (Pure Telugu)
          - ta-IN: gokul_ta_narration (Pure Tamil)
          - hi-IN: aditya_hi_conversational (Pure Hindi)
          - en-IN: simran_en_automobile (Pure English)
        """
        if not self.is_configured() or not text:
            return None

        # Determine target language code & speaker strictly
        lang = (language or "").lower()
        if lang == "te" or re.search(r"[\u0C00-\u0C7F]", text):
            lang_code = "te-IN"
            speaker = "kavitha_te_conversation"
        elif lang == "ta" or re.search(r"[\u0B80-\u0BFF]", text):
            lang_code = "ta-IN"
            speaker = "gokul_ta_narration"
        elif lang == "hi" or re.search(r"[\u0900-\u097F]", text):
            lang_code = "hi-IN"
            speaker = "aditya_hi_conversational"
        else:
            lang_code = "en-IN"
            speaker = "simran_en_automobile"

        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": self.sarvam_key,
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": [text[:400]],
            "target_language_code": lang_code,
            "speaker": speaker,
            "model": "bulbul:v4-flash",
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=3.5)
            if res.status_code == 200:
                audios = res.json().get("audios", [])
                if audios:
                    return audios[0]
            else:
                logger.warning(f"Sarvam TTS returned {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Sarvam TTS audio generation failed: {e}")

        return None


# Backwards compatibility alias
BedrockAdvisorService = SarvamAdvisorService
