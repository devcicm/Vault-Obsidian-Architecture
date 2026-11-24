"""Fase H: contrato ejecutable de redaccion, informes, reportes de datos y citas APA.

Fija el contrato verificable:
- `vault.kernel.redaccion` declara `FORMAS_DE_DOCUMENTO`, `NIVELES_EPISTEMICOS`,
  `evaluar_forma` (sin inventar ni mutar contenido) y `formatear_cita_apa` (APA 7
  sin fabricar autor ni fecha: usa `s.f.` y mueve el titulo si falta autor).
- `vault_write --shape informe|reporte|auditoria|...` estampa `document_shape` en
  frontmatter, rechaza formas fuera de vocabulario y devuelve `shape_review` en el envelope.
- `vault_bibliography_save --author ... --published-date ... --citation-style apa`
  guarda metadatos estructurados y `citation_apa` en frontmatter y cuerpo (idempotente).
- `vault_audit` reporta diagnostico informativo de formas documentales y citas APA
  sin penalizar notas legadas.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

from apoyo import correr_tool

import vault_audit
import vault_bibliography_save
import vault_io
import vault_write


def _init_vault(tmp_path: Path) -> Path:
    raiz = tmp_path / "vault"
    for carpeta in ("00_System", "07_Knowledge", "12_Bibliography", "19_Audits"):
        (raiz / carpeta).mkdir(parents=True, exist_ok=True)
    return raiz


def test_kernel_redaccion_evalua_formas_y_formatea_apa_sin_inventar():
    from vault.kernel.redaccion import (
        FORMAS_DE_DOCUMENTO,
        NIVELES_EPISTEMICOS,
        evaluar_forma,
        formatear_cita_apa,
    )

    assert set(FORMAS_DE_DOCUMENTO) == {
        "resumen",
        "sintesis",
        "informe",
        "reporte",
        "decision",
        "auditoria",
        "referencia",
    }
    assert set(NIVELES_EPISTEMICOS) == {
        "observado",
        "inferencia",
        "propuesta",
        "decision",
        "desconocido",
    }

    texto_reporte = textwrap.dedent(
        """\
        # Reporte de Latencia Q4

        ## Resumen de datos

        **Observado:** La latencia p95 bajo de 293 ms a 198 ms tras la carga perezosa.

        ## Metricas

        | Indicador | Antes | Despues |
        |---|---|---|
        | CLI startup | 293 ms | 198 ms |

        ## Fuente y corte

        Medido el 2026-11-23 sobre [[bench-cli]].

        ## Observaciones

        **Inferencia:** El ahorro proviene de diferir imports de comandos no invocados.
        """
    )
    ev = evaluar_forma(texto_reporte, "reporte")
    assert ev["forma"] == "reporte"
    assert ev["secciones_faltantes"] == []
    assert "observado" in ev["marcadores_epistemicos"]
    assert "inferencia" in ev["marcadores_epistemicos"]
    assert ev["tiene_evidencia"] is True

    # APA 7 con autor y fecha completos
    cita_completa = formatear_cita_apa(
        title="Designing Data-Intensive Applications",
        url="https://dataintensive.net",
        author="Kleppmann, M.",
        published_date="2017-03-16",
        accessed_at="2026-11-23T12:00:00Z",
    )
    assert "Kleppmann, M. (2017)." in cita_completa
    assert "Designing Data-Intensive Applications." in cita_completa
    assert "https://dataintensive.net" in cita_completa

    # APA 7 sin autor ni fecha: nunca inventa (AP-45), usa s.f. y titulo al inicio
    cita_incompleta = formatear_cita_apa(
        title="FastAPI Documentation",
        url="https://fastapi.tiangolo.com",
        author=None,
        published_date=None,
        accessed_at="2026-11-23T12:00:00Z",
    )
    assert cita_incompleta.startswith("FastAPI Documentation. (s.f.).")
    assert "https://fastapi.tiangolo.com" in cita_incompleta


def test_vault_write_shape_estampa_frontmatter_y_devuelve_shape_review(tmp_path):
    raiz = _init_vault(tmp_path)
    prev = vault_io.set_vault_root(raiz)
    try:
        contenido = textwrap.dedent(
            """\
            # Informe de Salud del Grafo

            ## Resumen ejecutivo

            **Observado:** El grafo tiene cero enlaces rotos en la medicion actual.

            ## Hallazgos

            Se revisaron todas las notas activas de [[index]] con resultado consistente.

            ## Evidencia

            Resultado verificado en `vault_audit.py` con 0 enlaces rotos.

            ## Conclusiones

            El estado operativo es estable para la siguiente iteracion del estandar.
            """
        )
        res = vault_write.vault_write(
            folder="19_Audits",
            title="Informe de Salud del Grafo",
            content=contenido,
            tags=["informe", "auditoria"],
            meta={"agent": "tester", "document_shape": "informe"},
        )
        assert res.get("ok"), res
        assert res["shape_review"]["forma"] == "informe"
        assert res["shape_review"]["secciones_faltantes"] == []
        texto_disco = (raiz / res["path"]).read_text(encoding="utf-8")
        assert "document_shape: informe" in texto_disco

        # Forma invalida se rechaza antes de escribir
        malo = vault_write.vault_write(
            folder="19_Audits",
            title="Nota Forma Invalida",
            content=contenido,
            tags=["informe"],
            meta={"agent": "tester", "document_shape": "poema_epico"},
        )
        assert malo.get("ok") is False
        assert malo.get("error_code") == "INVALID_INPUT"
    finally:
        vault_io.set_vault_root(prev)

    # Via CLI `--shape reporte`
    env = {**os.environ, "VAULT_ROOT": str(raiz)}
    proc = correr_tool(
        "vault_write.py",
        "--folder",
        "19_Audits",
        "--title",
        "Reporte Metricas CLI",
        "--content",
        textwrap.dedent(
            """\
            # Reporte Metricas CLI

            ## Resumen de datos

            **Observado:** Tiempo de arranque medido en 198 ms en ejecucion limpia.

            ## Metricas

            | Metrica | Valor |
            |---|---|
            | startup_ms | 198 |

            ## Fuente y corte

            Corte 2026-11-23 sobre [[index]].

            ## Observaciones

            Sin regresiones en los comandos revisados.
            """
        ),
        "--tags",
        "reporte",
        "--agent",
        "tester",
        "--shape",
        "reporte",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    assert out["shape_review"]["forma"] == "reporte"
    assert out["shape_review"]["secciones_faltantes"] == []


def test_vault_bibliography_save_soporta_author_published_date_y_apa(tmp_path):
    raiz = _init_vault(tmp_path)
    env = {**os.environ, "VAULT_ROOT": str(raiz)}

    proc = correr_tool(
        "vault_bibliography_save.py",
        "--title",
        "Attention Is All You Need",
        "--url",
        "https://arxiv.org/abs/1706.03762",
        "--summary",
        "Arquitectura Transformer basada en autoatencion para secuencias.",
        "--source_type",
        "paper",
        "--author",
        "Vaswani, A., et al.",
        "--published-date",
        "2017-06-12",
        "--citation-style",
        "apa",
        "--agent",
        "tester",
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert "Vaswani, A., et al. (2017)." in data["citation_apa"]

    nota = raiz / data["path"]
    texto = nota.read_text(encoding="utf-8")
    assert "author:" in texto
    assert "published_date:" in texto
    assert "citation_apa:" in texto
    assert "## Referencia APA" in texto

    # Sin autor ni fecha: usa s.f. y NO inventa author ni published_date en frontmatter
    prev = vault_io.set_vault_root(raiz)
    try:
        res_sin = vault_bibliography_save.vault_bibliography_save(
            title="Python AST Docs",
            url="https://docs.python.org/3/library/ast.html",
            summary="Documentacion oficial del modulo ast en Python.",
            source_type="docs",
            agent="tester",
        )
        assert res_sin.get("ok"), res_sin
        assert "(s.f.)" in res_sin["citation_apa"]
        texto_sin = (raiz / res_sin["path"]).read_text(encoding="utf-8")
        assert "\nauthor:" not in texto_sin
        assert "\npublished_date:" not in texto_sin

        # Diagnostico informativo en vault_audit detecta la cita incompleta sin penalizar
        diag = vault_audit._detect_redaccion_y_citas([raiz / data["path"], raiz / res_sin["path"]])
        assert diag["citations"]["checked"] == 2
        assert len(diag["citations"]["incomplete"]) == 1
        assert diag["citations"]["incomplete"][0]["path"] == res_sin["path"]
    finally:
        vault_io.set_vault_root(prev)
