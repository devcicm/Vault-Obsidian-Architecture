# Pirámide de validación (medida)

Fuente: `JUnit de una corrida real`. Nivel de un fichero de test = mediana del
tiempo por caso. Cortes (convención declarada):
L0 < 1s · L1 < 5s · L2 < 30s · L3 >= 30s (mediana por caso).

| Nivel | Significa | Ficheros | Casos | Suma de tiempos | % del total |
|---|---|---:|---:|---:|---:|
| L0 | sanidad | 465 | 5542 | 3882.4s | 47.0% |
| L1 | unidad | 83 | 605 | 1691.8s | 20.5% |
| L2 | integración | 37 | 160 | 2453.4s | 29.7% |
| L3 | extremo | 2 | 6 | 227.1s | 2.8% |
| total | — | 587 | 6313 | 8254.8s | 100% |

Reloj real de la corrida: 1076s contra 8255s de suma de casos → factor de paralelismo 7.7×.

## El extremo L3 (ficheros whose mediana supera el corte)

Estos dominan el coste total; son la cola que el carril rápido
evita y la que conviene revisar primero (identificados por su
nombre, no por estimación):

- `test_reindex_check_codigo` — 4 casos, mediana 33.1s, total 127s
- `test_sandbox_fixture` — 2 casos, mediana 50.2s, total 100s

## Los 10 casos únicos más caros (mediana los esconde)

Un solo caso largo dentro de un fichero de unidad es el patrón
de 'gate completo dentro de un test': el carril rápido lo evita
igual, pero la revisión del harness debe verlo:

- `test_fix_all` — caso más caro 137s (mediana del fichero 6.6s, nivel L2)
- `test_banco_agente` — caso más caro 90s (mediana del fichero 0.0s, nivel L0)
- `test_sandbox_fixture` — caso más caro 66s (mediana del fichero 50.2s, nivel L3)
- `test_arch_escrituras_de_sistema` — caso más caro 59s (mediana del fichero 1.2s, nivel L1)
- `test_nota_de_comandos` — caso más caro 59s (mediana del fichero 0.1s, nivel L0)
- `test_arquitectura_trazabilidad` — caso más caro 52s (mediana del fichero 3.1s, nivel L1)
- `test_vault_onboard` — caso más caro 44s (mediana del fichero 1.1s, nivel L1)
- `test_move_lock` — caso más caro 42s (mediana del fichero 11.5s, nivel L2)
- `test_mcp_traza_contenida` — caso más caro 42s (mediana del fichero 23.1s, nivel L2)
- `test_puertos_verificados` — caso más caro 39s (mediana del fichero 0.0s, nivel L0)

## Carril rápido

L0+L1 cubren 6147 casos de 6313 (97.4%) con 5574s de suma sobre 8255s (67.5%): es el carril para
iterar; NO sustituye al cierre completo.

Duplicaciones detectadas con medición (gates ejecutados dentro
de tests): viven en la lista del extremo L3 — su coste es la
señal; el criterio de desduplicación lo decide la revisión del
harness, no este documento.
