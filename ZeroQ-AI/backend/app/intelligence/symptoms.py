"""
Rule-based symptom extraction over English (or glossed) text.

Symptoms are evidence for the admin and drive the offline "rules" fallback when
the classifier is unsure and no LLM is configured. Each rule requires every
pattern group to match somewhere in the text.
"""
import re
from typing import List, Dict

# (symptom, subcategory hint, [pattern groups — all must match], suggested checks)
SYMPTOM_RULES = [
    ("Machine overheating", "Machine Overheating",
     [r"\b(machine|equipment|motor|line|oven|sealer|mixer|extruder)\b", r"(overheat|\bhot\b|\bheat|high temp|temperature)"],
     "Check process/motor temperature, motor load, cooling and lubrication."),
    ("Reduced production output", "Reduced Production Output",
     [r"\b(production|output|throughput|yield|capacity)\b", r"\b(low|reduced|less|drop|decreas|down|fall|slow)"],
     "Review line speed, downtime log and upstream material supply."),
    ("Machine stoppage / breakdown", "Machine Breakdown",
     [r"\b(machine|line|equipment|motor|conveyor)\b", r"(stop|breakdown|break down|jam|trip|not running|failure)"],
     "Inspect drive, interlocks and maintenance history for the stopped equipment."),
    ("Abnormal noise / vibration", "Abnormal Noise / Vibration",
     [r"(noise|vibrat|rattl|grinding sound|abnormal sound)"],
     "Check bearings, alignment and fasteners; compare vibration with baseline."),
    ("Seal failure", "Poor Sealing",
     [r"\bseal", r"(open|broken|weak|poor|not proper|improper|fail|loose|unseal|torn)"],
     "Verify sealing temperature, pressure and dwell time; inspect seal jaws."),
    ("Leakage", "Leakage",
     [r"(leak|oozing|dripping)"],
     "Check seal integrity and packaging material lot for the affected batch."),
    ("Damaged packaging", "Damaged Pack",
     [r"\b(pack|packet|carton|box|pouch|packaging|wrapper)", r"(damag|torn|tear|crush|dent|puncture|open)"],
     "Review handling, palletisation and packaging material strength."),
    ("Labelling error", "Incorrect Label",
     [r"\blabel", r"(wrong|incorrect|missing|mismatch|misprint|not match)"],
     "Verify label artwork and line clearance at the packing station."),
    ("Insect / pest presence", "Insect Presence",
     [r"(insect|pest|worm|weevil|infest|cockroach|\bbugs?\b|larva|\bants?\b)"],
     "Inspect pest-control records and raw-material storage for the batch."),
    ("Foreign particle", "Foreign Particle",
     [r"(plastic|metal|glass|stone|hair|foreign|particle|fragment|\bwire\b)"],
     "Check sieves, magnets and metal-detector logs; review equipment integrity."),
    ("Off odour", "Off Odour",
     [r"(smell|odou?r|stink)"],
     "Check raw-material freshness and storage conditions; run sensory evaluation."),
    ("Unusual taste", "Unusual Taste",
     [r"(taste|bitter|sour|rancid|salty)"],
     "Review recipe dosing and ingredient lots; run sensory evaluation."),
    ("Spoilage / mould", "Suspected Contamination",
     [r"(spoil|stale|mou?ld|fung|expired|rotten)"],
     "Check shelf-life, water activity and storage temperature."),
    ("Broken product", "Broken Product",
     [r"(broken|crush|crumb|cracked|pieces)"],
     "Review conveyor transfer points and packing handling."),
    ("Weight / quantity issue", "Short Quantity",
     [r"(weight|quantity|underweight|overweight|short|fewer)"],
     "Check filler calibration and checkweigher rejects."),
    ("Colour variation", "Colour Variation",
     [r"colou?r"],
     "Check baking/frying temperature profile and raw-material variation."),
    ("Texture issue", "Texture Deviation",
     [r"(soggy|texture|chewy|too hard|too soft)"],
     "Check moisture, baking time and packaging barrier."),
]


def extract_symptoms(text: str) -> List[Dict[str, str]]:
    low = (text or "").lower()
    found = []
    for name, sub_hint, groups, checks in SYMPTOM_RULES:
        if all(re.search(g, low) for g in groups):
            found.append({"symptom": name, "subcategory_hint": sub_hint, "suggested_checks": checks})
    return found
