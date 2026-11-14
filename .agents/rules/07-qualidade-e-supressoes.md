# 07. Qualidade, lint e supressões

A configuração das ferramentas é o **padrão de qualidade do projeto**, não um obstáculo a contornar.
Quem escreve o código não decide, sozinho, que uma verificação deixa de valer.

## Ferramentas (todas dentro de `scripts/check`)

| Ferramenta | Para quê | Configuração |
|---|---|---|
| `ruff check` | lint: estilo, bugs prováveis, segurança, imports, supressões | `backend/pyproject.toml` |
| `ruff format` | formatação (linha 100); o formatador manda, não se discute estilo | idem |
| `mypy --strict` | tipos em `src/` | idem |
| `import-linter` | camadas ([rule 03](03-arquitetura.md)) | idem |
| `pytest` + cobertura | testes, piso 92% ([rule 04](04-testes.md)) | idem |
| `prettier` + `tsc` | frontend (gerado em `src/contract` é ignorado) | `frontend/` |
| `check_*.py` | supressões, atribuição, governança | `scripts/` |

## Proibido para fazer um portão passar

- Desligar ou relaxar regra; adicionar a `ignore`, `per-file-ignores`, `exclude`, `omit`; baixar `fail_under`;
  afrouxar `mypy`; remover regra de `select`.
- `# noqa` ou `# type: ignore` **sem código**, ou sem justificativa.
- `--no-verify`, ou apagar/enfraquecer um teste para ficar verde.
- `Any`, `cast` ou `getattr` com string usados só para calar o verificador de tipos.

## Ordem de tratamento de um achado

1. **Corrija a causa.** É o que se espera em quase todos os casos.
2. Se for falso positivo, ou o custo da correção for desproporcional ao problema: **supressão local** (abaixo).
3. Se a regra em si estiver errada para o projeto: **peça ao dono**. Mudança de configuração só com pedido
   explícito, com o motivo escrito num comentário ao lado da regra.

## Supressão local válida

- Código específico: `# noqa: S310`, `# type: ignore[assignment]`.
- Menor extensão possível: uma linha, nunca arquivo ou bloco.
- Justificativa na mesma linha, depois de ` — `, ou num comentário na linha de cima:
  `# noqa: S310 — esquema http(s) validado em LlmConfig`.
- Proporcional: uma linha para um falso positivo pontual. Se o mesmo padrão se repete, o problema é a regra:
  vá ao dono.

## O que é automático

`ruff` (`PGH003`, `PGH004`, `RUF100`: supressão sem código ou sem efeito falha), `mypy`
(`warn_unused_ignores`, `ignore-without-code`) e `scripts/check_suppressions.py`, que exige código + justificativa e,
comparando com a branch base, **falha se a configuração enfraqueceu** (menos regras, mais ignores, `fail_under`
menor, mypy sem strict). Limite honesto: o dono pode aceitar um enfraquecimento ao fazer o merge de forma
consciente; a máquina só garante que ele não passe despercebido.

## Formatação e lint no dia a dia

`cd backend && .venv/bin/ruff format . ../scripts --config pyproject.toml` aplica o formato; `ruff check --fix`
corrige o que é seguro. Rode `scripts/check --fast` antes de commitar. Ver a skill `quality-gate`.
