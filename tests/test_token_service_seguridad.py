"""SP-04 alcanza también al servicio de tokens: no lo invoca cualquiera.

Medido el 2026-10-08 contra el servicio real (`vault_token_service --port`):
no pedía credencial, aceptaba JSON con cualquier `Content-Type` y no miraba
`Origin` ni `Host`. Una página abierta en el navegador del usuario podía
hacer `POST /stop` —un formulario basta, sin preflight— y apagarlo, escribir
eventos en un flujo o, con DNS rebinding, leer `GET /flows/<id>`, que guarda
el texto del prompt cuando se pide `--store-text`. `SECURITY.md` lo declaraba
como «no autentica»; declarar un hueco no lo cierra.

Se comprueba con el criterio del consumidor (AP-44): el servicio real por
HTTP desde fuera, y el cliente `vault_token_counter` hablándole sin que nadie
le pase el token a mano.
"""

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
TOKEN = "t0ken-de-prueba-" + "y" * 32


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _entorno(vault: Path, token):
    env = {**os.environ, "VAULT_ROOT": str(vault), "PYTHONIOENCODING": "utf-8"}
    env.pop("VAULT_TOKEN_SERVICE_TOKEN", None)
    if token is not None:
        env["VAULT_TOKEN_SERVICE_TOKEN"] = token
    return env


class Servicio:
    def __init__(self, vault: Path, token=TOKEN):
        self.vault = vault
        self.port = _puerto_libre()
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "vault_token_service.py"), "--port", str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=_entorno(vault, token), cwd=str(vault),
        )
        limite = time.time() + 30
        while time.time() < limite:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError(self.proc.stderr.read().decode("utf-8", "replace"))
                time.sleep(0.1)
        raise RuntimeError("el servicio no abrió el puerto")

    def pedir(self, metodo, ruta, cabeceras=None, cuerpo=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest(metodo, ruta, skip_host=True)
        c.putheader("Host", host or f"127.0.0.1:{self.port}")
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else b""
        for k, v in (cabeceras or {}).items():
            c.putheader(k, v)
        c.putheader("Content-Length", str(len(datos)))
        c.endheaders(datos)
        r = c.getresponse()
        cuerpo_resp = r.read().decode("utf-8")
        c.close()
        return r.status, cuerpo_resp

    def cerrar(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stderr.close()


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    for s in ("00_System", "07_Knowledge"):
        (vault / s).mkdir(parents=True)
    return vault


@pytest.fixture
def servicio(tmp_path):
    srv = Servicio(_vault(tmp_path))
    yield srv
    srv.cerrar()


CON_TOKEN = {"Authorization": f"Bearer {TOKEN}"}


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/status"), ("GET", "/flows/x"), ("POST", "/flows/start"),
    ("POST", "/events"), ("POST", "/flows/end"), ("POST", "/stop"),
])
def test_sin_token_no_se_atiende_ninguna_ruta(servicio, metodo, ruta):
    estado, _ = servicio.pedir(metodo, ruta, cuerpo={} if metodo == "POST" else None)
    assert estado == 401, (metodo, ruta, estado)


def test_un_token_equivocado_se_rechaza(servicio):
    estado, _ = servicio.pedir("GET", "/status", {"Authorization": "Bearer otro"})
    assert estado == 401


def test_con_token_se_atiende(servicio):
    estado, cuerpo = servicio.pedir("POST", "/flows/start", CON_TOKEN,
                                    {"flow_id": "f1", "operation": "prueba"})
    assert estado == 200 and json.loads(cuerpo)["ok"], cuerpo
    estado, cuerpo = servicio.pedir("GET", "/flows/f1", CON_TOKEN)
    assert estado == 200 and json.loads(cuerpo)["flow"]["flow_id"] == "f1"


def test_una_peticion_de_navegador_se_rechaza_aun_con_token(servicio):
    estado, _ = servicio.pedir("POST", "/stop", {**CON_TOKEN, "Origin": "https://evil.example"}, {})
    assert estado == 403


def test_un_host_ajeno_se_rechaza_anti_dns_rebinding(servicio):
    estado, _ = servicio.pedir("GET", "/status", CON_TOKEN, host=f"evil.example:{servicio.port}")
    assert estado == 403


def test_stop_sin_token_no_apaga_el_servicio(servicio):
    servicio.pedir("POST", "/stop", cuerpo={})
    time.sleep(0.5)
    assert servicio.proc.poll() is None
    estado, _ = servicio.pedir("GET", "/status", CON_TOKEN)
    assert estado == 200


def _cliente(vault: Path, *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "vault_token_counter.py"), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        env=_entorno(vault, None), cwd=str(vault),
    )
    return json.loads(r.stdout)


def test_sin_token_configurado_se_genera_uno_que_el_cliente_encuentra(tmp_path):
    """Default cerrado: sin variable de entorno el servicio genera el token y
    lo deja junto al fichero de puerto, dentro del vault (AP-36); el cliente
    lo lee de ahí. Quien no puede leer el vault no puede invocar el servicio."""
    vault = _vault(tmp_path)
    srv = Servicio(vault, token=None)
    try:
        estado, _ = srv.pedir("GET", "/status")
        assert estado == 401
        fichero = vault / "00_System"
        tokens = list(fichero.rglob("token-service.token"))
        assert len(tokens) == 1, tokens
        assert len(tokens[0].read_text(encoding="utf-8").strip()) >= 32
        resultado = _cliente(vault, "status")
        assert resultado.get("ok") is True, resultado
    finally:
        srv.cerrar()


def test_el_auto_test_del_cliente_sigue_en_verde(tmp_path):
    resultado = _cliente(_vault(tmp_path), "self-test")
    assert resultado.get("ok") is True, resultado


def test_la_ruta_del_token_cuelga_del_vault(tmp_path):
    sys.path.insert(0, str(REPO_ROOT))
    from vault.consulta.repositorio import RepositorioConsulta
    from vault.kernel import construir

    repo = RepositorioConsulta(construir(_vault(tmp_path)))
    assert repo.token_servicio_tokens.is_relative_to(repo.dir_uso_tokens)
    assert repo.token_servicio_tokens.parent == repo.puerto_servicio_tokens.parent


def test_sp04_cubre_el_servicio_de_tokens():
    sys.path.insert(0, str(SCRIPTS))
    import vault_norms_catalog

    norma = next(n for n in vault_norms_catalog.NORM_CATALOG if n["code"] == "SP-04")
    assert "vault_token_service" in norma["description"]
    assert "vault_token_service" in norma["tools_enforcing"]
