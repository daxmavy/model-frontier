import json
import pathlib
import sys
import tempfile
import unittest
import unittest.mock as mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "pipeline"))

import epoch                                                    # noqa: E402
import weights                                                  # noqa: E402

CSV = """model,task,best_score,mean_score,Best score (across scorers),Parameters
gpt-5-2025-08-07_high,FrontierMath-Tiers-1-3-v2-Private,0.34,0.31,0.34,
gpt-5-2025-08-07_high,GPQA diamond,0.82,0.80,0.82,
gpt-5-2025-08-07_high,GPQA diamond,0.79,0.78,0.79,
claude-opus-4-6_max,OTIS Mock AIME 2024-2025,91,90,91,
zai-org/GLM-4.6,GPQA diamond,0.71,0.70,0.71,357000000000
kimi-k2.6,Some Unlisted Task,0.99,0.99,0.99,
qwen3.7-max_none,MATH level 5,0.66,0.65,0.66,
"""


class TestModelIds(unittest.TestCase):
    def test_effort_suffix_is_split_off(self):
        self.assertEqual(epoch.split_model("gpt-5-2025-08-07_high"), ("gpt-5", "high"))
        self.assertEqual(epoch.split_model("claude-opus-4-6_max"), ("claude-opus-4-6", "max"))

    def test_none_effort_means_no_reasoning(self):
        self.assertEqual(epoch.split_model("qwen3.7-max_none"), ("qwen3-7-max", None))

    def test_a_model_without_a_suffix_keeps_its_name(self):
        self.assertEqual(epoch.split_model("kimi-k2.6"), ("kimi-k2-6", None))

    def test_an_underscore_that_is_not_an_effort_is_kept(self):
        self.assertEqual(epoch.split_model("seed_oss_36b"), ("seed-oss-36b", None))

    def test_the_hosting_org_is_stripped(self):
        self.assertEqual(epoch.split_model("zai-org/GLM-4.6"), ("glm-4-6", None))


class TestEpochParse(unittest.TestCase):
    def setUp(self):
        self.scores, self.params = epoch.parse(CSV)

    def test_scores_land_under_the_right_model_and_effort(self):
        self.assertAlmostEqual(self.scores[("gpt-5", "high")]["epoch_frontiermath"], 0.34)

    def test_percentage_scores_are_rescaled_to_fractions(self):
        self.assertAlmostEqual(self.scores[("claude-opus-4-6", "max")]["epoch_aime"], 0.91)

    def test_the_best_of_repeated_runs_wins(self):
        self.assertAlmostEqual(self.scores[("gpt-5", "high")]["epoch_gpqa"], 0.82)

    def test_unlisted_tasks_are_ignored(self):
        self.assertNotIn(("kimi-k2-6", None), self.scores)

    def test_parameter_counts_are_collected(self):
        self.assertEqual(self.params["glm-4-6"], 357e9)

    def test_every_metric_it_declares_has_a_label(self):
        for key, label, kind, help_ in epoch.metrics():
            self.assertTrue(key.startswith("epoch_"))
            self.assertEqual(kind, "frac")
            self.assertTrue(label and help_)


class TestVram(unittest.TestCase):
    def test_bf16_needs_about_two_bytes_a_parameter_plus_headroom(self):
        self.assertAlmostEqual(weights.vram_gb(70e9), 70 * 2 * 1.2, places=6)

    def test_quantising_reduces_the_requirement(self):
        self.assertLess(weights.vram_gb(70e9, "int4"), weights.vram_gb(70e9, "bf16"))

    def test_a_70b_model_does_not_fit_one_80gb_card_at_bf16(self):
        self.assertGreater(weights.vram_gb(70e9), 80)


class TestResolve(unittest.TestCase):
    def test_cached_ids_are_not_refetched(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d) / "params.json"
            cache.write_text(json.dumps({"a/known": 8e9}))
            with mock.patch.object(weights, "fetch_params", return_value=1e9) as f:
                out = weights.resolve(["a/known", "b/new"], cache)
            f.assert_called_once_with("b/new")
            self.assertEqual(out["a/known"], 8e9)
            self.assertEqual(out["b/new"], 1e9)

    def test_a_repository_with_no_count_is_remembered_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d) / "params.json"
            with mock.patch.object(weights, "fetch_params", return_value=None):
                weights.resolve(["c/silent"], cache)
            with mock.patch.object(weights, "fetch_params") as f:
                out = weights.resolve(["c/silent"], cache)
            f.assert_not_called()
            self.assertNotIn("c/silent", out)


if __name__ == "__main__":
    unittest.main()
