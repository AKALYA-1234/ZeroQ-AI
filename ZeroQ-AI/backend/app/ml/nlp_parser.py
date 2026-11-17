"""
ZeroQ AI - Manufacturing Quality NLP Entity Parser
Extracts manufacturing domain entities from conversational user queries
without relying on external paid APIs.
"""

import re
from typing import Dict, Any, Tuple, List, Optional

PRODUCTS = [
    "Classic Biscuits", "Digestive Biscuits", "Chocolate Cookies", "Butter Cookies", "Cream Wafers",
    "Salty Crackers", "Rusks", "Potato Chips", "Tortilla Chips", "Extruded Snacks",
    "Roasted Peanuts", "Trail Mix", "Fruit Jam", "Mango Pickle", "Mixed Pickle",
    "Tomato Ketchup", "Chilli Sauce", "Mayonnaise", "Instant Noodles", "Pasta"
]

PRODUCT_CATEGORIES = {
    "Classic Biscuits": "Biscuits",
    "Digestive Biscuits": "Biscuits",
    "Chocolate Cookies": "Biscuits",
    "Butter Cookies": "Biscuits",
    "Cream Wafers": "Biscuits",
    "Salty Crackers": "Biscuits",
    "Rusks": "Bakery",
    "Potato Chips": "Snacks",
    "Tortilla Chips": "Snacks",
    "Extruded Snacks": "Snacks",
    "Roasted Peanuts": "Snacks",
    "Trail Mix": "Snacks",
    "Fruit Jam": "Spreads",
    "Mango Pickle": "Pickles",
    "Mixed Pickle": "Pickles",
    "Tomato Ketchup": "Sauces",
    "Chilli Sauce": "Sauces",
    "Mayonnaise": "Dressings",
    "Instant Noodles": "Noodles",
    "Pasta": "Pasta"
}

FACILITIES = [
    ("Chennai Manufacturing Unit", ["chennai", "tamil nadu", "fac001"]),
    ("Pune Manufacturing Unit", ["pune", "maharashtra", "fac002"]),
    ("Hyderabad Manufacturing Unit", ["hyderabad", "telangana", "fac003"]),
    ("Bengaluru Manufacturing Unit", ["bengaluru", "bangalore", "karnataka", "fac004"]),
    ("Kolkata Manufacturing Unit", ["kolkata", "west bengal", "fac005"])
]

FACILITY_STATES = {
    "Chennai Manufacturing Unit": "Tamil Nadu",
    "Pune Manufacturing Unit": "Maharashtra",
    "Hyderabad Manufacturing Unit": "Telangana",
    "Bengaluru Manufacturing Unit": "Karnataka",
    "Kolkata Manufacturing Unit": "West Bengal"
}

SHIFTS = ["Morning", "Evening", "Night"]

def parse_manufacturing_query(text: str) -> Tuple[Dict[str, Any], float, List[str], List[str]]:
    """
    Parses a free-text user query into structured manufacturing entities.
    Returns:
        (extracted_entities, parse_confidence, clues_found, assumed_defaults)
    """
    if not text or not text.strip():
        return {}, 0.0, [], []

    raw_text = text.strip()
    low = raw_text.lower()
    extracted: Dict[str, Any] = {}
    clues: List[str] = []
    assumed: List[str] = []

    # 1. Batch ID (e.g. BAT000004, BAT012345, batch 4, lot 88482)
    batch_match = re.search(r'\b(BAT\d{6})\b', raw_text, re.IGNORECASE)
    if batch_match:
        extracted["batch_id"] = batch_match.group(1).upper()
        clues.append(f"Batch Identifier: {extracted['batch_id']}")
    else:
        batch_num = re.search(r'\bbatch\s*#?\s*(\d+)\b', low)
        if batch_num:
            num = int(batch_num.group(1))
            extracted["batch_id"] = f"BAT{num:06d}"
            clues.append(f"Batch Identifier: {extracted['batch_id']}")

    # 2. Product Name & Category
    matched_product = None
    for prod in PRODUCTS:
        if prod.lower() in low:
            matched_product = prod
            break
    if not matched_product:
        # Check partial words (e.g. "Biscuits", "Chips", "Noodles", "Jam", "Cookies", "Pickle")
        for prod in PRODUCTS:
            words = [w for w in prod.lower().split() if len(w) > 3]
            if any(w in low for w in words):
                matched_product = prod
                break

    if matched_product:
        extracted["product_name"] = matched_product
        extracted["product_category"] = PRODUCT_CATEGORIES.get(matched_product, "General Food")
        clues.append(f"Product: {matched_product} ({extracted['product_category']})")

    # 3. Manufacturing Facility
    for fac_name, aliases in FACILITIES:
        if any(alias in low for alias in aliases) or fac_name.lower() in low:
            extracted["facility_name"] = fac_name
            extracted["facility_state"] = FACILITY_STATES.get(fac_name, "Tamil Nadu")
            clues.append(f"Facility: {fac_name} ({extracted['facility_state']})")
            break

    # 4. Production Shift
    for shift in SHIFTS:
        if shift.lower() in low:
            extracted["production_shift"] = shift
            clues.append(f"Shift: {shift}")
            break

    # 5. Supplier Quality Grade
    grade_match = re.search(r'\bgrade\s*([abc123])\b', low)
    if grade_match:
        g = grade_match.group(1).upper()
        norm_grade = "A" if g in ["1", "A"] else ("B" if g in ["2", "B"] else "C")
        extracted["supplier_quality_grade"] = norm_grade
        clues.append(f"Supplier Quality Grade: {norm_grade}")

    # 6. Process Temperature (°C)
    temp_match = re.search(r'(?:process\s*temp(?:erature)?|temp(?:erature)?)\s*(?:is|of|at|:)?\s*([0-9.]+)\s*(?:c|deg|°)?', low)
    if temp_match and "sealing" not in low[max(0, temp_match.start() - 10):temp_match.start()]:
        try:
            extracted["process_temperature_c"] = float(temp_match.group(1))
            clues.append(f"Process Temperature: {extracted['process_temperature_c']}°C")
        except ValueError:
            pass

    # 7. Sealing Temperature (°C)
    seal_match = re.search(r'(?:sealing|seal)\s*(?:temp(?:erature)?)?\s*(?:is|of|at|:)?\s*([0-9.]+)\s*(?:c|deg|°)?', low)
    if seal_match:
        try:
            extracted["sealing_temperature_c"] = float(seal_match.group(1))
            clues.append(f"Sealing Temperature: {extracted['sealing_temperature_c']}°C")
        except ValueError:
            pass

    # 8. Ambient Humidity (%)
    hum_match = re.search(r'(?:ambient\s*humidity|humidity)\s*(?:is|of|at|:)?\s*([0-9.]+)\s*%?', low)
    if hum_match:
        try:
            extracted["ambient_humidity_pct"] = float(hum_match.group(1))
            clues.append(f"Ambient Humidity: {extracted['ambient_humidity_pct']}%")
        except ValueError:
            pass
    elif "high humidity" in low:
        extracted["ambient_humidity_pct"] = 75.0
        clues.append("Ambient Humidity: High (75%)")
    elif "low humidity" in low:
        extracted["ambient_humidity_pct"] = 35.0
        clues.append("Ambient Humidity: Low (35%)")

    # 9. Line Pressure (bar)
    press_match = re.search(r'(?:line\s*pressure|pressure)\s*(?:is|of|at|:)?\s*([0-9.]+)\s*(?:bar)?', low)
    if press_match:
        try:
            extracted["line_pressure_bar"] = float(press_match.group(1))
            clues.append(f"Line Pressure: {extracted['line_pressure_bar']} bar")
        except ValueError:
            pass

    # 10. Process Deviation Flag
    if any(word in low for word in ["deviation", "anomaly", "abnormal", "spike", "breakdown", "glitch", "failure", "defect"]):
        extracted["process_deviation_flag"] = 1
        clues.append("Process Deviation Flag: 1 (Anomaly indicated in text)")
    else:
        extracted["process_deviation_flag"] = 0

    # 11. Packaging / Raw Material Grade
    mat_match = re.search(r'(?:sealant|foil|carton|packaging|raw material)\s*(?:grade\s*([0-9a-c]))?', low)
    if mat_match and mat_match.group(1):
        g_num = mat_match.group(1).upper()
        if "sealant" in low:
            extracted["packaging_material_name"] = f"Sealant Grade {g_num}"
            clues.append(f"Packaging Material: {extracted['packaging_material_name']}")
        elif "carton" in low:
            extracted["packaging_material_name"] = f"Carton Grade {g_num}"
            clues.append(f"Packaging Material: {extracted['packaging_material_name']}")

    # Calculate Confidence Score
    confidence = 0.0
    if "batch_id" in extracted:
        confidence = 0.95
    else:
        if "product_name" in extracted:
            confidence += 0.40
        if "facility_name" in extracted:
            confidence += 0.25
        if "production_shift" in extracted:
            confidence += 0.15
        if "supplier_quality_grade" in extracted:
            confidence += 0.10
        if any(k in extracted for k in ["process_temperature_c", "sealing_temperature_c", "ambient_humidity_pct", "line_pressure_bar"]):
            confidence += 0.20
        confidence = min(0.95, round(confidence, 2))

    # Identify Assumed Defaults
    if "batch_id" not in extracted:
        if "product_name" not in extracted:
            assumed.append("Product defaulted to 'Classic Biscuits' (highest historical volume)")
        if "facility_name" not in extracted:
            assumed.append("Facility defaulted to 'Chennai Manufacturing Unit' (Primary Plant)")
        if "production_shift" not in extracted:
            assumed.append("Shift defaulted to 'Morning'")
        if "supplier_quality_grade" not in extracted:
            assumed.append("Supplier quality grade defaulted to 'A'")
        if "process_temperature_c" not in extracted:
            assumed.append("Process temperature defaulted to nominal baseline (123.4°C)")
        if "sealing_temperature_c" not in extracted:
            assumed.append("Sealing temperature defaulted to nominal baseline (165.1°C)")
        if "ambient_humidity_pct" not in extracted:
            assumed.append("Ambient humidity defaulted to standard condition (54.9%)")
        if "line_pressure_bar" not in extracted:
            assumed.append("Line pressure defaulted to operating nominal (5.01 bar)")

    return extracted, confidence, clues, assumed
