# Scripts Operacionais

## `codex_issue_batch.py`

Executa uma sessão nova de `codex exec --ephemeral` por issue do GitHub.

O script foi desenhado para ser conservador:

- uma issue por vez;
- branch isolada no padrão `feat/issue-<numero>-<slug>`;
- prompt TDD padronizado;
- validação local depois da sessão Codex;
- PR só se houver commit novo, worktree limpo, validação passando e marcadores finais de conclusão;
- PR fecha a issue apenas quando for mergeado, via `Closes #<numero>` no corpo.

Ele não usa `/clean`, porque `codex exec --ephemeral` já inicia uma sessão limpa para cada issue e não persiste chat.

### Ver Ordem Sem Executar

```bash
python3 scripts/codex_issue_batch.py --all
```

Por padrão, PRDs e issues meta são ignoradas. Para incluir PRDs:

```bash
python3 scripts/codex_issue_batch.py --all --include-prd
```

### Rodar Uma Issue Sem Criar PR

```bash
python3 scripts/codex_issue_batch.py --issues 35 --yes --no-pr
```

### Rodar Uma Issue E Abrir PR

```bash
python3 scripts/codex_issue_batch.py --issues 35 --yes
```

### Rodar Todas As Issues Abertas De Entrega

```bash
python3 scripts/codex_issue_batch.py --all --yes
```

Use com cautela. O script para no primeiro erro, a menos que você passe:

```bash
python3 scripts/codex_issue_batch.py --all --yes --continue-on-failure
```

### Requisitos

- `codex` disponível no terminal;
- GitHub CLI disponível em `.tools/gh/bin/gh` ou `gh`;
- worktree limpo antes de iniciar;
- autenticação GitHub configurada;
- permissão para criar branches, push e PR.

### Gates Para Abrir PR

O PR só é criado quando:

- `codex exec` termina com sucesso;
- validação local passa;
- o resumo final do agent contém:

```text
ISSUE_STATUS: complete
VALIDATION: passed
REQUIRES_USER_INPUT: no
```

- há pelo menos um commit novo na branch;
- `git status --porcelain` está limpo.

Se qualquer gate falhar, o script não abre PR.
