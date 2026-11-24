if [[ -x "$TOOLZ_PATH/bin/codex-vault" ]]; then
codex() { "$TOOLZ_PATH/bin/codex-vault" -C "$PWD" --add-dir "$WORKSTATION_PROJECTS" --sandbox workspace-write "$@"; }
mcpsecret() { "$TOOLZ_PATH/docker-tools/vault/local/secret.sh" "$@"; }
mcpvault() { docker compose -f "$TOOLZ_PATH/docker-tools/vault/local/docker-compose.yml" "$@"; }
mcpvault-ensure() { "$TOOLZ_PATH/docker-tools/vault/local/ensure.sh" "$@"; }
mcpvault-status() { "$TOOLZ_PATH/docker-tools/vault/local/status.sh" "$@"; }
mcpvault-unseal() { "$TOOLZ_PATH/docker-tools/vault/local/unseal.sh" "$@"; }
# Use migration.py backup for a consistent encrypted backup of local Vault.
fi
mcp() {
  local root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  [[ -f "$HOME/.config/mcp/mcp.json" ]] || return 1
  mkdir -p "$root/.vscode"
  cp "$HOME/.config/mcp/mcp.json" "$root/.vscode/mcp.json"
}
if [[ -n "$ZENSICAL_DOCS_DIRECTORY" && -d "$ZENSICAL_DOCS_DIRECTORY" ]]; then
zensical() {
  docker run --rm -it -v "$ZENSICAL_DOCS_DIRECTORY:/docs" \
    -p 8010:8000 --entrypoint zensical zensical-docs serve -a 0.0.0.0:8000 "$@"
}
fi
bastion-rdp() {
  local target=${1:?Usage: bastion-rdp server [local-port]} local_port=${2:-13389}
  [[ -n ${BASTION_SSH_TARGET:-} ]] || { print -u2 'Configure bastion_ssh_target in inventory/local.yml'; return 1; }
  ssh -S "$HOME/.ssh/cm/${BASTION_SSH_TARGET}:22" -N -o ExitOnForwardFailure=yes \
    -L "${local_port}:${target}:3389" "$BASTION_SSH_TARGET"
}
if [[ -o interactive && ${WORKSTATION_AUTOSTART:-0} == 1 ]]; then
  [[ -x "$TOOLZ_PATH/docker-tools/vault/local/ensure-on-login.sh" ]] && "$TOOLZ_PATH/docker-tools/vault/local/ensure-on-login.sh"
fi
