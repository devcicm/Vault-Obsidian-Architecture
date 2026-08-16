# Instalar el toolkit fuera de este repo

Este repositorio es el **estándar**. Para usarlo sobre un vault tuyo no hace falta
clonarlo entero ni instalar nada de npm o PyPI: se copian cuatro carpetas y se dice
dónde está el vault.

## Requisitos

- **Python 3.9+**. Nada más: el toolkit vive de la stdlib. PyYAML es opcional y cada
  módulo que lo importa tiene su `except ImportError` — sin él se pierde el parseo
  estricto de frontmatter, no la ejecución.
- **Node 18+** solo si vas a usar el servidor MCP. Cero dependencias npm.

## Instalación

```bash
# 1. Copia el toolkit donde quieras que viva
cp -r scripts vault cli mcp  /ruta/donde/lo/instalas/vault-toolkit/

# 2. Di dónde está TU vault. Esto no es opcional fuera del repo: ver abajo.
export VAULT_ROOT=/ruta/a/mi-vault

# 3. Comprueba
python /ruta/donde/lo/instalas/vault-toolkit/scripts/vault_audit.py
```

Para un vault nuevo desde cero, `vault_init` crea la estructura completa:

```bash
python .../scripts/vault_init.py --target /ruta/a/mi-vault
```

## Por qué `VAULT_ROOT` es obligatorio fuera del repo

Dentro de este repositorio la autodetección resuelve `vault-sandbox/` y acierta. Fuera,
si no encuentra ningún vault, cae a un último recurso llamado `repo_root_fallback`, que
significa literalmente *«no encontré nada y estoy suponiendo»* — y devuelve el directorio
del propio programa. Escribir con esa raíz sembraba artefactos de vault **dentro del
toolkit**, no en tu vault.

Desde v40.30 eso se rechaza: **leer** con una raíz dudosa sigue permitido (el diagnóstico
tiene que poder correr justo cuando algo va mal), **escribir** no. El error dice qué raíz
se eligió, con qué origen y cómo salir de ahí. Para volver al comportamiento anterior,
`VAULT_PERMISSIVE_ROOT=1`.

Alternativa a la variable: crea el vault en un directorio llamado `vault-<algo>/`, que es
uno de los marcadores que la detección reconoce con confianza. Verifica con:

```bash
python -c "import vault_io; print(vault_io.get_vault_root(), vault_io.vault_root_origin())"
```

## Servidor MCP

```bash
node .../mcp/nodejs/vault-mcp-server.mjs            # stdio (para un cliente MCP)
node .../mcp/nodejs/vault-mcp-server.mjs --port 8790  # SSE/HTTP
```

Dos cosas que conviene saber antes de usarlo:

- **El puerto escucha solo en `127.0.0.1` y no tiene autenticación.** Es local por
  diseño. Exponerlo a una red requiere poner delante autenticación y TLS; no lo hace
  este servidor.
- **Fuera de este repo no escanea el disco.** Dentro, registra los vaults hermanos porque
  son los consumidores conocidos del estándar. Instalado en cualquier otro sitio,
  `..` es una carpeta tuya, así que el default es no mirar nada: se registra el vault que
  le des. Para escanear rutas concretas, `VAULT_SCAN_ROOTS=/ruta/a;/otra/ruta`.

## Vaults preexistentes

Un vault que no generó este toolkit se mide **en solo lectura** antes de tocarlo:

```bash
python .../scripts/vault_foreign_check.py --root /ruta/al/vault/ajeno
```

Es la regla 7 del estándar en forma ejecutable, y existe porque una medida tomada contra
material que uno mismo generó comparte sus supuestos y no puede exhibir el fallo. El
proceso completo de adopción está en `docs/MODO-AGENTICO-SANACION.md` (12 fases, y allí
la regla es que nada se borra).
