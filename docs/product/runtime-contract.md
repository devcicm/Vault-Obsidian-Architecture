# Runtime Contract

Este documento define la frontera verificable del **runtime documental** en el
modelo híbrido. No redefine secciones, vocabularios, capacidades, normas ni
arquitectura. Cuando necesite esos datos, el toolkit debe leer sus registros
canónicos.

## Definición

Un runtime es una raíz elegida por el consumidor que contiene la memoria
documental de un proyecto. Sus fuentes durables son Markdown y YAML
frontmatter. Los índices y reportes existen para consultar, verificar o
recuperar esa memoria; no la sustituyen.

Un runtime no contiene ni necesita copias de `scripts/`, `cli/` o `vault/`.

## Identidad y versiones

| Dato | Dueño | Contrato |
|---|---|---|
| Raíz | Consumidor | Ruta explícita o detectada con origen y nivel de confianza observables mediante `vault_io`. |
| Identidad | Runtime | Metadatos persistentes que distinguen el vault y no dependen de la ruta de instalación del toolkit. |
| `toolkit_version` | Toolkit instalado | Sale de `vault_version.CURRENT_VERSION`; no se escribe como versión aplicada del runtime. |
| `runtime_schema_version` | Runtime | `applied_version` en `00_System/standard-version.json`. |

Cambiar la versión instalada no cambia `runtime_schema_version`. Una migración
explícita puede cambiarla después de aplicar y verificar sus pasos.

## Estructura mínima

La estructura requerida es la declarada por
`vault_registry.ORDERED_SECTIONS`. Este documento no reproduce la lista ni su
conteo. Un validador debe importar el registro, contrastarlo con la raíz y
declarar ausencias o incompatibilidades.

`00_System/` conserva identidad, versión aplicada, contratos/proyecciones y
registros operativos. `99_Index/` conserva índices derivados. Las demás
secciones tienen el propósito definido por los registros y el estándar.

## Ownership de artefactos

| Clase | Ownership | Mutabilidad y recuperación |
|---|---|---|
| Notas Markdown | Humano/agente | Fuente durable; cambios revisables y versionables. |
| YAML frontmatter | Runtime bajo contrato | Editable sin salir de vocabularios y reglas vigentes. |
| Identidad y preferencias | Consumidor/runtime | Persisten entre instalaciones del toolkit. |
| `standard-version.json` | Runtime | Solo cambia mediante inicialización o migración explícita. |
| `tool-spec.json` | Proyección versionada | Se genera desde los registros del toolkit para la compatibilidad del runtime. |
| Índices | Derivados del runtime | Regenerables; su pérdida no debe borrar las notas fuente. |
| Informes y trazas | Toolkit dentro del runtime | Evidencia operativa con ubicación y retención declaradas. |
| Temporales y locks | Toolkit dentro del runtime | Acotados a la raíz; se limpian o recuperan conforme al contrato de escritura. |
| Backups | Toolkit, propiedad del consumidor | Permanecen dentro del ámbito autorizado y deben poder verificarse antes de restaurar. |
| Código Python/CLI | Toolkit | No pertenece al runtime ni se copia durante `init`. |

## Proyección del contrato de tools

`00_System/tool-spec.json` acompaña al runtime para hacer observable el
contrato compatible de sus herramientas. Es una proyección versionada:

- se deriva de registros canónicos del toolkit;
- puede inspeccionarse sin ejecutar una migración;
- no autoriza a sobrescribir una proyección más nueva o divergente en silencio;
- su ausencia, corrupción o incompatibilidad debe aparecer en `doctor` y
  `status`;
- el fallback legacy documentado por `resolve_tool_spec()` permanece de solo
  lectura mientras esté soportado.

## Índices y artefactos derivados

Un índice debe poder reconstruirse desde documentos y registros del runtime.
Una operación de reindexado puede cambiar derivados, pero no debe presentar su
existencia como prueba de que el conocimiento fuente es correcto o completo.

Cada derivado debe tener un productor identificable, una ubicación contenida y
un criterio de staleness o reconstrucción cuando el estándar lo defina.

## Escrituras e invariantes

1. Toda escritura se contiene bajo la raíz resuelta del runtime.
2. Backups, trazas, locks y temporales también permanecen bajo esa raíz.
3. Las notas se escriben por el camino atómico y con los guards aplicables.
4. Una operación de solo lectura no cambia versión, contrato, notas ni índices.
5. Instalar, actualizar o desinstalar el toolkit no escribe en el runtime.
6. `doctor` y `status` informan incompatibilidades; no migran.
7. Ninguna migración se aplica silenciosamente.
8. La pérdida del toolkit no impide leer Markdown y YAML con herramientas
   comunes.
9. El runtime no necesita código del toolkit dentro de su árbol.
10. Los derivados no sustituyen la fuente documental durable.

## Inicialización

`vault init` recibe o resuelve una raíz autorizada, crea la estructura desde el
registro canónico y escribe la identidad, versión aplicada y proyecciones
iniciales. Debe ser seguro frente a contenido preexistente y no puede tratar
`--clean` ni otra operación destructiva como comportamiento implícito.

## Migraciones

El mecanismo de upgrade existente es el dueño de las migraciones. El flujo de
producto requerido es:

```text
inspect → report → plan/dry-run → backup → explicit confirmation
→ apply → verify → record applied version
```

Si una etapa falla, el runtime conserva evidencia suficiente para diagnosticar
y recuperar. Ampliar una versión instalada no equivale a aplicar una migración.

## Garantías y límites

El contrato garantiza propiedades únicamente cuando la operación usa los
caminos y guards publicados. No garantiza que toda afirmación sea verdadera,
que todo conocimiento haya sido capturado ni que un índice esté actualizado si
su productor no se ejecutó correctamente.

La portabilidad significa que los datos durables siguen siendo legibles y
versionables sin el toolkit. No significa que las consultas, auditorías o
migraciones ejecutables funcionen después de desinstalarlo.

## Verificación futura

La implementación deberá comprobar, sin duplicar registros:

- raíz y confianza de detección;
- estructura mínima contra `ORDERED_SECTIONS`;
- identidad y versión aplicada;
- proyección de contrato legible y compatible;
- ausencia de código vendorizado como requisito operativo;
- contención de derivados, temporales, locks y backups;
- migraciones pendientes sin aplicarlas.

Estas verificaciones se incorporarán después de estabilizar la unidad
instalable. Este documento define el contrato; no declara prematuramente una
gate verde.
