import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kb.config import Config
from kb.ollama_client import OllamaClient


class OllamaModelDiscoveryTests(unittest.TestCase):
    def test_installed_models_reads_ollama_tags(self):
        with tempfile.TemporaryDirectory() as td:
            config = Config(vault_path=Path(td))
            with patch("kb.ollama_client.ollama.Client"):
                client = OllamaClient(config)
            response = io.BytesIO(
                b'{"models":[{"name":"qwen3:8b"},{"model":"bge-m3"},{}]}'
            )

            with patch(
                "kb.ollama_client.urllib.request.urlopen",
                return_value=response,
            ) as urlopen:
                models = client.installed_models()

            self.assertEqual(models, {"qwen3:8b", "bge-m3"})
            urlopen.assert_called_once_with(
                "http://localhost:11434/api/tags",
                timeout=10,
            )


if __name__ == "__main__":
    unittest.main()
