import unittest

from kb import llm
from kb.models import PaperAnalysis, PaperMetadata
from kb.pipeline import _fallback_paper_classification


class LLMClassificationTests(unittest.TestCase):
    def test_metadata_subdomain_beats_model_subdomain_and_body_terms(self):
        metadata = PaperMetadata(
            title="ASafePlace",
            summary="VR relaxation support for anxiety and wellbeing.",
            methods="participant study with qualitative feedback in an art therapy task",
            key_contributions=["user-led personalization for therapy"],
            tags=["paper", "hci"],
            venue="CHI",
            venue_type="conferencePaper",
            source_url="https://example.org/asafeplace",
        )
        metadata_text = llm.classification_metadata_text(metadata)

        cls = llm._coerce_classification(
            {"primary_domain": "HCI", "subdomain": "VR/AR Interaction"},
            ["Computer Science", "Generative AI", "HCI", "Statistics"],
            fallback_text=(
                "The body mentions diffusion, mesh generation, neural rendering, "
                "multiple testing, and statistical inference."
            ),
            metadata_text=metadata_text,
        )

        self.assertEqual(cls.primary_domain, "HCI")
        self.assertEqual(cls.subdomain, "Health & Wellbeing")

    def test_metadata_classification_text_includes_structured_fields(self):
        metadata = PaperMetadata(
            title="Tagged Paper",
            summary="computer graphics reconstruction",
            methods="registration and expression analysis",
            key_contributions=["3d morphable face model"],
            tags=["neural-network"],
            source_url="https://doi.org/10.0000/example",
            venue="ACM Transactions on Graphics",
            venue_type="journalArticle",
            doi="10.0000/example",
            publisher="ACM",
        )

        text = llm.classification_metadata_text(metadata)

        self.assertIn("computer graphics reconstruction", text)
        self.assertIn("3d morphable face model", text)
        self.assertIn("https://doi.org/10.0000/example", text)

    def test_pipeline_fallback_keeps_metadata_priority_when_classifier_fails(self):
        metadata = PaperMetadata(
            title="ASafePlace",
            summary="VR relaxation support for anxiety and wellbeing.",
            methods="participant study with qualitative feedback in an art therapy task",
            tags=["paper", "hci"],
            venue="CHI",
            venue_type="conferencePaper",
        )
        analysis = PaperAnalysis(
            approach=(
                "The approach section mentions diffusion, mesh generation, "
                "neural rendering, multiple testing, and statistical inference."
            )
        )

        cls = _fallback_paper_classification(
            metadata,
            analysis,
            ["Computer Science", "Generative AI", "HCI", "Statistics"],
        )

        self.assertEqual(cls.primary_domain, "HCI")
        self.assertEqual(cls.subdomain, "Health & Wellbeing")


if __name__ == "__main__":
    unittest.main()
