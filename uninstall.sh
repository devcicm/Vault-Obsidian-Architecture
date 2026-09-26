#!/usr/bin/env bash
# uninstall.sh — Desinstalador del toolkit Vault-Obsidian-Architecture
#
# Uso: ./uninstall.sh [--mcp] [--all]
#   --mcp  Incluir eliminación del symlink MCP
#   --all  Desinstalar todo (CLI + MCP)
#
# Requiere: pip

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

UNINSTALL_MCP="${UNINSTALL_MCP:-0}"
UNINSTALL_ALL="${UNINSTALL_ALL:-0}"

for arg in "$@"; do
    case "$arg" in
        --mcp)  UNINSTALL_MCP=1 ;;
        --all)  UNINSTALL_MCP=1; UNINSTALL_ALL=1 ;;
        --dry-run)
            echo "[dry-run] Acciones que se ejecutarían:"
            echo "  pip uninstall -y vault-obsidian-architecture"
            if [ "$UNINSTALL_MCP" = "1" ]; then
                echo "  rm -f /usr/local/bin/vault-mcp"
            fi
            exit 0
            ;;
        --help|-h)
            echo "Uso: $0 [--mcp] [--all] [--dry-run]"
            echo "  --mcp  Incluir eliminación del symlink MCP"
            echo "  --all  Desinstalar todo"
            exit 0
            ;;
    esac
done

echo "=== Vault-Obsidian-Architecture uninstall ==="
echo

if [ "$UNINSTALL_MCP" = "1" ]; then
    echo "[1/2] Eliminando symlink MCP..."
    MCP_DEST="/usr/local/bin/vault-mcp"
    if [ -L "$MCP_DEST" ]; then
        rm -f "$MCP_DEST"
        echo "  Eliminado: $MCP_DEST"
    else
        echo "  No existía: $MCP_DEST"
    fi
    echo
fi

echo "[2/2] Desinstalando paquete pip..."
pip uninstall -y vault-obsidian-architecture || echo "  No estaba instalado via pip"

echo
echo "=== Desinstalación completa ==="
echo "  El directorio del repo queda intacto."
echo "  Para eliminar definitivamente: rm -rf $REPO_ROOT"
