from datetime import date

from app.services.pricing import age_at, classify, weight_for, AgeBracket


def test_age_at_anniversary():
    born = date(2000, 6, 15)
    assert age_at(born, date(2024, 6, 14)) == 23
    assert age_at(born, date(2024, 6, 15)) == 24
    assert age_at(born, date(2024, 6, 16)) == 24


def test_classify_brackets_with_default_rules():
    today = date(2026, 7, 10)
    baby = date(2025, 1, 1)
    kid = date(2018, 1, 1)
    teen = date(2010, 1, 1)
    adult = date(1990, 1, 1)
    assert classify(baby, today, baby_max=2, kid_max=13) == AgeBracket.BABY
    assert classify(kid, today, baby_max=2, kid_max=13) == AgeBracket.KID
    assert classify(teen, today, baby_max=2, kid_max=13) == AgeBracket.TEEN_OR_ADULT
    assert classify(adult, today, baby_max=2, kid_max=13) == AgeBracket.TEEN_OR_ADULT


def test_weight_for_brackets():
    assert weight_for(AgeBracket.BABY) == 0.0
    assert weight_for(AgeBracket.KID) == 0.5
    assert weight_for(AgeBracket.TEEN_OR_ADULT) == 1.0


def test_classify_no_birthdate_treated_as_adult():
    assert classify(None, date(2026, 7, 10), baby_max=2, kid_max=13) == AgeBracket.TEEN_OR_ADULT
