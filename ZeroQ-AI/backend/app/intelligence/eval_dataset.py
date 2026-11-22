"""
Independent multilingual evaluation set (never used for training).

Each item: (text, language, expected_category, issue_group). `issue_group` ties
together different phrasings of the same issue across languages, so results can be
read per issue as well as per language. Wording was written independently of
seeds.py. Items in UNSUPPORTED_OFFLINE are languages the offline glossary does not
cover; they are scored separately (they need the LLM translator).

Size is ~90 items: enough to compare model versions and spot weak languages or
categories, NOT enough to state a production accuracy. Real accuracy comes from
admin-verified incidents.
"""
FM, INF, PKG, PHY, SEN, WGT, PRC, OTH, MCH = (
    "Foreign Matter / Contamination", "Infestation", "Packaging Defect", "Physical Defect",
    "Sensory Defect", "Weight / Quantity", "Process-related Defect", "Other Customer Concern",
    "Machine / Equipment Abnormality",
)

EVAL_ITEMS = [
    # ── English ──────────────────────────────────────────────────────────
    ("There was a sharp bit of plastic in my chips", "en", FM, "plastic"),
    ("I bit into something metallic in the cookie", "en", FM, "metal"),
    ("Saw tiny bugs moving inside the noodle packet", "en", INF, "insects"),
    ("The ketchup bottle leaked all over the bag", "en", PKG, "leak"),
    ("Pouch arrived unsealed", "en", PKG, "seal"),
    ("Expiry date printed on the label is wrong", "en", PKG, "label"),
    ("Half of the biscuits came crushed", "en", PHY, "broken"),
    ("The jam smells rotten", "en", SEN, "odour"),
    ("Chips taste very bitter", "en", SEN, "taste"),
    ("The pack had much less than the weight printed", "en", WGT, "weight"),
    ("Spice powder is clumped, not spread through the noodles", "en", PRC, "mixing"),
    ("The biscuits are raw and doughy in the centre", "en", PRC, "undercooked"),
    ("Received tomato ketchup instead of the chilli sauce I ordered", "en", OTH, "wrong_product"),
    ("Line 3 motor is overheating and output dropped", "en", MCH, "machine_heat"),
    ("Our sealer on line M-12 keeps stopping mid-shift", "en", MCH, "machine_stop"),
    # ── Tamil (script) ───────────────────────────────────────────────────
    ("சிப்ஸ் பாக்கெட்டில் பிளாஸ்டிக் துண்டு இருந்தது", "ta", FM, "plastic"),
    ("பிஸ்கட்டில் சின்ன கம்பி துண்டு இருந்தது", "ta", FM, "metal"),
    ("பாக்கெட்டில் முடி இருந்தது", "ta", FM, "hair"),
    ("நூடுல்ஸ் பாக்கெட்டுக்குள் பூச்சிகள் இருந்தன", "ta", INF, "insects"),
    ("சாஸ் பாட்டிலில் இருந்து கசிவு வருகிறது", "ta", PKG, "leak"),
    ("லேபிளில் தவறான தேதி உள்ளது", "ta", PKG, "label"),
    ("பிஸ்கட் எல்லாம் உடைந்து இருந்தது", "ta", PHY, "broken"),
    ("ஊறுகாய் துர்நாற்றம் வருகிறது", "ta", SEN, "odour"),
    ("பாக்கெட் எடை குறைவாக உள்ளது", "ta", WGT, "weight"),
    ("இயந்திரம் அதிகமாக சூடாகிறது, உற்பத்தி குறைவு", "ta", MCH, "machine_heat"),
    # ── Tanglish (romanised, code-mixed) ─────────────────────────────────
    ("Chips packet la plastic piece irundhuchu", "ta", FM, "plastic"),
    ("Biscuit la oru chinna kambi irundhuchu", "ta", FM, "metal"),
    ("Noodles packet ulla poochi irundhuchu", "ta", INF, "insects"),
    ("Ketchup bottle la irundhu leak aaguthu", "ta", PKG, "leak"),
    ("Packet seal sariya illa, open aa irundhuchu", "ta", PKG, "seal"),
    ("Pickle romba naathama irukku", "ta", SEN, "odour"),
    ("Biscuits ellam odanji pochu", "ta", PHY, "broken"),
    ("Packet edai kammiya irukku", "ta", WGT, "weight"),
    ("Machine romba heat aaguthu, output kammi aagiduchu", "ta", MCH, "machine_heat"),
    ("Line 2 machine nikkudhu, production kammi", "ta", MCH, "machine_stop"),
    # ── Hindi (script) ───────────────────────────────────────────────────
    ("नमकीन के पैकेट में कीड़े थे", "hi", INF, "insects"),
    ("बिस्कुट में प्लास्टिक का टुकड़ा मिला", "hi", FM, "plastic"),
    ("चिप्स में बाल मिला", "hi", FM, "hair"),
    ("सॉस से बदबू आ रही है", "hi", SEN, "odour"),
    ("नूडल्स का स्वाद खराब है", "hi", SEN, "taste"),
    ("पैकेट का वजन कम है", "hi", WGT, "weight"),
    ("बोतल से सॉस लीक हो रहा है", "hi", PKG, "leak"),
    ("पैकेट की सील खुली हुई थी", "hi", PKG, "seal"),
    ("सारे बिस्कुट टूटे हुए थे", "hi", PHY, "broken"),
    ("मशीन बहुत गर्म हो रही है और उत्पादन कम हो गया है", "hi", MCH, "machine_heat"),
    # ── Hinglish ─────────────────────────────────────────────────────────
    ("Noodles ka swad kharab hai aur badbu aa rahi hai", "hi", SEN, "taste"),
    ("Packet ka wazan kam hai", "hi", WGT, "weight"),
    ("Ketchup bottle se leak ho raha hai", "hi", PKG, "leak"),
    ("Biscuit packet mein keede mile", "hi", INF, "insects"),
    ("Chips mein plastic ka tukda tha", "hi", FM, "plastic"),
    ("Saare biscuit toote hue the", "hi", PHY, "broken"),
    ("Packet ki seal khuli thi", "hi", PKG, "seal"),
    ("Label pe galat expiry date hai", "hi", PKG, "label"),
    ("Jam mein fungus lag gaya hai", "hi", FM, "mould"),
    ("Machine bahut garam ho rahi hai, production kam ho gaya", "hi", MCH, "machine_heat"),
    # ── Telugu ───────────────────────────────────────────────────────────
    ("బిస్కెట్ ప్యాకెట్ లో పురుగులు ఉన్నాయి", "te", INF, "insects"),
    ("చిప్స్ లో ప్లాస్టిక్ ముక్క ఉంది", "te", FM, "plastic"),
    ("సాస్ బాటిల్ నుండి లీక్ అవుతోంది", "te", PKG, "leak"),
    ("ఊరగాయ నుండి దుర్వాసన వస్తోంది", "te", SEN, "odour"),
    ("ప్యాకెట్ బరువు తక్కువగా ఉంది", "te", WGT, "weight"),
    ("బిస్కెట్లు అన్నీ విరిగిపోయాయి", "te", PHY, "broken"),
    ("యంత్రం చాలా వేడిగా ఉంది, ఉత్పత్తి తక్కువ", "te", MCH, "machine_heat"),
    ("నూడుల్స్ రుచి బాగోలేదు", "te", SEN, "taste"),
    # ── Malayalam ────────────────────────────────────────────────────────
    ("ചിപ്സ് പാക്കറ്റിൽ പ്ലാസ്റ്റിക് കഷണം ഉണ്ടായിരുന്നു", "ml", FM, "plastic"),
    ("ബിസ്കറ്റ് പാക്കറ്റിൽ പ്രാണികൾ ഉണ്ടായിരുന്നു", "ml", INF, "insects"),
    ("സോസ് കുപ്പിയിൽ നിന്ന് ചോർച്ചയുണ്ട്", "ml", PKG, "leak"),
    ("അച്ചാറിന് ദുർഗന്ധം ഉണ്ട്", "ml", SEN, "odour"),
    ("പാക്കറ്റിന്റെ ഭാരം കുറവാണ്", "ml", WGT, "weight"),
    ("ബിസ്കറ്റുകൾ എല്ലാം പൊട്ടിയിരുന്നു", "ml", PHY, "broken"),
    ("യന്ത്രം വളരെ ചൂടാകുന്നു, ഉത്പാദനം കുറവാണ്", "ml", MCH, "machine_heat"),
    ("നൂഡിൽസിന്റെ രുചി മോശമാണ്", "ml", SEN, "taste"),
    # ── Kannada ──────────────────────────────────────────────────────────
    ("ಸಾಸ್ ಬಾಟಲಿಯಿಂದ ಸೋರಿಕೆ ಆಗುತ್ತಿದೆ", "kn", PKG, "leak"),
    ("ಬಿಸ್ಕತ್ ಪ್ಯಾಕೆಟ್ ನಲ್ಲಿ ಕೀಟಗಳು ಇದ್ದವು", "kn", INF, "insects"),
    ("ಚಿಪ್ಸ್ ನಲ್ಲಿ ಪ್ಲಾಸ್ಟಿಕ್ ತುಂಡು ಇತ್ತು", "kn", FM, "plastic"),
    ("ಉಪ್ಪಿನಕಾಯಿ ದುರ್ವಾಸನೆ ಬರುತ್ತಿದೆ", "kn", SEN, "odour"),
    ("ಪ್ಯಾಕೆಟ್ ತೂಕ ಕಡಿಮೆ ಇದೆ", "kn", WGT, "weight"),
    ("ಬಿಸ್ಕತ್ ಎಲ್ಲಾ ಒಡೆದು ಹೋಗಿದೆ", "kn", PHY, "broken"),
    ("ಯಂತ್ರ ತುಂಬಾ ಬಿಸಿಯಾಗುತ್ತಿದೆ, ಉತ್ಪಾದನೆ ಕಡಿಮೆ", "kn", MCH, "machine_heat"),
    ("ನೂಡಲ್ಸ್ ರುಚಿ ಚೆನ್ನಾಗಿಲ್ಲ", "kn", SEN, "taste"),
]

# Detected, but outside the offline glossary — they need the LLM translator.
UNSUPPORTED_OFFLINE = [
    ("প্যাকেটে পোকা ছিল", "bn", INF, "insects"),
    ("પેકેટમાં જીવાત હતી", "gu", INF, "insects"),
    ("Había insectos dentro del paquete", "es", INF, "insects"),
    ("La bouteille de sauce fuit", "fr", PKG, "leak"),
]
