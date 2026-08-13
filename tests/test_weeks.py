from datetime import date

from bot.services.weeks import week_bounds, week_number_for_date


def test_kickoff_sunday_is_hors_semaine():
    wave_start = date(2026, 8, 2)  # dimanche
    assert week_number_for_date(wave_start, wave_start) == 0


def test_first_monday_starts_week_1():
    wave_start = date(2026, 8, 2)  # dimanche
    first_monday = date(2026, 8, 3)
    assert week_number_for_date(first_monday, wave_start) == 1


def test_end_of_week_1_still_week_1():
    wave_start = date(2026, 8, 2)
    sunday_end_week1 = date(2026, 8, 9)
    assert week_number_for_date(sunday_end_week1, wave_start) == 1


def test_week_2_starts_next_monday():
    wave_start = date(2026, 8, 2)
    monday_week2 = date(2026, 8, 10)
    assert week_number_for_date(monday_week2, wave_start) == 2


def test_wave_start_on_monday():
    wave_start = date(2026, 8, 3)  # lundi
    assert week_number_for_date(wave_start, wave_start) == 1


def test_week_bounds():
    wave_start = date(2026, 8, 2)
    start, end = week_bounds(1, wave_start)
    assert start == date(2026, 8, 3)
    assert end == date(2026, 8, 9)

    start2, end2 = week_bounds(2, wave_start)
    assert start2 == date(2026, 8, 10)
    assert end2 == date(2026, 8, 16)
