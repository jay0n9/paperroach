import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kb import figures, obsidian, pipeline, rag
from kb.config import Config
from kb.models import Chunk, Document, FigureAsset, PaperMetadata
from kb.store import KBStore


class FakeBBox:
    def __init__(self, width=60, height=50):
        self.l = 10
        self.t = 20
        self.r = self.l + width
        self.b = self.t + height
        self.width = width
        self.height = height


class FakeImage:
    def save(self, path, format="PNG"):
        Path(path).write_bytes(f"fake {format} image".encode("ascii"))


class FakePicture:
    def __init__(self, image, caption="Figure 1: Prototype interface", width=60, height=50):
        self._image = image
        self._caption = caption
        self.prov = [SimpleNamespace(page_no=1, bbox=FakeBBox(width, height))]

    def get_image(self, _document):
        return self._image

    def caption_text(self, _document):
        return self._caption


class FakeTable:
    def __init__(self, image, caption="Table 1: Results", width=60, height=50):
        self._image = image
        self._caption = caption
        self.prov = [SimpleNamespace(page_no=1, bbox=FakeBBox(width, height))]

    def get_image(self, _document):
        return self._image

    def caption_text(self, _document):
        return self._caption


class FakeDocument:
    def __init__(self, elements):
        self.elements = elements
        self.pages = {1: SimpleNamespace(size=SimpleNamespace(width=100, height=100))}

    def iterate_items(self):
        return [(element, 0) for element in self.elements]


class FakeOptions:
    def __init__(self):
        self.accelerator_options = SimpleNamespace(device="auto")
        self.images_scale = 1.0
        self.generate_picture_images = False
        self.generate_table_images = False


class FakePdfFormatOption:
    def __init__(self, pipeline_options):
        self.pipeline_options = pipeline_options


class FakeInputFormat:
    PDF = object()


class FakeDocumentConverter:
    document = None
    options = None

    def __init__(self, format_options):
        type(self).options = format_options

    def convert(self, _path):
        return SimpleNamespace(document=type(self).document)


class FakeVisionClient:
    def __init__(self):
        self.calls = []

    def generate_vision_json(self, system, user, image_path):
        self.calls.append((system, user, image_path))
        return {
            "figure_type": "interface_screenshot",
            "observable_facts": ["A two-panel interface shows a user workflow."],
            "interpretation": "The figure supports a user-centered prototype contribution.",
            "research_evidence": ["The prototype exposes a personalization flow."],
            "hci_signals": ["interactive prototype", "user workflow"],
            "visible_text": ["Personalize"],
            "uncertainties": ["Small labels are not fully legible."],
            "importance": "critical",
        }


class FakeBackfillClient:
    def __init__(self, config):
        self.config = config

    def ping(self):
        return None

    def unload_llm(self):
        return None

    def unload_embed(self):
        return None

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FigurePipelineTests(unittest.TestCase):
    def _config(self, root: Path, **overrides) -> Config:
        vault = root / "vault"
        vault.mkdir(parents=True)
        values = {
            "vault_path": vault,
            "figure_mode": "extract",
            "figure_min_area_ratio": 0.02,
        }
        values.update(overrides)
        config = Config(**values)
        config.ensure_dirs()
        return config

    def _docling_patch(self, document):
        FakeDocumentConverter.document = document
        return patch.object(
            figures,
            "_docling_components",
            return_value=(
                FakeDocumentConverter,
                FakePdfFormatOption,
                FakeInputFormat,
                FakeOptions,
                FakePicture,
                FakeTable,
            ),
        )

    def test_extract_and_finalize_figure_assets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root)
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            image = FakeImage()

            with self._docling_patch(FakeDocument([FakePicture(image)])):
                extracted = figures.extract_figures(source, "abc123abc123", config)

            self.assertEqual(len(extracted), 1)
            figure = extracted[0]
            self.assertEqual(figure.caption, "Figure 1: Prototype interface")
            self.assertEqual(figure.page, 1)
            self.assertTrue(figure.staging_path.exists())

            figures.finalize_assets(extracted, "abc123abc123", config)

            self.assertTrue(figure.asset_path.exists())
            self.assertFalse(figure.staging_path.exists())
            self.assertEqual(
                figure.asset_relpath,
                f"Assets/PaperRoach/abc123abc123/{figure.asset_path.name}",
            )

    def test_extract_skips_small_elements_and_includes_tables_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = FakeImage()
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")

            config = self._config(root, figure_min_area_ratio=0.2)
            with self._docling_patch(FakeDocument([FakePicture(image, width=10, height=10)])):
                self.assertEqual(figures.extract_figures(source, "small", config), [])

            config = self._config(root / "with-tables", figure_include_tables=True)
            source = root / "with-tables" / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            with self._docling_patch(FakeDocument([FakeTable(image, caption="Table 1: Results")])):
                extracted = figures.extract_figures(source, "tables", config)

            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].source_kind, "table")

    def test_vision_description_is_grounded_and_searchable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, figure_mode="describe")
            stage = config.kb_path / "figure-staging" / "doc"
            stage.mkdir(parents=True)
            image_path = stage / "figure.png"
            image_path.write_bytes(b"test figure bytes")
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            figure = FigureAsset(
                figure_id="doc:figure:test",
                index=1,
                page=3,
                caption="Figure 2: A personalization interface.",
                image_sha256=digest,
                staging_path=image_path,
            )

            client = FakeVisionClient()
            described, errors = figures.describe_figures([figure], client, config)

            self.assertEqual((described, errors), (1, []))
            self.assertEqual(figure.figure_type, "interface_screenshot")
            self.assertEqual(figure.importance, "critical")
            self.assertIn("interactive prototype", figure.searchable_text())
            self.assertIn("HCI signals", figures.figure_evidence([figure]))
            self.assertIn("source_caption", client.calls[0][1])

    def test_note_render_and_store_keep_figure_evidence_linked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, embed_dim=2)
            asset = config.figure_assets_path / "doc" / "figure-p002-abc.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"figure")
            figure = FigureAsset(
                figure_id="doc:figure:abc",
                index=1,
                page=2,
                caption="Figure 1: Interaction prototype.",
                image_sha256="abc",
                asset_path=asset,
                asset_relpath="Assets/PaperRoach/doc/figure-p002-abc.png",
                figure_type="interface_screenshot",
                observed_facts=["A two-panel interaction flow is visible."],
                interpretation="The image documents the prototype flow.",
                hci_signals=["interactive prototype"],
                importance="critical",
            )
            doc = Document(
                doc_id="aaaaaaaaaaaa",
                source_path=root / "paper.pdf",
                kind="pdf",
                markdown="# Paper",
                metadata=PaperMetadata(title="Visual Paper", year=2026),
                figures=[figure],
                figures_synced=True,
            )
            doc.note_path = config.references_path / "Visual Paper (2026).md"

            rendered = obsidian.render_note(doc, [], config)
            self.assertIn("## Key Figures", rendered)
            self.assertIn("![[Assets/PaperRoach/doc/figure-p002-abc.png|720]]", rendered)
            self.assertIn("^figure-abc", rendered)

            store = KBStore(config)
            store.replace_figures(doc, [[1.0, 0.0]])
            hits = store.search_figures([1.0, 0.0], 1)
            self.assertEqual(hits[0]["figure_id"], "doc:figure:abc")
            self.assertIn("Interaction prototype", hits[0]["text"])

            merged = rag._search_rows(store, [1.0, 0.0], 1)
            self.assertEqual(merged[0]["header"], "Figure 1 - interface_screenshot (p. 2)")

    def test_pymupdf_fallback_extracts_embedded_image_and_caption(self):
        try:
            import pymupdf
        except ModuleNotFoundError:  # pragma: no cover - project dependency
            self.skipTest("PyMuPDF is not installed")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, figure_backend="pymupdf")
            png = root / "figure.png"
            png.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFklEQVR4nGP8//8/A27AhEeO"
                    "YeRKAwCl4wMRx3ocVQAAAABJRU5ErkJggg=="
                )
            )
            source = root / "paper.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page(width=400, height=500)
            page.insert_image(pymupdf.Rect(40, 80, 360, 300), filename=str(png))
            page.insert_text((40, 330), "Figure 1: Prototype interaction flow.", fontsize=12)
            pdf.save(source)
            pdf.close()

            extracted = figures.extract_figures(source, "fallbackdoc", config)

            self.assertEqual(len(extracted), 1)
            self.assertIn("Figure 1", extracted[0].caption)
            self.assertTrue(extracted[0].staging_path.exists())

    def test_pymupdf_fallback_renders_compound_image_tiles(self):
        try:
            import pymupdf
        except ModuleNotFoundError:  # pragma: no cover - project dependency
            self.skipTest("PyMuPDF is not installed")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, figure_backend="pymupdf")
            png = root / "tile.png"
            png.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFklEQVR4nGP8//8/A27AhEeO"
                    "YeRKAwCl4wMRx3ocVQAAAABJRU5ErkJggg=="
                )
            )
            source = root / "compound.pdf"
            pdf = pymupdf.open()
            page = pdf.new_page(width=400, height=500)
            for rect in (
                pymupdf.Rect(40, 80, 100, 140),
                pymupdf.Rect(120, 80, 180, 140),
                pymupdf.Rect(40, 160, 100, 220),
                pymupdf.Rect(120, 160, 180, 220),
            ):
                page.insert_image(rect, filename=str(png))
            page.insert_text((40, 260), "Figure 2: Four-part reconstruction comparison.", fontsize=12)
            pdf.save(source)
            pdf.close()

            extracted = figures.extract_figures(source, "compounddoc", config)

            self.assertEqual(len(extracted), 1)
            self.assertEqual(extracted[0].page, 1)
            self.assertIn("Figure 2", extracted[0].caption)
            staged = list((config.kb_path / "figure-staging" / "compounddoc").glob("*.png"))
            self.assertEqual(staged, [extracted[0].staging_path])

    def test_pymupdf_limit_does_not_leave_extra_staging_assets(self):
        try:
            import pymupdf
        except ModuleNotFoundError:  # pragma: no cover - project dependency
            self.skipTest("PyMuPDF is not installed")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, figure_backend="pymupdf", figure_max_per_paper=1)
            png = root / "figure.png"
            png.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAFklEQVR4nGP8//8/A27AhEeO"
                    "YeRKAwCl4wMRx3ocVQAAAABJRU5ErkJggg=="
                )
            )
            source = root / "limit.pdf"
            pdf = pymupdf.open()
            first = pdf.new_page(width=400, height=500)
            first.insert_image(pymupdf.Rect(40, 80, 360, 300), filename=str(png))
            second = pdf.new_page(width=400, height=500)
            second.insert_image(pymupdf.Rect(40, 80, 340, 280), filename=str(png))
            pdf.save(source)
            pdf.close()

            extracted = figures.extract_figures(source, "limitdoc", config)

            self.assertEqual(len(extracted), 1)
            staged = list((config.kb_path / "figure-staging" / "limitdoc").glob("*.png"))
            self.assertEqual(staged, [extracted[0].staging_path])

    def test_docling_failure_uses_pymupdf_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root)
            source = root / "paper.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            expected = [FigureAsset(figure_id="fallback", index=1)]
            with patch.object(
                figures,
                "_extract_docling_figures",
                side_effect=figures.FigureError("model artifacts unavailable"),
            ):
                with patch.object(
                    figures, "_extract_pymupdf_figures", return_value=expected
                ):
                    self.assertIs(figures.extract_figures(source, "doc", config), expected)

    def test_existing_note_backfill_preserves_user_content_and_indexes_figures(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = self._config(root, embed_dim=2)
            source = root / "historical.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            note = config.references_path / "Historical Paper (2024).md"
            note.write_text(
                "---\n"
                "kb-generated: true\n"
                f"kb-source: {source}\n"
                "---\n"
                "# Historical Paper\n\n"
                "## TL;DR\n\nExisting summary.\n\n"
                "## My Notes\n\nKeep this personal observation.\n\n"
                "---\n# References\n",
                encoding="utf-8",
            )
            doc = Document(
                doc_id="historical01",
                source_path=source,
                kind="pdf",
                markdown="# Historical Paper",
                metadata=PaperMetadata(title="Historical Paper", year=2024),
                chunks=[Chunk(chunk_index=0, header="", text="Existing summary")],
            )
            doc.note_path = note
            store = KBStore(config)
            store.upsert_document(doc, [[1.0, 0.0]], [1.0, 0.0])

            def extract(_source, doc_id, cfg):
                stage = cfg.kb_path / "figure-staging" / doc_id
                stage.mkdir(parents=True)
                image = stage / "figure.png"
                image.write_bytes(b"historical figure")
                return [
                    FigureAsset(
                        figure_id=f"{doc_id}:figure:historical",
                        index=1,
                        page=4,
                        caption="Figure 1: Historical prototype.",
                        image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                        staging_path=image,
                    )
                ]

            with patch.object(pipeline, "OllamaClient", FakeBackfillClient):
                with patch.object(pipeline.figures_mod, "extract_figures", side_effect=extract):
                    preview = pipeline.enrich_figures(config, apply=False)
                    result = pipeline.enrich_figures(config, apply=True)

            self.assertEqual(preview["eligible"], 1)
            self.assertEqual(result["updated"], 1)
            rendered = note.read_text(encoding="utf-8")
            self.assertIn("## Key Figures", rendered)
            self.assertIn("Keep this personal observation.", rendered)
            self.assertEqual(KBStore(config).figures.count_rows(), 1)


if __name__ == "__main__":
    unittest.main()
