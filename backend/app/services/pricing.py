"""Age-bracket pricing weights.

- Baby (age <= baby_max_age): weight 0 (free, no bed, no budget impact).
- Kid (baby_max_age < age <= kid_max_age): weight 0.5 (half price across all expenses).
- Teen+adult (age > kid_max_age): weight 1.0.
"""

from datetime import date
from enum import Enum


class AgeBracket(str, Enum):
    BABY = "baby"
    KID = "kid"
    TEEN_OR_ADULT = "teen_or_adult"


def age_at(birthdate: date, on: date) -> int:
    years = on.year - birthdate.year
    if (on.month, on.day) < (birthdate.month, birthdate.day):
        years -= 1
    return years


def classify(birthdate: date | None, on: date, *, baby_max: int, kid_max: int) -> AgeBracket:
    if birthdate is None:
        return AgeBracket.TEEN_OR_ADULT
    age = age_at(birthdate, on)
    if age <= baby_max:
        return AgeBracket.BABY
    if age <= kid_max:
        return AgeBracket.KID
    return AgeBracket.TEEN_OR_ADULT


_WEIGHTS: dict[AgeBracket, float] = {
    AgeBracket.BABY: 0.0,
    AgeBracket.KID: 0.5,
    AgeBracket.TEEN_OR_ADULT: 1.0,
}


def weight_for(bracket: AgeBracket) -> float:
    return _WEIGHTS[bracket]
