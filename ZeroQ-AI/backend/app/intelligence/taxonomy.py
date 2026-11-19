"""
Issue taxonomy. The first eight categories (and their subcategories) are the ones
used across the 6,000 historical complaints; the operational category covers
plant / machine abnormalities reported through the same channel, which the
historical data does not contain (it is learned only from verified incidents).
"""

SUBCATEGORY_TO_CATEGORY = {
    "Plastic Fragment": "Foreign Matter / Contamination",
    "Suspected Contamination": "Foreign Matter / Contamination",
    "Foreign Particle": "Foreign Matter / Contamination",
    "Metal Fragment": "Foreign Matter / Contamination",
    "Pest Damage": "Infestation",
    "Insect Presence": "Infestation",
    "Other": "Other Customer Concern",
    "Storage Concern": "Other Customer Concern",
    "Incorrect Product": "Other Customer Concern",
    "Poor Sealing": "Packaging Defect",
    "Damaged Pack": "Packaging Defect",
    "Leakage": "Packaging Defect",
    "Incorrect Label": "Packaging Defect",
    "Broken Product": "Physical Defect",
    "Deformed Shape": "Physical Defect",
    "Cracks": "Physical Defect",
    "Incomplete Processing": "Process-related Defect",
    "Inconsistent Batch": "Process-related Defect",
    "Improper Mixing": "Process-related Defect",
    "Colour Variation": "Sensory Defect",
    "Off Odour": "Sensory Defect",
    "Texture Deviation": "Sensory Defect",
    "Unusual Taste": "Sensory Defect",
    "Short Quantity": "Weight / Quantity",
    "Underweight Pack": "Weight / Quantity",
    "Overweight Pack": "Weight / Quantity",
    # Operational (not present in historical complaint data)
    "Machine Overheating": "Machine / Equipment Abnormality",
    "Reduced Production Output": "Machine / Equipment Abnormality",
    "Machine Breakdown": "Machine / Equipment Abnormality",
    "Abnormal Noise / Vibration": "Machine / Equipment Abnormality",
}

OPERATIONAL_CATEGORY = "Machine / Equipment Abnormality"
NEW_ISSUE_CATEGORY = "Other / New Issue"

CATEGORIES = sorted(set(SUBCATEGORY_TO_CATEGORY.values())) + [NEW_ISSUE_CATEGORY]
SEVERITIES = ["low", "medium", "high", "critical"]


def category_for(subcategory: str, default: str = NEW_ISSUE_CATEGORY) -> str:
    return SUBCATEGORY_TO_CATEGORY.get(subcategory, default)
