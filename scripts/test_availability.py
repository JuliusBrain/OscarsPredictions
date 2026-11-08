import unittest
from availability import estimate, parse_providers, parse_release_dates, pick_match, check_film


class AvailabilityTests(unittest.TestCase):
    def test_estimate_from_cinema_date(self):
        e = estimate("2026-12-18", "2026-12-16")
        self.assertEqual(e["rent_buy"], ["2027-02-01", "2027-03-18"])
        self.assertEqual(e["streaming"], ["2027-03-18", "2027-06-16"])
        self.assertIn("Typical gap", e["basis"])

    def test_estimate_prefers_known_digital_date(self):
        e = estimate("2026-07-17", "2026-07-06", {"date": "2026-11-17", "country": "US"})
        self.assertEqual(e["rent_buy"], ["2026-11-17", "2026-12-17"])
        self.assertIn("2026-11-17", e["basis"])

    def test_estimate_without_dates(self):
        self.assertIsNone(estimate(None, None))
        self.assertIsNone(estimate(None, "2026-03-09"))  # world premiere alone is not enough
        self.assertIsNotNone(estimate(None, "2026-03-09", {"date": "2026-06-01", "country": "US"}))

    def test_parse_providers_poland_only(self):
        p = parse_providers({"results": {"US": {"flatrate": [{"provider_name": "Max"}]},
                                         "PL": {"link": "x", "flatrate": [{"provider_name": "Netflix"}, {"provider_name": "Netflix"}],
                                                "rent": [{"provider_name": "Apple TV"}]}}})
        self.assertEqual(p["providers"]["flatrate"], ["Netflix"])
        self.assertEqual(p["providers"]["rent"], ["Apple TV"])
        self.assertEqual(p["providers"]["buy"], [])
        self.assertEqual(parse_providers({"results": {}})["providers"]["flatrate"], [])

    def test_release_dates(self):
        payload = {"results": [{"iso_3166_1": "US", "release_dates": [{"type": 3, "release_date": "2026-07-17T00:00:00.000Z"}, {"type": 4, "release_date": "2026-11-17T00:00:00.000Z"}]},
                               {"iso_3166_1": "PL", "release_dates": [{"type": 4, "release_date": "2026-12-01T00:00:00.000Z"}]}]}
        hint, pl = parse_release_dates(payload)
        self.assertEqual(hint, {"date": "2026-11-17", "country": "US"})
        self.assertEqual(pl, "2026-12-01")

    def test_pick_match_by_year_and_popularity(self):
        r = [{"id": 1, "release_date": "1999-01-01", "popularity": 90}, {"id": 2, "release_date": "2026-05-01", "popularity": 5},
             {"id": 3, "release_date": "2025-12-01", "popularity": 50}]
        self.assertEqual(pick_match(r, 2026), 3)
        self.assertIsNone(pick_match(r, 2040))

    def test_check_film_flow_with_fake_api(self):
        calls = []
        def get(path, **params):
            calls.append(path)
            if path == "/search/movie":
                return {"results": [{"id": 7, "release_date": "2026-03-20", "popularity": 1}]}
            if path.endswith("/watch/providers"):
                return {"results": {"PL": {"flatrate": [{"provider_name": "Netflix"}]}}}
            return {"results": []}
        r = check_film(get, "X", 2026)
        self.assertEqual((r["tmdb_id"], r["providers"]["flatrate"]), (7, ["Netflix"]))
        r2 = check_film(get, "X", 2026, tmdb_id=7)
        self.assertNotIn("/search/movie", calls[-3:])
        self.assertEqual(check_film(lambda p, **k: {"results": []}, "Nope", 2026), {"tmdb_id": None, "unmatched": True})


if __name__ == "__main__":
    unittest.main()
