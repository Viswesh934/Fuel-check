/**
 * Fuel Check — Indian Truck Driver Co-Pilot Client Application
 * Standardized for Indian Commercial Highways (NH 48, NH 44, Golden Quadrilateral)
 * Features:
 *  - Metric Units: km, Liters (L), Indian Rupees (₹)
 *  - 4 Supported Languages: English (en-IN), हिन्दी (hi-IN), தமிழ் (ta-IN), తెలుగు (te-IN)
 *  - Hands-free Wake-Word "Disha" / "दिशा"
 *  - Zero-scroll single plane cockpit layout
 *  - Dhabas, 24/7 Trauma Centers, Puncture/Mechanics, and Diesel bunks
 */

// API Endpoints
const API_URL = "/api/v1/routes/optimize/";
const VOICE_API_URL = "/api/v1/voice/query/";
const TTS_API_URL = "/api/v1/voice/tts/";
const HOTEL_BOOK_URL = "/api/v1/copilot/hotels/book/";
const HOSPITAL_ALERT_URL = "/api/v1/copilot/hospitals/alert/";
const MECHANIC_REQ_URL = "/api/v1/copilot/mechanics/request/";
const SOS_URL = "/api/v1/copilot/sos/";
const MANIFEST_API_URL = "/api/v1/routes/manifest/";

// In-Memory Audio Cache for instant Sarvam voice playback (avoids browser TTS)
const audioCache = new Map();
let currentActiveAudio = null;

// Lightweight Client-Side In-Memory & Session Storage Cache (LRU)
class ClientCache {
    constructor(prefix = "fc_cache_", maxEntries = 20) {
        this.prefix = prefix;
        this.maxEntries = maxEntries;
        this.mem = new Map();
        this._loadFromSession();
    }

    _loadFromSession() {
        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const k = sessionStorage.key(i);
                if (k && k.startsWith(this.prefix)) {
                    const raw = sessionStorage.getItem(k);
                    if (raw) {
                        this.mem.set(k.replace(this.prefix, ""), JSON.parse(raw));
                    }
                }
            }
        } catch (_) {}
    }

    get(key) {
        return this.mem.get(key) || null;
    }

    set(key, val) {
        if (this.mem.size >= this.maxEntries) {
            const firstKey = this.mem.keys().next().value;
            this.mem.delete(firstKey);
            try { sessionStorage.removeItem(this.prefix + firstKey); } catch (_) {}
        }
        this.mem.set(key, val);
        try {
            sessionStorage.setItem(this.prefix + key, JSON.stringify(val));
        } catch (_) {}
    }
}

const clientRouteCache = new ClientCache("fc_route_", 20);
const clientVoiceCache = new ClientCache("fc_voice_", 20);

// Indian Metric & Currency Constants
const MILES_TO_KM = 1.60934;
const GALS_TO_LITERS = 3.78541;
const DEFAULT_DIESEL_INR_PER_LITER = 90.75; // Average Indian Highway Diesel Rate (₹/L)

// 4 Supported Languages Dictionary (English, हिन्दी, தமிழ், తెలుగు)
const i18n = {
    en: {
        app_name: "Fuel Check",
        app_sub: "INDIAN TRUCK DRIVER CO-PILOT",
        origin_label: "Start Location",
        dest_label: "Destination",
        btn_find: "Find Route",
        sos_btn: "🚨 SOS (112)",
        dist_label: "Total Distance",
        time_label: "Drive Time",
        fuel_label: "Diesel Needed",
        cost_label: "Est. Fuel Cost",
        tab_diesel: "⛽ Affordable Diesel (₹/L)",
        tab_dhaba: "🏨 Dhabas & Rest",
        tab_doctor: "🏥 Doctor & Hospital",
        tab_mechanic: "🔧 Mechanic / Puncture",
        tab_cargo: "📦 Cargo / Bilti",
        disha_wake_prompt: "Say \"Disha\" or tap mic",
        disha_listening: "Disha is listening... (Speak now)",
        disha_thinking: "Disha is checking the highway...",
        disha_speaking: "Disha is answering...",
        book_now: "Book Dhaba",
        call_er: "Call ER Doctor",
        call_mechanic: "Call Mechanic",
        road_clear: "NH highway is clear ahead. Safe journey!",
        wind_alert: "Strong winds reported. Keep truck steady.",
        legend_fuel: "Diesel (₹)",
        legend_dhaba: "Dhaba",
        legend_doctor: "Hospital",
        legend_mechanic: "Mechanic",
        legend_weather: "Weather",
        loading_text: "Calculating highway route and affordable diesel...",
        disha_default_greeting: "Namaste! I am Disha. Delhi to Mumbai route and affordable diesel stops are ready. Say 'Disha' anytime!",
        unit_km: "km",
        unit_l: "L",
        unit_hrs: "hrs",
        currency_symbol: "₹",
    },
    hi: {
        app_name: "फ्यूल चेक",
        app_sub: "भारतीय ट्रक ड्राइवर हमसफ़र",
        origin_label: "कहाँ से",
        dest_label: "कहाँ तक",
        btn_find: "रास्ता खोजें",
        sos_btn: "🚨 आपातकाल (112)",
        dist_label: "कुल दूरी",
        time_label: "ड्राइव समय",
        fuel_label: "डीज़ल खपत",
        cost_label: "डीज़ल खर्चा",
        tab_diesel: "⛽ किफायती डीज़ल (₹/L)",
        tab_dhaba: "🏨 ढाबा और आराम",
        tab_doctor: "🏥 डॉक्टर और अस्पताल",
        tab_mechanic: "🔧 पंचर और मिस्त्री",
        tab_cargo: "📦 बिल्टी / लोड",
        disha_wake_prompt: "\"दिशा\" बोलें या माइक दबाएँ",
        disha_listening: "दिशा सुन रही है... बोलिए",
        disha_thinking: "दिशा हाईवे चेक कर रही है...",
        disha_speaking: "दिशा जवाब दे रही है...",
        book_now: "ढाबा बुक करें",
        call_er: "अस्पताल कॉल",
        call_mechanic: "मिस्त्री बुलाएँ",
        road_clear: "हाईवे एकदम साफ़ है। शुभ यात्रा!",
        wind_alert: "आगे तेज़ आँधी है, गाड़ी की रफ़्तार नियंत्रित रखें।",
        legend_fuel: "डीज़ल (₹)",
        legend_dhaba: "ढाबा",
        legend_doctor: "अस्पताल",
        legend_mechanic: "मिस्त्री",
        legend_weather: "मौसम",
        loading_text: "किफायती डीज़ल और सबसे अच्छा हाईवे रूट खोज रहे हैं...",
        disha_default_greeting: "नमस्ते! मैं दिशा हूँ। दिल्ली से मुंबई का किफायती डीज़ल और ढाबा तैयार है। 'दिशा' बोलें कभी भी!",
        unit_km: "किमी",
        unit_l: "ली",
        unit_hrs: "घंटे",
        currency_symbol: "₹",
    },
    ta: {
        app_name: "ஃப்யூல் செக்",
        app_sub: "இந்திய லாரி டிரைவர் வழிகாட்டி",
        origin_label: "புறப்படும் இடம்",
        dest_label: "சேருமிடம்",
        btn_find: "வழி தேடு",
        sos_btn: "🚨 அவசர உதவி (112)",
        dist_label: "மொத்த தூரம்",
        time_label: "பயண நேரம்",
        fuel_label: "டீசல் தேவை",
        cost_label: "டீசல் செலவு",
        tab_diesel: "⛽ சிக்கனமான டீசல் (₹)",
        tab_dhaba: "🏨 தாபா & தங்குமிடம்",
        tab_doctor: "🏥 மருத்துவமனை & டாக்டர்",
        tab_mechanic: "🔧 மெக்கானிக் & பஞ்சர்",
        tab_cargo: "📦 சரக்கு பில்டி",
        disha_wake_prompt: "\"திஷா\" என்று சொல்லவும்",
        disha_listening: "திஷா கேட்கிறது... பேசுங்கள்",
        disha_thinking: "திஷா வழியை சரிபார்க்கிறது...",
        disha_speaking: "திஷா பேசுகிறது...",
        book_now: "தாபா முன்பதிவு",
        call_er: "அவசர அழைப்பு",
        call_mechanic: "மெக்கானிக் அழைக்க",
        road_clear: "தேசிய நெடுஞ்சாலை சீராக உள்ளது. பாதுகாப்பான பயணம்!",
        wind_alert: "முன்னே பலத்த காற்று. லாரியை கவனமாக ஓட்டவும்.",
        legend_fuel: "டீசல் (₹)",
        legend_dhaba: "தாபா",
        legend_doctor: "மருத்துவமனை",
        legend_mechanic: "மெக்கானிக்",
        legend_weather: "வானிலை",
        loading_text: "சிறந்த நெடுஞ்சாலை மற்றும் சிக்கனமான டீசல் தேடப்படுகிறது...",
        disha_default_greeting: "வணக்கம்! நான் திஷா. சிக்கனமான டீசல் பங்க், தாபா அல்லது உதவிக்கு 'திஷா' என்று கூறவும்!",
        unit_km: "கி.மீ",
        unit_l: "லி",
        unit_hrs: "மணி",
        currency_symbol: "₹",
    },
    te: {
        app_name: "ఫ్యూయల్ చెక్",
        app_sub: "భారతీయ లారీ డ్రైవర్ సలహాదారు",
        origin_label: "ఎక్కడ నుండి",
        dest_label: "ఎక్కడికి",
        btn_find: "రూట్ శోధించండి",
        sos_btn: "🚨 అత్యవసర సహాయం (112)",
        dist_label: "మొత్తం దూరం",
        time_label: "ప్రయాణ సమయం",
        fuel_label: "డీజిల్ పరిమాణం",
        cost_label: "డీజిల్ ఖర్చు",
        tab_diesel: "⛽ సరసమైన డీజిల్ (₹)",
        tab_dhaba: "🏨 ధాబా & విశ్రాంతి",
        tab_doctor: "🏥 డాక్టర్ & ఆసుపత్రి",
        tab_mechanic: "🔧 మెకానిక్ & పంక్చర్",
        tab_cargo: "📦 బిల్టీ / సరుకు",
        disha_wake_prompt: "\"దిశ\" అని చెప్పండి",
        disha_listening: "దిశ వింటోంది... చెప్పండి",
        disha_thinking: "దిశ హైవే పరిశీలిస్తోంది...",
        disha_speaking: "దిశ మాట్లాడుతోంది...",
        book_now: "ధాబా బుకింగ్",
        call_er: "ఆసుపత్రి కాల్",
        call_mechanic: "మెకానిక్ పిలవండి",
        road_clear: "జాతీయ రహదారి స్పష్టంగా ఉంది. శుభ ప్రయాణం!",
        wind_alert: "ముందు బలమైన గాలులు ఉన్నాయి. వేగాన్ని నియంత్రించండి.",
        legend_fuel: "డీజిల్ (₹)",
        legend_dhaba: "ధాబా",
        legend_doctor: "ఆసుపత్రి",
        legend_mechanic: "మెకానిక్",
        legend_weather: "వాతావరణం",
        loading_text: "సరసమైన డీజిల్ మరియు హైవే మార్గం శోధిస్తున్నాము...",
        disha_default_greeting: "నమస్కారం! నేను దిశను. సరసమైన డీజిల్ బంక్, ధాబా లేదా వైద్య సహాయం కోసం 'దిశ' అని పిలవండి!",
        unit_km: "కి.మీ",
        unit_l: "లీ",
        unit_hrs: "గం",
        currency_symbol: "₹",
    }
};

let currentLang = "en";
let currentCategory = "fuel";
let currentRouteData = null;
let currentAudioBase64 = null;
let isVoiceActive = false;
let speechRecognizer = null;
let wakeRecognizer = null;
let isWakeListening = false;

// 1. Initialize Map Centered on India (Delhi - Mumbai Corridor)
const map = L.map("map", { zoomControl: false }).setView([22.5, 78.5], 5);
L.control.zoom({ position: "bottomright" }).addTo(map);

L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 16,
    attribution: "Tiles &copy; Esri &bull; Fuel Check India"
}).addTo(map);

L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 16
}).addTo(map);

let routeLayer = null;
let markers = [];

// 2. Chime Audio Tone on Wake-Word "Disha" / "दिशा"
function playChime() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.28);
        osc.start();
        osc.stop(ctx.currentTime + 0.28);
    } catch (e) {
        console.warn("Chime error:", e);
    }
}

// 3. Language Switcher Engine
function changeLanguage(langKey) {
    if (!i18n[langKey]) langKey = "en";
    currentLang = langKey;

    document.querySelectorAll(".btn-lang").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-lang") === langKey);
    });

    const dict = i18n[langKey];

    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (dict[key]) {
            el.textContent = dict[key];
        }
    });

    const startInput = document.getElementById("start");
    const finishInput = document.getElementById("finish");
    if (startInput) startInput.placeholder = dict.origin_label || "Start";
    if (finishInput) finishInput.placeholder = dict.dest_label || "Destination";

    const dishaSub = document.getElementById("disha-sub-label");
    if (dishaSub && !isVoiceActive) dishaSub.textContent = dict.disha_wake_prompt;

    // Reset speech text to language default greeting and clear stale audio
    currentAudioBase64 = null;
    const speechEl = document.getElementById("disha-speech-text");
    if (speechEl && dict.disha_default_greeting) {
        speechEl.textContent = dict.disha_default_greeting;
        // Pre-fetch native Sarvam voice for instantaneous replay
        getOrFetchSarvamAudio(dict.disha_default_greeting, currentLang).then(b64 => {
            if (b64 && currentLang === langKey) currentAudioBase64 = b64;
        });
    }

    // Update quick chips in selected language
    const chipTexts = {
        hi: [
            { text: "⛽ डीजल पंप", q: "यहां का डीजल पंप कहां है" },
            { text: "🏨 ढाबा / रेस्ट", q: "आसपास ढाबा और सोने की जगह कहां है" },
            { text: "🏥 अस्पताल", q: "इमरजेंसी डॉक्टर या अस्पताल" },
            { text: "🔧 मिस्त्री", q: "पंचर मिस्त्री को बुलाओ" }
        ],
        te: [
            { text: "⛽ డీజిల్ బంక్", q: "ఇక్కడ డీజిల్ బంక్ ఎక్కడ ఉంది" },
            { text: "🏨 ధాబా & విశ్రాంతి", q: "సమీపంలోని ధాబా మరియు విశ్రాంతి స్థలం ఎక్కడ ఉంది" },
            { text: "🏥 ఆసుపత్రి", q: "ఎమర్జెన్సీ డాక్టర్ లేదా ఆసుపత్రి" },
            { text: "🔧 మెకానిక్", q: "పంక్చర్ మెకానిక్ పిలవండి" }
        ],
        ta: [
            { text: "⛽ டீசல் பங்க்", q: "இங்கு டீசல் பங்க் எங்கே உள்ளது" },
            { text: "🏨 தாபா & ஓய்வு", q: "அருகிலுள்ள தாபா மற்றும் தங்குமிடம் எங்கே" },
            { text: "🏥 மருத்துவமனை", q: "அவசர சிகிச்சை அல்லது மருத்துவமனை" },
            { text: "🔧 மெக்கானிக்", q: "பஞ்சர் மெக்கானிக் அழைக்கவும்" }
        ],
        en: [
            { text: "⛽ Diesel Bunks", q: "Where is the nearest diesel pump?" },
            { text: "🏨 Dhabas & Rest", q: "Where can I find dhabas and truck rest?" },
            { text: "🏥 Hospitals", q: "Emergency doctor and hospital near me" },
            { text: "🔧 Mechanics", q: "Call emergency truck mechanic for puncture" }
        ]
    };

    const chipsContainer = document.querySelector(".disha-quick-chips");
    if (chipsContainer && chipTexts[langKey]) {
        chipsContainer.innerHTML = chipTexts[langKey].map(c => 
            `<button type="button" class="disha-chip" onclick="askDishaPreset('${c.q}')">${c.text}</button>`
        ).join("");
    }

    const textInput = document.getElementById("disha-text-input");
    if (textInput) {
        const phs = {
            hi: "पूछिए (Ask Disha in Hindi)...",
            te: "అడగండి (Ask Disha in Telugu)...",
            ta: "கேளுங்கள் (Ask Disha in Tamil)...",
            en: "Ask Disha in English..."
        };
        textInput.placeholder = phs[langKey] || phs.en;
    }

    if (wakeRecognizer) {
        const wakeLangs = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN" };
        wakeRecognizer.lang = wakeLangs[currentLang] || "en-IN";
    }

    if (currentRouteData) {
        updateStatsDisplay(currentRouteData);
        renderCategoryCards(currentCategory);
        // Refresh route advisory and amenities in chosen language
        const s = document.getElementById("start")?.value || "Delhi";
        const f = document.getElementById("finish")?.value || "Mumbai";
        calculateRoute(s, f);
    }

    console.log(`[Language Switched to ${langKey}]`);
}

// 4. Update Stats in Metric Units (km, L, ₹)
function updateStatsDisplay(data) {
    const dict = i18n[currentLang] || i18n.en;

    const rawMiles = data.route?.distance_miles || 878.8;
    const rawMins = data.route?.duration_minutes || 1351;
    const rawGals = data.fuel?.consumed_gallons || (rawMiles / 10.0);

    // Metric conversions
    const distKm = Math.round(rawMiles * MILES_TO_KM);
    const durHrs = (rawMins / 60).toFixed(1);
    const liters = Math.round(rawGals * GALS_TO_LITERS);
    const totalCostInr = Math.round(liters * DEFAULT_DIESEL_INR_PER_LITER);

    document.getElementById("stat-distance").textContent = `${distKm.toLocaleString('en-IN')} ${dict.unit_km || 'km'}`;
    document.getElementById("stat-duration").textContent = `${durHrs} ${dict.unit_hrs || 'hrs'}`;
    document.getElementById("stat-fuel").textContent = `${liters.toLocaleString('en-IN')} ${dict.unit_l || 'L'}`;
    document.getElementById("stat-cost").textContent = `₹${totalCostInr.toLocaleString('en-IN')}`;
}

const categoryVoiceAnnouncements = {
    fuel: {
        hi: "हाईवे पर आगे 120 किमी पर इंडियनऑयल स्वागत पंप है, जहाँ डीज़ल ₹90.75 प्रति लीटर है।",
        en: "Next diesel stop is IndianOil Swagat Bunk, 120 km ahead at ₹90.75/L.",
        ta: "வழியில் 120 கி.மீ முன்னால் இந்தியன் ஆயில் பங்க் உள்ளது (டீசல் ₹90.75/L).",
        te: "ముందు 120 కి.మీ దూరంలో ఇండియన్ ఆయిల్ బంక్ ఉంది (డీజిల్ ₹90.75/L)."
    },
    dhaba: {
        hi: "हाईवे पर 45 किमी आगे पहलवान ढाबा और 24 घंटे सुरक्षित ट्रक पार्किंग उपलब्ध है।",
        en: "Pahalwan Dhaba with 24/7 chai and secure truck parking is 45 km ahead.",
        ta: "45 கி.மீ முன்னால் பாதுகாப்பான லாரி பார்க்கிங் மற்றும் தாபா ஓய்வு வசதி உள்ளது.",
        te: "45 కి.మీ దూరంలో సురక్షితమైన లారీ పార్కింగ్ మరియు ధాబా అందుబాటులో ఉన్నాయి."
    },
    doctor: {
        hi: "निकटतम 24/7 ट्रॉमा सेंटर अपेक्स इमरजेंसी हॉस्पिटल है। आपातकालीन कॉल: 108 या 112।",
        en: "Nearest 24/7 trauma emergency center is Apex Hospital. Hotline: 108 / 112.",
        ta: "அருகிலுள்ள அவசர சிகிச்சை மையம் அபெக்ஸ் மருத்துவமனை. அவசர உதவி: 108 / 112.",
        te: "సమీపంలోని 24/7 ఆసుపత్రి అపెక్స్ హాస్పిటల్. అత్యవసర కాల్: 108 / 112."
    },
    mechanic: {
        hi: "बालाजी 24/7 मोबाइल ट्रक मिस्त्री सेवा उपलब्ध है (~20 मिनट पहुँच)। फोन: +91-94140-11223।",
        en: "Balaji 24/7 mobile truck mechanic dispatched (~20 mins arrival). Tel: +91-94140-11223.",
        ta: "24/7 நடமாடும் மெக்கானிக் சேவை தயார் (~20 நிமிடங்கள்). எண்: +91-94140-11223.",
        te: "24/7 మొబైల్ మెకానిక్ సేవ అందుబాటులో ఉంది (~20 నిమిషాలు). ఫోన్: +91-94140-11223."
    },
    cargo: {
        hi: "बिल्टी #WB-DEL-984421 सक्रिय है। 18 टन माल भिवंडी लॉजिस्टिक्स हब, डॉक 3 पर पहुँचाना है।",
        en: "E-Way Bill #WB-DEL-984421 is active for 18 tonnes FMCG cargo to Bhiwandi Dock #3.",
        ta: "பில்டி #WB-DEL-984421 செயலில் உள்ளது. சரக்கு டாக் 3-ல் இறக்கப்பட வேண்டும்.",
        te: "బిల్టీ #WB-DEL-984421 సక్రియంగా ఉంది. సరుకు డాక్ 3 లో డెలివరీ చేయాలి."
    }
};

// 5. Category Tab Switcher
function switchCategory(cat) {
    currentCategory = cat;
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === cat);
    });
    renderCategoryCards(cat);

    // Update Disha Speech Bubble with category guidance in active language
    const msg = categoryVoiceAnnouncements[cat]?.[currentLang] || categoryVoiceAnnouncements[cat]?.en;
    if (msg) {
        document.getElementById("disha-speech-text").textContent = msg;
        currentAudioBase64 = null;
        getOrFetchSarvamAudio(msg, currentLang).then(b64 => {
            if (b64 && currentCategory === cat) {
                currentAudioBase64 = b64;
            }
        });
    }
}

function askDishaPreset(queryText) {
    executeVoiceQuery(queryText);
}

function handleDishaTextSubmit(e) {
    e.preventDefault();
    const input = document.getElementById("disha-text-input");
    if (!input || !input.value.trim()) return;
    const q = input.value.trim();
    input.value = "";
    executeVoiceQuery(q);
}

// 6. Render Indian Driver Cards (₹/L, km, Dhabas, 108/112 Hospitals)
function renderCategoryCards(category) {
    const container = document.getElementById("category-cards-container");
    if (!container) return;
    container.innerHTML = "";

    const dict = i18n[currentLang] || i18n.en;

    if (!currentRouteData) {
        container.innerHTML = `<div style="padding:16px; color:#8496a5; font-size:12px; text-align:center;">${dict.loading_text}</div>`;
        return;
    }

    const amenities = currentRouteData.copilot_amenities || {};
    const stops = currentRouteData.fuel_stops || [];

    if (category === "fuel") {
        // 1. Interstate Fuel Arbitrage Strategy Banner (Zero-Key Realtime Engine)
        if (currentRouteData.live_fuel_strategy && currentRouteData.live_fuel_strategy.advisory) {
            const strat = currentRouteData.live_fuel_strategy;
            const stratCard = document.createElement("div");
            stratCard.className = "fuel-strategy-banner";
            stratCard.innerHTML = `
                <div class="strategy-header">
                    <span class="strategy-badge">⚡ BORDER ARBITRAGE</span>
                    <span class="strategy-savings">Save ~₹${(strat.estimated_tank_savings_inr || 1600).toLocaleString('en-IN')}</span>
                </div>
                <p class="strategy-msg">${strat.advisory}</p>
            `;
            container.appendChild(stratCard);
        }

        // 2. Daily 6:00 AM OMC Benchmark State Rates Ticker
        const rates = (currentRouteData && currentRouteData.live_state_rates) || window.cachedStateRates || {};
        if (Object.keys(rates).length > 0) {
            const ticker = document.createElement("div");
            ticker.className = "fuel-rates-ticker";
            const pills = ["DL", "HR", "GJ", "RJ", "MH"]
                .filter(c => rates[c])
                .map(c => `<span class="rate-pill"><strong>${c}:</strong> ₹${rates[c].diesel_inr.toFixed(2)}</span>`)
                .join("");
            ticker.innerHTML = `
                <div class="ticker-label">📊 Daily 6 AM OMC Diesel Rates (₹/L):</div>
                <div class="ticker-pills">${pills}</div>
            `;
            container.appendChild(ticker);
        }

        const indianBunkNames = ["IndianOil Swagat Bunk", "Bharat Petroleum Ghar", "HP Highway King Point", "Reliance Petroleum Oasis"];
        const demoStops = stops.length ? stops : [
            { station_name: "IndianOil Swagat Bunk", city: "Kotputli Bypass (NH 48)", route_mile: 120, gallons_pumped: 25, price_per_liter: 88.35, state_code: "HR", savings_per_liter: 4.05 },
            { station_name: "Bharat Petroleum Ghar", city: "Udaipur Highway Stop", route_mile: 410, gallons_pumped: 35, price_per_liter: 91.25, state_code: "RJ", savings_per_liter: 1.15 }
        ];

        demoStops.forEach((s, idx) => {
            const bName = s.station_name || s.name || indianBunkNames[idx % indianBunkNames.length];
            const distKm = Math.round((s.route_mile || (idx + 1) * 260) * MILES_TO_KM);
            const pumpedL = Math.round((s.gallons_pumped || s.gallons || 30) * GALS_TO_LITERS);
            const rateInr = s.price_per_liter ? Number(s.price_per_liter).toFixed(2) : (DEFAULT_DIESEL_INR_PER_LITER + (idx === 0 ? -1.25 : 0.65)).toFixed(2);
            const costInr = Math.round(pumpedL * rateInr);
            const statePill = s.state_code ? `<span class="state-pill">${s.state_code}</span>` : "";
            const savingsBadge = s.savings_per_liter && s.savings_per_liter > 0
                ? `<span class="card-tag tag-savings">Save ₹${Number(s.savings_per_liter).toFixed(2)}/L</span>`
                : `<span class="card-tag tag-green">₹${rateInr} / L</span>`;

            const card = document.createElement("div");
            card.className = "driver-item-card";
            card.innerHTML = `
                <div class="card-top-row">
                    <strong class="card-name">⛽ ${bName} ${statePill}</strong>
                    ${savingsBadge}
                </div>
                <div class="card-meta-row">
                    <span>📍 ${s.city || s.state_name || 'Highway Exit'} (${distKm} km point)</span>
                    <strong style="color:var(--green)">Pump: ${pumpedL} L @ ₹${rateInr}</strong>
                </div>
                <div class="card-actions-row">
                    <span style="color:#8496a5; font-size:11px;">Est. Cost: ₹${costInr.toLocaleString('en-IN')}</span>
                    <button class="btn-card-action" onclick="zoomToMarker(${s.latitude || 27.5}, ${s.longitude || 76.5})">📍 Show on Map</button>
                </div>
            `;
            container.appendChild(card);
        });
    } else if (category === "dhaba") {
        const indianDhabas = [
            { name: "Pahalwan Dhaba & AC Rest Bay", city: "NH 48 Kotputli", price_inr: 450, phone: "+91-98123-45678" },
            { name: "Sukhdev Highway Dhaba & Truck Rest", city: "Near Murthal Hub", price_inr: 600, phone: "+91-98765-43210" },
            { name: "Rajwada Punjabi Dhaba", city: "Kishangarh Expressway", price_inr: 500, phone: "+91-94140-55678" },
            { name: "Milan Highway Motel & Parking", city: "Surat Bypass", price_inr: 750, phone: "+91-97250-99887" }
        ];

        indianDhabas.forEach(h => {
            const card = document.createElement("div");
            card.className = "driver-item-card";
            card.innerHTML = `
                <div class="card-top-row">
                    <strong class="card-name">🏨 ${h.name}</strong>
                    <span class="card-tag tag-blue">₹${h.price_inr} / night</span>
                </div>
                <div class="card-meta-row">
                    <span>📍 ${h.city} (Secure Truck Parking)</span>
                    <a class="card-phone" href="tel:${h.phone}">📞 ${h.phone}</a>
                </div>
                <div class="card-actions-row">
                    <span style="font-size:11px; color:var(--green)">✓ 24/7 Chai & Food</span>
                    <button class="btn-card-action" onclick="alert('Dhaba bed reserved for truck driver.')">${dict.book_now}</button>
                </div>
            `;
            container.appendChild(card);
        });
    } else if (category === "doctor") {
        const indianHospitals = [
            { name: "Apex 24/7 Trauma & Emergency Center", city: "Jaipur Bypass (NH 48)", phone: "108 / +91-141-2751800", level: "Level I Trauma" },
            { name: "Government Sub-District Hospital", city: "Kotputli (Highway ER)", phone: "108 / 112", level: "Emergency ER 24/7" },
            { name: "Geetanjali Hospital & Trauma Unit", city: "Udaipur Highway", phone: "108 / +91-294-2860000", level: "Level II Trauma" },
            { name: "Civil Emergency Hospital", city: "Surat Ring Road", phone: "108 / 112", level: "Critical Care 24/7" }
        ];

        indianHospitals.forEach(h => {
            const card = document.createElement("div");
            card.className = "driver-item-card";
            card.innerHTML = `
                <div class="card-top-row">
                    <strong class="card-name">🏥 ${h.name}</strong>
                    <span class="card-tag tag-red">${h.level}</span>
                </div>
                <div class="card-meta-row">
                    <span>📍 ${h.city}</span>
                    <a class="card-phone" style="color:var(--red)" href="tel:108">🚨 108 / 112 Hotline</a>
                </div>
                <div class="card-actions-row">
                    <span style="font-size:11px; color:#8496a5;">Ambulance on Standby</span>
                    <button class="btn-card-action" style="border-color:var(--red); color:var(--red)" onclick="alert('Emergency ER Alert Sent to ' + '${h.name}')">${dict.call_er}</button>
                </div>
            `;
            container.appendChild(card);
        });
    } else if (category === "mechanic") {
        const indianMechanics = [
            { name: "Balaji 24/7 Mobile Truck Puncture & Tyre", city: "NH 48 Behror", phone: "+91-94140-11223", eta: 20 },
            { name: "Guru Nanak Heavy Truck Spares & Repair", city: "Jaipur Transport Nagar", phone: "+91-98290-33445", eta: 25 },
            { name: "Shiv Shakti Hydraulic Jack & Kamani Works", city: "Ajmer Highway", phone: "+91-97850-77889", eta: 30 },
            { name: "Surat National Highway Recovery Crane", city: "Kamrej Toll Plaza", phone: "+91-98790-22110", eta: 15 }
        ];

        indianMechanics.forEach(m => {
            const card = document.createElement("div");
            card.className = "driver-item-card";
            card.innerHTML = `
                <div class="card-top-row">
                    <strong class="card-name">🔧 ${m.name}</strong>
                    <span class="card-tag tag-amber">~${m.eta} min arrival</span>
                </div>
                <div class="card-meta-row">
                    <span>📍 ${m.city}</span>
                    <a class="card-phone" href="tel:${m.phone}">📞 ${m.phone}</a>
                </div>
                <div class="card-actions-row">
                    <span style="font-size:11px; color:#8496a5;">Air Compressor & Hydraulic</span>
                    <button class="btn-card-action" onclick="alert('Mechanic dispatched. Reaching in ~' + '${m.eta}' + ' mins.')">${dict.call_mechanic}</button>
                </div>
            `;
            container.appendChild(card);
        });
    } else if (category === "cargo") {
        const card = document.createElement("div");
        card.className = "driver-item-card";
        card.innerHTML = `
            <div class="card-top-row">
                <strong class="card-name">📦 Bilti / E-Way Bill: #WB-DEL-984421</strong>
                <span class="card-tag tag-green">ACTIVE IN TRANSIT</span>
            </div>
            <div class="card-meta-row">
                <span>Destination: Bhiwandi Logistics Hub, Mumbai</span>
                <strong style="color:var(--green)">Dock #3</strong>
            </div>
            <div class="card-actions-row">
                <span style="font-size:11px; color:#8496a5;">Consignment: 18 Tonnes FMCG Goods</span>
                <button class="btn-card-action" onclick="alert('E-Way Bill validated for toll clearance.')">Verify Bilti</button>
            </div>
        `;
        container.appendChild(card);
    }
}

// 7. Map Zoom
function zoomToMarker(lat, lng) {
    if (!lat || !lng) return;
    map.flyTo([lat, lng], 11, { animate: true, duration: 1.2 });
}

// 8. Route Calculation Engine with Small LRU & Session Storage Cache
async function calculateRoute(start, finish) {
    const cleanStart = (start || "Delhi").trim();
    const cleanFinish = (finish || "Mumbai").trim();
    const cacheKey = `${cleanStart.toLowerCase()}|${cleanFinish.toLowerCase()}|${currentLang}`;

    const applyRouteData = (data) => {
        currentRouteData = data;
        updateStatsDisplay(data);
        renderRouteOnMap(data);
        renderCategoryCards(currentCategory);

        const advisory = data.copilot_advisory?.message;
        if (advisory) {
            document.getElementById("disha-speech-text").textContent = advisory;
            currentAudioBase64 = data.copilot_advisory?.audio_base64 || null;
        }

        const weatherHazards = data.live_weather?.weather_hazards || [];
        const banner = document.getElementById("road-weather-banner");
        const weatherText = document.getElementById("weather-text");
        if (banner && weatherText) {
            if (weatherHazards.length > 0) {
                banner.className = "weather-alert-strip warning";
                weatherText.textContent = `⚠️ Alert: ${weatherHazards[0].title}. Keep speed steady.`;
            } else {
                banner.className = "weather-alert-strip";
                weatherText.textContent = i18n[currentLang]?.road_clear || "NH highway is clear ahead. Safe journey!";
            }
        }
    };

    // 1. Instant Cache hit (sub-millisecond UI update, 0ms latency)
    const cachedData = clientRouteCache.get(cacheKey);
    if (cachedData) {
        applyRouteData(cachedData);
        return;
    }

    const loading = document.getElementById("map-loading");
    if (loading) loading.classList.remove("hidden");

    try {
        const res = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ start: cleanStart, finish: cleanFinish, language: currentLang })
        });

        if (!res.ok) {
            let errMsg = "Route calculation failed";
            try {
                const err = await res.json();
                errMsg = err.error || err.detail || errMsg;
            } catch (_) {
                try {
                    const raw = await res.text();
                    errMsg = `Server error (${res.status}): ${raw.slice(0, 120)}`;
                } catch (e) {
                    errMsg = `Server returned status ${res.status}`;
                }
            }
            throw new Error(errMsg);
        }

        const data = await res.json();
        clientRouteCache.set(cacheKey, data);
        applyRouteData(data);

    } catch (e) {
        console.error("Error calculating route:", e);
        showCockpitToast("Route update: " + e.message, "error");
    } finally {
        if (loading) loading.classList.add("hidden");
    }
}

// 9. Render Polyline & Indian Corridors on Leaflet Map
function renderRouteOnMap(data) {
    if (routeLayer) map.removeLayer(routeLayer);
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    if (data.route?.geometry?.coordinates) {
        const latLngs = data.route.geometry.coordinates.map(pt => [pt[1], pt[0]]);
        routeLayer = L.polyline(latLngs, {
            color: "#e5a93c",
            weight: 5.5,
            opacity: 0.92,
            lineJoin: "round"
        }).addTo(map);

        map.fitBounds(routeLayer.getBounds(), { padding: [50, 50] });
    }

    // Fuel stops
    (data.fuel_stops || []).forEach((s, idx) => {
        const marker = L.circleMarker([s.latitude, s.longitude], {
            radius: 7.5,
            fillColor: "#2fb36d",
            color: "#1c2026",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.95
        }).addTo(map);
        marker.bindPopup(`<b>⛽ Diesel Bunk</b><br>Rate: ₹${(DEFAULT_DIESEL_INR_PER_LITER - 1.2).toFixed(2)}/L<br>📍 NH Corridor`);
        markers.push(marker);
    });

    // Medical emergency
    (data.copilot_amenities?.hospitals || []).forEach(h => {
        const marker = L.circleMarker([h.latitude, h.longitude], {
            radius: 7,
            fillColor: "#ff4757",
            color: "#fff",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.95
        }).addTo(map);
        marker.bindPopup(`<b>🏥 ${h.name}</b><br>🚨 108 / 112 Emergency ER`);
        markers.push(marker);
    });
}

// 10. Sarvam AI Indic Audio Playback Engine
async function getOrFetchSarvamAudio(text, lang) {
    if (!text) return null;
    const cleanText = text.trim();
    const cacheKey = `${lang}:${cleanText}`;
    if (audioCache.has(cacheKey)) {
        return audioCache.get(cacheKey);
    }
    try {
        const res = await fetch(TTS_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: cleanText, language: lang })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.audio_base64) {
                audioCache.set(cacheKey, data.audio_base64);
                return data.audio_base64;
            }
        }
    } catch (e) {
        console.warn("Sarvam TTS request failed:", e);
    }
    return null;
}

function playAudioBase64(base64Str) {
    if (!base64Str) return;
    try {
        if (currentActiveAudio) {
            currentActiveAudio.pause();
            currentActiveAudio = null;
        }
        currentActiveAudio = new Audio("data:audio/wav;base64," + base64Str);
        currentActiveAudio.play();
    } catch (e) {
        console.warn("Audio playback error:", e);
    }
}

async function replayDishaAudio() {
    if (currentAudioBase64) {
        playAudioBase64(currentAudioBase64);
    } else {
        const text = document.getElementById("disha-speech-text")?.textContent;
        if (!text) return;
        const b64 = await getOrFetchSarvamAudio(text, currentLang);
        if (b64) {
            currentAudioBase64 = b64;
            playAudioBase64(b64);
        }
    }
}

// 11. Disha Floating Voice Button State
function setDishaVoiceState(state) {
    const btn = document.getElementById("disha-mic-btn");
    const mainLabel = document.getElementById("disha-main-label");
    const subLabel = document.getElementById("disha-sub-label");
    const dict = i18n[currentLang] || i18n.en;

    if (!btn) return;

    if (state === "listening") {
        isVoiceActive = true;
        btn.className = "disha-floating-btn active";
        if (mainLabel) mainLabel.textContent = "Listening...";
        if (subLabel) subLabel.textContent = dict.disha_listening;
    } else if (state === "thinking") {
        btn.className = "disha-floating-btn thinking";
        if (mainLabel) mainLabel.textContent = "Disha";
        if (subLabel) subLabel.textContent = dict.disha_thinking;
    } else {
        isVoiceActive = false;
        btn.className = "disha-floating-btn";
        if (mainLabel) mainLabel.textContent = "Disha";
        if (subLabel) subLabel.textContent = dict.disha_wake_prompt;
    }
}

// 12. Send Voice Command to Backend (Sarvam + Bolna) with Fast Client Cache
async function executeVoiceQuery(queryText) {
    const start = document.getElementById("start")?.value || "Delhi";
    const finish = document.getElementById("finish")?.value || "Mumbai";
    const cacheKey = `${queryText.trim().toLowerCase()}|${start.trim().toLowerCase()}|${finish.trim().toLowerCase()}|${currentLang}`;

    const applyVoiceData = (data) => {
        const spoken = data.spoken_answer || data.audio_speech_text || "Checked the highway corridor for you.";
        document.getElementById("disha-speech-text").textContent = spoken;

        if (data.audio_base64) {
            currentAudioBase64 = data.audio_base64;
            playAudioBase64(data.audio_base64);
        } else {
            getOrFetchSarvamAudio(spoken, currentLang).then(b64 => {
                if (b64) {
                    currentAudioBase64 = b64;
                    playAudioBase64(b64);
                }
            });
        }

        if (data.intent === "hospital_search") switchCategory("doctor");
        else if (data.intent === "hotel_search" || data.intent === "hotel_booking") switchCategory("dhaba");
        else if (data.intent === "mechanic_search" || data.intent === "mechanic_dispatch") switchCategory("mechanic");
        else if (data.intent === "parcel_tracking") switchCategory("cargo");
        else if (data.intent === "route_and_fuel" || data.intent === "fuel_search") switchCategory("fuel");
        else if (data.intent === "emergency_sos") startSimulatedEmergencyCall();
    };

    // Check instant voice query cache
    const cachedVoice = clientVoiceCache.get(cacheKey);
    if (cachedVoice) {
        applyVoiceData(cachedVoice);
        setDishaVoiceState("idle");
        return;
    }

    setDishaVoiceState("thinking");
    try {
        const res = await fetch(VOICE_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query: queryText,
                start,
                finish,
                language: currentLang
            })
        });

        const data = await res.json();
        clientVoiceCache.set(cacheKey, data);
        applyVoiceData(data);

    } catch (e) {
        console.error("Voice query failed:", e);
        document.getElementById("disha-speech-text").textContent = "High-speed connection busy. Please speak again.";
    } finally {
        setDishaVoiceState("idle");
    }
}

// 13. Voice Recording Trigger
function toggleDishaVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Voice recognition is not supported in this browser. Please type your query.");
        return;
    }

    if (isVoiceActive) {
        if (speechRecognizer) speechRecognizer.stop();
        return;
    }

    startActiveVoiceQuery();
}

function startActiveVoiceQuery() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    if (speechRecognizer) {
        try { speechRecognizer.abort(); } catch (e) {}
    }

    speechRecognizer = new SpeechRecognition();
    const speechLangs = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN" };
    speechRecognizer.lang = speechLangs[currentLang] || "hi-IN";
    speechRecognizer.interimResults = false;
    speechRecognizer.maxAlternatives = 1;

    speechRecognizer.onstart = () => {
        setDishaVoiceState("listening");
    };

    speechRecognizer.onresult = (evt) => {
        const transcript = evt.results[0][0].transcript;
        console.log("[Driver Voice Query]:", transcript);
        executeVoiceQuery(transcript);
    };

    speechRecognizer.onerror = (err) => {
        console.warn("Speech error:", err);
        setDishaVoiceState("idle");
    };

    speechRecognizer.onend = () => {
        if (!isVoiceActive) setDishaVoiceState("idle");
    };

    speechRecognizer.start();
}

// 14. Wake-Word Listener for "Disha" / "दिशा"
function initWakeWordListener() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    try {
        wakeRecognizer = new SpeechRecognition();
        wakeRecognizer.continuous = true;
        wakeRecognizer.interimResults = true;
        const wakeLangs = { en: "en-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN" };
        wakeRecognizer.lang = wakeLangs[currentLang] || "en-IN";

        wakeRecognizer.onresult = (e) => {
            for (let i = e.resultIndex; i < e.results.length; i++) {
                const transcript = e.results[i][0].transcript.toLowerCase();
                if (
                    transcript.includes("disha") ||
                    transcript.includes("dishaa") ||
                    transcript.includes("दिशा") ||
                    transcript.includes("దిశ") ||
                    transcript.includes("திஷா") ||
                    transcript.includes("deesha")
                ) {
                    console.log("[Wake-word Triggered: 'Disha']");
                    wakeRecognizer.stop();
                    playChime();
                    startActiveVoiceQuery();
                    break;
                }
            }
        };

        wakeRecognizer.onend = () => {
            if (!isVoiceActive && isWakeListening) {
                setTimeout(() => {
                    try { wakeRecognizer.start(); } catch (err) {}
                }, 500);
            }
        };

        wakeRecognizer.start();
        isWakeListening = true;
        console.log("[Wake-Word Active: Listening for 'Disha']");
    } catch (e) {
        console.log("Wake word listener initialized.");
    }
}

// 15. Simulated Emergency Dispatch Call (Test Mode • Does Not Connect to Live 112)
let phoneAudioCtx = null;
let ringOsc1 = null;
let ringOsc2 = null;
let ringGain = null;
let callDurationTimer = null;
let callStepTimer = null;
let callSeconds = 0;
let isCallMuted = false;
let isCallSpeaker = true;

const testCallMessages = {
    en: {
        dialing: "Connecting to NHAI Emergency Dispatch...",
        ringing: "Ringing 112 / 1033 Control Room...",
        connected: "Simulated Dispatch Line Active",
        ended: "Test Call Ended • Log Stored",
        badge: "⚠️ TEST SIMULATION • NOT CONNECTED TO 112",
        speech: "Namaste. This is the Disha Highway Emergency Dispatch test line. Your vehicle GPS on NH 48 is logged. This is an automated test simulation. Highway patrol units standing by. Stay safe inside your vehicle."
    },
    hi: {
        dialing: "NHAI इमरजेंसी कंट्रोल रूम से कनेक्ट हो रहे हैं...",
        ringing: "112 / 1033 हेल्पलाइन की घंटी बज रही है...",
        connected: "सिम्युलेटेड टेस्ट हेल्पलाइन चालू है",
        ended: "परीक्षण कॉल समाप्त • डेटा सुरक्षित",
        badge: "⚠️ परीक्षण कॉल • 112 से कनेक्ट नहीं है",
        speech: "नमस्ते। यह दिशा हाईवे इमरजेंसी हेल्पलाइन की टेस्ट लाइन है। NH 48 पर आपकी गाड़ी की लोकेशन दर्ज हो गई है। यह केवल एक परीक्षण कॉल है, आपातकालीन सेवाएं अलर्ट पर हैं। कृपया गाड़ी के अंदर सुरक्षित रहें।"
    },
    ta: {
        dialing: "நெடுஞ்சாலை அவசர உதவி கட்டுப்பாட்டு அறை...",
        ringing: "112 / 1033 அவசர உதவிக்கு அழைக்கிறது...",
        connected: "சோதனை அவசர அழைப்பு செயலில் உள்ளது",
        ended: "சோதனை அழைப்பு முடிந்தது • பதிவு செய்யப்பட்டது",
        badge: "⚠️ மாதிரி சோதனை அழைப்பு • 112 உடன் இணைக்கப்படவில்லை",
        speech: "வணக்கம். இது திஷா தேசிய நெடுஞ்சாலை அவசர உதவி மாதிரி சோதனை அழைப்பு. NH 48 இல் உங்கள் வாகனம் பதிவு செய்யப்பட்டுள்ளது. இது மாதிரி சோதனை மட்டுமே. வாகனத்திற்குள் பாதுகாப்பாக இருக்கவும்."
    },
    te: {
        dialing: "జాతీయ రహదారి ఎమర్జెన్సీ డిస్పాచ్ కనెక్ట్ అవుతోంది...",
        ringing: "112 / 1033 కంట్రోల్ రూమ్‌కు రింగ్ అవుతోంది...",
        connected: "సిమ్యులేటెడ్ టెస్ట్ హెల్ప్‌లైన్ యాక్టివ్‌గా ఉంది",
        ended: "టెస్ట్ కాల్ ముగిసింది • లాగ్ సేవ్ చేయబడింది",
        badge: "⚠️ సిమ్యులేటెడ్ టెస్ట్ కాల్ • 112కి కనెక్ట్ కాలేదు",
        speech: "నమస్తే. ఇది దిశా జాతీయ రహదారి అత్యవసర హెల్ప్‌లైన్ టెస్ట్ కాల్. NH 48 కారిడార్‌లో మీ వాహన జీపీఎస్ నమోదైంది. ఇది సిమ్యులేటెడ్ టెస్ట్ కాల్ మాత్రమే. వాహనం లోపలే సురక్షితంగా ఉండండి."
    }
};

function startPhoneRingingAudio() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        phoneAudioCtx = new AudioContext();
        ringOsc1 = phoneAudioCtx.createOscillator();
        ringOsc2 = phoneAudioCtx.createOscillator();
        ringGain = phoneAudioCtx.createGain();

        ringOsc1.type = "sine";
        ringOsc2.type = "sine";
        ringOsc1.frequency.setValueAtTime(400, phoneAudioCtx.currentTime);
        ringOsc2.frequency.setValueAtTime(450, phoneAudioCtx.currentTime);

        ringGain.gain.setValueAtTime(0, phoneAudioCtx.currentTime);
        ringOsc1.connect(ringGain);
        ringOsc2.connect(ringGain);
        ringGain.connect(phoneAudioCtx.destination);

        ringOsc1.start();
        ringOsc2.start();

        // Standard Indian telecom ringback: 0.4s beep, 0.2s pause, 0.4s beep, 2.2s silence
        let t = phoneAudioCtx.currentTime + 0.1;
        for (let i = 0; i < 3; i++) {
            ringGain.gain.setValueAtTime(0.08, t);
            ringGain.gain.setValueAtTime(0, t + 0.4);
            ringGain.gain.setValueAtTime(0.08, t + 0.6);
            ringGain.gain.setValueAtTime(0, t + 1.0);
            t += 2.6;
        }
    } catch (e) {
        console.warn("AudioContext tone init note:", e);
    }
}

function stopPhoneRingingAudio() {
    try {
        if (ringOsc1) { ringOsc1.stop(); ringOsc1.disconnect(); ringOsc1 = null; }
        if (ringOsc2) { ringOsc2.stop(); ringOsc2.disconnect(); ringOsc2 = null; }
        if (ringGain) { ringGain.disconnect(); ringGain = null; }
        if (phoneAudioCtx && phoneAudioCtx.state !== "closed") {
            phoneAudioCtx.close();
            phoneAudioCtx = null;
        }
    } catch (_) {}
}

function playCallDisconnectBeep() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.setValueAtTime(425, ctx.currentTime);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.setValueAtTime(0, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.12, ctx.currentTime + 0.25);
        gain.gain.setValueAtTime(0, ctx.currentTime + 0.4);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.5);
    } catch (_) {}
}

function triggerDirectSOS() {
    startSimulatedEmergencyCall();
}

function startSimulatedEmergencyCall() {
    const modal = document.getElementById("sos-call-modal");
    if (!modal) return;

    // Reset timers & state
    clearInterval(callDurationTimer);
    clearTimeout(callStepTimer);
    callSeconds = 0;
    isCallMuted = false;
    isCallSpeaker = true;

    const tData = testCallMessages[currentLang] || testCallMessages.en;
    document.getElementById("sos-test-badge").textContent = tData.badge;
    document.getElementById("sos-status-label").textContent = tData.dialing;
    document.getElementById("sos-call-timer").textContent = "00:00";
    document.getElementById("sos-transcript-text").textContent = "Establishing simulated dispatch frequency...";
    const tagEl = document.getElementById("sos-telemetry-tag");
    if (tagEl) tagEl.textContent = "Simulating 112 Broadcast";

    const dot = document.getElementById("sos-status-dot");
    if (dot) dot.className = "sos-status-dot pulsing";

    // Set current route corridor info if available
    const startLoc = document.getElementById("start")?.value || "Delhi";
    const finishLoc = document.getElementById("finish")?.value || "Mumbai";
    const locEl = document.getElementById("sos-telemetry-loc");
    if (locEl) locEl.textContent = `${startLoc} ➔ ${finishLoc} (NH 48 Corridor)`;

    // Show modal
    modal.classList.remove("hidden");

    // Phase 1: Play ringback audio
    startPhoneRingingAudio();

    // After 1.5s: Update label to Ringing...
    callStepTimer = setTimeout(() => {
        const lbl = document.getElementById("sos-status-label");
        if (lbl) lbl.textContent = tData.ringing;
    }, 1500);

    // Phase 2: After 3.8s: Dispatcher answers (Simulated Test Broadcast)
    setTimeout(() => {
        stopPhoneRingingAudio();

        if (dot) dot.className = "sos-status-dot connected";
        const lbl = document.getElementById("sos-status-label");
        if (lbl) lbl.textContent = tData.connected;

        const transEl = document.getElementById("sos-transcript-text");
        if (transEl) transEl.textContent = tData.speech;

        if (tagEl) tagEl.textContent = "Test Telemetry Logged";

        // Start call timer
        callDurationTimer = setInterval(() => {
            callSeconds++;
            const mm = String(Math.floor(callSeconds / 60)).padStart(2, "0");
            const ss = String(callSeconds % 60).padStart(2, "0");
            const timerEl = document.getElementById("sos-call-timer");
            if (timerEl) timerEl.textContent = `${mm}:${ss}`;

            // Auto-hangup after 12 seconds
            if (callSeconds >= 12) {
                endSimulatedCall();
            }
        }, 1000);

        // Synthesize / play automated dispatcher announcement in active language
        if (isCallSpeaker) {
            getOrFetchSarvamAudio(tData.speech, currentLang).then(b64 => {
                if (b64) {
                    playAudioBase64(b64);
                }
            });
        }

        // Fire non-blocking telemetry event to backend for demo completeness
        fetch(SOS_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                emergency_type: "SIMULATED_TEST_BROADCAST",
                latitude: 28.4595,
                longitude: 77.0266,
                is_simulation: true
            })
        }).catch(() => {});

    }, 3800);
}

function endSimulatedCall() {
    stopPhoneRingingAudio();
    clearInterval(callDurationTimer);
    clearTimeout(callStepTimer);

    // Stop active spoken audio if playing
    if (currentActiveAudio) {
        try { currentActiveAudio.pause(); } catch (_) {}
    }

    playCallDisconnectBeep();

    const tData = testCallMessages[currentLang] || testCallMessages.en;
    const label = document.getElementById("sos-status-label");
    if (label) label.textContent = tData.ended;

    const dot = document.getElementById("sos-status-dot");
    if (dot) dot.className = "sos-status-dot";

    setTimeout(() => {
        const modal = document.getElementById("sos-call-modal");
        if (modal) modal.classList.add("hidden");
    }, 1100);
}

function toggleCallMute() {
    isCallMuted = !isCallMuted;
    const btn = document.getElementById("btn-toggle-mic");
    const lbl = document.getElementById("mic-lbl-call");
    const ico = document.getElementById("mic-icon-call");
    if (btn) btn.classList.toggle("active", isCallMuted);
    if (lbl) lbl.textContent = isCallMuted ? "Unmute" : "Mute";
    if (ico) ico.textContent = isCallMuted ? "🔇" : "🎙️";
}

function toggleCallSpeaker() {
    isCallSpeaker = !isCallSpeaker;
    const btn = document.getElementById("btn-toggle-speaker");
    const lbl = document.getElementById("spk-lbl-call");
    if (btn) btn.classList.toggle("active", !isCallSpeaker);
    if (lbl) lbl.textContent = isCallSpeaker ? "Speaker" : "Earpiece";

    if (!isCallSpeaker && currentActiveAudio) {
        try { currentActiveAudio.volume = 0.3; } catch (_) {}
    } else if (currentActiveAudio) {
        try { currentActiveAudio.volume = 1.0; } catch (_) {}
    }
}

function setQuickRoute(start, finish) {
    document.getElementById("start").value = start;
    document.getElementById("finish").value = finish;
    calculateRoute(start, finish);
}

// 16. Initialization
document.addEventListener("DOMContentLoaded", () => {
    const routeForm = document.getElementById("route-form");
    if (routeForm) {
        routeForm.addEventListener("submit", (e) => {
            e.preventDefault();
            const start = document.getElementById("start").value;
            const finish = document.getElementById("finish").value;
            calculateRoute(start, finish);
        });
    }

    document.body.addEventListener("click", () => {
        if (!isWakeListening) {
            initWakeWordListener();
        }
    }, { once: true });

    // Fetch zero-key daily 6 AM OMC benchmark rates
    fetch(`${API_BASE}/api/v1/fuel/rates/`)
        .then(r => r.json())
        .then(data => {
            if (data && data.state_rates) {
                window.cachedStateRates = data.state_rates;
                if (currentCategory === "fuel") {
                    renderCategoryCards("fuel");
                }
            }
        })
        .catch(err => console.warn("Live fuel rates fetch deferred:", err));

    // Initial Indian Highway Route: Delhi -> Mumbai (NH 48)
    calculateRoute("Delhi", "Mumbai");
});



// --- Cockpit In-App Toast & Waybill Modal Actions ---

function showCockpitToast(message, type = "info", duration = 4000) {
    const container = document.getElementById("cockpit-toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `cockpit-toast toast-${type}`;
    const icon = type === "error" ? "⚠️" : type === "success" ? "✅" : type === "warning" ? "⚡" : "ℹ️";
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(10px)";
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

let currentManifestData = null;

async function openManifestModal() {
    const modal = document.getElementById("manifest-modal");
    const preview = document.getElementById("manifest-text-preview");
    if (!modal || !preview) return;

    modal.classList.remove("hidden");
    preview.textContent = "Compiling commercial waybill (Bilti) from current route telemetry...";

    try {
        const start = document.getElementById("start")?.value || "Delhi";
        const finish = document.getElementById("finish")?.value || "Mumbai";
        const cacheKey = `${start.trim().toLowerCase()}|${finish.trim().toLowerCase()}|${currentLang}`;
        const cachedRoute = clientRouteCache.get(cacheKey);

        const payload = cachedRoute ? { route_data: cachedRoute } : { start, finish, language: currentLang };
        const res = await fetch(MANIFEST_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Failed to export waybill manifest");
        const data = await res.json();
        currentManifestData = data;
        preview.textContent = data.printable_waybill || JSON.stringify(data, null, 2);
    } catch (e) {
        preview.textContent = "Unable to load waybill preview. Please calculate a valid route first.\n\nError: " + e.message;
        showCockpitToast("Manifest preview error: " + e.message, "error");
    }
}

function closeManifestModal() {
    const modal = document.getElementById("manifest-modal");
    if (modal) modal.classList.add("hidden");
}

function closeManifestModalOnBackdrop(e) {
    if (e.target.id === "manifest-modal") {
        closeManifestModal();
    }
}

function copyManifestText() {
    const preview = document.getElementById("manifest-text-preview");
    if (!preview || !preview.textContent) return;
    navigator.clipboard.writeText(preview.textContent).then(() => {
        showCockpitToast("Waybill text copied to clipboard!", "success");
    }).catch(() => {
        showCockpitToast("Could not access clipboard.", "warning");
    });
}

function printManifest() {
    window.print();
}
