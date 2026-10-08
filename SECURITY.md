# Política de seguridad

Este toolkit escribe en el disco de quien lo instala y, en modo HTTP, abre un
puerto. Un fallo de seguridad en él se reporta en privado, no en un issue: un
issue público lo enseña antes de que exista arreglo.

La política sigue la estructura de ISO/IEC 29147 (divulgación de
vulnerabilidades): qué se soporta, por dónde avisar, qué esperar y qué
superficie hay. Que este fichero exista y tenga estas secciones lo vigila
`vault_produccion` (promesa `politica_de_vulnerabilidades`).

## Versiones soportadas

Solo la versión vigente del estándar recibe arreglos de seguridad: la de
`vault_version.CURRENT_VERSION`, que es también la `version` de
`pyproject.toml`. Una versión anterior se arregla actualizando, no con un
parche hacia atrás.

## Cómo reportar

Por el reporte privado de vulnerabilidades de GitHub:
<https://github.com/devcicm/Vault-Obsidian-Architecture/security/advisories/new>

Incluye, si puedes: la versión (`vault --version`), el sistema operativo, el
modo del servidor MCP (stdio o HTTP), los pasos para reproducirlo y qué
consigue quien lo explota. No hace falta un exploit: basta con poder
reproducirlo.

No abras un issue ni un pull request público con el detalle del fallo.

## Qué esperar

- Un acuse de recibo, y si se confirma, una nota en el changelog del
  manifiesto con la versión que lo cierra.
- El arreglo sigue el ciclo del repo: síntoma → norma → guard → test. Un fallo
  de seguridad confirmado acaba como norma con su guard, para que no vuelva.
- Quien lo reporta aparece en esa nota, si quiere.

No hay plazos comprometidos: el proyecto lo mantiene una persona.

## Superficie expuesta

Lo que sigue lo hace el código hoy; cada punto tiene su guard o su test.

- **Servidor MCP por stdio** (modo por defecto): no abre puertos. Habla solo
  con el proceso que lo lanzó.
- **Servidor MCP por HTTP** (`--port`): escucha solo en `127.0.0.1`, exige
  `Authorization: Bearer <token>` —de `VAULT_MCP_TOKEN` o generado al arrancar—
  comparado en tiempo constante, rechaza con 403 un `Host` ajeno (DNS
  rebinding) y toda petición con cabecera `Origin` (navegadores). Es la norma
  SP-04.
- **Escrituras**: toda ruta pasa por `vault_io.assert_within_vault`; una tool
  no escribe fuera del vault que se le señala (AP-36).
- **Ingesta**: `vault_ingest` ejecuta un pre-vuelo anti-poison que no se puede
  desactivar (`cli/safety.py`) antes de escribir texto de origen externo.
- **Errores**: el envelope de error no lleva traceback salvo con
  `VAULT_DEBUG=1`.
- **Red saliente**: una sola tool la usa, `vault_ingest --url`, solo con
  `--allow-network` explícito, solo `http(s)` y solo hacia la URL que se le
  pasa; lo descargado pasa por el mismo pre-vuelo. No hay base
  de datos, embeddings ni servicio externo.
- **Servicio de tokens** (`vault_token_service`, grupo 26): escucha en
  `127.0.0.1` por defecto y **no autentica**. `--host` permite abrirlo a otra
  interfaz; hacerlo lo expone a cualquiera que la alcance. No lo abras fuera
  de la máquina.

Lo que está fuera: el contenido de las notas es del usuario. El toolkit no
cifra el vault; protegerlo en disco es cosa del sistema donde vive.
