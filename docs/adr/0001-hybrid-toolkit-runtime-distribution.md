# ADR-0001: distribución híbrida de toolkit y runtime documental

- **Estado:** aceptado
- **Fecha:** 2026-09-06
- **Decisión:** Modelo D — híbrido
- **Alcance:** distribución y frontera de propiedad; no redefine la arquitectura canónica

## Contexto

Vault Obsidian Architecture es un estándar abierto con un toolkit para dar a
agentes LLM memoria documental persistente, auditable y gobernada sobre
Markdown plano. El modelo histórico pedía copiar `scripts/` al repositorio
consumidor, pero la ejecución también depende de `vault/`, `cli/`, catálogos y
recursos. Esa copia parcial no es una unidad de distribución reproducible.

El producto necesita poder actualizar su software sin apropiarse del
conocimiento del usuario, y el conocimiento debe seguir siendo legible si el
toolkit se desinstala o deja de existir.

## Opciones evaluadas

### A. Vendoring completo

Copiar al consumidor `scripts/`, `vault/`, `cli/` y sus recursos. Facilita una
instantánea autocontenida, pero mezcla código y conocimiento, multiplica forks
y traslada al usuario la sincronización del toolkit.

### B. Paquete Python con runtime incorporado

Instalar software y guardar también la memoria dentro del paquete. Simplifica
la localización del código, pero acopla los datos al ciclo de instalación y
rompe la propiedad independiente del runtime.

### C. Toolkit externo sin contrato local de runtime

Instalar el ejecutable fuera del proyecto y tratar cualquier directorio como
datos. Reduce archivos en el consumidor, pero deja implícitas la versión, la
compatibilidad y la migración de la memoria.

### D. Modelo híbrido

Instalar y versionar el toolkit como software; conservar el runtime documental
en una raíz elegida por el consumidor y gobernada por un contrato explícito.

## Decisión

Se adopta el **modelo D — híbrido**:

1. El toolkit vive en un entorno Python instalable y expone un único entry
   point público, `vault`, sobre la CLI consolidada existente.
2. El conocimiento vive en un runtime documental fuera del paquete instalado.
3. La raíz del runtime se recibe o resuelve como dato de operación; nunca se
   infiere a partir de la ubicación del paquete en `site-packages`.
4. Código Python, CLI, catálogos ejecutables, migraciones y recursos de
   bootstrap pertenecen al toolkit.
5. Markdown, YAML frontmatter, identidad, preferencias y estado aplicado
   pertenecen al runtime.
6. Los índices son derivados del runtime y pueden regenerarse desde sus fuentes
   durables.
7. `<runtime>/00_System/tool-spec.json` es una proyección versionada del
   contrato compatible con ese runtime; no sustituye a los registros canónicos
   del toolkit.
8. `<runtime>/00_System/standard-version.json` declara la versión del estándar
   aplicada al runtime. No es la versión del paquete instalado.
9. Instalar, actualizar o desinstalar el toolkit no borra ni migra
   automáticamente el runtime.
10. Una migración requiere inspección, plan, backup, solicitud explícita,
    aplicación y verificación.

El contrato operativo de esta decisión se desarrolla en
[`runtime-contract.md`](../product/runtime-contract.md).

## Propiedad de versiones

| Versión | Dueño | Significado |
|---|---|---|
| `toolkit_version` | Paquete instalado; fuente canónica en `vault_version.CURRENT_VERSION` | Versión del software disponible para operar. |
| `runtime_schema_version` | Runtime; representada por `applied_version` en `standard-version.json` | Versión del estándar aplicada a esos datos. |
| Proyección de tools | Runtime; generada desde registros del toolkit | Contrato compatible que acompaña al runtime. |

Una diferencia entre toolkit y runtime es un estado observable. `doctor` o
`status` deben informarlo; no deben resolverlo escribiendo.

## Actualización y rollback

- **Actualizar toolkit:** instalar otra versión del paquete. No modifica notas,
  índices ni estado aplicado.
- **Rollback de toolkit:** reinstalar una versión compatible anterior.
- **Actualizar runtime:** ejecutar primero diagnóstico y dry-run; crear un
  backup; aplicar después de confirmación explícita; verificar el resultado.
- **Rollback de runtime:** usar los mecanismos de backup/restauración del
  toolkit o el historial Git del consumidor, según el contrato de la operación.

La compatibilidad soportada debe publicarse como una relación entre versiones
de toolkit y schema de runtime, no deducirse por igualdad de números.

## Migración desde consumidores históricos

Un consumidor que contiene una copia de `scripts/` se trata como legacy:

```text
detectar → informar → planificar → dry-run → backup → confirmar
→ instalar/usar toolkit → upgrade explícito → verificar
```

La migración no elimina la copia vendorizada. Tras verificar el nuevo camino,
el dueño del repositorio decide si la conserva, archiva o retira. Los fallbacks
legacy existentes se mantienen mientras su contrato siga soportado y cualquier
reemplazo se anota mediante la política de no-derogación.

## Operación offline y dependencia externa

Las operaciones locales principales funcionan sin red una vez instalado el
artefacto y sus dependencias locales. La memoria no exige base de datos,
embeddings ni servicio externo. Python y PyYAML son dependencias del toolkit,
no del formato durable del conocimiento.

## Consecuencias

### Positivas

- El usuario conserva y versiona sus datos independientemente del software.
- El toolkit puede actualizarse y probarse como un artefacto reproducible.
- Una desinstalación no hace ilegible la memoria.
- La instalación deja de depender de copiar una fracción del repositorio.

### Costes y restricciones

- La CLI y las operaciones deben dejar de depender del layout del checkout.
- Los recursos empaquetados necesitan un mecanismo estable de resolución.
- Deben existir compatibilidad declarada, migraciones explícitas y pruebas de
  instalación del artefacto real.
- El adaptador MCP puede requerir distribución adicional, pero no define ni
  bloquea el runtime documental.

## Fuentes canónicas relacionadas

Este ADR decide la frontera de distribución; no copia los registros que
gobiernan el contenido:

- servicio y capacidades: `scripts/vault_servicio.py`;
- versión del toolkit: `scripts/vault_version.py`;
- estructura del runtime: `scripts/vault_registry.py`;
- raíz operativa: `scripts/vault_io.py`;
- migraciones: `scripts/vault_standard_upgrade.py`;
- contratos de tools: `scripts/vault_mcp_catalog.py` y la proyección resuelta
  por `vault_io.resolve_tool_spec()`.
