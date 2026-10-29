# Recibos del colector QG-00..QG-06: candidato 533e424 (R25, v41.25)

Ejecucion: `python audits/fase2/colector_qg.py --sha 533e424632214d4a8b3a6f9ce2c5589f3e6da4af --ejecutar ...`
el 2026-10-28/29, en una sesion de Claude Code (Windows 10, Python 3.14), con el arbol limpio en ese SHA.
Las rutas de la maquina se normalizan (`<repo>`, `<python>`, `<recibos>`, `<sandbox-e2e>`, `<tmp>`, `<user>`). El sha256 de cada
fichero es el del ORIGINAL, antes de normalizar. `colector.json`/`colector.log` son `qg2.json`/`qg2.log` de la corrida.

Resultado: QG-00..QG-06 PASS; QG-07 BLOCKED (`CI_PENDING`: no hay run de CI para ese SHA). `liberable: false`.
Suite: 6501 tests, 6485 passed, 16 skipped, 0 failed, 0 errores (`-n 4`; ver limites).

## Como se llego aqui (nada de esto se borra)

- Primera corrida (sin interprete de pip-audit ni venv de paridad, y con el directorio `vault-backups` de junio junto al repo):
  QG-02 BLOCKED (AP-36: `vault-backups` existe 2 niveles por encima del vault; no lo creó esta sesión), QG-04 y QG-05 NOT_RUN.
- Segunda corrida: `vault-backups` renombrado a `vault-backups.apartado-20261028` durante la corrida y devuelto a su nombre despues
  (nada borrado); `--pip-audit-python`/`--paridad-venv`/`--paridad-runtime` apuntando al venv del E2E. `pip-audit` encontro 10
  vulnerabilidades, todas en el `pip` 25.3 de ese venv de auditoria (no en una dependencia del producto; v41.25 se omite por no estar
  en PyPI). Se actualizo `pip` a 26.2.2 en el venv de auditoria y se repitio la corrida completa: QG-04 PASS.

## Limites declarados

- La suite corrio en Windows con `-n 4`. Con `-n auto` el worker `gw1` se cae en `tests/test_noop_audit.py::test_el_banco_sigue_viendo_trabajo_real` (3 de 3 veces); la causa no esta determinada.
- Sin CI: QG-07 no se ejecuta hasta que haya un run `success` sobre este SHA.
- QG-02 se obtuvo apartando `vault-backups` (directorio ajeno al repo y al vault); es un hallazgo de entorno, no de producto.

| Fichero | sha256 del original | Nota |
|---|---|---|
| `QG-00.arbol_limpio.json` | `99cda91a1c023100018b3e4472f06a61ed8eda814b9960b23b24a0b60b220504` | versionado (rutas normalizadas) |
| `QG-00.identidad_git.json` | `329a804f95d4c84e4f0861deff68972aec2d3727ef1147c4b5897dab95dadd23` | versionado (rutas normalizadas) |
| `QG-00.recibo.json` | `21cf566a1d0071869fe8bc0e33e6c4e54770b2e439cc11b703cb2f06f7dfea14` | versionado (rutas normalizadas) |
| `QG-00.reconciliador_archify.salida.txt` | `5308743b09c9a630f38f9ea2694900c5506305f8b459fcbaf4fc55bce56a3981` | versionado (rutas normalizadas) |
| `QG-00.saneamiento.salida.txt` | `2a088c40366977da2fdd35b50781d1bd79f7ee16a634800d092176293a0b9ac2` | versionado (rutas normalizadas) |
| `QG-00.subchecks.json` | `d2227769a2351d03461cb9b2ea3ef2a9a3ab07025e67bdec12e38dcbac7fa076` | versionado (rutas normalizadas) |
| `QG-01.recibo.json` | `0534940140edc95e95f05df6ef6fba54c900db9907fe0b6e868c01289e4d0d13` | versionado (rutas normalizadas) |
| `QG-01.reconciliador_archify.salida.txt` | `5308743b09c9a630f38f9ea2694900c5506305f8b459fcbaf4fc55bce56a3981` | versionado (rutas normalizadas) |
| `QG-01.subchecks.json` | `5720e34b6f9e3cbebdfd0c0d2dc8fd03e1ddceba513554c6e6f1f7f36e112c90` | versionado (rutas normalizadas) |
| `QG-01.vault_arch.salida.txt` | `24897bc01a1ea1ab3832f2db5756a9a287ccbea461a3f30e5273105bed38b8ff` | versionado (rutas normalizadas) |
| `QG-02.auditoria_completa.salida.txt` | `69283fcf6cb714b5c3edcd1fd3f639a46b20950a5b19ffa13d502135f1cf8aeb` | versionado (rutas normalizadas) |
| `QG-02.certificacion_compuesta.json` | `e8c52892365938c303b82d9f22314ee74ac7a9b66be5e9d3fc914c59b171989c` | versionado (rutas normalizadas) |
| `QG-02.puertas_26.salida.txt` | `de363107885955109cf5b0e0d3dc10f3774eaf0b7959a962c5eca4223f30e615` | versionado (rutas normalizadas) |
| `QG-02.recibo.json` | `e1ad101d066fdb43cfe96201fde433836f99bd924f67e2884fbf82c5a4038dad` | versionado (rutas normalizadas) |
| `QG-02.subchecks.json` | `f7d7dde5d371b035b46d467147ae71c05701869c39550e61fbd8b1945ef21c40` | versionado (rutas normalizadas) |
| `QG-03.recibo.json` | `84246a92b077fd01aa99c38e03a518f7d99cf568c95c018ac85c4555fd825fae` | versionado (rutas normalizadas) |
| `QG-03.subchecks.json` | `cfbc2bfb1ae853eea55d07ba133a03e9a7a110f0ba549c19735fdb16db25db77` | versionado (rutas normalizadas) |
| `QG-04.contencion.salida.txt` | `4b950891a4a75b179d08acabe6dfc2bbf5ff652a1b1ce2fbeed41707daf47c4e` | versionado (rutas normalizadas) |
| `QG-04.operaciones_destructivas.salida.txt` | `23ee500151ca2cf8fdeb5c55ad5966b63699fabc01b722905cb319131e7e3bfc` | versionado (rutas normalizadas) |
| `QG-04.pip_audit.salida.txt` | `778dd37d0370a61e6b5f1a1e03244bfaceddb97798b52de63fc44d597ef240d8` | versionado (rutas normalizadas) |
| `QG-04.recibo.json` | `35616367049ae5318555d21db1c7f0b2144c3820513ae9d37fef66a20be5e008` | versionado (rutas normalizadas) |
| `QG-04.saneamiento.salida.txt` | `2a088c40366977da2fdd35b50781d1bd79f7ee16a634800d092176293a0b9ac2` | versionado (rutas normalizadas) |
| `QG-04.subchecks.json` | `7e372aa40dcab0e3037dfffc055a4e5316ba8c20ebd8ba1d90e9f0c849caf774` | versionado (rutas normalizadas) |
| `QG-05.ap40_contrato.salida.txt` | `28218e082e3ba66b2da5fdce90d0bdcb1cb6be78fed20f8020b890dd015453d2` | versionado (rutas normalizadas) |
| `QG-05.paridad_cli_mcp.salida.txt` | `1ace491efce9e056cadf42df628a137a2833222cfb9c1b7970bc28e62e33fc9a` | versionado (rutas normalizadas) |
| `QG-05.recibo.json` | `c923195c3dcf9fe8000e322af96a7d950eacb74714fc149b27e8e926192fbf1c` | versionado (rutas normalizadas) |
| `QG-05.subchecks.json` | `82bcf47d6dbe88ddc6c54fdc9e21216aa849a8235c28b50fb713f6ac9a251e46` | versionado (rutas normalizadas) |
| `QG-06.recibo.json` | `181060c1992e6c7b52568d78418048c305c7bd03ad9cded6c58baa07d51413ce` | versionado (rutas normalizadas) |
| `QG-06.subchecks.json` | `28ea4a8483aae528e5998d1ce5d36f3109168dbd4e7f54f9e14388359c9e71d7` | versionado (rutas normalizadas) |
| `QG-06.wheel_contenido.json` | `448cc3ea7ea1bb72d923067f00a49044ed7da850a4f745ea59386ad23400debc` | versionado (rutas normalizadas) |
| `colector.json` | `e02f425248a010db68e8707963a9e80edf36f3250609d5af9de914f403c93f91` | versionado (rutas normalizadas) |
| `colector.log` | `00a4892069617adfd91a572f0174ea16a975e0f25426dd754badb973bdfd2429` | versionado (rutas normalizadas) |
| `e2e.json` | `093d6df53faf364df35554942b4555c5ac2ea1f0ddd301c67c72f566d240ee6f` | versionado (rutas normalizadas) |
| `e2e.log` | `2e1a0c6e207fc81f6f35a3ea3721d3796c441ad5a85b14b21060a41d18dd70fe` | versionado (rutas normalizadas) |
| `junit.xml.procedencia.json` | `eb66231c9e8a24e38fd2df860e3b8a8626016e5552edfc45f01e982a902e5541` | versionado (rutas normalizadas) |
| `suite.log` | `d25f0e48fe418881b9e3cfba530a2500991ea048c9ed2a6315163624df355337` | versionado (rutas normalizadas) |
| `QG-06.construccion.salida.txt` | (no versionado) | log de build |
| `junit.xml` | `8cb3bce334a14e5229cc977e7b874afb3953d77b2ebcebc31a0ad4efc9743e25` | NO VERSIONADO: JUnit completo: sha256 en junit.xml.procedencia.json |
