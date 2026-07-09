import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from kb import pipeline, rag
from kb.config import Config
from kb.models import PaperAnalysis, PaperClassification, PaperMetadata, doc_id_for


class FakeOllamaClient:
    last_prompt = ""

    def __init__(self, config):
        self.config = config

    def ping(self):
        return None

    def unload_embed(self):
        return None

    def unload_llm(self):
        return None

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    def embed_one(self, text):
        return self._vector(text)

    def generate_text(self, system, user):
        type(self).last_prompt = user
        if "incremental annotations" in user:
            return "Grounded answer: it uses incremental annotations."
        return "Grounded answer: evidence was provided."

    def _vector(self, text):
        text = str(text).lower()
        return [
            1.0 if "incremental" in text else 0.0,
            1.0 if "annotation" in text else 0.0,
            1.0 if "multimedia" in text else 0.0,
            1.0 if "hci" in text else 0.0,
        ]


class BuildSearchAskSmokeTests(unittest.TestCase):
    def test_stubbed_build_search_ask_flow_uses_real_store(self):
        with tempfile.TemporaryDirectory() as td:
            FakeOllamaClient.last_prompt = ""
            root = Path(td)
            source = root / "safe-place.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            config = Config(
                vault_path=root / "vault",
                kb_dir=".kb",
                embed_dim=4,
                chunk_size=500,
                chunk_overlap=50,
                create_concept_notes=False,
                rag_top_k=3,
            )
            markdown = (
                "# Abstract\n\n"
                "This paper introduces incremental annotations for safe-place "
                "multimedia moderation.\n\n"
                "## Method\n\n"
                "The method connects HCI evidence with multimedia retrieval."
            )

            patches = [
                patch.object(pipeline, "OllamaClient", FakeOllamaClient),
                patch.object(rag, "OllamaClient", FakeOllamaClient),
                patch.object(pipeline.ingest_mod, "ingest", return_value=markdown),
                patch.object(
                    pipeline,
                    "extract_metadata",
                    return_value=PaperMetadata(
                        title="Safe Place Multimedia",
                        year=2026,
                        summary="Incremental annotations for multimedia moderation.",
                        tags=["hci"],
                    ),
                ),
                patch.object(
                    pipeline,
                    "extract_analysis",
                    return_value=PaperAnalysis(
                        tl_dr="Incremental annotations improve moderation.",
                        approach="The method connects HCI evidence with retrieval.",
                        key_results="The prototype supports multimedia triage.",
                    ),
                ),
                patch.object(
                    pipeline,
                    "classify_paper",
                    return_value=PaperClassification(
                        primary_domain="HCI",
                        subdomain="Health & Wellbeing",
                    ),
                ),
                patch.object(
                    pipeline.zotero,
                    "enrich",
                    side_effect=lambda metadata, _path, _config: metadata,
                ),
            ]

            with ExitStack() as stack:
                for patcher in patches:
                    stack.enter_context(patcher)
                with redirect_stdout(StringIO()):
                    build_result = pipeline.build([source], config)
                search_rows = rag.search("incremental annotation method", config, k=3)
                answer = rag.ask(
                    "How does the incremental annotation method work?",
                    config,
                    k=2,
                )

            self.assertEqual(build_result["processed"], 1)
            self.assertEqual(build_result["succeeded"], [doc_id_for(source)])
            self.assertTrue(search_rows)
            self.assertEqual(search_rows[0]["title"], "Safe Place Multimedia")
            self.assertIn("incremental annotations", search_rows[0]["text"])
            self.assertIn("incremental annotations", FakeOllamaClient.last_prompt)
            self.assertIn("Grounded answer", answer["answer"])
            self.assertEqual(
                answer["sources"],
                [
                    {
                        "title": "Safe Place Multimedia",
                        "note_path": str(
                            config.references_path
                            / "HCI"
                            / "Health & Wellbeing"
                            / "Safe Place Multimedia (2026).md"
                        ),
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
