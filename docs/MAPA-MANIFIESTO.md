# Mapa del manifiesto

<!-- propiedad: CARLOS IVAN CM · revisión: manual -->

Cada titular de nivel 2 del
[manifiesto](../vault-obsidian-architecture.md) clasificado por qué es: **qué
obliga y para quién**. La fuente normativa es el manifiesto; esto solo es el
mapa para no perderse en 12.000 líneas.

`test_mapa_manifiesto.py` cruza este mapa contra los titulares reales del
manifiesto: un titular nuevo sin clasificar, o una entrada que ya no existe,
ponen el test en rojo. La clasificación es juicio humano —qué es ley y qué es
guía no se deriva de nada—; que esté completa, eso lo vigila la máquina.

## Las cuatro clases

| Clase | Qué significa | Para quién obliga |
|---|---|---|
| **norma** | Principio, contrato o definición: lo que el estándar garantiza y exige | Cualquier implementación del estándar |
| **guía** | Cómo operar con un vault real, paso a paso | Quien trabaja con un vault concreto |
| **gobierno** | Cómo evoluciona el propio estándar — versionado, changelog | Quien mantiene este repositorio |
| **registro** | Historial fechado; no se reescribe | El que quiera saber qué pasó y cuándo |

## El mapa

### norma — lo que el estándar es y garantiza

| Titular | Qué es |
|---|---|
| Qué es este estándar | La definición: qué resuelve, qué garantiza, qué no es |
| Por qué existe este documento | El origen del estándar y la política de no-derogación |
| Principios de diseño | Los principios que mandan sobre cualquier decisión posterior |
| Marco de Datos y Gobernanza | CIA, F1–F8, DQ, FAIR, V's — las garantías declaradas y medidas |
| Estructura del Vault | Las secciones, su clase documental y su contrato |
| Las Tools del Vault — Contrato normativo | Qué garantizan las herramientas de memoria y sus convenciones |
| Compatibilidad con Obsidian Desktop | Alcance: qué requiere y qué no Obsidian |
| MCP Server Monolith — Servicio Directo para IAs (v37) | La superficie MCP y su contrato |
| Auto-features del Harness | Lo que el harness hace por sí solo |
| Niveles de implementación | Qué implementar en qué orden |
| Anti-patrones de implementación — Guía de prevención | La introducción a los AP: cómo se lee y cómo se previenen |
| Patrones recomendados | Los PAT: las formas que el estándar recomienda |
| Protocolo de sesión — SP-XX (v30) | Los protocolos de sesión: qué se registra y cuándo |
| Convenciones de nomenclatura — CN-XX (v30) | Las convenciones de nombres: ficheros, carpetas, slugs |
| Directivas de Proyecto — Extensión del 00_System | Cómo se extiende el estándar sin romperlo |
| Por qué este diseño vs alternativas | El ADR resumido: cada alternativa y por qué no |

### guía — cómo operar con un vault real

| Titular | Qué es |
|---|---|
| Casos de uso concretos | Flujos aplicados con las tools del contrato |
| Inicializar un vault desde cero | `vault_init` y el arranque limpio |
| Sanar un vault preexistente — el modo agéntico | Adaptar un vault que no generó el estándar, sin borrar nada |
| Poblar un vault desde un proyecto existente — el modo agéntico | El onboarding desde un repo |
| Protocolo de sesión para LLMs remotos | El protocolo para agentes sin acceso directo al disco |
| La casa de los vaults | Dónde viven los vaults y cómo se gestionan |
| Configuración de VAULT_ROOT en los scripts | Cómo resuelve cada script su vault objetivo |
| Checklist de implementación en repositorio existente | Qué instalar y en qué orden |

### gobierno — cómo evoluciona el propio estándar

| Titular | Qué es |
|---|---|
| Versionado del estándar | Las reglas del versionado y quién aprueba cada release |

### registro — lo que pasó y cuándo

| Titular | Qué es |
|---|---|
| Changelog | Cada versión, su fecha y su hash de commit — sellado por `vault_changelog_check` |
