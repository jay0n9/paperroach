import unittest

from kb import taxonomy


class TaxonomyTests(unittest.TestCase):
    def test_hyphenated_metadata_tags_match_phrase_cues(self):
        text = "paper computer-vision deep-learning neural-network"

        self.assertTrue(taxonomy._cue_present(text, "computer vision"))
        self.assertTrue(taxonomy._cue_present(text, "deep learning"))
        self.assertTrue(taxonomy._cue_present(text, "neural network"))

    def test_canonical_subdomain_tags_beat_generic_ml_tags(self):
        self.assertEqual(
            taxonomy.classify_subdomain_any("paper computer-graphics neural-network"),
            ("Computer Science", "Computer Graphics"),
        )
        self.assertEqual(
            taxonomy.classify_subdomain_any("paper computer-vision neural-network"),
            ("Computer Science", "Computer Vision"),
        )

    def test_face_model_metadata_files_graphics_before_ml(self):
        text = "paper face-model registration expression-analysis blending deep-learning"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("Computer Science", "Computer Graphics"),
        )

    def test_morphable_model_metadata_is_not_generative_evaluation(self):
        text = "paper 3d-mm craniofacial texture morphable alignment evaluation applications"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("Computer Science", "Computer Graphics"),
        )

    def test_statistics_metadata_is_not_software_testing(self):
        text = "paper multiple-testing false-discovery-rate correlations meta-analyses"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("Statistics", "Statistical Inference"),
        )

    def test_plural_statistics_metadata_cues(self):
        text = "Equivalence Tests A Practical Primer for t Tests Correlations and Meta-Analyses"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("Statistics", "Statistical Inference"),
        )

    def test_rank_test_metadata_cues(self):
        text = "Estimates of Location Based on Rank Tests"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("Statistics", "Statistical Inference"),
        )

    def test_hci_wellbeing_metadata(self):
        text = "paper vr relaxation art-therapy anxiety participant-study"

        self.assertEqual(
            taxonomy.classify_subdomain_any(text),
            ("HCI", "Health & Wellbeing"),
        )


if __name__ == "__main__":
    unittest.main()
