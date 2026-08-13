"""AP-05 — el mismo dato con valores distintos en varias notas.

La última norma `critical` que quedaba sin detector, y la que más tardó: desde
v19 hasta v40.15. El motivo escrito en su `cobertura_descubierta` era cierto y
sigue siéndolo — decidir qué es «el mismo dato» sin embeddings es un problema
abierto—, así que lo primero que fija este fichero **no** es lo que la tool ve:
es lo que declara que no ve. Una medida parcial que se presenta como total es
peor que ninguna, porque el verde se lee como garantía.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import vault_fuente_unica as fu
from vault_regex import es_ipv4, tipo_de_valor


def _nota(p: Path, cuerpo: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cuerpo, encoding="utf-8")


@pytest.fixture
def vault(tmp_path):
    """Un conflicto real rodeado de las cuatro cosas que NO son conflicto."""
    _nota(tmp_path / "infra/a.md", "---\nproject: acme\n---\n\nip: 192.168.1.10\npuerto: 8080\n")
    _nota(tmp_path / "infra/b.md", "---\nproject: acme\n---\n\nip: 192.168.1.20\npuerto: 8080\n")
    # Dentro de un fence es un ejemplo, no una afirmación (AP-57).
    _nota(tmp_path / "infra/doc.md", "---\nproject: acme\n---\n\n```\nip: 10.9.9.9\n```\n")
    # Instantánea congelada: no es una nota del vault.
    _nota(tmp_path / ".history/vieja.md", "---\nproject: acme\n---\n\nip: 172.16.0.1\n")
    # Otro ámbito: dos proyectos no se contradicen por compartir clave.
    _nota(tmp_path / "infra/c.md", "---\nproject: otro\n---\n\nip: 8.8.8.8\n")
    return tmp_path


class TestLoQueVe:
    def test_detecta_la_divergencia_real(self, vault):
        c = fu.medir(vault)
        assert len(c) == 1
        assert c[0]["clave"] == "ip" and c[0]["tipo"] == "ipv4"
        assert set(c[0]["valores"]) == {"192.168.1.10", "192.168.1.20"}

    def test_el_report_dice_quien_afirma_cada_valor(self, vault):
        """Sin esto el hallazgo no es accionable: hay que ir nota a nota."""
        texto = "\n".join(fu.report(vault)["report"])
        assert "a.md" in texto and "b.md" in texto

    def test_semver_divergente_es_conflicto(self, tmp_path):
        _nota(tmp_path / "s/a.md", "---\nproject: p\n---\n\npve_version: 9.1.1\n")
        _nota(tmp_path / "s/b.md", "---\nproject: p\n---\n\npve_version: 8.4.16\n")
        c = fu.medir(tmp_path)
        assert len(c) == 1 and c[0]["tipo"] == "semver"


class TestLoQueNoEsConflicto:
    """Cada uno de estos, si fallara, produce ruido — y un guard con ruido deja
    de leerse, que es como se pierde el hallazgo verdadero que estaba al lado."""

    def test_el_mismo_valor_en_dos_notas_no_es_conflicto(self, vault):
        assert not any(c["clave"] == "puerto" for c in fu.medir(vault))

    def test_un_valor_dentro_de_un_fence_no_se_cuenta(self, vault):
        vistos = {v for c in fu.medir(vault) for v in c["valores"]}
        assert "10.9.9.9" not in vistos

    def test_una_instantanea_no_afirma_nada(self, vault):
        vistos = {v for c in fu.medir(vault) for v in c["valores"]}
        assert "172.16.0.1" not in vistos

    def test_dos_ambitos_distintos_no_se_contradicen(self, vault):
        vistos = {v for c in fu.medir(vault) for v in c["valores"]}
        assert "8.8.8.8" not in vistos

    def test_la_version_de_la_nota_no_es_un_dato_compartido(self, tmp_path):
        """`version: 1.0.0` y `version: 2.0.0` no divergen: son dos notas.

        Sin `CLAVES_DE_LA_NOTA` la medida marca el frontmatter entero de
        cualquier vault y nace inservible.
        """
        _nota(tmp_path / "n/a.md", "---\nproject: p\nversion: 1.0.0\n---\n")
        _nota(tmp_path / "n/b.md", "---\nproject: p\nversion: 2.0.0\n---\n")
        assert fu.medir(tmp_path) == []

    def test_un_valor_sin_tipo_no_se_compara(self, tmp_path):
        """Un `status:` diverge entre notas legítimamente."""
        _nota(tmp_path / "n/a.md", "---\nproject: p\n---\n\nstatus: activo\n")
        _nota(tmp_path / "n/b.md", "---\nproject: p\n---\n\nstatus: archivado\n")
        assert fu.medir(tmp_path) == []


class TestElLimiteDeclarado:
    """Verde no prueba una sola fuente de verdad. Estos tests fijan los tres
    huecos **como huecos**: si alguien los cierra, que sea a propósito y que
    cambie la declaración, no que se entere por una regresión."""

    def test_la_prosa_no_se_ve(self, tmp_path):
        _nota(tmp_path / "n/a.md", "---\nproject: p\n---\n\nEl host es 10.0.0.1 desde ayer.\n")
        _nota(tmp_path / "n/b.md", "---\nproject: p\n---\n\nEl host es 10.0.0.2 ahora.\n")
        assert fu.medir(tmp_path) == [], "si esto detecta algo, actualiza el límite declarado"

    def test_el_sinonimo_no_se_ve(self, tmp_path):
        _nota(tmp_path / "n/a.md", "---\nproject: p\n---\n\nip: 10.0.0.1\n")
        _nota(tmp_path / "n/b.md", "---\nproject: p\n---\n\ndireccion_ip: 10.0.0.2\n")
        assert fu.medir(tmp_path) == [], "reconocerlo pediría los embeddings que no hay"

    def test_el_envelope_dice_lo_que_verde_no_prueba(self, tmp_path):
        r = fu.check(tmp_path)
        assert r["ok"] is True
        assert "no prueba" in r["hint"]


class TestTipos:
    def test_una_ip_no_se_confunde_con_un_semver(self):
        """El orden importa: `192.168.1.10` casa con el regex de semver."""
        assert tipo_de_valor("192.168.1.10") == "ipv4"
        assert tipo_de_valor("1.2.3") == "semver"

    def test_los_octetos_se_validan(self):
        assert es_ipv4("10.0.0.1")
        assert not es_ipv4("999.1.1.1")
        assert not es_ipv4("10.0.0")

    def test_lo_que_no_es_comparable_devuelve_none(self):
        for v in ("activo", "Carlos", "", "un texto cualquiera"):
            assert tipo_de_valor(v) is None


class TestContratoCLI:
    def _run(self, *args):
        return subprocess.run([sys.executable, str(RAIZ / "scripts" / "vault_fuente_unica.py"), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=RAIZ)

    def test_freeze_y_check_a_la_vez_sale_por_el_contrato_de_error(self):
        """AP-52: el fallo del usuario no se publica como fallo interno.

        `emit_error` **construye** el envelope; devolverlo desde `main` hacía
        que `wrap_main` publicara `UNEXPECTED_ERROR`. Ese defecto ya se coló dos
        veces sin que ninguna prueba pisara la rama.
        """
        r = self._run("--freeze", "--check")
        assert r.returncode == 1
        assert "CONFLICTING_ARGS" in r.stdout
        assert "UNEXPECTED_ERROR" not in r.stdout

    def test_check_strict_sale_cero_en_el_sandbox(self):
        r = self._run("--check", "--strict")
        assert r.returncode == 0, r.stdout[-500:]


def test_la_baseline_ilegible_no_se_lee_como_vacia(tmp_path, monkeypatch):
    """Leerla como vacía estrenaría la deuda entera como «sin deuda» (AP-51)."""
    mala = tmp_path / "b.json"
    mala.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(fu, "BASELINE", mala)
    with pytest.raises(RuntimeError):
        fu._baseline()


def test_ap05_ya_no_esta_descubierta():
    """El dato que motiva toda esta tanda."""
    from vault_norms import NORM_CATALOG
    ap05 = next(n for n in NORM_CATALOG if n["code"] == "AP-05")
    assert ap05["tools_detecting"] == ["vault_fuente_unica"]
    assert not ap05.get("cobertura_descubierta")
    # Y la cobertura sigue diciéndose parcial: es lo que impide leer el verde
    # como una garantía que la medida no da.
    assert "parte decidible" in ap05["cobertura_parcial"]


def test_la_puerta_16_existe():
    from vault_gate import PUERTAS
    assert any(p["id"] == "fuente_unica" for p in PUERTAS)


class TestLoQueDestapoElQADeV40_16:
    """Tres defectos de esta tool que ninguna prueba de v40.15 podía ver.

    Los tres tienen la misma forma: la tool salía verde y el verde no
    significaba lo que decía. El sandbox no los exhibe porque no tiene ninguna
    nota que cite un comando ni ninguna clave con guion — que es, otra vez, el
    motivo por el que la regla 7 existe.
    """

    def test_la_exclusion_mira_la_ruta_y_no_el_texto_de_la_nota(self, tmp_path):
        """v40.15 llamaba `es_documentacion_del_estandar(crudo, rel)`, invertido.

        Con el contenido en el parámetro de la ruta, la función buscaba
        `"/scripts/"` dentro del **texto**: cualquier nota que citara un comando
        —lo que este toolkit escribe todo el rato— quedaba fuera de la medida.
        """
        _nota(tmp_path / "infra/a.md",
              "---\nproject: acme\n---\n\nDespliegue: `python scripts/deploy.py`\nhost_ip: 10.0.0.1\n")
        _nota(tmp_path / "infra/b.md",
              "---\nproject: acme\n---\n\nVer `repo/scripts/otro.sh`\nhost_ip: 10.0.0.2\n")
        conflictos = fu.medir(tmp_path)
        claves = {c["clave"] for c in conflictos}
        assert "host_ip" in claves, (
            "Dos notas que citan una ruta con /scripts/ deben medirse igual: "
            "el criterio de exclusión decide sobre la ruta de la nota, no "
            "sobre lo que la nota cuenta."
        )

    def test_la_clave_del_frontmatter_se_normaliza_como_la_del_cuerpo(self, tmp_path):
        """`port-local:` es «clave de la nota» en el cuerpo y lo era en el
        frontmatter: se filtraba con `lower()` a secas y se normalizaba
        después, así que el guion sobrevivía al filtro."""
        _nota(tmp_path / "infra/a.md", "---\nproject: acme\nport-local: 8080\n---\n\ntexto\n")
        _nota(tmp_path / "infra/b.md", "---\nproject: acme\nport-local: 9090\n---\n\ntexto\n")
        assert fu.medir(tmp_path) == [], (
            "`port_local` está en CLAVES_DE_LA_NOTA: escrito con guion en el "
            "frontmatter tiene que excluirse igual que en el cuerpo."
        )

    def test_freeze_se_niega_aunque_la_baseline_este_vacia(self, tmp_path, monkeypatch):
        """La condición llevaba `and base`, así que la negativa se desactivaba
        justo cuando la baseline nace vacía — el momento más barato para
        congelar la primera deuda sin que nadie la vea pasar."""
        _nota(tmp_path / "infra/a.md", "---\nproject: acme\n---\n\nip: 1.1.1.1\n")
        _nota(tmp_path / "infra/b.md", "---\nproject: acme\n---\n\nip: 2.2.2.2\n")
        monkeypatch.setattr(fu, "BASELINE", tmp_path / "no-existe.json")
        salida = fu.freeze(tmp_path)
        assert salida["ok"] is False
        assert salida["error_code"] == "DEBT_WOULD_GROW"
        assert salida["new_conflicts"], "la deuda que se niega a congelar se lista"
