# ADR-0002: puente scripts → _impl en la wheel instalada

- **Estado:** aceptado
- **Fecha:** 2026-09-27
- **Decisión:** Fachada de re-export en `scripts/vault_regex.py` + `package-dir` en `pyproject.toml`
- **Alcance:** resolución de imports entre el checkout fuente y la wheel instalada; no redefine la arquitectura de contextos

## Contexto

El toolkit se distribuye como paquete Python. El código vivo reside en `scripts/`, pero la wheel instalada proyecta ese contenido en `vault_toolkit/_impl/`. Ambas rutas deben ser importables con el mismo nombre (`from vault_regex import ...`, `from vault_lib import ...`) sin que el llamador sepa si está en el source checkout o en la wheel.

Además, `vault/kernel/regex.py` es el **único dueño** de los patrones wikilink (AP-50) y de `strip_code_blocks` (AP-57). Ese módulo no puede vivir en `_impl` (que es solo para operaciones legacy), así que la wheel debe incluirlo también en `vault/kernel/`.

## Opciones evaluadas

### A. Imports absolutos condicionados

En cada script, detectar si estamos en la wheel o en el source y ajustar `sys.path` consecuentemente. Hace que cada import seaaware del contexto de ejecución, viola AP-57 (el dueño del símbolo no sabe de dónde se importa).

### B. Alias en site-packages

Usar un módulo `_vault_regex` en site-packages que re-exporte desde `vault.kernel.regex`. Añade un nivel de indirección innecesario y complica el tracking de quién es el dueño real del símbolo.

### C. Fachada de re-export + package-dir

`scripts/vault_regex.py` funciona como fachada: re-exporta todo desde `vault.kernel.regex` usando `from vault.kernel.regex import *`. En el source checkout, `scripts/` está en `sys.path`; en la wheel, `vault_toolkit/_impl/` se mapea ahí vía `package-dir` en `pyproject.toml`. El símbolo vive exactamente donde el dueño lo decidió, y el import funciona igual en ambos entornos.

## Decisión

Se adopta la **opción C**:

1. `scripts/vault_regex.py` re-exporta desde `vault.kernel.regex` (`from vault.kernel.regex import *`).
2. `pyproject.toml` declara `package-dir = {"vault_toolkit._impl": "scripts"}` para que `_impl/vault_regex.py` en la wheel sea el mismo fichero fuente.
3. `vault/kernel/regex.py` es el dueño de `RE_WIKILINK`, `PATRON_WIKILINK`, `strip_code_blocks` y cualquier otra常量 de regex.
4. `vault/consulta/safety.py` reside en `vault/consulta/` (no en `_impl`) y contiene las definiciones de anti-poisoning usadas por `cli/safety.py` y `vault_ingest`.
5. `vault_toolkit/_impl/` recibe una copia de `scripts/` durante el build de la wheel, con `_impl/vault_io.py` como stub que delega al `vault_io` del package instalado.

## Consecuencias

- **Positivas:** El dueño de un símbolo (AP-50/AP-57) es unambiguous; los imports funcionan igual en source y wheel.
- **Negativas:** El散 directorios `scripts/` y `_impl` deben mantenerse sincronizados; un cambio en `scripts/` sin rebuild no se refleja en la wheel instalada.
- **Mitigación:** El pre-commit hook regenera `_impl/` desde `scripts/` en cada commit, y `clean_install_gate` verifica que la wheel contiene lo esperado.

## Notas

- La fachada `vault_regex` no define ningún símbolo propio: es puro re-export. El guard AP-57 verifica que `strip_code_blocks` se importe desde `vault_lib`, que a su vez lo importa desde `vault.kernel.regex`.
- El blocker B7 original era que `_impl/vault_io.py` (stub) podía ser ignorado si `vault_io.py` existía en el CWD. El test `test_impl_shadow` verifica que cuando `_impl/vault_io.py` existe, se prefiere sobre cualquier `vault_io.py` espurio en el CWD.

## Addendum (v40.35): _impl en la wheel

**Pregunta:** ¿Por qué incluir `_impl/` (copia de `scripts/`) en la wheel si `package-dir` ya mapea `_impl → scripts`?

**Respuesta:** porque `import_toolkit_module` necesita que `_impl/` exista como directorio para poder priorizarlo en `sys.path`. Sin un `_impl/` físico en la wheel, la lookup de `importlib.import_module` para el stub de `vault_io` no encuentra dónde insertar la prioridad.

El `package-dir` permite que `import vault_toolkit._impl.vault_regex` resuelva al fichero fuente en `scripts/`, pero no crea el directorio `_impl/` en el artefacto wheel. Para que la jerarquía de directorios de la wheel sea completa y `import_toolkit_module` pueda resolver `_impl/vault_io.py` como ruta real, se incluye `_impl/` en la wheel durante el build.

**Decisión:** `_impl/` se incluye en la wheel. El pre-commit hook lo regenera desde `scripts/` en cada commit. Es una copia de trabajo, no la fuente autoritativa.
