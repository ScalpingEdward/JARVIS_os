from datetime import date
from types import SimpleNamespace as NS

from app.instagram_content.pillars import derive, group_pillar, pick_next, pillar_of


def test_pillar_comes_from_what_the_analysis_saw_and_brano_wins():
    assert derive("gym-mirror-selfie", ["gym", "weights", "mirror-selfie"]) == "Gym"
    assert derive("hotel-breakfast-plate", ["food", "coffee"]) == "Essen"
    assert derive("trading-desk-setup", ["laptop", "monitors"]) == "Trading"
    assert derive("palm-lined-promenade", ["palm trees", "beach"]) == "Travel"
    assert derive("shopping-mall", ["candid", "money"]) is None
    assert pillar_of(NS(theme="beach", tags=["beach"], pillar="Portrait")) == "Portrait"


def test_a_post_is_what_most_of_its_pictures_are():
    gym, beach = NS(theme="gym", tags=["gym"], pillar=None), NS(theme="beach", tags=["beach"], pillar=None)
    assert group_pillar([beach, gym, gym]) == "Gym"
    assert group_pillar([beach, gym]) == "Travel"          # tie: the hook decides


def test_next_post_skips_a_repeated_pillar_only_within_the_same_day():
    d1, d2 = date(2021, 1, 5), date(2021, 1, 6)
    drafts = [NS(id="a", content_day=d1, p="Gym"), NS(id="b", content_day=d1, p="Travel"), NS(id="c", content_day=d2, p="Essen")]
    by = lambda d: d.p  # noqa: E731
    assert pick_next(drafts, by, "Gym").id == "b"           # same day has another pillar
    assert pick_next(drafts, by, "Travel").id == "a"
    assert pick_next(drafts[:1] + drafts[2:], by, "Gym").id == "a"   # the next DAY never jumps ahead
    assert pick_next(drafts, by, None).id == "a"
