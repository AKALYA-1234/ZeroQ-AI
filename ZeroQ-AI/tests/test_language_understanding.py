"""Unit tests for multilingual detection, glossing and symptom extraction (offline path)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.intelligence.language import detect_language, gloss_to_english
from app.intelligence.symptoms import extract_symptoms


def test_detects_plain_english():
    info = detect_language("The biscuit pack seal was open and the product tasted stale.")
    assert info.code == "en"
    assert info.is_code_mixed is False


def test_detects_tamil_script():
    info = detect_language("பிஸ்கட் பாக்கெட் சீல் சரியா இல்ல, உள்ளே பூச்சி இருந்தது")
    assert info.code == "ta"
    assert info.script == "Tamil"


def test_detects_hindi_script():
    info = detect_language("पैकेट में कीड़े मिले और बदबू आ रही है")
    assert info.code == "hi"


def test_detects_telugu_malayalam_kannada_scripts():
    assert detect_language("ప్యాకెట్ లో పురుగులు ఉన్నాయి").code == "te"
    assert detect_language("പാക്കറ്റിൽ പ്രാണി ഉണ്ടായിരുന്നു").code == "ml"
    assert detect_language("ಪ್ಯಾಕೆಟ್ ನಲ್ಲಿ ಕೀಟ ಇತ್ತು").code == "kn"


def test_detects_tanglish_code_mixing():
    info = detect_language("Machine romba heat aguthu, production output kammiya irukku.")
    assert info.code == "ta"
    assert info.is_code_mixed is True
    assert "Tanglish" in info.name


def test_detects_hinglish_code_mixing():
    info = detect_language("Packet mein keede the aur badbu aa rahi hai")
    assert info.code == "hi"
    assert info.is_code_mixed is True


def test_tanglish_with_locative_la_is_not_spanish():
    info = detect_language("Chips packet la plastic piece irundhuchu")
    assert info.code == "ta"


def test_spanish_still_detected():
    assert detect_language("La caja está rota y el producto tiene mal olor").code == "es"


def test_unknown_script_is_reported_not_guessed_as_english():
    info = detect_language("Упаковка была повреждена")
    assert info.code == "ru"


def test_gloss_translates_tanglish_domain_terms():
    gloss = gloss_to_english("Machine romba heat aguthu, production output kammiya irukku.", "ta")
    text = gloss.text.lower()
    assert "overheating" in text
    assert "reduced" in text or "low" in text
    assert gloss.coverage > 0


def test_gloss_keeps_english_words_in_mixed_text():
    gloss = gloss_to_english("Packet mein keede the", "hi")
    assert "packet" in gloss.text.lower()
    assert "insect" in gloss.text.lower()


def test_symptoms_from_tanglish_example():
    gloss = gloss_to_english("Machine romba heat aguthu, production output kammiya irukku.", "ta")
    symptoms = extract_symptoms(gloss.text)
    names = [s["symptom"] for s in symptoms]
    assert "Machine overheating" in names
    assert "Reduced production output" in names


def test_symptoms_from_english_packaging_issue():
    names = [s["symptom"] for s in extract_symptoms("The seal was open and the pack was leaking")]
    assert "Seal failure" in names
    assert "Leakage" in names
