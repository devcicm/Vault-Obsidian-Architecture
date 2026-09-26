#!/usr/bin/env bash
# install-mcp.sh — Instala solo el symlink del servidor MCP
#
# Uso: ./install-mcp.sh [--dry-run]
#
# Requiere: permisos de escritura en /usr/local/bin (o usa sudo)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"

MCP_SRC="$REPO_ROOT/mcp/nodejs/vault-mcp-server.mjs"
MCP_DEST="/usr/local/bin/vault-mcp"

if [ ! -f "$MCP_SRC" ]; then
    echo "[ERROR] MCP server no encontrado: $MCP_SRC"
    exit 1
fi

if [ "$1" = "--dry-run" ]; then
    echo "[dry-run] Simbolicaría: $MCP_DEST -> $MCP_SRC"
    exit 0
fi

echo "=== MCP server install ==="
echo "Source: $MCP_SRC"
echo "Dest:  $MCP_DEST"
echo

if [ -w "$(dirname "$MCP_DEST")" ]; then
    [ -L "$MCP_DEST" ] && rm "$MCP_DEST"
    [ -f "$MCP_DEST" ] && { echo "[ERROR] $MCP_DEST existe y no es symlink"; exit 1; }
    ln -s "$MCP_SRC" "$MCP_DEST"
    echo "OK: Symlink creado"
    echo
    echo "Verificar:"
    echo "  vault-mcp --help"
    echo "  node $MCP_SRC --help"
else
    echo "[WARN] Sin permisos de escritura en /usr/local/bin"
    echo "Ejecuta como sudo:"
    echo "  sudo ln -sf '$MCP_SRC' '$MCP_DEST'"
    exit 1
fi
