import unittest
from availability import estimate, parse_providers, parse_release_dates, pick_match, check_film


class AvailabilityTests(unittest.TestCase):
    def test_estimate_from_cinema_date(self):
        e = estimate("2026-12-18", "2026-12-16")
        self.assertEqual(e["rent_buy"], ["2027-02-01", "2027-03-18"])
        self.assertEqual(e["streaming"], ["2027-03-18", "2027-06-16"])
        self.assertIn("Typical gap", e["basis"])
        self.assertEqual((e["basis_kind"], e["hint"]), ("typical", None))

    def test_estimate_prefers_known_digital_date(self):
        e = estimate("2026-07-17", "2026-07-06", {"date": "2026-11-17", "country": "US"})
        self.assertEqual(e["rent_buy"], ["2026-11-17", "2026-12-17"])
        self.assertIn("2026-11-17", e["basis"])
        self.assertEqual((e["basis_kind"], e["hint"]["country"]), ("digital", "US"))

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

    def test_pick_match_by_year_popularity_and_date(self):
        r = [{"id": 1, "release_date": "1999-01-01", "popularity": 90}, {"id": 2, "release_date": "2026-05-01", "popularity": 5},
             {"id": 3, "release_date": "2025-12-01", "popularity": 50}]
        self.assertEqual(pick_match(r, 2026)["id"], 3)
        self.assertIsNone(pick_match(r, 2040))
        # same-title older film is rejected by the date cross-check
        homonyms = [{"id": 10, "release_date": "2026-02-01", "popularity": 80}, {"id": 11, "release_date": "2026-10-05", "popularity": 3}]
        self.assertEqual(pick_match(homonyms, 2026, "2026-10-05")["id"], 11)
        self.assertEqual(pick_match(homonyms, 2026)["id"], 10)  # without a reference date popularity wins

    def test_title_must_match_not_just_date(self):
        r = [{"id": 1, "title": "The Wicker Children", "release_date": "2026-06-14", "popularity": 50},
             {"id": 2, "title": "Wicker", "release_date": "2026-06-14", "popularity": 1}]
        self.assertEqual(pick_match(r, 2026, "2026-01-24", ["Wicker"])["id"], 2)
        self.assertIsNone(pick_match(r[:1], 2026, "2026-01-24", ["Wicker"]))
        self.assertEqual(pick_match([{"id": 3, "title": "Czarna kula", "original_title": "La bola negra", "release_date": "2026-09-25"}], 2026, None, ["La Bola Negra!"])["id"], 3)

    def test_check_film_flow_with_fake_api(self):
        calls = []
        def get(path, **params):
            calls.append((path, params))
            if path == "/search/movie":
                return {"results": [{"id": 7, "title": "X", "release_date": "2026-03-20", "popularity": 1}]}
            if path.endswith("/watch/providers"):
                return {"results": {"PL": {"flatrate": [{"provider_name": "Netflix"}]}}}
            if path == "/movie/7":
                return {"title": "X", "release_date": "2026-03-20"}
            return {"results": []}
        r = check_film(get, ["X"], 2026, "2026-03-09")
        self.assertEqual((r["tmdb_id"], r["tmdb_title"], r["providers"]["flatrate"]), (7, "X", ["Netflix"]))
        n = len(calls)
        check_film(get, ["X"], 2026, "2026-03-09", cached=7)
        self.assertFalse(any(p == "/search/movie" for p, _ in calls[n:]))  # cached id validated, no search

    def test_wrong_cached_id_is_dropped_and_researched(self):
        def get(path, **params):
            if path == "/movie/99":
                return {"title": "Other Artificial", "release_date": "2024-02-17"}
            if path == "/search/movie":
                return {"results": [{"id": 5, "title": "Artificial", "release_date": "2026-10-05", "popularity": 2}]}
            return {"results": {}}
        r = check_film(get, ["Artificial"], 2026, "2026-10-05", cached=99)
        self.assertEqual(r["tmdb_id"], 5)

    def test_unmatched_reports_candidates_and_tries_alternate_titles(self):
        qs = []
        def get(path, **params):
            qs.append(params.get("query"))
            return {"results": [{"id": 1, "title": "Nope", "release_date": "1990-01-01", "popularity": 1}]}
        r = check_film(get, ["Possible Love", "Ganeunghan sarang", None], 2026, "2026-09-06")
        self.assertEqual(r["tmdb_id"], None)
        self.assertTrue(r["unmatched"] and r["candidates"])
        self.assertEqual(qs, ["Possible Love", "Ganeunghan sarang"])

    def test_override_is_trusted(self):
        r = check_film(lambda p, **k: {"title": "T", "release_date": "1990-01-01", "results": {}}, ["x"], 2026, "2026-09-06", override=42)
        self.assertEqual(r["tmdb_id"], 42)


if __name__ == "__main__":
    unittest.main()
