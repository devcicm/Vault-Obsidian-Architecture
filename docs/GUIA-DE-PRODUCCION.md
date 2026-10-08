# Guía de construcción — las preguntas que no se hace el repo a sí mismo

> **Documento derivado.** Sale de `scripts/vault_produccion.PREGUNTAS` y se
> regenera con `python scripts/vault_produccion.py --guia`. Lo que se escriba
> a mano aquí se pierde: es lo que lo mantiene honesto.

## De dónde sale

De una pregunta hecha con todas las puertas en verde y una versión recién
cerrada: **«¿ya puede usarlo otra persona, aparte de mí, y con resultados
fiables?»**. En menos de diez minutos apareció un defecto que ninguna puerta
veía —el piso de Python prometido que ninguna máquina ejecutaba—, porque
todas las puertas miden *el repo contra sí mismo* y en esa sala no está el
consumidor.

El patrón es siempre el mismo, y es el de toda la tanda v40.30:

```
alcance declarado  >  alcance ejercido   ⇒   el hueco devuelve CERO,
                                             y un cero se lee como limpio.
```

Por eso la pregunta se hace **antes** de dar algo por terminado, y por eso
está escrita como registro ejecutable y no como recordatorio.

## Cómo se usa en construcción

1. Antes de cerrar una versión, `python scripts/vault_produccion.py --check --strict`.
2. Cuando añadas una promesa al consumidor —una versión soportada, una
   plataforma, una dependencia opcional, una superficie de red— **añade su fila**
   con el predicado que la ejerce. Una promesa sin fila no la mide nadie.
3. Si no tiene ejecutor, se declara `descubierta` **con el motivo escrito**. No
   es un fallo: es la forma barata. Lo que rompe la puerta es una promesa
   marcada como cubierta cuyo ejecutor ya no existe — una mentira comprobable.

## Estado

| Promesa | Pregunta | Estado | Quién la ejerce |
|---|---|---|---|
| `piso_de_lenguaje` | ¿La versión mínima que promete el paquete la ejecuta alguien? | ✅ cubierta | matriz python-version de .github/workflows/vault-ci.yml + tests/test_piso_python.py |
| `dependencias_reales` | ¿Lo que se importa sin red está declarado como dependencia? | ✅ cubierta | pyproject.toml [project.dependencies] |
| `instalacion_fuera_del_repo` | ¿Funciona copiado fuera de este repositorio? | ✅ cubierta | tests/test_portabilidad_v4030.py + README.md (instrucciones de instalación inlined) |
| `material_ajeno` | ¿Se ha medido contra material que este repo no generó? | ✅ cubierta | vault_foreign_check --root <vault ajeno>, o --self-test sin uno a mano |
| `sistemas_operativos` | ¿Se ejecuta en los sistemas donde se dice que corre? | ✅ cubierta | matriz os de la CI (ubuntu-latest, windows-latest) |
| `superficie_expuesta` | ¿Está escrito qué expone y a quién, donde lo lee quien instala? | ✅ cubierta | tests/test_mcp_http_seguridad.py (servidor real por HTTP) + README.md |
| `ergonomia_de_entrada` | ¿Se invoca como un programa o como un montón de scripts? | ✅ cubierta | vault/meta_toolkit/tools-catalog.json + empaquetado/fuera-de-la-wheel.json + `vault run` en tests/clean_install_gate.py |
| `mcp_requiere_checkout` | ¿Se puede instalar el servidor MCP con un solo comando de pip/npm? | ✅ cubierta | pyproject.toml (package data) + vault mcp-path + tests/test_mcp_instalado.py + tests/clean_install_gate.py |
| `contrato_con_quien_contribuye` | ¿Sabe alguien de fuera cómo aportar o cómo reportar un fallo? | ✅ cubierta | README.md (sección «Estado del proyecto») |
| `lo_publicado_es_solo_el_estandar` | ¿Puede irse en un push algo que no es de este repo? | ✅ cubierta | tests/test_publicacion_limpia.py (mide el índice de git, no el disco) |
| `wheel_instalada_funciona` | ¿Funciona la wheel instalada en un venv limpio fuera del repo? | ✅ cubierta | tests/run_product_gates.py (clean_install + memory_e2e) + job 'product-gates' en vault-ci.yml |
| `madurez_declarada` | ¿El grado de madurez publicado lo sostiene este registro? | ✅ cubierta | vault_produccion._madurez_coherente + tests/test_produccion.py |
| `wheel_sin_gobernanza` | ¿Lo que instalo es el producto, o también las herramientas que miden este repo? | ✅ cubierta | empaquetado/construir.py + vault_servicio --check (invariante 11) + tests/clean_install_gate.py |
| `memoria_para_agentes` | ¿Un agente LLM que solo ve el MCP consigue orientarse, escribir, recordar, recuperarse y borrar? | ✅ cubierta | tests/banco_agente.py (sesión MCP con VAULT_MCP_PERFIL=agente) + tests/test_banco_agente.py |
| `sbom_y_licencias` | ¿Sabe quien instala qué paquetes recibe y bajo qué licencia? | ✅ cubierta | empaquetado/sbom.py en el job product-gates de la CI + tests/test_sbom.py |
| `politica_de_vulnerabilidades` | ¿Sabe quien encuentra un fallo de seguridad por dónde avisar sin publicarlo? | ✅ cubierta | SECURITY.md (secciones de SECCIONES_SECURITY) + tests/test_produccion_iso.py |

## Los huecos, escritos

**`sistemas_operativos` — cubierta con hueco.** La CI declara la suite y las product gates en ubuntu, pero esta rama no ha pasado por la CI. El paseo de INSTALACIÓN fuera del repo se ha hecho de forma recurrente en Windows y una vez a mano en Linux (2026-10-04, wheel 40.35 en python:3.12-slim con usuario sin privilegios: 16/16); en Linux no lo repite ninguna máquina. macOS no lo toca nadie. Las instrucciones de instalación están inlined en README.md.

**`lo_publicado_es_solo_el_estandar` — cubierta con hueco.** Mide el índice de HOY. Lo que ya esté en un commit anterior del historial no lo ve nadie: para eso haría falta recorrer todos los árboles, y este repo nunca ha versionado esos directorios.

**`memoria_para_agentes` — cubierta con hueco.** La suite ejerce las cinco tareas sobre un vault que crea el propio repo. El recuerdo sobre notas preexistentes de un vault ajeno (--copiar-de, regla 7) es una medida que se ejecuta a mano sobre copias y se reporta; no la repite la CI. Sin Node en el PATH el test se salta, y esta rama no ha pasado por la CI.

**`sbom_y_licencias` — cubierta con hueco.** El SBOM se publica como artefacto de la CI, no viaja dentro de la wheel. Cubre las dependencias directas; las transitivas no, porque PyYAML no tiene. Esta rama no ha pasado por la CI.

**`politica_de_vulnerabilidades` — cubierta con hueco.** El canal es el reporte privado de vulnerabilidades de GitHub, y solo funciona si el dueño lo activa en la configuración del repositorio; desde aquí no se puede comprobar.

## Qué NO demuestra el verde

Que toda promesa **listada** tiene ejecutor. No que la lista esté completa:
una promesa que nadie escribió en el registro sigue sin medirse, y esta tool
no puede leer lo que prometiste en un README que no conoce. El registro se
amplía cuando alguien tropieza — que es exactamente como nació.
