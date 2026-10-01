# Análisis y hallazgos del repositorio

> Archivado el 2026-10-01 desde la raíz del repo (`auditado.md`, entonces
> excluido de git). El texto es el original; la última sección habla de ese
> estado anterior. Los hallazgos posteriores están en
> [la comparativa v34/v40](2026-10-01-comparativa-v34-v40.md).

Fecha de revisión: 2026-09-25.

## Alcance

Este informe recoge la revisión de documentación, estructura y fragmentos de código realizada para explicar el propósito del repositorio. Incluye una relectura del README antes de escribir este documento, porque su contenido cambió respecto de la revisión inicial.

No constituye una auditoría exhaustiva ni una certificación de funcionamiento. No se ejecutaron herramientas sobre vaults, pruebas, puertas de calidad ni procedimientos de instalación. Las conclusiones distinguen evidencia del código, declaraciones documentales e interpretaciones.

## De qué trata

Vault Obsidian Architecture define un estándar y un toolkit para dar memoria documental persistente a agentes LLM. El conocimiento se conserva en Markdown con metadatos YAML y enlaces entre notas, para poder recuperarlo entre sesiones.

Este repositorio contiene la especificación y su implementación. Cada proyecto consumidor mantiene su propio vault; `vault-sandbox/` es el vault de pruebas de este repositorio.

El servicio declarado en [scripts/vault_servicio.py](scripts/vault_servicio.py) organiza el trabajo en tres capacidades:

- **Escritura → gobernanza:** capturar, normalizar, versionar y auditar conocimiento.
- **Consulta → contexto:** convertir una pregunta en una selección de documentos dentro de un presupuesto de contexto.
- **Gobernanza del estándar:** comprobar la coherencia del repositorio, sus contratos y su documentación.

El diseño prescinde de bases de datos, embeddings y servicios externos obligatorios. Obsidian es una interfaz humana compatible; el agente puede operar mediante las herramientas sin tenerlo instalado.

## Organización observada

| Ruta | Responsabilidad |
|---|---|
| `vault-obsidian-architecture.md` | Manifiesto y especificación pública. |
| `scripts/` | Herramientas, adaptadores y registros canónicos. |
| `vault/` | Paquete organizado en autoría, consulta, grafo, índices, gobernanza, durabilidad, ciclo de vida, núcleo y meta-toolkit. |
| `cli/` | Interfaz consolidada y controles previos a la ejecución. |
| `vault/product_cli.py` | Interfaz pública del toolkit instalado. |
| `mcp/nodejs/` | Integración de herramientas mediante MCP. |
| `tests/` | Pruebas de comportamiento y contratos; no ejecutadas durante esta revisión. |
| `docs/` | Arquitectura, guías y procedimientos de onboarding y sanación. |
| `vault-sandbox/` | Runtime de pruebas. |

## Mecanismos relevantes

### Recuperación de contexto

[scripts/vault_context_pack.py](scripts/vault_context_pack.py) describe una cadena de interpretación de consulta, búsqueda léxica, expansión por grafo, ordenación y selección bajo presupuesto de tokens. Esto permite recuperar decisiones, errores resueltos y conocimiento relacionado para una tarea posterior.

La persistencia de documentos no hace que el agente los consulte automáticamente: su entorno de ejecución debe integrar estas operaciones e incorporar los resultados al contexto.

### Gobernanza y custodia

La documentación establece el recorrido registro en código → documentación derivada → comprobación automática → prueba. También exige conservar contratos reemplazados y declarar sus sucesores.

[cli/safety.py](cli/safety.py) contiene controles de contención, validación previa y patrones para detectar instrucciones maliciosas en contenido que podría convertirse en memoria del agente. La documentación también describe escrituras atómicas, historial, backups y detección de secretos.

La presencia de estos mecanismos no demuestra por sí sola su cobertura completa o efectividad: en esta revisión no se ejercieron sus rutas de ejecución.

## Hallazgos y seguimiento

### AUD-01 — Discrepancia sobre la existencia del comando `vault`

**Estado: corregida en el README actual; funcionamiento pendiente de verificar.**

En la lectura inicial, el README afirmaba que no había comando `vault` y describía una instalación mediante copia de carpetas. Sin embargo, [pyproject.toml](pyproject.toml) declaraba `vault = "vault.product_cli:main"` y existía la implementación correspondiente en [vault/product_cli.py](vault/product_cli.py).

Antes de crear este informe se releyó el README. Ahora documenta `pip install -e .` y los entry points `vault` y `vault_gobernanza`. La contradicción textual inicial ya no está presente. Este informe conserva el hallazgo y su cambio de estado; no atribuye autoría a la corrección.

**Pendiente:** comprobar el recorrido de instalación y el alcance real de las operaciones disponibles desde el paquete instalado.

### AUD-02 — Referencia residual a una limitación de copia

**Estado: observado en la relectura.**

La tabla «Qué leer después» del [README.md](README.md) todavía describe el Quick Start con la frase «con su limitación de copia indicada». La sección Quick Start consultada ahora presenta instalación con `pip install -e .` y ya no incluye el aviso inicial sobre copiar únicamente `scripts/` que aparecía en la revisión anterior.

**Impacto:** el enlace conserva una explicación que no corresponde al recorrido de instalación que encabeza la sección.

**Seguimiento propuesto:** reconciliar esa descripción con el procedimiento de instalación vigente. No se modificó el README durante la elaboración de este informe.

### AUD-03 — Complejidad de adopción

**Estado: valoración arquitectónica, no defecto demostrado.**

El proyecto combina herramientas para la memoria del agente con un conjunto amplio de herramientas para gobernar el propio estándar. También mantiene scripts históricos y distintas interfaces de acceso.

Esta estructura aporta trazabilidad y compatibilidad, pero exige explicar con claridad qué interfaz debe usar un consumidor y qué operaciones pertenecen al mantenimiento del estándar. La distinción entre estándar, toolkit y runtime del README ayuda a orientarse.

### AUD-04 — Límites de las garantías

**Estado: límite documentado.**

Una puntuación de salud o una validación estructural no demuestra que el contenido sea verdadero, completo o relevante. Las ediciones externas tampoco pasan automáticamente por los controles del toolkit. Estos límites aparecen reconocidos en el README y deben conservarse al explicar el producto.

## Verificaciones pendientes

- Ejecutar las puertas de calidad y la suite para conocer el estado operativo del checkout.
- Comprobar la instalación documentada y las operaciones accesibles mediante los entry points.
- Ejercer la captura y recuperación de contexto sobre el sandbox.
- Contrastar cualquier medida nueva con un vault ajeno en solo lectura, según las reglas del repositorio.

Estas tareas son seguimiento propuesto. No se realizaron ni se presentan como resultados de esta revisión.

## Ampliación: candidatos positivos y gaps negativos por rango

### Criterio y límites de esta clasificación

Revisión ampliada: 2026-09-25. Los rangos expresan prioridad de tratamiento, no una puntuación automática de calidad. Los identificadores POS y NEG son referencias locales de este informe; no incorporan normas al catálogo canónico.

| Rango | Negativos: urgencia de tratamiento | Positivos: prioridad de inversión |
|---|---|---|
| R1 — Crítico | Pérdida de datos o exposición grave reproducida, con alcance establecido. | Capacidad imprescindible para resolver un bloqueo crítico confirmado. |
| R2 — Alto | Riesgo concreto de pérdida, operación principal bloqueada, éxito engañoso o pérdida de contexto vinculante. | Mejora de confianza, instalación o continuidad que desbloquea el uso ordinario. |
| R3 — Medio | Cobertura insuficiente, portabilidad limitada o contrato/documentación incoherente. | Ampliación útil de cobertura, observabilidad o facilidad de adopción. |
| R4 — Bajo | Claridad, mantenimiento o detalles de uso con impacto acotado. | Mejora incremental de experiencia y presentación. |

No se asigna R1: esta revisión estática no reprodujo incidentes ni estableció su alcance. Esto no demuestra ausencia de problemas críticos.

**Evidencia:** «observado» significa visible en el código o documentación; «candidato» requiere comprobar el comportamiento en ejecución; «gap de cobertura» identifica lo que no está ejercido en las superficies revisadas. Las búsquedas de pruebas sirven para delimitar esta revisión, no para afirmar que una capacidad carece absolutamente de pruebas.

**Checkout en evolución:** al iniciar esta ampliación había cambios locales en README, documentación, catálogos y `scripts/vault_criterios.py`, además de instaladores nuevos sin seguimiento de Git. Los hallazgos sobre esos instaladores corresponden al trabajo local observado, no necesariamente a una versión publicada. En esta tarea solo se amplía este informe.

### Negativos que requieren tratamiento

#### NEG-01 · R2 · Reemplazo y eliminación sin comprobar propiedad

- **Evidencia observada:** [vault/install.py](vault/install.py), función `_install_mcp`, elimina el destino con `unlink()` si existe o es un enlace. [vault/uninstall.py](vault/uninstall.py), función `_uninstall_mcp`, aplica el mismo criterio. No verifican que el archivo o destino del enlace pertenezca a esta instalación. `install.sh` usa `ln -sf`; otros wrappers rechazan archivos normales, pero tampoco verifican el dueño de un enlace existente.
- **Consecuencia condicionada:** si `/usr/local/bin/vault-mcp` corresponde a otro archivo o instalación, podría eliminarse o reemplazarse. No se ejecutó esa operación.
- **Tratamiento:** registrar el destino administrado y verificar su propiedad antes de sustituirlo o retirarlo; ante conflicto, conservarlo y explicar el fallo. Esta es una operación de instalación del producto, por lo que debe declararse su alcance propio sin confundirla con escrituras de notas dentro del vault.
- **Cierre:** pruebas aisladas con archivo ajeno, enlace ajeno y enlace propio; los dos primeros sobreviven y producen un conflicto explícito. Referencia de diseño: contención de efectos y AP-36, con alcance de instalación por definir.

#### NEG-02 · R2 · Errores parciales terminan en éxito

- **Evidencia observada:** `_install_cli()` captura `ImportError`, imprime una advertencia y devuelve cero. `main()` de `vault/install.py` continúa tras un retorno no cero de `_install_mcp()` y acaba con «Instalación completa» y cero. `vault/uninstall.py` también devuelve cero después de un fallo de pip. Los wrappers shell contienen rutas equivalentes que imprimen advertencias sin hacer fallar el proceso.
- **Impacto:** un usuario o automatización puede interpretar una instalación incompleta como terminada.
- **Tratamiento:** propagar el resultado de cada componente solicitado y comunicar un resultado parcial explícito. No equiparar «no estaba instalado» con cualquier error de pip.
- **Cierre:** un fallo simulado de importación, pip o enlace produce código no cero y diagnóstico del componente afectado. Revisar la correspondencia con AP-37, AP-51 y el contrato de errores aplicable a estas interfaces.

#### NEG-03 · R2 · El alias MCP no coincide con la condición de arranque

- **Evidencia observada:** los instaladores crean un comando llamado `vault-mcp`. El bloque final de [vault-mcp-server.mjs](mcp/nodejs/vault-mcp-server.mjs) solo llama a `main()` cuando `process.argv[1]` termina en `vault-mcp-server.mjs` o `vault-mcp-server`.
- **Estado:** candidato funcional. Cuando Node conserve el nombre del enlace invocado en `argv[1]`, el alias instalado no arrancará el servidor. Falta ejercer el alias en los sistemas soportados.
- **Tratamiento:** diseñar un arranque compatible con el comando publicado y con la importación del módulo por las pruebas.
- **Cierre:** invocar el alias instalado desde otro directorio, comprobar `--help`, `--version` y un intercambio MCP real. AP-40/AP-42 son referencias para contrato y recorrido ejecutable.

#### NEG-04 · R2 · Fallar al cargar preferencias puede parecer ausencia de preferencias

- **Evidencia observada:** `_must_preferences()` de [scripts/vault_context_pack.py](scripts/vault_context_pack.py) devuelve `[]` si el listado devuelve `ok: false`; ante ciertas excepciones emite un error y también devuelve `[]`. El resultado principal usa esa lista para emitir `preferences_included: 0`, sin incorporar a sus `warnings` una causa específica de fallo de preferencias.
- **Impacto:** el consumidor del resultado puede confundir «no hay preferencias vinculantes» con «no se pudieron recuperar». Que se emita un diagnóstico por otro canal no resuelve esa ambigüedad en el resultado devuelto.
- **Tratamiento:** distinguir ausencia legítima, carga correcta y recuperación fallida; definir si un fallo de preferencias obligatorias bloquea el paquete o lo marca como degradado.
- **Cierre:** casos de listado fallido, excepción y lista legítimamente vacía producen resultados distinguibles. Referencia: AP-51 y contrato de errores.

#### NEG-05 · R2 · El presupuesto puede excederse por preferencias obligatorias

- **Evidencia observada:** `vault_context_pack()` agrega el bloque de preferencias antes de comprobar el coste de las notas. No comprueba si ese bloque más la cabecera ya excede `budget_tokens`. El resultado puede seguir siendo `ok: true`, con `used` mayor que `budget` y `remaining` fijado en cero, sin advertencia específica de exceso.
- **Impacto:** la prioridad de las preferencias está declarada, pero el consumidor necesita conocer que el paquete ya no cabe en su presupuesto.
- **Tratamiento:** conservar las preferencias y declarar un estado de presupuesto insuficiente, el mínimo requerido y el exceso; no descartarlas silenciosamente para hacer cuadrar la cifra.
- **Cierre:** presupuesto menor que las preferencias, igual al coste obligatorio y mayor que este, con un contrato inequívoco para cada caso. Contrastar la medida de tokens con el criterio del consumidor conforme a AP-44.

#### NEG-06 · R2 · CI no instala explícitamente la dependencia de runtime

- **Evidencia observada:** [.github/workflows/vault-ci.yml](.github/workflows/vault-ci.yml) instala `pytest` y `pytest-cov`, pero no el proyecto ni PyYAML. [pyproject.toml](pyproject.toml) declara PyYAML; módulos como `vault/autoria/conocimiento.py`, `vault/gobernanza/base.py` y pruebas importan `yaml` directamente.
- **Estado:** gap de reproducibilidad. El resultado dependerá de lo que ya tenga la imagen del runner; no se consultaron ejecuciones de CI ni se reprodujo un entorno limpio.
- **Tratamiento:** instalar las dependencias desde la declaración canónica del proyecto antes de ejecutar la suite.
- **Cierre:** CI en un entorno sin paquetes heredados, con las dependencias resueltas por el mecanismo de instalación declarado.

#### NEG-07 · R3 · Pruebas de instalación limpia fuera del recorrido CI observado

- **Evidencia observada:** [tests/clean_install_gate.py](tests/clean_install_gate.py) declara expresamente que no se recoge como pytest. Existen también `runtime_lifecycle_gate.py` y `memory_recovery_e2e_gate.py`. No se encontraron invocaciones explícitas de esos archivos en el workflow revisado ni en `scripts/vault_gate.py`.
- **Impacto:** que existan pruebas de wheel, instalación y recuperación no asegura que cada cambio las ejecute. Una instalación editable puede ocultar dependencias del checkout.
- **Tratamiento:** integrar las comprobaciones de producto pertinentes en el recorrido automatizado y declarar sus dependencias, incluido el constructor de wheel. Alinear primero sus destinos temporales con las reglas de ejecución del repositorio.
- **Cierre:** una ejecución automatizada demuestra instalación y uso desde un directorio independiente, sin `scripts/` ni checkout disponibles como fallback.

#### NEG-08 · R3 · Instalación MCP con supuestos de plataforma y recursos incompletos

- **Evidencia observada:** `vault/install.py` fija `/usr/local/bin/vault-mcp` sin distinguir Windows de sistemas POSIX. Si falla el enlace, propone copiar únicamente el `.mjs`; el servidor carga `env-table.json` y `tools-catalog.json` relativos a su ubicación, y calcula desde ella la ruta de `scripts/`.
- **Impacto:** el instalador no expresa una ruta específica para Windows; copiar solo el archivo no conserva los recursos y rutas que necesita el servidor.
- **Tratamiento:** definir instalación por plataforma y un launcher que conserve el conjunto de recursos. La alternativa de copia debe cumplir el contrato completo.
- **Cierre:** instalación desde un directorio con espacios en Windows y Linux; arranque con recursos presentes y error claro cuando falte alguno. macOS debe seguir declarado como pendiente hasta tener evidencia.

#### NEG-09 · R3 · Registro de producción desactualizado sobre los entry points

- **Evidencia observada:** `PREGUNTAS['ergonomia_de_entrada']` —entrada identificada por `id` dentro del registro— en [scripts/vault_produccion.py](scripts/vault_produccion.py) sigue afirmando que no existe `[project.scripts]`. Su predicado comprueba precisamente la existencia de esa sección, que ya está en `pyproject.toml`. La guía derivada conserva el texto antiguo.
- **Impacto:** corregir el README cerró AUD-01 en esa superficie, pero no cerró la incoherencia del registro y su documentación derivada.
- **Tratamiento:** actualizar el registro con el alcance real del comando instalado y regenerar la guía. La existencia del entry point no demuestra que todas las herramientas sean instalables.
- **Cierre:** registro, guía, README y prueba de instalación describen la misma capacidad. Referencias: fuente canónica primero y AP-47/AP-55.

#### NEG-10 · R3 · Comprobaciones de CI convierten errores en mensajes informativos

- **Evidencia observada:** el workflow añade `|| echo "… not yet implemented"` a las llamadas de `vault_validate`, `vault_audit --dry-run` y `vault_spec_validate`.
- **Impacto:** en shells que aceptan esa expresión, el paso puede terminar correctamente aunque la herramienta falle por un defecto real. Otros gates pueden cubrir parte del comportamiento; no se concluye que toda la CI permita esos fallos.
- **Tratamiento:** separar capacidad no implementada de ejecución fallida y decidir qué comprobaciones son obligatorias. Propagar los fallos de estas últimas.
- **Cierre:** introducir un fallo controlado en cada comprobación obligatoria hace fallar su paso, con la causa original visible.

#### NEG-11 · R4 · Descripciones de recorte y dry-run necesitan precisión

- **Evidencia observada:** el docstring de `vault_context_pack.py` afirma que no parte notas, pero el empaquetado llama a `_truncate_to_tokens()` y publica `truncated`. La trazabilidad del recorte existe; la explicación inicial es demasiado absoluta.
- **Evidencia adicional:** `install.sh` y `uninstall.sh` procesan `--dry-run` con salida inmediata dentro del bucle de argumentos; si aparece antes de `--mcp`, la vista previa no incluye ese componente.
- **Tratamiento:** documentar que se seleccionan notas y se entregan extractos marcados; analizar todos los argumentos antes de generar una vista previa. Mantener aquí el seguimiento de AUD-02, la referencia residual a la copia en el README.
- **Cierre:** ayuda y resultado coinciden; reordenar las opciones no cambia las acciones descritas por dry-run.

### Positivos: candidatos para mejorar y ampliar

Estas propuestas aprovechan mecanismos existentes. Su prioridad expresa valor esperado; no afirma que ya estén implementadas ni justifica ampliar el catálogo sin una capacidad de negocio concreta.

| ID / rango | Tipo | Base observada y candidato | Beneficio y criterio de aceptación |
|---|---|---|---|
| POS-01 · R2 | Mejorar | Aprovechar `tests/clean_install_gate.py` y las pruebas de ciclo de vida/recuperación para consolidar un recorrido de consumidor automatizado. | Instalación, inicialización, escritura y recuperación funcionan sin depender del checkout. Conecta con NEG-06 y NEG-07. |
| POS-02 · R2 | Mejorar | Unificar el contrato de instalación y desinstalación que hoy repiten Python y shell. | Mismos resultados, propiedad de destinos y códigos de salida en cada interfaz. Conecta con NEG-01, NEG-02, NEG-03 y NEG-08. |
| POS-03 · R2 | Mejorar | Usar los campos existentes `included`, `excluded`, `warnings` y `tokens` para explicar presupuesto y degradación del contexto. | El consumidor distingue contexto completo, parcial, sin preferencias recuperables y con presupuesto insuficiente. Conecta con NEG-04 y NEG-05. |
| POS-04 · R3 | Ampliar | Derivar una matriz de disponibilidad desde `execution_module` y los estados de `vault/meta_toolkit/resolucion_producto.py`. | Mostrar qué operación está instalada, cuál requiere el checkout y cuál mantiene el estándar, sin duplicar listas a mano. |
| POS-05 · R3 | Ampliar | Crear un conjunto de consultas de evaluación con notas relevantes identificadas por el consumidor. | Medir si la recuperación devuelve decisiones útiles, omisiones y coste de tokens; incluir un contraste de solo lectura con un vault preexistente autorizado según AP-44. No requiere embeddings ni servicios externos. |
| POS-06 · R3 | Ampliar | Ampliar evidencia de instalación por plataforma usando la matriz actual Windows/Linux. | Ejercer alias, rutas con espacios y recursos MCP en ambos sistemas; incorporar macOS solo cuando exista ejecutor y promesa explícita. |
| POS-07 · R4 | Mejorar | Convertir las guías de producto y las capas conceptuales existentes en un recorrido breve para el primer uso. | Una persona identifica qué instalar, cómo señalar su vault y cómo guardar y recuperar una decisión, con ejemplos comprobables y documentación derivada donde corresponda. |

### Orden recomendado de tratamiento

1. **Integridad de la instalación:** NEG-01 y NEG-02; después comprobar y resolver NEG-03 y NEG-08. POS-02 reúne el contrato común.
2. **Confianza del contexto:** NEG-04 y NEG-05, apoyados por POS-03.
3. **Evidencia automatizada:** NEG-06, NEG-07 y NEG-10; aprovechar POS-01 para validar el producto desde fuera del checkout.
4. **Coherencia y claridad:** NEG-09, NEG-11 y AUD-02; derivar disponibilidad con POS-04.
5. **Ampliaciones:** POS-05, POS-06 y POS-07, según las necesidades reales del consumidor.

El orden combina prioridad y dependencias; R3 no obliga a esperar cuando su arreglo sea necesario para cerrar un R2.

### Condiciones para cerrar los candidatos

Al implementar una corrección se aplicará el ciclo del repositorio: síntoma → norma existente o nueva justificada → guard, audit y heal según corresponda → prueba. Las referencias normativas de este informe son puntos de partida para revisar el catálogo, no declaraciones de cobertura ya demostrada.

Una ampliación de medida exige el contraste externo previsto por AP-44. Los artefactos derivados se regeneran desde su dueño canónico. Una baseline no se amplía para ocultar deuda nueva y un hallazgo resuelto se conserva con su evidencia de cierre.

Esta ampliación solo examinó archivos y documentó candidatos. No ejecutó instaladores, servidores, gates, suite ni operaciones sobre vaults; tampoco corrigió los problemas enumerados. Las pruebas descritas son criterios futuros de aceptación.

## Auditoría de flujos: crashes y bloqueos de avance

Continuación y cierre documental: 2026-09-26. Esta sección amplía la revisión estática anterior con reproducciones controladas. Las afirmaciones anteriores de «no ejecutado» describen aquella etapa; la evidencia de ejecución de esta etapa se detalla aquí.

### Alcance y evidencia conservada

Se revisaron los flujos de empaquetado → arranque, instalación → verificación, inicialización → diagnóstico, escritura → recuperación, consulta → contexto y comando de auditoría en CI.

Las reproducciones se hicieron en Windows, con el Python disponible en el entorno (3.14). Se fijaron `VAULT_ROOT` al sandbox y `VAULT_STRICT_ROOT=1`; se comprobó origen `env`. No se instalaron paquetes globales, no se modificaron launchers del sistema, no se arrancaron servidores persistentes y no se accedió a vaults ajenos.

- [Resultados de runtime y contexto](vault-sandbox/audit-flows-20260925/runtime-results.json).
- [Resultados de distribución, entrada MCP y argumento de CI](vault-sandbox/audit-flows-20260925/distribution-results.json).
- [Programa de reproducción de runtime](vault-sandbox/audit-flows-20260925/probe.py).
- [Programa de reproducción de distribución](vault-sandbox/audit-flows-20260925/distribution_probe.py).

Los datos desechables y las fuentes copiadas se conservaron en ZIP dentro de esa misma carpeta. Se retiraron sus directorios expandidos para que las notas deliberadamente dañadas no contaminen futuras auditorías del sandbox. Las rutas absolutas que aparecen en los resultados identifican ubicaciones anteriores al archivado.

La prueba de distribución construyó un wheel desde una copia de `pyproject.toml`, README, licencia, `vault/`, `vault_toolkit/` y `scripts/`. Se extrajo el wheel y se importó su CLI con Python `-I`, agregando únicamente el directorio extraído. Esto comprueba el contenido y el arranque del artefacto; no sustituye una instalación completa en cada plataforma.

No se ejecutaron la suite completa ni todas las puertas. Los escenarios con permisos denegados, fallo de catálogo y preferencias inaccesibles usan simulación explícita; no representan incidentes observados en el sistema real.

### Resumen priorizado

| ID | Rango | Flujo | Resultado observado |
|---|---|---|---|
| FL-01 | R1 | Guardar conocimiento de dos proyectos | El segundo guardado reemplaza la nota del primero y ambos devuelven éxito. |
| FL-02 | R2 | Construir wheel → abrir CLI | `ModuleNotFoundError: No module named 'vault_toolkit'` antes de mostrar ayuda. |
| FL-03 | R2 | Guardar/recuperar título con `---` | `ScannerError` o pérdida de metadatos en la lectura, según el título. |
| FL-04 | R2 | Recuperar conocimiento con una fecha YAML inválida | `ValueError` aborta la recuperación completa. |
| FL-05 | R2 | Diagnosticar → reinicializar runtime dañado | `doctor` lanza `TypeError`; `init` responde que ya está inicializado correctamente. |
| FL-06 | R2 | Inicializar o desinstalar con permisos denegados | Excepciones de permisos simuladas escapan del flujo sin resultado controlado. |
| FL-07 | R2 | Verificar instalación con `python -m vault.product_cli` | Salida cero y vacía: no se ejecuta `main()`. |
| FL-08 | R3 | Diagnosticar runtime incompleto → reparar | La CLI descarta la lista de elementos faltantes que el dominio sí devuelve. |

FL-01 eleva la prioridad respecto de la etapa estática: ahora hay pérdida de contenido reproducida en una ruta concreta. R1 se limita a esa colisión de escritura; no implica pérdida demostrada en todos los adaptadores ni en vaults reales.

### FL-01 — Colisión entre notas de distintos proyectos

**Recorrido:** `guardar_conocimiento()` en [vault/autoria/conocimiento.py](vault/autoria/conocimiento.py) → ruta por categoría y slug del título → `_atomic_write()` → `escritura_atomica()` → `os.replace()`.

**Reproducción:** guardar categoría `concept`, título `Misma decision`, proyecto A y contenido A; repetir título y categoría con proyecto B y contenido B. Las dos respuestas son `ok: true` y apuntan a `07_Knowledge/concepts/misma-decision.md`. El archivo final contiene B y la búsqueda filtrada por A devuelve cero resultados.

**Causa:** `project` no participa en la identidad del destino y esta ruta no comprueba existencia, conflicto ni actualización intencionada. El escritor predeterminado sustituye el archivo sin conservar una revisión anterior en este recorrido.

**Alcance:** reproducido en la función estable y su escritor predeterminado, que usa el módulo empaquetado `vault.autoria.knowledge_save`. El adaptador legacy inyecta otro escritor; la prueba no demuestra que sus políticas de historial sean idénticas.

**Tratamiento:** definir identidad y política de actualización explícitas. Un segundo proyecto no debe sustituir silenciosamente una nota del primero. Conservar compatibilidad de rutas y enlaces; no resolverlo moviendo notas existentes sin migración.

**Cierre:** ambas notas permanecen recuperables o el segundo guardado devuelve conflicto sin cambiar la primera. Probar también títulos distintos que convergen al mismo slug y actualización autorizada con conservación de identidad e historial. Revisar el contrato de no-derogación y la norma aplicable antes de implementar.

### FL-02 — El wheel omite un paquete requerido para arrancar

**Recorrido:** [pyproject.toml](pyproject.toml) enumera los paquetes → wheel generado → `vault.product_cli` importa `vault.kernel.adaptadores` → este importa `vault_toolkit.loading`.

**Reproducción:** el wheel se construye correctamente, contiene `vault/product_cli.py`, pero no contiene `vault_toolkit/`. Importar su CLI desde el artefacto extraído termina con código 1 y `ModuleNotFoundError`, antes de procesar `--help`.

**Causa:** el paquete importado no aparece en la lista explícita de distribución. Además, el catálogo local apunta operaciones a `vault_toolkit.operations.*`, cuyos wrappers recurren a módulos históricos; añadir solo el paquete superior podría dejar otra dependencia sin distribuir.

**Tratamiento:** cerrar la frontera instalable de extremo a extremo: paquetes, implementaciones, recursos y catálogo. No dar por terminado el arreglo únicamente porque la ayuda abra dentro del checkout.

**Cierre:** wheel instalado en entorno limpio; ejecutar ayuda, versión, listado, inicialización, consulta y escritura/lectura sin checkout ni fallback a `scripts/`. Referencias: AP-42 y criterio del consumidor AP-44.

### FL-03 — Separación del frontmatter por una subcadena del título

**Recorrido:** `_render()` produce YAML → `_validate_frontmatter()` usa `text.split('---', 2)`; `_split_markdown()` repite el mismo criterio al leer.

**Reproducción real:** `Titulo: --- ejemplo` provoca `ScannerError` en el guardado. `Titulo---simple` se guarda con éxito, pero una consulta posterior con su proyecto no encuentra la nota.

**Causa:** el separador se reconoce en cualquier posición, incluso dentro de un valor YAML. En el primer caso corta un escalar entre comillas; en el segundo permite analizar solo un fragmento del frontmatter, perdiendo `project` y otros campos. La excepción YAML del primer caso no está contenida por el `except (OSError, ValueError)` del guardado.

**Tratamiento:** delegar la delimitación y lectura al dueño canónico del frontmatter, respetando separadores de línea y el contrato del parser real. Evitar otra implementación de parsing en paralelo.

**Cierre:** ida y vuelta íntegra de títulos, valores y cuerpos que contengan `---`; notas recuperables por categoría y proyecto. Referencias: AP-44, AP-46, AP-57 y AP-61.

### FL-04 — Una fecha inválida interrumpe todas las búsquedas

**Recorrido:** `recuperar_conocimiento()` recorre Markdown → `_split_markdown()` → `yaml.safe_load()`.

**Reproducción real:** una nota de prueba con `createdAt: 2026-99-99` produce `ValueError: month must be in 1..12, not 99`. La consulta aborta antes de devolver las notas sanas.

**Causa:** `_split_markdown()` contiene `yaml.YAMLError` y `RecursionError`, pero la conversión de fecha lanza `ValueError`. El bucle lector solo contiene errores de lectura y decodificación.

**Tratamiento:** usar el parser canónico que contiene las excepciones reales y reportar degradación por archivo. Un fallo de una nota no debe convertirse en ausencia silenciosa de resultados ni derribar toda la búsqueda.

**Cierre:** la nota defectuosa queda identificada, los documentos válidos se recuperan y el resultado declara lectura parcial. Referencias: AP-51 y AP-61.

### FL-05 — Diagnóstico y reconocimiento de runtime discrepan

**Recorrido:** [vault/ciclo_de_vida/producto.py](vault/ciclo_de_vida/producto.py), `diagnosticar_runtime()` lee `standard-version.json`; `_initialized()` decide si `inicializar_runtime()` puede responder idempotentemente.

**Reproducción real:** tras inicializar un runtime desechable, sustituir el JSON de versión por `[]`. `doctor` termina con `TypeError: list indices must be integers or slices, not str`. Sobre ese mismo directorio, `init` responde `ok: true`, `INIT_ALREADY_EXISTS`.

**Causa:** el diagnóstico indexa el JSON antes de comprobar que sea un objeto; `_initialized()` solo comprueba existencia de rutas y no valida contenido ni tipos de todos los elementos.

**Tratamiento:** validar esquema antes de acceder a campos y compartir el criterio de runtime válido entre diagnóstico e idempotencia. Ante corrupción, explicar la reparación necesaria sin sobrescribir el runtime.

**Cierre:** JSON objeto, lista, null, escalar, versión inválida y sección sustituida por archivo producen estados coherentes y controlados. Ningún runtime declarado inválido por el diagnóstico obtiene éxito de inicialización como si estuviera sano.

### FL-06 — Permisos denegados fuera del manejo de errores

**Evidencia simulada:** forzar `PermissionError` en `tempfile.mkdtemp()` de `inicializar_runtime()` deja escapar la excepción, porque la creación de staging ocurre antes del `try` que maneja el resto de la inicialización. Forzar el mismo error en `unlink()` del desinstalador también deja escapar la excepción.

**Evidencia estática complementaria:** en `vault/install.py`, crear el directorio padre y eliminar el destino ocurren antes del `try` dedicado a crear el symlink.

**Tratamiento:** definir el resultado de errores de permisos para el flujo completo, incluyendo preparación y limpieza, con código no cero, operación fallida y ruta relevante. Mantener la comprobación de propiedad de NEG-01 antes de cualquier eliminación.

**Cierre:** permisos simulados y reales sobre datos de prueba producen diagnósticos controlados sin mensajes de finalización exitosa. Un destino ya ausente sigue siendo una desinstalación idempotente legítima.

### FL-07 — La verificación por módulo da un falso positivo

**Recorrido:** `install.sh` ejecuta `python -m vault.product_cli --help` para verificar la CLI.

**Reproducción real en el checkout:** retorno cero, stdout vacío y stderr vacío. [vault/product_cli.py](vault/product_cli.py) define `main()` pero no lo llama al ejecutarse como módulo.

**Impacto:** la verificación del instalador puede imprimir OK sin haber procesado la ayuda ni probado un comando. El entry point `vault = vault.product_cli:main` sí llama la función; son superficies diferentes.

**Tratamiento:** verificar el entry point realmente instalado y su salida esperada. Si se mantiene y publica la ejecución `python -m`, darle su propio arranque efectivo.

**Cierre:** el comando de verificación produce ayuda reconocible y falla si no puede abrir el programa. La prueba debe ejercer la interfaz que utilizará el consumidor.

### FL-08 — Se pierde información necesaria para reparar

**Reproducción real:** el diagnóstico de un runtime incompleto devuelve `SYSTEM_FILES_MISSING` y una lista `missing`. Pasar por `product_cli.main(['doctor', ruta])` devuelve código 8 y un envelope `INVALID_ACTION`, pero elimina `missing` y la ruta del runtime.

**Causa:** `_lifecycle_result()` transforma cualquier fallo en `_error(state, detail, code)` sin conservar los campos específicos del resultado original. El hint genérico pide revisar `--help`, aunque el dominio ya identificó lo que falta.

**Tratamiento:** conservar contexto y campos de recuperación al traducir el fallo al contrato público. Usar la causa adecuada sin degradar todos los problemas de runtime a acción inválida.

**Cierre:** el usuario recibe los elementos faltantes y la raíz afectada desde la CLI, sin tener que invocar internamente el dominio. Revisar AP-52 y la traducción canónica de causas.

### Hallazgos anteriores contrastados en ejecución

| Referencia | Caso | Evidencia nueva y límite |
|---|---|---|
| NEG-02 | Instalación MCP devuelve 1 | Con el componente simulado en fallo y CLI simulada correcta, `install.main(['--mcp'])` devuelve 0 y anuncia instalación completa. |
| NEG-03 | Nombre `vault-mcp` | Simular ese `process.argv` e importar el servidor devuelve cero sin ayuda; invocar el nombre original con `--help` sí imprime ayuda. Falta instalar e invocar el enlace real por plataforma. |
| NEG-04 | Listado de preferencias falla | Simular `ok: false` en el listado produce `[]` desde `_must_preferences()`. |
| NEG-05 | Preferencias superan presupuesto | Con preferencias sintéticas y presupuesto de 10, el paquete informa `used: 431`, `ok: true`, sin advertencia específica del exceso. |
| NEG-10 | Paso CI de auditoría | Ejecutar `vault_audit.py --dry-run` devuelve código 2: argumento no reconocido. No alcanza a auditar el vault. |

### Diferencias de superficie y candidatos todavía abiertos

- **Contrato de raíz:** el módulo `vault.autoria.knowledge_save` requiere `--root`, mientras el catálogo local dirige `vault run vault_knowledge_save` a un wrapper legacy que lo rechaza. Se reprodujo el rechazo con salida 7. La interfaz legacy se configura mediante `VAULT_ROOT`; rechazar `--root` no prueba por sí solo un defecto en esa interfaz. El gap es documentar y comprobar la transición entre superficies para que un ejemplo del módulo estable no se presente como ejemplo intercambiable del catálogo.
- **Catálogo ilegible:** al simular `ValueError` desde el lector de catálogo, `vault tools list` deja escapar la excepción. Falta ensayar todos los casos de recurso ausente, malformado y semánticamente divergente sobre el paquete instalado. Debe fallar explícitamente, pero con diagnóstico de instalación recuperable.
- **Pérdida del contrato en el adaptador:** `ToolsCatalogAdapter._to_fragment()` entrega listas vacías para `guards`, `side_effects` y `required_args`; `NormCatalogAdapter.enforcement_de()` pide un atributo que `ToolProducto` no declara. Evidencia estática de metadatos descartados; falta medir qué bloqueos o falsos permisos causa en cada operación antes de atribuirle un incidente.
- **HTTP/MCP:** el callback HTTP asíncrono y el arranque del listener merecen pruebas específicas de puerto ocupado, desconexión y solicitud inválida. No se reprodujeron en esta tanda y no se consideran crashes confirmados.

### Controles que sí avanzaron

La inicialización normal del runtime de prueba devolvió `INIT_CREATED`, y su diagnóstico inicial devolvió `RUNTIME_OK`. La consulta posicional por la función del entry point público produjo JSON y código cero en el checkout. La ayuda del servidor MCP usando su nombre original también funcionó. Estos controles delimitan los fallos: el resultado depende de la entrada, la interfaz y la forma de distribución.

### Orden de corrección tras las reproducciones

1. **FL-01:** impedir sustituciones silenciosas entre notas distintas y conservar trazabilidad.
2. **FL-02:** cerrar el contenido del wheel y verificar el producto fuera del checkout.
3. **FL-03 y FL-04:** resolver el parsing de frontmatter con su dueño canónico; una nota no debe bloquear guardado o recuperación global.
4. **FL-05 y FL-08:** unificar reconocimiento de runtime y conservar el diagnóstico de reparación.
5. **FL-06, FL-07 y NEG-01/02/03/10:** cerrar permisos, verificaciones reales, alias y comandos CI.
6. **NEG-04/05:** hacer explícitos la degradación de preferencias y el exceso de presupuesto.

Los hallazgos están documentados, no corregidos. Cada corrección requiere el ciclo norma → guard/audit/heal aplicable → prueba, seguido de las puertas y suite exigidas por el repositorio. Este informe y sus evidencias son locales: `auditado.md` figura actualmente en `.gitignore` y el sandbox contiene artefactos de ejecución, no una publicación de la auditoría.
