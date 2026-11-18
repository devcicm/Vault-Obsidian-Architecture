#!/usr/bin/env bash
# install.sh — Instalador CLI + entry points del toolkit Vault-Obsidian-Architecture
#
# Uso: ./install.sh [--mcp] [--all]
#   --mcp   Incluir MCP server symlink en /usr/local/bin
#   --all   Instalar todo (CLI + MCP + skills)
#
# Requiere: Python 3.9+, pip, Git
#
# El intérprete es `$PYTHON` (por defecto `python3`): Debian y Ubuntu no traen
# `python`, y `pip` a secas puede ser el de otro Python. Con un venv activo,
# `python3` ya es el del venv.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
PYTHON="${PYTHON:-python3}"

INSTALL_MCP="${INSTALL_MCP:-0}"
INSTALL_ALL="${INSTALL_ALL:-0}"

for arg in "$@"; do
    case "$arg" in
        --mcp)  INSTALL_MCP=1 ;;
        --all)  INSTALL_MCP=1; INSTALL_ALL=1 ;;
        --dry-run)
            echo "[dry-run] Acciones que se ejecutarían:"
            echo "  $PYTHON -m pip install -e '$REPO_ROOT'"
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

if ! command -v "$PYTHON" > /dev/null 2>&1; then
    echo "[ERROR] No se encontró el intérprete '$PYTHON'."
    echo "  Indica uno de Python 3.9+: PYTHON=/ruta/a/python3 $0 $*"
    exit 1
fi

# PEP 668 (Debian 12, Ubuntu 23.04+): el pip del sistema rechaza instalar
# fuera de un venv. Se dice antes de intentarlo, con el camino que funciona.
if "$PYTHON" -c 'import os, sys, sysconfig; sys.exit(0 if sys.prefix == sys.base_prefix and os.path.isfile(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")) else 1)'; then
    echo "[ERROR] $PYTHON es el Python del sistema (EXTERNALLY-MANAGED, PEP 668): pip no instala en él."
    echo "  Crea un entorno virtual y vuelve a ejecutar este script desde él:"
    echo "    $PYTHON -m venv .venv && . .venv/bin/activate && $0 $*"
    exit 1
fi

if ! "$PYTHON" -m pip --version > /dev/null 2>&1; then
    echo "[ERROR] pip no está disponible para $PYTHON."
    echo "  Usa un entorno virtual ($PYTHON -m venv .venv) o instala pip para ese intérprete."
    exit 1
fi

# CLI + entry points
echo "[1/2] Instalando CLI ($PYTHON -m pip install -e .)..."
"$PYTHON" -m pip install -e "$REPO_ROOT"

echo
echo "[2/2] Verificando entry points..."
"$PYTHON" -m vault.product_cli --help > /dev/null 2>&1 && echo "  vault.product_cli: OK" || echo "  vault.product_cli: FAIL"
"$PYTHON" -m vault.gobernanza.tool --help > /dev/null 2>&1 && echo "  vault.gobernanza.tool: OK" || echo "  vault.gobernanza.tool: FAIL"

if [ "$INSTALL_MCP" = "1" ]; then
    echo
    echo "[MCP] Creando symlink..."
    MCP_SRC="$REPO_ROOT/mcp/nodejs/vault-mcp-server.mjs"
    MCP_DEST="/usr/local/bin/vault-mcp"

    # Un symlink corre con el modo de su destino: sin el bit de ejecución
    # (zip, copia sin modos) `vault-mcp` daría «permission denied».
    [ -x "$MCP_SRC" ] || chmod +x "$MCP_SRC"
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
echo "  $PYTHON -m vault.gobernanza.tool --help"
echo
if [ "$INSTALL_MCP" = "1" ]; then
    echo "MCP server:"
    echo "  vault-mcp --help"
    echo "  node '$MCP_SRC' --help"
fi
