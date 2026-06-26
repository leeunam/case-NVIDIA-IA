from pathlib import Path
import tomllib
import unittest


class ToolingConfigTests(unittest.TestCase):
    def test_project_declares_pytest_ruff_and_mypy_baseline_commands(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

        with pyproject_path.open("rb") as pyproject_file:
            config = tomllib.load(pyproject_file)

        self.assertEqual(config["tool"]["pytest"]["ini_options"]["pythonpath"], ["src"])
        self.assertIn("ruff", config["tool"])
        self.assertIn("mypy", config["tool"])
        self.assertEqual(config["tool"]["ruff"]["target-version"], "py311")
        self.assertEqual(config["tool"]["mypy"]["python_version"], "3.11")
        self.assertEqual(config["tool"]["mypy"]["files"], ["src"])

    def test_readme_documents_local_validation_commands(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"

        readme = readme_path.read_text(encoding="utf-8")

        self.assertIn("python -m pytest -q", readme)
        self.assertIn("python -m ruff check .", readme)
        self.assertIn("python -m mypy src", readme)
        self.assertIn("strictness", readme)

    def test_readme_documents_optional_llm_adapter_validation_separately(self) -> None:
        readme_path = Path(__file__).resolve().parents[1] / "README.md"
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

        readme = readme_path.read_text(encoding="utf-8")
        with pyproject_path.open("rb") as pyproject_file:
            config = tomllib.load(pyproject_file)

        self.assertIn("Validação Opcional LLM Adapters", readme)
        self.assertIn("NVIDIA_STARTUP_INTEL_LLM_PROVIDER", readme)
        self.assertIn("NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV", readme)
        self.assertIn("NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE", readme)
        self.assertIn("tests/integration/test_llm_adapter_integration_smoke.py", readme)
        self.assertIn("LiteLLM e LangChain não fazem parte da suíte local padrão", readme)
        self.assertIn(
            "llm_adapter_integration: optional real LLM/framework adapter smoke tests, "
            "skipped unless explicitly enabled",
            config["tool"]["pytest"]["ini_options"]["markers"],
        )

    def test_downstream_docs_mark_walking_skeleton_capabilities_as_implemented(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        readme = (project_root / "README.md").read_text(encoding="utf-8")
        roadmap = (
            project_root / "context" / "roadmap-nvidia-knowledge-recommendation-briefing.md"
        ).read_text(encoding="utf-8")

        for implemented_capability in (
            "`Human Review Briefing` versionado",
            "workflow downstream local com branches auditáveis",
            "recomendações de programa/Inception",
            "persistência downstream JSON/SQL",
        ):
            self.assertIn(implemented_capability, readme)

        missing_core_section = readme.split("## Follow-ups Recomendados", maxsplit=1)[0]
        for implemented_capability in (
            "Human Review Briefing",
            "workflow completo `ready_for_briefing` / `human_review_requested`",
            "recomendações de programa/Inception",
            "persistência downstream de knowledge, recommendations e briefings",
        ):
            self.assertNotIn(f"- {implemented_capability};", missing_core_section)

        for checklist_item in (
            "- [x] Human review gera briefing detalhado com contexto suficiente para decisão humana.",
            "- [x] Workflow possui branch `ready_for_briefing`.",
            "- [x] Persistência downstream permite reprocessamento.",
            "- [x] Nova suíte local de validação continua sem rede, credenciais ou serviços externos obrigatórios.",
        ):
            self.assertIn(checklist_item, roadmap)


if __name__ == "__main__":
    unittest.main()
