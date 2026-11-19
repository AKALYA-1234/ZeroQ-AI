"""
Curated domain seed phrases (English) per subcategory.

Why: the historical complaint descriptions use only ~35 template sentences, so a
classifier trained on them alone cannot generalise to real customer wording.
These hand-written paraphrases widen vocabulary coverage. They are labelled as
`seed` in training metadata and are never used for evaluation (see benchmark.py,
which is phrased independently).
"""

SEED_PHRASES = {
    "Plastic Fragment": [
        "found a piece of plastic in the biscuits", "hard plastic bit inside the chips",
        "there was a plastic strip mixed in the noodles", "plastic piece in the food",
    ],
    "Metal Fragment": [
        "metal piece found in the product", "small iron wire in the snack",
        "a steel fragment was in the pack", "metal shaving inside the food",
    ],
    "Foreign Particle": [
        "hair found inside the packet", "a small stone in the peanuts",
        "foreign object found in the food", "black particles in the product",
        "glass piece in the jar",
    ],
    "Suspected Contamination": [
        "product looks contaminated", "mould growing on the bread",
        "fungus on the pickle", "product spoiled before expiry", "food made me sick",
    ],
    "Insect Presence": [
        "insects inside the packet", "live worms in the noodles",
        "found a cockroach in the box", "small bugs crawling in the biscuits",
    ],
    "Pest Damage": [
        "packet bitten by rats", "holes in the pack from pests",
        "rodent damage on the carton", "pests had chewed the packaging",
    ],
    "Other": [
        "general complaint about the service", "not happy with the product",
        "delivery person was rude", "need help with my order",
    ],
    "Storage Concern": [
        "product was stored in a hot warehouse", "kept in the sun at the shop",
        "stored in a damp place", "cold chain was not maintained",
    ],
    "Incorrect Product": [
        "received a different product than ordered", "wrong flavour delivered",
        "ordered ketchup but got chilli sauce", "wrong item in the box",
    ],
    "Poor Sealing": [
        "the seal was open when I bought it", "pack not sealed properly",
        "seal came apart easily", "weak seal on the pouch",
    ],
    "Damaged Pack": [
        "the box was crushed", "packet torn on arrival", "carton dented and damaged",
        "outer pack was punctured",
    ],
    "Leakage": [
        "sauce leaking from the bottle", "oil leaking out of the pouch",
        "jar was leaking", "liquid oozing from the pack",
    ],
    "Incorrect Label": [
        "label shows the wrong expiry date", "wrong label on the pack",
        "ingredients on the label do not match", "label missing batch number",
        "misprinted label",
    ],
    "Broken Product": [
        "all the biscuits were broken", "cookies crushed into crumbs",
        "most chips were broken pieces", "rusks broken inside the pack",
    ],
    "Deformed Shape": [
        "the biscuits were misshapen", "noodles block was deformed",
        "cookies had irregular shape", "product shape was odd",
    ],
    "Cracks": [
        "cracks on the biscuit surface", "wafers were cracked",
        "cracked cookies", "visible cracks in the product",
    ],
    "Incomplete Processing": [
        "the biscuit was undercooked", "product looked raw in the middle",
        "chips not fried properly", "pasta was not dried completely",
    ],
    "Inconsistent Batch": [
        "each packet tastes different", "quality varies between packs",
        "some pieces are fine and others are not", "inconsistent quality in the same batch",
    ],
    "Improper Mixing": [
        "spices not mixed evenly", "lumps of masala in the noodles",
        "salt was uneven across the chips", "ingredients were not mixed properly",
    ],
    "Colour Variation": [
        "the colour looked different from usual", "biscuits were too dark",
        "chips had a burnt colour", "jam colour was faded",
    ],
    "Off Odour": [
        "bad smell when I opened the packet", "it smelled rancid",
        "strange odour from the sauce",
    ],
    "Texture Deviation": [
        "the chips were soggy", "biscuits were too hard",
        "texture was chewy instead of crisp", "product was soft and not crunchy",
    ],
    "Unusual Taste": [
        "the taste was bitter", "tasted sour and strange", "taste was not like before",
        "too salty to eat",
    ],
    "Short Quantity": [
        "fewer biscuits than stated", "the pack was half empty",
        "less quantity than printed", "missing pieces in the box",
    ],
    "Underweight Pack": [
        "pack weighed less than declared", "net weight is lower than printed",
        "the packet was underweight", "weight was short",
    ],
    "Overweight Pack": [
        "pack weighed more than declared", "overfilled packet",
        "net weight higher than label", "the jar was overweight",
    ],
    "Machine Overheating": [
        "machine is overheating", "the motor is running very hot",
        "oven temperature is too high on line two", "the sealer is getting too hot",
    ],
    "Reduced Production Output": [
        "production output is low today", "line throughput has dropped",
        "output is reduced compared to normal", "we produced far fewer cases this shift",
    ],
    "Machine Breakdown": [
        "the machine stopped working", "conveyor keeps jamming",
        "line breakdown during the shift", "the line trips every hour",
    ],
    "Abnormal Noise / Vibration": [
        "machine making a loud noise", "strong vibration in the mixer",
        "grinding sound from the motor", "the conveyor is shaking",
    ],
}
