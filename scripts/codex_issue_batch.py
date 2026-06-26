#!/usr/bin/env python3
"""Run one fresh Codex session per GitHub issue.

This script is intentionally conservative. It starts a new non-interactive
Codex session for each issue, expects the agent to commit its own work on an
isolated branch, reruns local validation, and opens a PR only when objective
completion markers and validation pass.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from textwrap import dedent


DEFAULT_REPO = "leeunam/case-NVIDIA-IA"
DEFAULT_BASE = "main"
DEFAULT_LABEL = "ready-for-agent"
DEFAULT_VALIDATION = "PYTHONPATH=src python3 -m unittest discover -s tests"
RUNS_DIR = Path("runs/codex-issue-batch")


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    url: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def main() -> int:
    args = parse_args()
    gh = resolve_gh(args.gh)
    codex = resolve_codex(args.codex)
    run_root = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")

    issues = selected_issues(args, gh)
    if args.max_issues is not None:
        issues = issues[: args.max_issues]

    if not issues:
        print("No matching issues found.")
        return 0

    print("Planned issue order:")
    for issue in issues:
        print(f"- #{issue.number}: {issue.title}")

    if not args.yes:
        print("\nDry run only. Re-run with --yes to execute Codex sessions.")
        return 0

    ensure_clean_worktree()
    run_root.mkdir(parents=True, exist_ok=True)

    for issue in issues:
        try:
            process_issue(issue=issue, args=args, gh=gh, codex=codex, run_root=run_root)
        except Exception as exc:  # noqa: BLE001 - batch runner reports and optionally continues.
            print(f"\nIssue #{issue.number} failed: {exc}", file=sys.stderr)
            if not args.continue_on_failure:
                return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo in OWNER/REPO format.")
    parser.add_argument("--base", default=DEFAULT_BASE, help="Base branch for issue branches and PRs.")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="GitHub issue label to select.")
    parser.add_argument("--issues", nargs="*", type=int, help="Specific issue numbers to process.")
    parser.add_argument("--all", action="store_true", help="Process all open labelled issues.")
    parser.add_argument("--include-prd", action="store_true", help="Include PRD/meta issues.")
    parser.add_argument("--max-issues", type=int, help="Limit how many issues are processed.")
    parser.add_argument("--yes", action="store_true", help="Actually run Codex. Without this, prints plan only.")
    parser.add_argument("--no-pr", action="store_true", help="Do not push or create PRs.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Continue to next issue after failure.")
    parser.add_argument("--skip-sync", action="store_true", help="Do not fetch/pull the base branch before work.")
    parser.add_argument("--gh", default="", help="Path to gh. Defaults to .tools/gh/bin/gh or gh.")
    parser.add_argument("--codex", default="codex", help="Codex command path.")
    parser.add_argument("--model", default="", help="Optional Codex model.")
    parser.add_argument("--sandbox", default="workspace-write", help="Codex sandbox mode.")
    parser.add_argument("--approval", default="never", help="Codex approval policy.")
    parser.add_argument(
        "--validation",
        action="append",
        default=None,
        help="Validation command. Can be repeated. Defaults to unittest discovery.",
    )
    parser.add_argument(
        "--extra-instruction",
        action="append",
        default=(),
        help="Extra instruction appended to every Codex prompt.",
    )
    return parser.parse_args()


def resolve_gh(value: str) -> str:
    if value:
        return value
    local_gh = Path(".tools/gh/bin/gh")
    return str(local_gh) if local_gh.exists() else "gh"


def resolve_codex(value: str) -> str:
    return value or "codex"


def selected_issues(args: argparse.Namespace, gh: str) -> list[Issue]:
    if args.issues:
        return [load_issue(gh, args.repo, number) for number in args.issues]
    if not args.all:
        raise SystemExit("Pass --issues N [N...] or --all.")

    result = run(
        [
            gh,
            "issue",
            "list",
            "--repo",
            args.repo,
            "--state",
            "open",
            "--label",
            args.label,
            "--limit",
            "100",
            "--json",
            "number,title,url",
        ],
        check=True,
    )
    listed = json.loads(result.stdout)
    issues: list[Issue] = []
    for item in sorted(listed, key=lambda value: value["number"]):
        title = item["title"]
        if not args.include_prd and is_prd_issue(title):
            continue
        issues.append(load_issue(gh, args.repo, int(item["number"])))
    return issues


def load_issue(gh: str, repo: str, number: int) -> Issue:
    result = run(
        [
            gh,
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,body,url",
        ],
        check=True,
    )
    data = json.loads(result.stdout)
    return Issue(
        number=int(data["number"]),
        title=str(data["title"]),
        body=str(data.get("body") or ""),
        url=str(data.get("url") or ""),
    )


def is_prd_issue(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized.startswith("prd:") or "prd técnico" in normalized or "prd tecnico" in normalized


def process_issue(
    *,
    issue: Issue,
    args: argparse.Namespace,
    gh: str,
    codex: str,
    run_root: Path,
) -> None:
    branch = issue_branch_name(issue)
    issue_dir = run_root / f"issue-{issue.number}"
    issue_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Issue #{issue.number}: {issue.title} ===")
    ensure_clean_worktree()
    prepare_branch(base=args.base, branch=branch, skip_sync=args.skip_sync)

    prompt = build_prompt(issue, args)
    prompt_path = issue_dir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    last_message_path = issue_dir / "last-message.md"
    codex_log_path = issue_dir / "codex-output.log"
    codex_result = run_codex(
        codex=codex,
        prompt_path=prompt_path,
        last_message_path=last_message_path,
        model=args.model,
        sandbox=args.sandbox,
        approval=args.approval,
    )
    codex_log_path.write_text(codex_result.stdout + codex_result.stderr, encoding="utf-8")
    if codex_result.returncode != 0:
        raise RuntimeError(f"codex exec failed; see {codex_log_path}")

    validation_commands = args.validation or [DEFAULT_VALIDATION]
    validation_log_path = issue_dir / "validation.log"
    validation_output = []
    for command in validation_commands:
        result = run_shell(command)
        validation_output.append(f"$ {command}\n{result.stdout}{result.stderr}\n")
        if result.returncode != 0:
            validation_log_path.write_text("\n".join(validation_output), encoding="utf-8")
            raise RuntimeError(f"validation failed: {command}; see {validation_log_path}")
    validation_log_path.write_text("\n".join(validation_output), encoding="utf-8")

    if not completion_markers_pass(last_message_path):
        raise RuntimeError(f"completion markers missing or incomplete; see {last_message_path}")

    ensure_clean_worktree()
    ahead_count = count_commits_ahead(args.base)
    if ahead_count < 1:
        raise RuntimeError("no commits were created for this issue")

    if args.no_pr:
        print(f"Branch {branch} is ready with {ahead_count} commit(s). PR creation skipped.")
        switch_branch(args.base)
        return

    push_branch(branch)
    pr_body_path = issue_dir / "pr-body.md"
    pr_body_path.write_text(build_pr_body(issue, validation_commands, last_message_path), encoding="utf-8")
    create_pr(gh=gh, repo=args.repo, base=args.base, branch=branch, issue=issue, body_path=pr_body_path)
    switch_branch(args.base)


def build_prompt(issue: Issue, args: argparse.Namespace) -> str:
    extra = "\n".join(f"- {item}" for item in args.extra_instruction)
    return dedent(
        f"""
        Use a skill $tdd.

        Trabalhe somente na issue #{issue.number}: {issue.title}
        URL: {issue.url}

        Leia AGENTS.md, CONTEXT.md, README.md e os documentos downstream relevantes:
        - context/prd-nvidia-downstream-technical-architecture.md
        - context/prd-nvidia-knowledge-recommendation-briefing.md
        - context/roadmap-nvidia-knowledge-recommendation-briefing.md
        - context/domain-model.md
        - context/frameworks-and-retrieval-strategy.md

        Regras obrigatórias:
        - Confirme a branch atual com git status --branch --short.
        - Trabalhe apenas nesta issue.
        - Use TDD em fatias verticais: um teste observável, implementação mínima, validação, próximo teste.
        - Testes devem usar interfaces públicas e fixtures locais.
        - Não use rede, credenciais, Postgres real, LangGraph obrigatório, LLM real ou embedding real na suíte default.
        - Não reimplemente NVIDIA Knowledge quando a issue for consumidora; consuma o contrato existente.
        - Não avance além do escopo desta issue.
        - Não use git add .
        - Faça commit(s) pequenos e descritivos somente com arquivos relacionados.
        - Não abra PR. O script externo abrirá o PR se a issue estiver concluída.
        - Se precisar de opinião/intervenção humana, pare e explique o bloqueio sem forçar commit.

        Validação esperada:
        {"; ".join(args.validation or [DEFAULT_VALIDATION])}

        Ao final, escreva exatamente estes marcadores no resumo final quando a issue estiver 100% concluída:
        ISSUE_STATUS: complete
        VALIDATION: passed
        REQUIRES_USER_INPUT: no

        Se a issue não estiver 100% concluída, escreva:
        ISSUE_STATUS: partial ou ISSUE_STATUS: blocked
        REQUIRES_USER_INPUT: yes

        Corpo da issue:
        {issue.body}

        Instruções extras:
        {extra or "- Nenhuma."}
        """
    ).strip()


def run_codex(
    *,
    codex: str,
    prompt_path: Path,
    last_message_path: Path,
    model: str,
    sandbox: str,
    approval: str,
) -> CommandResult:
    command = [
        codex,
        "exec",
        "--ephemeral",
        "--cd",
        str(Path.cwd()),
        "--sandbox",
        sandbox,
        "--ask-for-approval",
        approval,
        "--output-last-message",
        str(last_message_path),
    ]
    if model:
        command.extend(["--model", model])
    command.append("-")
    prompt = prompt_path.read_text(encoding="utf-8")
    return run(command, input_text=prompt, check=False)


def prepare_branch(*, base: str, branch: str, skip_sync: bool) -> None:
    if not skip_sync:
        run(["git", "fetch", "origin", base], check=True)
    switch_branch(base)
    if not skip_sync:
        run(["git", "pull", "--ff-only", "origin", base], check=True)

    existing = run(["git", "rev-parse", "--verify", branch], check=False)
    if existing.returncode == 0:
        raise RuntimeError(f"branch already exists: {branch}")
    run(["git", "switch", "-c", branch], check=True)


def switch_branch(branch: str) -> None:
    run(["git", "switch", branch], check=True)


def push_branch(branch: str) -> None:
    run(["git", "push", "-u", "origin", branch], check=True)


def create_pr(*, gh: str, repo: str, base: str, branch: str, issue: Issue, body_path: Path) -> None:
    run(
        [
            gh,
            "pr",
            "create",
            "--repo",
            repo,
            "--base",
            base,
            "--head",
            branch,
            "--title",
            f"#{issue.number}: {issue.title}",
            "--body-file",
            str(body_path),
        ],
        check=True,
    )


def build_pr_body(issue: Issue, validation_commands: list[str], last_message_path: Path) -> str:
    last_message = last_message_path.read_text(encoding="utf-8") if last_message_path.exists() else ""
    validation_lines = "\n".join(f"- `{command}`" for command in validation_commands)
    return dedent(
        f"""
        Closes #{issue.number}

        ## Validation

        {validation_lines}

        ## Codex Completion Summary

        {last_message.strip()}
        """
    ).strip()


def completion_markers_pass(last_message_path: Path) -> bool:
    if not last_message_path.exists():
        return False
    text = normalize_marker_text(last_message_path.read_text(encoding="utf-8"))
    return (
        "issue_status: complete" in text
        and "validation: passed" in text
        and "requires_user_input: no" in text
    )


def normalize_marker_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def ensure_clean_worktree() -> None:
    result = run(["git", "status", "--porcelain"], check=True)
    if result.stdout.strip():
        raise RuntimeError(
            "working tree is not clean. Commit, stash, or remove unrelated changes before running automation."
        )


def count_commits_ahead(base: str) -> int:
    result = run(["git", "rev-list", "--count", f"{base}..HEAD"], check=True)
    return int(result.stdout.strip() or "0")


def issue_branch_name(issue: Issue) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", issue.title.lower()).strip("-")
    slug = slug[:60].strip("-") or "issue"
    return f"feat/issue-{issue.number}-{slug}"


def run_shell(command: str) -> CommandResult:
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        cwd=Path.cwd(),
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def run(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool,
) -> CommandResult:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        cwd=Path.cwd(),
    )
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        joined = " ".join(command)
        raise RuntimeError(f"command failed: {joined}\n{result.stdout}{result.stderr}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
