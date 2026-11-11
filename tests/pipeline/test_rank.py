"""pipeline.rank: headline templates, the quality factor, each of the six signals,
the score, ordering properties and the reasons shown to the reader."""

import unittest
from datetime import datetime, timedelta, timezone

from pipeline import rank
from pipeline.core import config

NOW = datetime(2026, 11, 11, 14, 30, tzinfo=timezone.utc)
WEIGHTS = config.load("site")["ranking"]["weights"]
HALF_LIFE = config.load("site")["ranking"]["recencyHalfLifeHours"]


def hours_ago(hours):
    return NOW - timedelta(hours=hours)


def facts(outlets=1, tier=2, age=1.0, via="direct", spread=0.5, **extra):
    """Ranking facts for a story with ``outlets`` outlets of one tier, the newest item ``age`` hours old.

    Outlets arrive ``spread`` hours apart, the first one earliest.
    """
    start = age + spread * (outlets - 1)
    base = {
        "outlets": [{"tier": tier, "via": via} for _ in range(outlets)],
        "bestTier": tier,
        "updatedAt": hours_ago(age),
        "firstAt": hours_ago(start),
        "arrivals": [hours_ago(start - spread * index) for index in range(outlets)],
        "points": 0, "comments": 0, "placements": [], "topSlots": [], "firstParty": False,
        "sourceCount": outlets,
    }
    base.update(extra)
    return base


def scored(story_facts, title="A plain headline about something that happened", summary="It happened."):
    values = rank.signals(story_facts, NOW, HALF_LIFE)
    return rank.score(values, WEIGHTS, rank.quality(title, summary)[0])


class TemplateTests(unittest.TestCase):

    def test_headline_templates(self):
        cases = {
            "Black Friday and Cyber Monday 2026: a first look at Amazon's best deals": "promo",
            "Today's Android app deals and freebies: Undead Slayer, more": "promo",
            "How to watch Camp Flog Gnaw 2026 festival on Prime Video": "promo",
            "Early Black Friday deals now live on Apple accessories": "promo",
            "India News Live Updates, 11 November 2026: Amul hikes milk prices": "live",
            "US envoys to meet Putin and Zelenskyy separately - Europe Live": "live",
            "Nasdaq futures jump as CoreWeave earnings beat: Live updates": "live",
            "Live: Counting begins in Bihar": "live",
            "Stocks to Watch for November 12: Tata Power, Bajaj Finance": "recurring",
            "Horoscope today: Aries, Taurus, Gemini": "recurring",
            "Money Market Operations as on November 10, 2026": "recurring",
            "Daily briefing: Where academic freedom is declining": "recurring",
            "Science Quiz: Unconventional science prizes": "recurring",
            "Evening Newswrap: Terrorists attack jawans in Kulgam & more": "recurring",
            "Kerala lottery Dhanalekshmi DL-77 result today 11/11/2026": "recurring",
            "NHL Scores, News & Stats": "recurring",
            "Treasury Bills: Full Auction Result": "recurring",
            "Broker's Call: Vardhman Textiles (Buy)": "recurring",
            "FirstFT: Anthropic bankers prepare to increase IPO valuation": "recurring",
            "Sensex, Nifty close higher as banks rally": "wrap",
            "Closing bell: Sensex ends 500 points higher": "wrap",
            "Stock markets end higher; Sensex and Nifty jump nearly 1%": "wrap",
            "Wall Street set for higher open as CoreWeave results temper AI concerns": "wrap",
            "Stock Market Today: Tech Stocks Poised to Jump": "wrap",
        }
        for title, expected in cases.items():
            with self.subTest(title):
                self.assertEqual(rank.template(title), expected)

    def test_ordinary_news_has_no_template(self):
        for title in (
                "Tesla recalls 200,000 Cybertrucks over faulty accelerator pedal",
                "Qatar's Loss of Polish LNG Deal Is a Serious Blow to Expansion Plans",
                "India and EU close in on trade deal after decade of talks",
                "Apple Support Community forums will permanently close on November 20",
                "Fish Audio Releases Live 3, a Full-Duplex Voice Model",
                "Jharkhand backs CBI probe into death of activist who killed herself on live stream",
                "Nvidia shares tumble over investigation into Huang's affair",
                "Oil falls below $90 as Trump pulls back from threat to strike Iran",
                "OpenAI to discontinue old ChatGPT voice modes; users to shift to live voice mode",
                "Russia offers India a discount on crude",
                "", None):
            with self.subTest(title):
                self.assertIsNone(rank.template(title))

    def test_market_wrap_is_recognised_on_a_story(self):
        self.assertTrue(rank.is_market_wrap({"title": "Sensex, Nifty end higher for fifth day"}))
        self.assertFalse(rank.is_market_wrap({"title": "Reliance to buy Disney's India business"}))


class QualityTests(unittest.TestCase):

    def test_news_is_not_marked_down(self):
        self.assertEqual(rank.quality("Tesla recalls 200,000 Cybertrucks over faulty pedal", "Details."), (1.0, None))

    def test_market_wrap_is_news(self):
        self.assertEqual(rank.quality("Sensex, Nifty close higher as banks rally", "")[0], 1.0)

    def test_junk_is_marked_down_with_a_reason(self):
        for title, reason in (("Best Black Friday deals on laptops", "promo"),
                              ("Bihar election results: Live updates", "live"),
                              ("Stocks to watch: Reliance, TCS", "recurring")):
            factor, why = rank.quality(title, "A summary.")
            self.assertEqual(why, reason)
            self.assertLess(factor, 0.7)

    def test_short_headline_without_summary_is_thin(self):
        self.assertEqual(rank.quality("Starlink Mini 2", "")[1], "thin")
        self.assertEqual(rank.quality("Starlink Mini 2", "The new dish is smaller.")[1], None)
        self.assertEqual(rank.quality("Starlink unveils the Mini 2 dish for travellers", "")[1], None)

    def test_headline_in_another_script_is_marked_down(self):
        self.assertEqual(rank.quality("दिल्ली में प्रदूषण का स्तर बढ़ा", "")[1], "foreign")
        self.assertEqual(rank.quality("Nestlé and Škoda open café in Zürich", "Text.")[1], None)

    def test_missing_title_does_not_crash(self):
        self.assertEqual(rank.quality(None, None)[1], "thin")


class BreadthTests(unittest.TestCase):

    def outlets(self, *tiers, **extra):
        return [dict({"tier": tier, "via": "direct"}, **extra) for tier in tiers]

    def test_one_outlet_alone_is_zero_whatever_its_tier(self):
        self.assertEqual(rank.breadth(self.outlets(1)), 0.0)
        self.assertEqual(rank.breadth([]), 0.0)

    def test_three_tier_one_outlets_beat_six_tier_three(self):
        self.assertGreater(rank.breadth(self.outlets(1, 1, 1)), rank.breadth(self.outlets(3, 3, 3, 3, 3, 3)))

    def test_more_outlets_is_more_breadth_but_sublinear(self):
        values = [rank.breadth(self.outlets(*[2] * count)) for count in range(1, 9)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(set(values)), len(values))
        self.assertGreater(values[2] - values[1], values[7] - values[6])

    def test_saturates_at_one(self):
        self.assertEqual(rank.breadth(self.outlets(*[1] * 30)), 1.0)

    def test_outlets_known_through_an_aggregator_count_less(self):
        direct = rank.breadth(self.outlets(2, 2, 2))
        relayed = rank.breadth(self.outlets(2, 2, 2, via="relayed"))
        listed = rank.breadth(self.outlets(2, 2, 2, via="listed"))
        self.assertGreater(direct, relayed)
        self.assertGreater(relayed, listed)
        self.assertGreater(listed, 0.0)


class OtherSignalTests(unittest.TestCase):

    def test_recency_halves_every_half_life(self):
        self.assertAlmostEqual(rank.recency(NOW, NOW, 18), 1.0)
        self.assertAlmostEqual(rank.recency(hours_ago(18), NOW, 18), 0.5)
        self.assertAlmostEqual(rank.recency(hours_ago(36), NOW, 18), 0.25)

    def test_recency_of_a_future_timestamp_is_one(self):
        self.assertEqual(rank.recency(NOW + timedelta(hours=5), NOW, 18), 1.0)

    def test_velocity_counts_outlets_in_the_first_six_hours(self):
        start = hours_ago(30)
        slow = [start, start + timedelta(hours=7), start + timedelta(hours=20)]
        fast = [start, start + timedelta(hours=1), start + timedelta(hours=5)]
        self.assertEqual(rank.velocity(slow), 0.0)
        self.assertGreater(rank.velocity(fast), 0.0)
        self.assertGreater(rank.velocity(fast + [start + timedelta(hours=2)]), rank.velocity(fast))
        self.assertEqual(rank.velocity([]), 0.0)
        self.assertEqual(rank.velocity([start]), 0.0)

    def test_velocity_does_not_depend_on_the_storys_age(self):
        def burst(age):
            return [hours_ago(age), hours_ago(age - 1), hours_ago(age - 2)]
        self.assertEqual(rank.velocity(burst(40)), rank.velocity(burst(3)))

    def test_attention_is_log_scaled_and_capped(self):
        self.assertEqual(rank.attention(None, None), 0.0)
        self.assertLess(rank.attention(10, 0), rank.attention(100, 0))
        self.assertLess(rank.attention(100, 0), rank.attention(100, 300))
        self.assertGreater(rank.attention(100, 0) - rank.attention(10, 0),
                           rank.attention(1000, 0) - rank.attention(900, 0))
        self.assertEqual(rank.attention(50000, 9000), 1.0)

    def test_editorial_two_tier_one_front_pages_agreeing_is_full_marks(self):
        self.assertEqual(rank.editorial([(1, 0), (1, 0)]), 1.0)
        self.assertEqual(rank.editorial([(1, 0)]), 0.5)
        self.assertEqual(rank.editorial([]), 0.0)

    def test_editorial_decays_with_position_and_tier(self):
        self.assertGreater(rank.editorial([(1, 0)]), rank.editorial([(1, 5)]))
        self.assertGreater(rank.editorial([(1, 5)]), rank.editorial([(1, 19)]))
        self.assertGreater(rank.editorial([(1, 0)]), rank.editorial([(2, 0)]))
        self.assertGreater(rank.editorial([(2, 0)]), rank.editorial([(3, 0)]))

    def test_editorial_averages_the_best_two_only(self):
        self.assertEqual(rank.editorial([(1, 0), (1, 0), (1, 19), (3, 12)]), 1.0)


class SignalsAndScoreTests(unittest.TestCase):

    def test_every_signal_is_between_zero_and_one(self):
        for story_facts in (facts(), facts(outlets=40, tier=1, age=0), facts(age=500),
                            facts(points=10 ** 6, comments=10 ** 6, placements=[(1, 0)] * 5, firstParty=True)):
            values = rank.signals(story_facts, NOW, HALF_LIFE)
            self.assertEqual(set(values), {"breadth", "tier", "recency", "velocity", "attention", "editorial"})
            for name, value in values.items():
                self.assertTrue(0.0 <= value <= 1.0, (name, value))

    def test_score_is_between_zero_and_a_hundred(self):
        best = rank.signals(facts(outlets=40, tier=1, age=0, spread=0.01, points=10 ** 6,
                                  placements=[(1, 0), (1, 0)]), NOW, HALF_LIFE)
        self.assertEqual(rank.score(best, WEIGHTS), 100.0)
        self.assertEqual(rank.score({name: 0.0 for name in best}, WEIGHTS), 0.0)

    def test_weights_need_not_sum_to_one(self):
        values = rank.signals(facts(outlets=3), NOW, HALF_LIFE)
        doubled = {name: 2 * weight for name, weight in WEIGHTS.items()}
        self.assertEqual(rank.score(values, WEIGHTS), rank.score(values, doubled))

    def test_unusable_weights_are_an_error(self):
        with self.assertRaises(ValueError):
            rank.score({"breadth": 1.0}, {})
        with self.assertRaises(ValueError):
            rank.score({"breadth": 1.0}, {"breadth": 0})

    def test_quality_factor_scales_the_score(self):
        values = rank.signals(facts(outlets=4), NOW, HALF_LIFE)
        self.assertAlmostEqual(rank.score(values, WEIGHTS, 0.5), rank.score(values, WEIGHTS) / 2, delta=0.06)

    def test_site_config_weights_cover_exactly_the_six_signals(self):
        self.assertEqual(set(WEIGHTS), {"breadth", "tier", "recency", "velocity", "attention", "editorial"})


class OrderingTests(unittest.TestCase):
    """What must outrank what, with the shipped weights."""

    def test_wider_coverage_wins(self):
        self.assertGreater(scored(facts(outlets=6)), scored(facts(outlets=2)))
        self.assertGreater(scored(facts(outlets=2)), scored(facts(outlets=1)))

    def test_better_outlets_win(self):
        self.assertGreater(scored(facts(outlets=3, tier=1)), scored(facts(outlets=3, tier=2)))
        self.assertGreater(scored(facts(outlets=3, tier=2)), scored(facts(outlets=3, tier=3)))

    def test_three_tier_one_outlets_beat_six_tier_three(self):
        self.assertGreater(scored(facts(outlets=3, tier=1)), scored(facts(outlets=6, tier=3)))

    def test_newer_wins(self):
        self.assertGreater(scored(facts(outlets=3, age=1)), scored(facts(outlets=3, age=20)))

    def test_a_big_story_from_yesterday_still_beats_a_fresh_single_source_item(self):
        self.assertGreater(scored(facts(outlets=9, tier=1, age=20)), scored(facts(outlets=1, tier=2, age=0.5)))

    def test_first_party_announcement_outranks_other_single_source_items(self):
        official = scored(facts(outlets=1, tier=1, firstParty=True))
        self.assertGreater(official, scored(facts(outlets=1, tier=1)))
        self.assertGreater(official, scored(facts(outlets=1, tier=2)))
        self.assertGreater(official, scored(facts(outlets=2, tier=3)))

    def test_first_party_floor_does_not_bury_well_covered_stories(self):
        self.assertGreater(scored(facts(outlets=4, tier=2)), scored(facts(outlets=1, tier=1, firstParty=True)))

    def test_first_party_floor_lifts_breadth_and_editorial_only(self):
        plain = rank.signals(facts(tier=1), NOW, HALF_LIFE)
        official = rank.signals(facts(tier=1, firstParty=True), NOW, HALF_LIFE)
        self.assertEqual((plain["breadth"], plain["editorial"]), (0.0, 0.0))
        self.assertEqual((official["breadth"], official["editorial"]),
                         (rank.FIRST_PARTY_BREADTH, rank.FIRST_PARTY_EDITORIAL))
        self.assertGreater(rank.FIRST_PARTY_BREADTH, 0.0)
        self.assertGreater(rank.FIRST_PARTY_EDITORIAL, 0.0)
        for name in ("tier", "recency", "velocity", "attention"):
            self.assertEqual(plain[name], official[name])

    def test_first_party_floor_never_lowers_a_signal(self):
        covered = facts(outlets=8, tier=1, placements=[(1, 0), (1, 1)])
        plain = rank.signals(covered, NOW, HALF_LIFE)
        official = rank.signals(dict(covered, firstParty=True), NOW, HALF_LIFE)
        self.assertEqual(plain, official)

    def test_front_page_placement_helps(self):
        self.assertGreater(scored(facts(outlets=3, placements=[(1, 0), (1, 2)])), scored(facts(outlets=3)))

    def test_hacker_news_attention_helps(self):
        self.assertGreater(scored(facts(points=900, comments=400)), scored(facts()))

    def test_a_story_that_broke_fast_beats_one_that_trickled(self):
        self.assertGreater(scored(facts(outlets=5, spread=0.5, age=1)), scored(facts(outlets=5, spread=4, age=1)))

    def test_junk_is_penalised(self):
        news = scored(facts(outlets=3))
        self.assertGreater(news, scored(facts(outlets=3), title="Best Black Friday deals on headphones"))
        self.assertGreater(news, scored(facts(outlets=3), title="Budget session: Live updates"))
        self.assertGreater(news, scored(facts(outlets=3), title="How to watch the Starship launch"))
        self.assertGreater(scored(facts()), scored(facts(), title="Red Flags", summary=""))

    def test_by_score_orders_deterministically(self):
        stories = [
            {"id": "sb", "score": 50.0, "updatedAt": "2026-11-11T10:00:00Z"},
            {"id": "sa", "score": 50.0, "updatedAt": "2026-11-11T10:00:00Z"},
            {"id": "sc", "score": 50.0, "updatedAt": "2026-11-11T12:00:00Z"},
            {"id": "sd", "score": 70.0, "updatedAt": "2026-11-10T01:00:00Z"},
        ]
        self.assertEqual([story["id"] for story in rank.by_score(stories)], ["sd", "sc", "sa", "sb"])
        self.assertEqual(rank.by_score(list(reversed(stories))), rank.by_score(stories))


class WhyTests(unittest.TestCase):

    def reasons(self, story_facts):
        return rank.why(story_facts, rank.signals(story_facts, NOW, HALF_LIFE), NOW)

    def test_single_source_story_with_nothing_special_has_no_reasons(self):
        self.assertEqual(self.reasons(facts(age=20)), [])

    def test_outlet_count(self):
        self.assertIn("9 outlets", self.reasons(facts(outlets=9, tier=1)))

    def test_front_page_slots_are_named(self):
        story = facts(outlets=4, tier=1, placements=[(1, 0), (1, 1)], topSlots=["BBC News", "New York Times", "DW"])
        self.assertIn("top of BBC News and New York Times", self.reasons(story))
        self.assertIn("top of BBC News", self.reasons(facts(outlets=2, placements=[(1, 2)], topSlots=["BBC News"])))

    def test_first_party(self):
        self.assertEqual(self.reasons(facts(tier=1, firstParty=True, age=20)), ["first-party source"])

    def test_hacker_news_points_need_to_be_worth_mentioning(self):
        self.assertIn("412 points on Hacker News", self.reasons(facts(points=412, comments=200)))
        self.assertEqual(self.reasons(facts(points=12, age=20)), [])

    def test_rising_only_while_young(self):
        fast = dict(outlets=6, tier=1, spread=0.3)
        self.assertIn("rising", self.reasons(facts(age=1, **fast)))
        self.assertNotIn("rising", self.reasons(facts(age=30, **fast)))

    def test_thread_day(self):
        self.assertIn("day 3", self.reasons(facts(outlets=3, threadDay=3)))
        self.assertNotIn("day 1", self.reasons(facts(outlets=3, threadDay=1)))

    def test_at_most_three_reasons_strongest_first(self):
        story = facts(outlets=9, tier=1, age=1, spread=0.2, points=800, comments=300, firstParty=True,
                      placements=[(1, 0), (1, 0)], topSlots=["BBC News", "DW"], threadDay=4)
        reasons = self.reasons(story)
        self.assertEqual(len(reasons), 3)
        self.assertEqual(reasons[0], "9 outlets")
        self.assertEqual(len(set(reasons)), 3)


if __name__ == "__main__":
    unittest.main()
