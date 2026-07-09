import unittest
from pathlib import Path

from kb import llm
from kb.models import PaperAnalysis, PaperMetadata
from kb.pipeline import _fallback_paper_classification


class PromptCaptureClient:
    def __init__(self, obj):
        self.obj = obj
        self.system = ""
        self.user = ""

    def generate_json(self, system, user):
        self.system = system
        self.user = user
        return self.obj


class LLMClassificationTests(unittest.TestCase):
    def test_metadata_extraction_preserves_explicit_domain_fields(self):
        metadata = llm._coerce(
            {
                "title": "Frontmatter Paper",
                "primary_domain": "HCI",
                "subdomain": "Health & Wellbeing",
                "tags": ["paper"],
            },
            "# Frontmatter Paper",
            Path("paper.md"),
        )

        self.assertEqual(metadata.primary_domain, "HCI")
        self.assertEqual(metadata.subdomain, "Health & Wellbeing")

    def test_classification_prompt_includes_explicit_metadata_domain_fields(self):
        client = PromptCaptureClient(
            {"primary_domain": "Generative AI", "subdomain": "3D Generation"}
        )
        metadata = PaperMetadata(
            title="Explicit Metadata",
            primary_domain="HCI",
            subdomain="Health & Wellbeing",
        )

        cls = llm.classify_paper(
            client,
            "The body mentions mesh diffusion and benchmark results.",
            metadata,
            PaperAnalysis(),
            config=type("ConfigStub", (), {"analysis_input_chars": 10000})(),
            candidate_domains=[
                "Computer Science",
                "Generative AI",
                "HCI",
                "Statistics",
            ],
        )

        self.assertIn("Explicit metadata domain: HCI", client.user)
        self.assertIn("Explicit metadata subdomain: Health & Wellbeing", client.user)
        self.assertEqual(cls.primary_domain, "HCI")
        self.assertEqual(cls.subdomain, "Health & Wellbeing")

    def test_explicit_metadata_subdomain_beats_model_and_metadata_cues(self):
        metadata = PaperMetadata(
            title="A Mixed Metadata Paper",
            tags=["hci-study", "participant-study"],
            venue="CHI",
            venue_type="conferencePaper",
            primary_domain="Computer Science",
            subdomain="Computer Graphics",
        )
        metadata_text = llm.classification_metadata_text(metadata)

        cls = llm._coerce_classification(
            {"primary_domain": "HCI", "subdomain": "Health & Wellbeing"},
            ["Computer Science", "Generative AI", "HCI", "Statistics"],
            fallback_text="The body discusses interviews and qualitative feedback.",
            metadata_text=metadata_text,
            metadata_primary=metadata.primary_domain,
            metadata_subdomain=metadata.subdomain,
        )

        self.assertEqual(cls.primary_domain, "Computer Science")
        self.assertEqual(cls.subdomain, "Computer Graphics")

    def test_explicit_metadata_subdomain_can_supply_parent_domain(self):
        metadata = PaperMetadata(
            title="Explicit Subdomain",
            tags=["hci-study", "participant-study"],
            subdomain="Computer Graphics",
        )

        self.assertEqual(
            llm.metadata_classification(
                metadata,
                ["Computer Science", "Generative AI", "HCI", "Statistics"],
            ),
            ("Computer Science", "Computer Graphics"),
        )

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

    def test_metadata_subdomain_overrides_model_primary_domain(self):
        metadata = PaperMetadata(
            title="Face Model Registration",
            summary="computer graphics reconstruction with 3d morphable face models",
            methods="registration and expression analysis",
            key_contributions=["face model alignment for animation"],
            tags=["paper", "computer-graphics", "neural-network"],
            venue="ACM Transactions on Graphics",
            venue_type="journalArticle",
        )
        metadata_text = llm.classification_metadata_text(metadata)

        cls = llm._coerce_classification(
            {"primary_domain": "HCI", "subdomain": "Health & Wellbeing"},
            ["Computer Science", "Generative AI", "HCI", "Statistics"],
            fallback_text=(
                "The body mentions users, interviews, participant feedback, "
                "therapy, diffusion models, and evaluation."
            ),
            metadata_text=metadata_text,
        )

        self.assertEqual(cls.primary_domain, "Computer Science")
        self.assertEqual(cls.subdomain, "Computer Graphics")

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

    def test_pipeline_fallback_prefers_explicit_metadata_subdomain(self):
        metadata = PaperMetadata(
            title="Conflicting Metadata",
            tags=["hci-study", "participant-study"],
            primary_domain="Computer Science",
            subdomain="Computer Graphics",
        )
        analysis = PaperAnalysis(
            approach="The body focuses on interviews, therapy, and qualitative feedback."
        )

        cls = _fallback_paper_classification(
            metadata,
            analysis,
            ["Computer Science", "Generative AI", "HCI", "Statistics"],
        )

        self.assertEqual(cls.primary_domain, "Computer Science")
        self.assertEqual(cls.subdomain, "Computer Graphics")


if __name__ == "__main__":
    unittest.main()
