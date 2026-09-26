#!/usr/bin/env bash
# install.sh — Instalador CLI + entry points del toolkit Vault-Obsidian-Architecture
#
# Uso: ./install.sh [--mcp] [--all]
#   --mcp   Incluir MCP server symlink en /usr/local/bin
#   --all   Instalar todo (CLI + MCP + skills)
#
# Requiere: Python 3.9+, pip, Git

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

INSTALL_MCP="${INSTALL_MCP:-0}"
INSTALL_ALL="${INSTALL_ALL:-0}"

for arg in "$@"; do
    case "$arg" in
        --mcp)  INSTALL_MCP=1 ;;
        --all)  INSTALL_MCP=1; INSTALL_ALL=1 ;;
        --dry-run)
            echo "[dry-run] Acciones que se ejecutarían:"
            echo "  pip install -e '$REPO_ROOT'"
            if [ "$INSTALL_MCP" = "1" ]; then
                echo "  ln -sf '$REPO_ROOT/mcp/nodejs/vault-mcp-server.mjs' /usr/local/bin/vault-mcp"
            fi
            exit 0
            ;;
        --help|-h)
            echo "Uso: $0 [--mcp] [--all] [--dry-run]"
            echo "  --mcp  Instalar MCP server symlink"
            echo "  --all  Instalar todo (CLI + MCP)"
            exit 0
            ;;
    esac
done

echo "=== Vault-Obsidian-Architecture install ==="
echo "Repo root: $REPO_ROOT"
echo

# CLI + entry points
echo "[1/2] Instalando CLI (pip install -e .)..."
pip install -e "$REPO_ROOT"

echo
echo "[2/2] Verificando entry points..."
python -m vault.product_cli --help > /dev/null 2>&1 && echo "  vault.product_cli: OK" || echo "  vault.product_cli: FAIL"
python -m vault.gobernanza.tool --help > /dev/null 2>&1 && echo "  vault.gobernanza.tool: OK" || echo "  vault.gobernanza.tool: FAIL"

if [ "$INSTALL_MCP" = "1" ]; then
    echo
    echo "[MCP] Creando symlink..."
    MCP_SRC="$REPO_ROOT/mcp/nodejs/vault-mcp-server.mjs"
    MCP_DEST="/usr/local/bin/vault-mcp"

    if [ -w "$(dirname "$MCP_DEST")" ]; then
        ln -sf "$MCP_SRC" "$MCP_DEST"
        echo "  Symlink: $MCP_DEST -> $MCP_SRC"
    else
        echo "  [WARN] No se pudo escribir en /usr/local/bin"
        echo "  Ejecuta como sudo: sudo ln -sf '$MCP_SRC' '$MCP_DEST'"
    fi
fi

echo
echo "=== Instalación completa ==="
echo
echo "CLAVE: exporta VAULT_ROOT al directorio de tu vault:"
echo "  export VAULT_ROOT=/ruta/al/tu-vault"
echo
echo "Verificar:"
echo "  vault --version"
echo "  vault tools list"
echo "  python -m vault.gobernanza.tool --help"
echo
if [ "$INSTALL_MCP" = "1" ]; then
    echo "MCP server:"
    echo "  vault-mcp --help"
    echo "  node '$MCP_SRC' --help"
fi
