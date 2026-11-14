#!/usr/bin/env bash
# Regenera contract/ e frontend/src/contract/ e falha se algo mudou: o contrato versionado
# precisa ser exatamente o que os modelos Pydantic geram. Não depende do estado do git.
set -euo pipefail

cd "$(dirname "$0")/.."
snapshot() { find contract frontend/src/contract -type f -print0 | sort -z | xargs -0 sha256sum; }

before="$(snapshot)"
(cd backend && .venv/bin/python -m devaneio.export_schema >/dev/null)
(cd frontend && npm run --silent types >/dev/null)
after="$(snapshot)"

if [[ "$before" != "$after" ]]; then
    echo "contrato desatualizado: regenerado agora. Revise o diff e commite (skill change-contract)." >&2
    diff <(echo "$before") <(echo "$after") >&2 || true
    exit 1
fi
echo "contrato em dia"
