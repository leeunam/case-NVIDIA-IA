from pathlib import Path
import tomllib
import unittest


class ToolingConfigTests(unittest.TestCase):
    def test_project_declares_ruff_and_mypy_baseline_commands(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

        with pyproject_path.open("rb") as pyproject_file:
            config = tomllib.load(pyproject_file)

        self.assertIn("ruff", config["tool"])
        self.assertIn("mypy", config["tool"])
        self.assertEqual(config["tool"]["ruff"]["target-version"], "py311")
        self.assertEqual(config["tool"]["mypy"]["python_version"], "3.11")
        self.assertEqual(config["tool"]["mypy"]["files"], ["src"])

    def test_readme_documents_static_validation_commands(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"

        readme = readme_path.read_text(encoding="utf-8")

        self.assertIn("PYTHONPATH=src python3 -m unittest discover -s tests", readme)
        self.assertIn("python -m ruff check .", readme)
        self.assertIn("python -m mypy src", readme)
        self.assertIn("strictness", readme)

    def test_readme_documents_optional_llm_adapter_validation_separately(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"

        readme = readme_path.read_text(encoding="utf-8")

        self.assertIn("Validação Opcional LLM Adapters", readme)
        self.assertIn("NVIDIA_STARTUP_INTEL_LLM_PROVIDER", readme)
        self.assertIn("NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV", readme)
        self.assertIn("LiteLLM e LangChain não fazem parte da suíte local padrão", readme)


if __name__ == "__main__":
    unittest.main()
