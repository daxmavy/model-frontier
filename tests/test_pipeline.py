import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "pipeline"))

from aa_parse import extract                                    # noqa: E402
import build                                                    # noqa: E402

# A miniature version of the flight-data payload the leaderboard page embeds:
# escaped quotes, one model split across two sections, and a "$undefined" hole.
PAGE = r'''
<script>self.__next_f.push([1,"a:[\"$\",\"$L1\",null,{\"models\":[
{\"slug\":\"acme-1-high\",\"shortName\":\"Acme 1 (high)\",\"intelligenceIndex\":42.5,
 \"effort\":{\"slug\":\"high\",\"label\":\"high\",\"level\":40},
 \"release\":{\"slug\":\"acme-1\",\"name\":\"Acme 1\"},
 \"modelCreatorName\":\"Acme\",\"isReasoning\":true,\"isOpenWeights\":false,
 \"deprecated\":false,\"releaseDate\":\"2026-05-01\",\"contextWindowTokens\":200000,
 \"price1mInputTokens\":2.0,\"price1mOutputTokens\":10.0,
 \"intelligenceIndexCostPerTask\":{\"cost\":{\"total\":4.0}},\"gpqa\":0.8},
{\"slug\":\"budget-9\",\"shortName\":\"Budget 9\",\"intelligenceIndex\":20.0,
 \"release\":{\"slug\":\"budget-9\",\"name\":\"Budget 9\"},\"modelCreatorName\":\"Thrift\",
 \"isReasoning\":false,\"isOpenWeights\":true,\"deprecated\":true,
 \"releaseDate\":\"2025-01-01\",\"contextWindowTokens\":8000,
 \"price1mInputTokens\":0.1,\"price1mOutputTokens\":0.4,
 \"intelligenceIndexCostPerTask\":\"$undefined\",\"gpqa\":0.4}]}]"])</script>
<script>self.__next_f.push([1,"b:[\"$\",\"$L2\",null,{\"models\":[
{\"slug\":\"acme-1-high\",\"medianOutputTokensPerSecond\":88.0}]}]"])</script>
'''


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.rows, self.keys = extract(PAGE)

    def test_finds_every_model_once(self):
        self.assertEqual(sorted(self.rows), ["acme-1-high", "budget-9"])

    def test_merges_fields_across_page_sections(self):
        # speed arrives in a later section than the rest of the row
        self.assertEqual(self.rows["acme-1-high"]["medianOutputTokensPerSecond"], 88.0)
        self.assertEqual(self.rows["acme-1-high"]["intelligenceIndex"], 42.5)

    def test_undefined_becomes_absent(self):
        self.assertIsNone(self.rows["budget-9"].get("intelligenceIndexCostPerTask"))

    def test_reasoning_effort_survives(self):
        self.assertEqual(self.rows["acme-1-high"]["effort"]["label"], "high")


class TestHelpers(unittest.TestCase):
    def test_norm_folds_punctuation_and_case(self):
        self.assertEqual(build.norm("Claude Fable 5.1"), "claude-fable-5-1")
        self.assertEqual(build.norm("GPT-6_Astra"), "gpt-6-astra")

    def test_norm_drops_trailing_qualifiers(self):
        self.assertEqual(build.norm("qwen3-max-preview"), "qwen3-max")

    def test_undate_strips_date_stamps(self):
        self.assertEqual(build.undate("deepseek-v4-pro-0813"), "deepseek-v4-pro")
        self.assertEqual(build.undate("gemini-3-8-flash-20260902"), "gemini-3-8-flash")

    def test_undate_leaves_version_numbers_alone(self):
        self.assertEqual(build.undate("glm-4-5v"), "glm-4-5v")

    def test_cost_total_reads_the_nested_value(self):
        self.assertEqual(build.cost_total({"intelligenceIndexCostPerTask": {"cost": {"total": 3.5}}}), 3.5)
        self.assertIsNone(build.cost_total({"intelligenceIndexCostPerTask": None}))
        self.assertIsNone(build.cost_total({}))

    def test_openrouter_index_ignores_variant_ids(self):
        idx = build.openrouter_index([
            {"id": "acme/acme-1", "name": "Acme: Acme 1", "pricing": {}},
            {"id": "acme/acme-1:batch", "name": "Acme: Acme 1 (batch)", "pricing": {}},
        ])
        self.assertEqual(idx["acme-1"]["id"], "acme/acme-1")

    def test_or_price_scales_to_per_million(self):
        m = {"pricing": {"prompt": "0.000002", "completion": "0"}}
        self.assertAlmostEqual(build.or_price(m, "prompt"), 2.0)
        self.assertIsNone(build.or_price(m, "completion"))   # zero means "not priced"


class TestBuild(unittest.TestCase):
    def test_offline_build_shapes_records(self):
        import unittest.mock as mock
        with mock.patch.object(build, "fetch", side_effect=RuntimeError("offline")):
            data = build.build_from_html(PAGE, min_models=1)
        by_slug = {m["slug"]: m for m in data["models"]}
        acme = by_slug["acme-1-high"]
        self.assertEqual(acme["effort"], "high")
        self.assertEqual(acme["release"], "Acme 1")
        self.assertEqual(acme["cost"]["aaii_cost_total"], 4.0)
        self.assertAlmostEqual(acme["cost"]["blended_price"], 0.75 * 2.0 + 0.25 * 10.0)
        self.assertAlmostEqual(acme["cost"]["cost_per_index_point"], 4.0 / 42.5, places=6)
        # each reasoning level links to its own page, not the family page
        self.assertTrue(acme["aaUrl"].endswith("/acme-1-high"))
        self.assertTrue(acme["aaReleaseUrl"].endswith("/acme-1"))

    def test_build_refuses_a_page_it_could_not_parse(self):
        with self.assertRaises(SystemExit):
            build.build_from_html("<html>nothing here</html>", min_models=1)


if __name__ == "__main__":
    unittest.main()
