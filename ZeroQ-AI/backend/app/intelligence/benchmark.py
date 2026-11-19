"""
Independent, multilingual benchmark queries for honest evaluation.

These were written separately from seeds.py (different wording) and are never
used for training. Expected labels are at category level. The set is small, so
treat its accuracy as indicative, not as a production accuracy figure; real
accuracy comes from admin-verified incidents (see learning.py).
"""

BENCHMARK = [
    # English
    ("There was a sharp bit of plastic in my chips", "en", "Foreign Matter / Contamination"),
    ("I bit into something metallic in the cookie", "en", "Foreign Matter / Contamination"),
    ("Saw tiny bugs moving inside the noodle packet", "en", "Infestation"),
    ("The ketchup bottle leaked all over the bag", "en", "Packaging Defect"),
    ("Pouch arrived unsealed", "en", "Packaging Defect"),
    ("Expiry date printed on the label is wrong", "en", "Packaging Defect"),
    ("Half of the biscuits came crushed", "en", "Physical Defect"),
    ("The jam smells rotten", "en", "Sensory Defect"),
    ("Chips taste very bitter", "en", "Sensory Defect"),
    ("The pack had much less than the weight printed", "en", "Weight / Quantity"),
    ("Spice powder is clumped, not spread through the noodles", "en", "Process-related Defect"),
    ("Line 3 motor is overheating and output dropped", "en", "Machine / Equipment Abnormality"),
    # Tamil (script)
    ("சிப்ஸ் பாக்கெட்டில் பிளாஸ்டிக் துண்டு இருந்தது", "ta", "Foreign Matter / Contamination"),
    ("பிஸ்கட் பாக்கெட்டில் பூச்சி இருந்தது", "ta", "Infestation"),
    ("சாஸ் பாட்டில் கசிவு உள்ளது", "ta", "Packaging Defect"),
    ("ஊறுகாய் துர்நாற்றம் வருகிறது", "ta", "Sensory Defect"),
    # Hindi (script)
    ("नमकीन के पैकेट में कीड़े थे", "hi", "Infestation"),
    ("बिस्कुट में प्लास्टिक का टुकड़ा मिला", "hi", "Foreign Matter / Contamination"),
    ("सॉस से बदबू आ रही है", "hi", "Sensory Defect"),
    ("पैकेट का वजन कम है", "hi", "Weight / Quantity"),
    # Telugu / Malayalam / Kannada
    ("బిస్కెట్ ప్యాకెట్ లో పురుగులు ఉన్నాయి", "te", "Infestation"),
    ("ചിപ്സ് പാക്കറ്റിൽ പ്ലാസ്റ്റിക് കഷണം ഉണ്ടായിരുന്നു", "ml", "Foreign Matter / Contamination"),
    ("ಸಾಸ್ ಬಾಟಲಿಯಿಂದ ಸೋರಿಕೆ ಆಗುತ್ತಿದೆ", "kn", "Packaging Defect"),
    # Code-mixed
    ("Machine romba heat aguthu, production output kammiya irukku", "ta", "Machine / Equipment Abnormality"),
    ("Chips packet la plastic piece irundhuchu", "ta", "Foreign Matter / Contamination"),
    ("Biscuit packet seal sariya illa, ulla poochi irundhuchu", "ta", "Infestation"),
    ("Noodles ka swad kharab hai aur badbu aa rahi hai", "hi", "Sensory Defect"),
    ("Packet ka wazan kam hai", "hi", "Weight / Quantity"),
    ("Ketchup bottle se leak ho raha hai", "hi", "Packaging Defect"),
]
