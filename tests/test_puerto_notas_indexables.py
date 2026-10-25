"""Puerto `enumeracion_indexable` (cruce C de la auditoría 2026-10-24).

`vault/ciclo_de_vida/sanacion.py` enumera por `vault_reindex.notas_indexables`
desde v40.9; el símbolo era público pero no estaba en la superficie publicada
de Índices. Estas pruebas fijan el contrato del puerto: la raíz alternativa
manda, los filtros del criterio del dueño se conservan (sección canónica, sin
tramos ocultos, nada suelto en la raíz — AP-15) y el puerto no filtra distinto
que el dueño (`vault/kernel/enumeracion.py`).

Ejecutar desde la raíz: python -m unittest discover -s tests -p 'test_puerto_notas_indexables.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import vault_reindex  # noqa: E402

INIT = ("import sys; from vault.product_cli import main; "
        "sys.exit(main(sys.argv[1:]))")


class PuertoEnumeracionIndexable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.padre = Path(tempfile.mkdtemp(prefix="puerto-enum-"))
        cls.raiz = cls.padre / "vault-a"
        cls.otra = cls.padre / "vault-b"
        cls.env = dict(
            os.environ, PYTHONIOENCODING="utf-8", VAULT_ROOT=str(cls.raiz),
            VAULT_STRICT_ROOT="1", VAULT_AGENT="agente-ejecutor",
            PYTHONPATH=os.pathsep.join(
                [str(ROOT), *filter(None, [os.environ.get("PYTHONPATH")])]))
        for vault in (cls.raiz, cls.otra):
            p = subprocess.run(
                [sys.executable, "-c", INIT, "init", str(vault)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", env=cls.env, cwd=cls.padre, timeout=600)
            sobre = json.loads(p.stdout or "{}")
            assert sobre.get("ok") is True, p.stdout[-600:] + p.stderr[-600:]
        # En `raiz`: dos notas en sección canónica y tres que el criterio
        # excluye — suelta en la raíz (AP-15), bajo tramo oculto y en carpeta
        # fuera del vocabulario de secciones.
        (cls.raiz / "01_Projects" / "nota-proyecto.md").write_text(
            "---\ntitle: A\n---\n\nCuerpo.\n", encoding="utf-8")
        (cls.raiz / "07_Knowledge" / "nota-saber.md").write_text(
            "---\ntitle: B\n---\n\nCuerpo.\n", encoding="utf-8")
        (cls.raiz / "suelta.md").write_text(
            "---\ntitle: S\n---\n\nCuerpo.\n", encoding="utf-8")
        oculta = cls.raiz / "01_Projects" / ".oculto"
        oculta.mkdir()
        (oculta / "nota-c.md").write_text(
            "---\ntitle: C\n---\n\nCuerpo.\n", encoding="utf-8")
        ajena = cls.raiz / "Carpeta_Ajena"
        ajena.mkdir()
        (ajena / "nota-x.md").write_text(
            "---\ntitle: X\n---\n\nCuerpo.\n", encoding="utf-8")
        # El señuelo en la otra raíz: si el puerto ignora el `root`, aparece.
        (cls.otra / "01_Projects" / "senaluelo.md").write_text(
            "---\ntitle: D\n---\n\nCuerpo.\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.padre, ignore_errors=True)

    def test_la_raiz_alternativa_manda(self):
        """`root=R` enumera R y solo R: ni la autodetección ni otra raíz
        hermana se cuelan en el conjunto."""
        rutas = vault_reindex.notas_indexables(root=self.raiz)
        nombres = {p.name for p in rutas}
        self.assertIn("nota-proyecto.md", nombres)
        self.assertIn("nota-saber.md", nombres)
        self.assertNotIn("senaluelo.md", nombres)
        raiz_resuelta = self.raiz.resolve()
        for p in rutas:
            self.assertTrue(
                Path(p).resolve().is_relative_to(raiz_resuelta),
                f"{p} no cuelga de la raíz pedida")

    def test_los_filtros_del_criterio_del_dueno(self):
        """Fuera de sección, suelto en la raíz y tramo oculto no son notas
        indexables; las de sección canónica sí."""
        nombres = {p.name for p in vault_reindex.notas_indexables(root=self.raiz)}
        self.assertNotIn("suelta.md", nombres)
        self.assertNotIn("nota-c.md", nombres)
        self.assertNotIn("nota-x.md", nombres)
        self.assertGreaterEqual(len(nombres), 2)

    def test_orden_estable_y_equivalencia_con_el_dueno(self):
        """Dos llamadas consecutivas devuelven el mismo orden, y el conjunto
        del puerto es exactamente el del dueño del criterio con las secciones
        del propio contexto — el puerto no filtra por su cuenta."""
        primera = vault_reindex.notas_indexables(root=self.raiz)
        segunda = vault_reindex.notas_indexables(root=self.raiz)
        self.assertEqual(primera, segunda)

        from vault.indices.repositorio import RepositorioIndices
        from vault.kernel import construir
        from vault.kernel.enumeracion import notas_en_disco
        repo = RepositorioIndices(construir(self.raiz))
        esperado = notas_en_disco(repo.raiz, repo.ctx.secciones.ordenadas())
        self.assertEqual(sorted(Path(p) for p in primera),
                         sorted(Path(p) for p in esperado))


if __name__ == "__main__":
    unittest.main()
