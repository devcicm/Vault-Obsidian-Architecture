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
| `instalacion_fuera_del_repo` | ¿Funciona copiado fuera de este repositorio? | ✅ cubierta | tests/test_portabilidad_v4030.py + INSTALL.md |
| `material_ajeno` | ¿Se ha medido contra material que este repo no generó? | ✅ cubierta | vault_foreign_check --root <vault ajeno>, o --self-test sin uno a mano |
| `sistemas_operativos` | ¿Se ejecuta en los sistemas donde se dice que corre? | ✅ cubierta | matriz os de la CI (ubuntu-latest, windows-latest) |
| `superficie_expuesta` | ¿Está escrito qué expone y a quién, donde lo lee quien instala? | ✅ cubierta | INSTALL.md, sección «Servidor MCP» |
| `ergonomia_de_entrada` | ¿Se invoca como un programa o como un montón de scripts? | ⚠️ descubierta | — |
| `contrato_con_quien_contribuye` | ¿Sabe alguien de fuera cómo aportar o cómo reportar un fallo? | ✅ cubierta | CONTRIBUTING.md + SECURITY.md |
| `lo_publicado_es_solo_el_estandar` | ¿Puede irse en un push algo que no es de este repo? | ✅ cubierta | tests/test_publicacion_limpia.py (mide el índice de git, no el disco) |

## Los huecos, escritos

**`sistemas_operativos` — cubierta con hueco.** La CI ejecuta la suite en ubuntu, pero el paseo de INSTALACIÓN fuera del repo solo se ha hecho en Windows. macOS no lo toca nadie.

**`ergonomia_de_entrada` — descubierta.** No hay [project.scripts], así que no existe un comando `vault`: se invoca `python .../scripts/vault_x.py`. Funciona y no engaña a nadie, pero es la diferencia entre un toolkit y un producto, y quien llega de fuera la nota en el primer minuto.

*Por qué se deja así:* Decisión de producto sin tomar. Declarar entry points ata el nombre público de cada tool del catálogo, y renombrar uno después rompe a quien lo llamara. Se decide el día que esto se publique en un índice de paquetes, no hoy.

**`lo_publicado_es_solo_el_estandar` — cubierta con hueco.** Mide el índice de HOY. Lo que ya esté en un commit anterior del historial no lo ve nadie: para eso haría falta recorrer todos los árboles, y este repo nunca ha versionado esos directorios.

## Qué NO demuestra el verde

Que toda promesa **listada** tiene ejecutor. No que la lista esté completa:
una promesa que nadie escribió en el registro sigue sin medirse, y esta tool
no puede leer lo que prometiste en un README que no conoce. El registro se
amplía cuando alguien tropieza — que es exactamente como nació.
