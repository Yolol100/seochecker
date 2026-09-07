import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "verify_page_expectations.py"
spec = importlib.util.spec_from_file_location("verify_page_expectations", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class VerifyPageExpectationsTests(unittest.TestCase):
    def observation(self):
        parsed = mod.parse_html(
            """<html><head><title>Brandwacht Amsterdam | Voorbeeld</title>
            <meta name='description' content='Brandwacht Amsterdam nodig voor tijdelijk toezicht.'>
            <link rel='canonical' href='/brandwacht-amsterdam/'></head>
            <body><h1>Brandwacht Amsterdam</h1>
            <a href='/brandwacht/'>Brandwacht</a><a href='/brandwacht-inhuren/'>Inhuren</a></body></html>""",
            "https://example.nl/brandwacht-amsterdam/",
            {},
        )
        parsed.update({"status": 200, "final_url": "https://example.nl/brandwacht-amsterdam/"})
        return parsed

    def test_passes_matching_contract(self):
        expected = {
            "status": 200,
            "indexable": True,
            "title_contains": "Brandwacht Amsterdam",
            "meta_contains": "brandwacht Amsterdam",
            "h1_contains": "Brandwacht Amsterdam",
            "canonical_equals": "/brandwacht-amsterdam/",
            "required_internal_links": ["/brandwacht/", "/brandwacht-inhuren/"],
        }
        self.assertEqual(mod.verify_observation(self.observation(), expected, "https://example.nl/brandwacht-amsterdam/"), [])

    def test_fails_missing_meta_phrase_and_link(self):
        expected = {"meta_contains": "exact ontbrekend", "required_internal_links": ["/offerte/"]}
        errors = mod.verify_observation(self.observation(), expected, "https://example.nl/brandwacht-amsterdam/")
        self.assertTrue(any("meta_description" in e for e in errors))
        self.assertTrue(any("required internal link missing" in e for e in errors))

    def test_noindex_from_x_robots(self):
        parsed = mod.parse_html("<html><head><title>X</title></head><body><h1>X</h1></body></html>", "https://example.nl/", {"x-robots-tag": "noindex"})
        self.assertFalse(parsed["indexable"])

    def test_does_not_invent_www_or_trailing_slash_equivalence(self):
        obs = self.observation()
        expected = {"required_internal_links": ["https://www.example.nl/brandwacht"]}
        self.assertTrue(mod.verify_observation(obs, expected, "https://example.nl/brandwacht-amsterdam/"))

    def test_exact_url_expectations_preserve_resource_identity(self):
        wanted = "https://example.nl/page/?id=1"
        for actual in ["http://example.nl/page/?id=1", "https://www.example.nl/page/?id=1", "https://example.nl:8443/page/?id=1", "https://example.nl/page?id=1", "https://example.nl/page/?id=2", "https://example.nl//page/?id=1"]:
            for field, key in [("canonical_equals", "canonical"), ("final_url_equals", "final_url")]:
                with self.subTest(actual=actual, field=field):
                    self.assertTrue(mod.verify_observation({key: actual}, {field: wanted}, wanted))
        self.assertEqual(mod.normalized_url_key(wanted), mod.normalized_url_key("https://EXAMPLE.nl:443/page/?id=1#section"))

    def test_empty_or_invalid_expectations_cannot_pass(self):
        for payload in [{"pages": []}, {"pages": None}, {"pages": [None]}, {"url": "https://example.nl", "expected": {}}, {"url": "https://example.nl", "expected": {"typo": True}}, {"url": "https://example.nl", "expected": {"title_contains": ""}}, {"url": "https://example.nl", "expected": {"indexable": "true"}}, {"url": "https://example.nl", "expected": {"required_internal_links": []}}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                mod.load_pages(payload)
        self.assertEqual(len(mod.load_pages({"url": "https://example.nl", "expected": {"status": 200}})), 1)


if __name__ == "__main__":
    unittest.main()
