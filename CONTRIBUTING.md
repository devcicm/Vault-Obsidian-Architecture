# Contribuir

Gracias por mirar esto. Antes de nada, dos avisos honestos sobre el estado del
proyecto, porque cambian lo que puedes esperar.

## Estado: en uso, en mejora, con riesgos conocidos

Este repositorio **funciona y se usa a diario**, pero lo mantiene una persona y
evoluciona rápido. Lo que eso significa en la práctica:

- **La API interna se mueve.** Los nombres de las tools son estables; los
  símbolos internos de los módulos no. No hay `[project.scripts]`, así que no
  existe un comando `vault`: se invoca `python .../scripts/vault_x.py`.
- **No hay versión publicada en PyPI ni en npm.** Se instala copiando carpetas
  (ver [`INSTALL.md`](INSTALL.md)).
- **El paseo de instalación fuera del repo solo se ha probado en Windows.** La CI
  corre la suite en Linux y Windows, pero instalar-y-usar fuera del repositorio
  no se ha medido en Linux ni en macOS. Si lo haces, cuéntalo en un issue: es
  información que hoy no tiene nadie.
- **El servidor MCP no tiene autenticación.** Es local por diseño. Lee
  [`SECURITY.md`](SECURITY.md) antes de exponerlo a cualquier cosa.

Los huecos conocidos no están escondidos: están publicados y **medidos** en
[`docs/GUIA-DE-PRODUCCION.md`](docs/GUIA-DE-PRODUCCION.md), que se genera desde
un registro ejecutable. Si encuentras uno que no esté ahí, eso es en sí mismo un
buen issue.

## Abrir un issue

**Los issues están abiertos y son bienvenidos**, incluidos los que solo dicen
«intenté usar esto y me perdí en el minuto dos». Ese tipo de reporte es el más
valioso que puede recibir este proyecto, por una razón concreta y medida:

> Todas las puertas de calidad de este repo miden **el repo contra sí mismo**. En
> esa sala no está el consumidor. La primera vez que se preguntó en serio «¿puede
> usar esto otra persona?» apareció en diez minutos un defecto que ninguna puerta
> veía: el paquete prometía Python 3.9 y nada ejecutaba 3.9.

Tú ves lo que el proyecto no puede verse. Para un fallo, ayuda incluir:

```bash
python scripts/vault_gate.py --strict          # las puertas
python -c "import sys; sys.path.insert(0,'scripts'); import vault_io; \
           print(vault_io.get_vault_root(), vault_io.vault_root_origin())"
python --version
```

**No** pegues contenido de tu vault si tiene datos reales. Un ejemplo mínimo
inventado sirve igual.

Para fallos de **seguridad**, no uses un issue público: ver [`SECURITY.md`](SECURITY.md).

## Enviar código

El repo tiene reglas duras y son ejecutables, así que no hace falta adivinarlas.
Están en [`CLAUDE.md`](CLAUDE.md) y las resumo:

1. **Nada se borra.** Ni tools, ni normas, ni secciones del manifiesto. Lo
   reemplazado se anota `superseded_by:` conservando su contrato.
2. **Registro canónico primero, documentación después.** El orden es: registro en
   código → doc derivada → guard que falla si divergen → test. Un concepto que
   solo existe en un documento no existe.
3. **Toda ejecución va contra `vault-sandbox/`**, nunca contra la raíz del repo
   ni contra un vault real.
4. **Ninguna norma nueva puede tener enforcement manual.** O la comprueba algo, o
   no es una norma.
5. **Lo derivado no se edita a mano** — `docs/BLUEPRINT.md`, `docs/ARQUITECTURA.md`,
   el índice de `scripts/README.md`, `docs/GUIA-DE-PRODUCCION.md` y las cifras de
   la documentación se regeneran. Lo que escribas a mano ahí se pierde, y eso es
   lo que los mantiene honestos.

### Antes de abrir un PR

```bash
python scripts/vault_gate.py --strict     # todas las puertas, ~1 min
python -m pytest tests/ --tb=short        # la suite, ~13 min
```

**Las dos.** Verde en las puertas no es verde en la suite.

Una trampa que cuesta tiempo si no la sabes: el árbol mezcla finales de línea LF
y CRLF, y los regeneradores (`--fix`, `--freeze`, `--blueprint`) los voltean. Si
un fichero te sale con el diff entero cambiado, compara los bytes contra
`git show HEAD:<fichero>` antes de commitear.

### Qué hace que un PR se acepte rápido

Que la norma que propones **la mida algo**. Este repo no acepta «hay que tener
cuidado con X» como aporte: acepta el guard que falla cuando alguien no lo tiene.
Si además el guard declara **qué no ve** —su alcance real, no el que le gustaría
tener—, mejor todavía. Media docena de los defectos más caros de este proyecto
salieron de medidas cuyo alcance declarado era más ancho que el que recorrían.

## Idioma

El código, los docstrings y la documentación están en español. Los issues y PRs,
en el idioma que prefieras: se contesta en el que escribas.

## Licencia

Al contribuir aceptas que tu aporte se publique bajo la licencia del repositorio
([`LICENSE`](LICENSE)).
