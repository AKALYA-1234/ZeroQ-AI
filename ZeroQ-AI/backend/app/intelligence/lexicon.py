"""
Multilingual manufacturing-quality lexicon.

Each concept maps native-script and romanised (code-mixed) surface forms to an
English gloss. It powers the *offline* understanding path: language detection
of romanised Indic text (Tanglish, Hinglish, ...) and a gloss translation good
enough for the issue classifier when no LLM translator is configured.

Coverage is deliberately domain-limited (food-manufacturing complaints and
plant symptoms). General-purpose translation of arbitrary text needs the LLM.

Matching rules (see language.py):
  * native scripts  -> substring match (Indic words are agglutinative,
    e.g. சூடாகுது contains the stem சூடா)
  * romanised forms -> word-prefix match (e.g. "kammiya" starts with "kammi")
"""

# concept_key: (english gloss, {lang_code: [native forms]}, {lang_code: [romanised forms]})
CONCEPTS = {
    "heat": ("overheating hot temperature", {
        "ta": ["சூடு", "சூடா", "வெப்பம்"],
        "hi": ["गर्म", "गरम", "गर्मी", "तापमान"],
        "te": ["వేడి"],
        "ml": ["ചൂട"],
        "kn": ["ಬಿಸಿ"],
    }, {
        "ta": ["soodu", "sudu", "sooda", "heat aguthu", "heat agudhu", "heat aagudhu"],
        "hi": ["garam", "garm", "garmi"],
        "te": ["vedi"],
        "ml": ["choodu", "chood"],
        "kn": ["bisi"],
    }),
    "more": ("high excessive", {
        "ta": ["அதிகம்", "அதிகமா", "ரொம்ப"],
        "hi": ["ज़्यादा", "ज्यादा", "बहुत"],
        "te": ["ఎక్కువ", "చాలా"],
        "ml": ["കൂടുതൽ", "വളരെ"],
        "kn": ["ಹೆಚ್ಚು", "ತುಂಬಾ"],
    }, {
        "ta": ["romba", "rombo", "adhigam", "athigam", "jasthi"],
        "hi": ["zyada", "jyada", "bahut", "bohot"],
        "te": ["ekkuva", "chala"],
        "ml": ["kooduthal", "valare"],
        "kn": ["hechchu", "thumba", "tumba"],
    }),
    "less": ("low reduced less", {
        "ta": ["குறைவு", "குறைஞ்", "கம்மி"],
        "hi": ["कम"],
        "te": ["తక్కువ"],
        "ml": ["കുറവ"],
        "kn": ["ಕಡಿಮೆ"],
    }, {
        "ta": ["kammi", "kuraivu", "korachal", "koraiv"],
        "hi": ["kam", "kami"],
        "te": ["takkuva", "thakkuva"],
        "ml": ["kurav"],
        "kn": ["kadime"],
    }),
    "production": ("production output", {
        "ta": ["உற்பத்தி"],
        "hi": ["उत्पादन"],
        "te": ["ఉత్పత్తి"],
        "ml": ["ഉത്പാദന", "ഉൽപ്പാദന"],
        "kn": ["ಉತ್ಪಾದನೆ"],
    }, {
        "ta": ["urpathi", "utpathi"],
        "hi": ["utpadan"],
        "te": ["utpatti"],
        "ml": ["ulpadanam"],
        "kn": ["utpadane"],
    }),
    "machine": ("machine equipment", {
        "ta": ["இயந்திர", "மெஷின்"],
        "hi": ["मशीन", "यंत्र"],
        "te": ["యంత్ర", "మెషిన్"],
        "ml": ["യന്ത്ര", "മെഷീൻ"],
        "kn": ["ಯಂತ್ರ", "ಮೆಷಿನ್"],
    }, {
        "ta": ["iyanthiram", "mechine"],
        "hi": ["mashin"],
        "te": ["yantram"],
        "ml": ["yanthram"],
        "kn": ["yantra"],
    }),
    "stopping": ("machine stopping breakdown", {
        "ta": ["நிக்குது", "நின்னு", "ஓடல"],
        "hi": ["बंद हो", "रुक"],
        "te": ["ఆగిపో"],
        "ml": ["നിന്നു"],
        "kn": ["ನಿಂತ"],
    }, {
        "ta": ["nikkudhu", "nikkuthu", "ninnu pochu", "odala"],
        "hi": ["band ho", "ruk gay", "ruk jat"],
        "te": ["aagipoy"],
        "ml": ["ninnu poyi"],
        "kn": ["nintu"],
    }),
    "noise": ("abnormal noise vibration", {
        "ta": ["சத்தம்"],
        "hi": ["आवाज़", "आवाज", "शोर"],
        "te": ["శబ్దం"],
        "ml": ["ശബ്ദ"],
        "kn": ["ಶಬ್ದ"],
    }, {
        "ta": ["satham", "saththam", "sattham"],
        "hi": ["awaaz", "awaz", "shor"],
        "te": ["shabdam"],
        "ml": ["shabdam"],
        "kn": ["shabda"],
    }),
    "broken": ("broken product pieces", {
        "ta": ["உடைந்", "உடைஞ்", "உடஞ்ச", "ஒடஞ்ச"],
        "hi": ["टूट"],
        "te": ["విరిగ"],
        "ml": ["പൊട്ടി"],
        "kn": ["ಒಡೆದ", "ಮುರಿದ"],
    }, {
        "ta": ["odanji", "udanji", "odanju", "udainju", "odanj"],
        "hi": ["toota", "tuta", "tuti", "toot", "tute"],
        "te": ["virigi"],
        "ml": ["potti"],
        "kn": ["odedu", "muridu"],
    }),
    "insect": ("insect pest infestation", {
        "ta": ["பூச்சி", "புழு", "வண்டு"],
        "hi": ["कीड़", "कीड", "इल्ली"],
        "te": ["పురుగు", "కీటక"],
        "ml": ["പ്രാണി", "പുഴു"],
        "kn": ["ಕೀಟ", "ಹುಳು"],
    }, {
        "ta": ["poochi", "puchi", "puzhu", "vandu"],
        "hi": ["keeda", "keede", "kida", "kide", "illi"],
        "te": ["purugu"],
        "ml": ["praani", "puzhu"],
        "kn": ["huLu", "hulu", "keeta"],
    }),
    "leak": ("leakage leaking", {
        "ta": ["கசிவு", "கசியுது", "ஒழுகு", "லீக்"],
        "hi": ["रिसाव", "लीक", "टपक"],
        "te": ["లీక్", "కారుతో"],
        "ml": ["ചോർ", "ലീക്ക്"],
        "kn": ["ಸೋರಿಕೆ", "ಲೀಕ್"],
    }, {
        "ta": ["ozhugudhu", "ozhukuthu", "olugudhu", "kasivu", "kasiyudhu"],
        "hi": ["risav", "tapak"],
        "te": ["karutondi"],
        "ml": ["chorunnu", "chorcha"],
        "kn": ["sorike"],
    }),
    "smell": ("off odour bad smell", {
        "ta": ["துர்நாற்றம்", "நாற்றம்", "நாத்தம்", "வாசனை"],
        "hi": ["बदबू", "गंध", "दुर्गंध"],
        "te": ["దుర్వాసన", "వాసన"],
        "ml": ["ദുർഗന്ധ", "നാറ്റ"],
        "kn": ["ದುರ್ವಾಸನೆ", "ವಾಸನೆ"],
    }, {
        "ta": ["naatram", "naathram", "naatham", "nathamu", "natham", "vasanai"],
        "hi": ["badbu", "badboo", "gandh", "durgandh"],
        "te": ["durvasana", "vasana"],
        "ml": ["naattam", "durgandham"],
        "kn": ["durvasane", "vasane"],
    }),
    "taste": ("unusual taste", {
        "ta": ["சுவை", "ருசி"],
        "hi": ["स्वाद"],
        "te": ["రుచి"],
        "ml": ["രുചി"],
        "kn": ["ರುಚಿ"],
    }, {
        "ta": ["suvai", "rusi", "taste sariyilla"],
        "hi": ["swad", "svad", "swaad"],
        "te": ["ruchi"],
        "ml": ["ruchi"],
        "kn": ["ruchi"],
    }),
    "spoiled": ("spoiled stale", {
        "ta": ["கெட்டு", "கெட்டுப்"],
        "hi": ["खराब", "सड़", "बासी"],
        "te": ["పాడై", "చెడి"],
        "ml": ["കേടായ", "ചീഞ്ഞ"],
        "kn": ["ಹಾಳಾ", "ಕೆಟ್ಟ"],
    }, {
        "ta": ["kettu", "ketta", "kettupoch"],
        "hi": ["kharab", "khraab", "sada", "basi"],
        "te": ["paadai", "chedi"],
        "ml": ["kedaya", "cheenja"],
        "kn": ["haalaa", "ketta"],
    }),
    "weight": ("weight quantity", {
        "ta": ["எடை"],
        "hi": ["वजन", "वज़न", "मात्रा"],
        "te": ["బరువు"],
        "ml": ["ഭാരം", "തൂക്ക"],
        "kn": ["ತೂಕ"],
    }, {
        "ta": ["edai", "yedai"],
        "hi": ["vajan", "wazan", "vazan", "matra"],
        "te": ["baruvu"],
        "ml": ["bhaaram", "thookkam"],
        "kn": ["tooka", "thooka"],
    }),
    "packet": ("pack packet", {
        "ta": ["பாக்கெட்", "பொட்டலம்"],
        "hi": ["पैकेट", "पैक"],
        "te": ["ప్యాకెట్"],
        "ml": ["പാക്കറ്റ്"],
        "kn": ["ಪ್ಯಾಕೆಟ್"],
    }, {}),
    "seal": ("seal sealing", {
        "ta": ["சீல்"],
        "hi": ["सील"],
        "te": ["సీల్"],
        "ml": ["സീൽ"],
        "kn": ["ಸೀಲ್"],
    }, {}),
    "open": ("open torn", {
        "ta": ["திறந்", "கிழிஞ்", "கிழிந்"],
        "hi": ["खुला", "फटा", "फटी"],
        "te": ["తెరిచి", "చిరిగ"],
        "ml": ["തുറന്ന", "കീറിയ"],
        "kn": ["ತೆರೆದ", "ಹರಿದ"],
    }, {
        "ta": ["thirandhu", "kizhinj", "kilinj"],
        "hi": ["khula", "phata", "fata", "phati"],
        "te": ["terichi", "chirigi"],
        "ml": ["thuranna", "keeriya"],
        "kn": ["tereda", "harida"],
    }),
    "plastic": ("plastic fragment foreign", {
        "ta": ["பிளாஸ்டிக்"],
        "hi": ["प्लास्टिक"],
        "te": ["ప్లాస్టిక్"],
        "ml": ["പ്ലാസ്റ്റിക്"],
        "kn": ["ಪ್ಲಾಸ್ಟಿಕ್"],
    }, {}),
    "metal": ("metal fragment foreign", {
        "ta": ["உலோக", "இரும்பு", "கம்பி"],
        "hi": ["धातु", "लोहे", "लोहा", "तार"],
        "te": ["లోహ", "ఇనుము"],
        "ml": ["ലോഹ", "ഇരുമ്പ്"],
        "kn": ["ಲೋಹ", "ಕಬ್ಬಿಣ"],
    }, {
        "ta": ["irumbu", "kambi"],
        "hi": ["dhatu", "loha", "lohe"],
        "te": ["inumu"],
        "ml": ["irumbu"],
        "kn": ["kabbina"],
    }),
    "hair": ("hair foreign particle", {
        "ta": ["முடி"],
        "hi": ["बाल"],
        "te": ["జుట్టు", "వెంట్రుక"],
        "ml": ["മുടി"],
        "kn": ["ಕೂದಲು"],
    }, {
        "ta": ["mudi"],
        "hi": ["baal"],
        "te": ["juttu"],
        "kn": ["koodalu"],
    }),
    "stone": ("stone foreign particle", {
        "ta": ["கல்"],
        "hi": ["पत्थर", "कंकड़"],
        "te": ["రాయి"],
        "ml": ["കല്ല"],
        "kn": ["ಕಲ್ಲು"],
    }, {
        "ta": ["kallu"],
        "hi": ["patthar", "kankad"],
        "te": ["raayi"],
    }),
    "fungus": ("mould fungus", {
        "ta": ["பூஞ்சை", "பூசணம்"],
        "hi": ["फफूंद", "फफूंदी"],
        "te": ["బూజు"],
        "ml": ["പൂപ്പൽ"],
        "kn": ["ಬೂಸ್ಟ್"],
    }, {
        "ta": ["poonjai", "boosanam"],
        "hi": ["phaphoond", "fafund", "fungus lag"],
        "te": ["booju"],
        "ml": ["pooppal"],
    }),
    "colour": ("colour variation", {
        "ta": ["நிறம்", "கலர்"],
        "hi": ["रंग"],
        "te": ["రంగు"],
        "ml": ["നിറ"],
        "kn": ["ಬಣ್ಣ"],
    }, {
        "ta": ["niram"],
        "hi": ["rang"],
        "te": ["rangu"],
        "ml": ["niram"],
        "kn": ["banna"],
    }),
    "label": ("label", {
        "ta": ["லேபிள்"],
        "hi": ["लेबल"],
        "te": ["లేబుల్"],
        "ml": ["ലേബൽ"],
        "kn": ["ಲೇಬಲ್"],
    }, {}),
    "wrong": ("wrong incorrect", {
        "ta": ["தப்பு", "தவறு", "தவறான"],
        "hi": ["गलत", "ग़लत"],
        "te": ["తప్పు"],
        "ml": ["തെറ്റ"],
        "kn": ["ತಪ್ಪು"],
    }, {
        "ta": ["thappu", "thavaru"],
        "hi": ["galat", "ghalat"],
        "te": ["tappu"],
        "ml": ["thettu"],
        "kn": ["tappu"],
    }),
    "not_proper": ("not proper improper", {
        "ta": ["சரியா இல்ல", "சரியில்ல"],
        "hi": ["ठीक नहीं", "सही नहीं"],
        "te": ["సరిగా లేదు"],
        "ml": ["ശരിയല്ല"],
        "kn": ["ಸರಿಯಿಲ್ಲ"],
    }, {
        "ta": ["sariya illa", "sariyilla", "sari illa"],
        "hi": ["theek nahi", "thik nahi", "sahi nahi"],
        "te": ["sariga ledu"],
        "ml": ["shariyalla"],
        "kn": ["sariyilla"],
    }),
    "soft": ("soggy soft texture", {
        "ta": ["நமுத்து", "மெத்து"],
        "hi": ["नरम", "गीला"],
        "te": ["మెత్త"],
        "ml": ["നനഞ്ഞ"],
        "kn": ["ಮೆತ್ತ"],
    }, {
        "ta": ["namuthu", "namuththu", "methu"],
        "hi": ["naram", "geela", "gila"],
        "te": ["metta"],
    }),
    "customer": ("customer", {}, {}),
}

# Function words that only signal *which* romanised language is being used.
ROMANISED_MARKERS = {
    "ta": ["irukku", "iruku", "illa", "aguthu", "agudhu", "aachu", "pochu", "romba", "enna",
           "konjam", "vandhu", "vanthu", "paathen", "kuduthaanga", "sollunga", "irundhuchu",
           "irunthuchu", "aayiduchu", "pannunga", "varudhu", "theriyala", "la", "ulla",
           "irundhuchu", "irunthathu", "irundhadhu", "kedachudhu"],
    "hi": ["hai", "hain", "nahi", "nahin", "tha", "thi", "bahut", "kya", "mein", "aur",
           "raha", "rahi", "gaya", "gayi", "kuch", "lekin", "abhi", "wala", "wali", "ka",
           "ki", "ke", "se", "mila", "mile"],
    "te": ["undi", "ledu", "chala", "enti", "ayyindi", "vachindi", "unnayi", "kaadu"],
    "ml": ["undu", "alla", "illa", "valare", "aayi", "poyi", "kittiyath", "aanu"],
    "kn": ["ide", "illa", "thumba", "aagide", "banthu", "beku", "aaytu"],
}

# Unicode script blocks → (language code, language name). Scripts shared by
# several languages map to their most common language for this market.
SCRIPT_RANGES = [
    (0x0B80, 0x0BFF, "ta", "Tamil"),
    (0x0900, 0x097F, "hi", "Hindi"),
    (0x0C00, 0x0C7F, "te", "Telugu"),
    (0x0D00, 0x0D7F, "ml", "Malayalam"),
    (0x0C80, 0x0CFF, "kn", "Kannada"),
    (0x0980, 0x09FF, "bn", "Bengali"),
    (0x0A80, 0x0AFF, "gu", "Gujarati"),
    (0x0A00, 0x0A7F, "pa", "Punjabi"),
    (0x0B00, 0x0B7F, "or", "Odia"),
    (0x0600, 0x06FF, "ar", "Arabic/Urdu"),
    (0x0400, 0x04FF, "ru", "Russian (Cyrillic)"),
    (0x4E00, 0x9FFF, "zh", "Chinese"),
    (0x3040, 0x30FF, "ja", "Japanese"),
    (0xAC00, 0xD7AF, "ko", "Korean"),
    (0x0E00, 0x0E7F, "th", "Thai"),
]

LANGUAGE_NAMES = {
    "en": "English", "ta": "Tamil", "hi": "Hindi", "te": "Telugu", "ml": "Malayalam",
    "kn": "Kannada", "bn": "Bengali", "gu": "Gujarati", "pa": "Punjabi", "or": "Odia",
    "ar": "Arabic/Urdu", "ru": "Russian (Cyrillic)", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "th": "Thai", "es": "Spanish", "fr": "French", "de": "German",
    "und": "Undetermined",
}

CODE_MIXED_NAMES = {
    "ta": "Tanglish (Tamil-English)", "hi": "Hinglish (Hindi-English)",
    "te": "Tenglish (Telugu-English)", "ml": "Manglish (Malayalam-English)",
    "kn": "Kanglish (Kannada-English)",
}

# Small stopword sets to tell common Latin-script languages apart from English.
LATIN_STOPWORDS = {
    "en": {"the", "is", "was", "and", "of", "in", "it", "with", "my", "not", "this", "found", "very"},
    "es": {"el", "la", "es", "con", "muy", "pero", "producto", "una", "que", "está"},
    "fr": {"le", "la", "est", "avec", "très", "mais", "produit", "une", "que", "dans"},
    "de": {"der", "die", "das", "ist", "mit", "sehr", "aber", "produkt", "eine", "nicht"},
}
