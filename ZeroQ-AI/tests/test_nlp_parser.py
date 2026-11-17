import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.ml.nlp_parser import parse_manufacturing_query

def test_nlp_extract_full_query():
    query = "Predict defect risk for Classic Biscuits in Pune facility on Night shift with temperature 135C"
    extracted, conf, clues, assumed = parse_manufacturing_query(query)

    assert extracted.get("product_name") == "Classic Biscuits"
    assert extracted.get("facility_name") == "Pune Manufacturing Unit"
    assert extracted.get("production_shift") == "Night"
    assert extracted.get("process_temperature_c") == 135.0
    assert conf >= 0.80
    assert len(clues) >= 3

def test_nlp_extract_batch_id():
    query = "Evaluate risk for batch BAT000004"
    extracted, conf, clues, assumed = parse_manufacturing_query(query)

    assert extracted.get("batch_id") == "BAT000004"
    assert conf >= 0.90
    assert "bat000004" in str(clues).lower()

def test_nlp_extract_batch_number_format():
    query = "Check quality outcome for batch #42"
    extracted, conf, clues, assumed = parse_manufacturing_query(query)

    assert extracted.get("batch_id") == "BAT000042"
    assert conf >= 0.90

def test_nlp_telemetry_parameters():
    query = "Evaluate Potato Chips with ambient humidity 82% and line pressure 5.8 bar and sealing temp 175C"
    extracted, conf, clues, assumed = parse_manufacturing_query(query)

    assert extracted.get("product_name") == "Potato Chips"
    assert extracted.get("ambient_humidity_pct") == 82.0
    assert extracted.get("line_pressure_bar") == 5.8
    assert extracted.get("sealing_temperature_c") == 175.0

def test_nlp_deviation_keywords():
    query = "Fruit Jam batch with abnormal temperature spike and seal defect"
    extracted, conf, clues, assumed = parse_manufacturing_query(query)

    assert extracted.get("product_name") == "Fruit Jam"
    assert extracted.get("process_deviation_flag") == 1

def test_nlp_empty_or_gibberish():
    empty_res = parse_manufacturing_query("")
    assert empty_res[1] == 0.0

    gibberish = "random greeting hello world today is a nice day"
    extracted, conf, clues, assumed = parse_manufacturing_query(gibberish)
    assert conf == 0.0
    assert "product_name" not in extracted
    assert "facility_name" not in extracted
    assert "batch_id" not in extracted
