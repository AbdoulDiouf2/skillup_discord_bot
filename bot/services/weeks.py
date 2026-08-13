from datetime import date, timedelta


def week_number_for_date(d: date, wave_start: date) -> int:
    """Numéro de semaine SkillUp (RG-14) : S1 démarre le lundi qui suit
    (ou coïncide avec) le lancement de la vague. Le jour de lancement
    lui-même, s'il tombe un dimanche, est hors-semaine."""
    first_monday = wave_start + timedelta(days=(7 - wave_start.weekday()) % 7)
    if wave_start.weekday() == 0:
        first_monday = wave_start
    if d < first_monday:
        return 0  # jour de kickoff, hors-semaine
    return ((d - first_monday).days // 7) + 1


def week_bounds(week_number: int, wave_start: date) -> tuple[date, date]:
    """Bornes (lundi, dimanche) de la semaine SkillUp donnée."""
    first_monday = wave_start + timedelta(days=(7 - wave_start.weekday()) % 7)
    if wave_start.weekday() == 0:
        first_monday = wave_start
    start = first_monday + timedelta(weeks=week_number - 1)
    end = start + timedelta(days=6)
    return start, end
