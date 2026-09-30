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
| `ergonomia_de_entrada` | ¿Se invoca como un programa o como un montón de scripts? | ✅ descubierta | catalogo_producto + distribucion.py |
| `mcp_requiere_checkout` | ¿Se puede instalar el servidor MCP con un solo comando de pip/npm? | ✅ descubierta | README.md + docs/INSTALACION.md |
| `contrato_con_quien_contribuye` | ¿Sabe alguien de fuera cómo aportar o cómo reportar un fallo? | ✅ cubierta | README.md (sección «Estado del proyecto») |
| `lo_publicado_es_solo_el_estandar` | ¿Puede irse en un push algo que no es de este repo? | ✅ cubierta | tests/test_publicacion_limpia.py (mide el índice de git, no el disco) |
| `wheel_instalada_funciona` | ¿Funciona la wheel instalada en un venv limpio fuera del repo? | ✅ descubierta | tests/run_product_gates.py + job 'product-gates' en vault-ci.yml |

## Los huecos, escritos

**`sistemas_operativos` — cubierta con hueco.** La CI ejecuta la suite en ubuntu, pero el paseo de INSTALACIÓN fuera del repo solo se ha hecho en Windows. macOS no lo toca nadie. Las instrucciones de instalación están inlined en README.md.

**`ergonomia_de_entrada` — descubierta.** [project.scripts] ya existe en pyproject.toml (`vault = vault.product_cli:main`), y vault es invocable. El hueco real (A2) es que `execution_module` está vacío en el catálogo del producto para 89 de las 93 tools runtime, así que `vault run` solo resuelve las 4 que lo tienen declarado.

*Por qué se deja así:* El catálogo del producto (tools-catalog.json) se genera desde TOOLS_CATALOG con execution_module=null para la mayoría de las tools. La solución (A2) es auto-derivar execution_module = vault_toolkit.operations.<tool> en catalogo_producto cuando script existe y execution_module es null, igual que hace distribucion.py en el source. La decisión ya está tomada en el código; falta persistirla en el artefacto.

**`mcp_requiere_checkout` — descubierta.** El servidor MCP vive en `mcp/nodejs/` y no está publicado en npm. No hay `npm install -g @carloseam/vault-mcp` ni nada equivalente: el único camino para levantarlo es un git clone de este repo y `node mcp/nodejs/vault-mcp-server.mjs`. Quien llegue buscando instrucciones de instalación estándar no las encuentra.

*Por qué se deja así:* Publicar el servidor en npm resolvería la expectativa pero ata el nombre público y exige mantener un paquete conRelease flow. La decisión de producto no tomada es si el servidor MCP es parte del producto que se publica o una herramienta de desarrollo del estándar. Mientras tanto, la promesa realista es «git clone + node».

**`lo_publicado_es_solo_el_estandar` — cubierta con hueco.** Mide el índice de HOY. Lo que ya esté en un commit anterior del historial no lo ve nadie: para eso haría falta recorrer todos los árboles, y este repo nunca ha versionado esos directorios.

**`wheel_instalada_funciona` — descubierta.** La wheel puede armarse mal y pasar los tests del repo (que usan el source) pero fallar en un venv limpio (que solo tiene lo instalado).

*Por qué se deja así:* La promesa existe (run_product_gates.py + CI) pero nunca se ha ejecutado contra un venv limpio real fuera de este repo. El gate ejecuta la wheel desde el mismo checkout fuente, así que el test no garantiza que la wheel funcione aislada. Pendiente: ejecutar run_product_gates.py en un CI separado o desde una maquina limpia que no tenga este repo.

## Qué NO demuestra el verde

Que toda promesa **listada** tiene ejecutor. No que la lista esté completa:
una promesa que nadie escribió en el registro sigue sin medirse, y esta tool
no puede leer lo que prometiste en un README que no conoce. El registro se
amplía cuando alguien tropieza — que es exactamente como nació.
