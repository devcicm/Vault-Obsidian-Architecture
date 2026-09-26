#!/usr/bin/env bash
# uninstall-mcp.sh — Elimina el symlink del servidor MCP
#
# Uso: ./uninstall-mcp.sh [--dry-run]

set -e

MCP_DEST="/usr/local/bin/vault-mcp"

if [ "$1" = "--dry-run" ]; then
    echo "[dry-run] Eliminaría symlink: $MCP_DEST"
    exit 0
fi

echo "=== MCP server uninstall ==="
echo "Dest: $MCP_DEST"
echo

if [ -L "$MCP_DEST" ]; then
    rm -f "$MCP_DEST"
    echo "OK: Symlink eliminado"
elif [ -f "$MCP_DEST" ]; then
    echo "[ERROR] $MCP_DEST existe y no es symlink — no se toca"
    exit 1
else
    echo "No existía: $MCP_DEST"
fi
