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
    #: Techo de espera del arranque. NO es una espera: el test sondea la
    #: conexión cada 100 ms y vuelve en cuanto el servicio escucha. El techo
    #: estaba en 30 s y en macOS (run 40299732445 → 40340865847) el servicio
    #: tardaba mas: el test fallaba 12 veces por job —1 FAIL y 11 ERROR— sin
    #: decir ni por que. Con el techo de 120 s el caso lento pasa; y si el
    #: servicio no llega, el mensaje dice el codigo de salida, si el proceso
    #: sigue vivo, su stderr acotado y el tiempo que tardo.
    PLAZO_ARRANQUE = 120.0
    #: Cuanto stderr se guarda para el diagnostico (el pipe puede ser enorme).
    MAX_STDERR = 4096

    def __init__(self, vault: Path, token=TOKEN, port=None):
        self.vault = vault
        self.token = token
        # Puerto 0: que lo elija el sistema y lo publique el servicio. Elegir
        # un puerto "libre" y cerrarlo antes de que lo tome el servicio es una
        # carrera (8 workers en paralelo y 12 servicios por worker en el mismo
        # job): el otro puede ocuparlo y el servicio no puede enlazar. Con
        # puerto 0 no hay carrera, y el fichero de puerto dice el que se usó.
        self.pedido = 0 if port is None else port
        self.port = self.pedido
        self.proc = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "vault_token_service.py"),
             "--port", str(self.pedido)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            env=_entorno(vault, token), cwd=str(vault),
        )
        inicio = time.time()
        limite = inicio + self.PLAZO_ARRANQUE
        while time.time() < limite:
            # El servicio escribe el fichero de puerto DESPUES de enlazar: su
            # aparicion es la senal de "ya escucha".
            leido = self._puerto_del_fichero()
            if leido:
                try:
                    with socket.create_connection(("127.0.0.1", leido), timeout=0.5):
                        self.port = leido
                        return
                except OSError:
                    pass
            if self.proc.poll() is not None:
                raise RuntimeError(self._diagnostico(inicio, "el proceso termino"))
            time.sleep(0.1)
        raise RuntimeError(self._diagnostico(inicio, "el servicio no abrio el puerto"))

    def _puerto_del_fichero(self):
        try:
            texto = (self.vault / "00_System" / "token-usage" /
                     "token-service.port").read_text(encoding="utf-8").strip()
            return int(texto) if texto else None
        except (OSError, ValueError):
            return None

    def _diagnostico(self, inicio: float, motivo: str) -> str:
        """Por que no arranca, con lo que se puede saber SIN el token.

        El token (fijo o generado) no aparece: se redacta del stderr. Se
        informa del codigo de salida, de si el proceso sigue vivo, del stderr
        acotado, del puerto pedido, de si el fichero de puerto existe (el
        servicio lo escribe DESPUES de enlazar: su presencia significa "ya
        escucha") y del tiempo transcurrido.
        """
        elapsed = time.time() - inicio
        vivo = self.proc.poll() is None
        codigo = self.proc.poll()
        stderr = b""
        try:
            if not vivo:
                stderr = self.proc.stderr.read() or b""
        except (OSError, ValueError):
            stderr = b""
        texto = stderr.decode("utf-8", "replace")[-self.MAX_STDERR:]
        # El token no sale: el generado esta en su fichero y el fijo lo sabe
        # el test. Se redacta lo que se parezca a el.
        for valor in self._tokens_posibles():
            if valor:
                texto = texto.replace(valor, "<TOKEN>")
        fichero_puerto = self.vault / "00_System" / "token-usage" / "token-service.port"
        try:
            puerto_en_fichero = fichero_puerto.read_text(encoding="utf-8").strip()
        except OSError:
            puerto_en_fichero = "(sin fichero de puerto)"
        return (
            f"{motivo} en {elapsed:.1f} s | puerto pedido {self.pedido} | "
            f"vivo={vivo} codigo={codigo} | "
            f"fichero de puerto: {puerto_en_fichero} | "
            f"stderr (ultimos {self.MAX_STDERR} bytes): {texto.strip() or '(vacio)'}"
        )

    def _tokens_posibles(self):
        """Los tokens que pueden aparecer en el stderr: el pedido y el generado."""
        valores = [self.token or ""]
        try:
            valores.append((self.vault / "00_System" / "token-usage" /
                             "token-service.token").read_text(encoding="utf-8").strip())
        except OSError:
            pass
        return [v for v in valores if v]

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
    """Un navegador puede mandar `POST /stop` con formulario —y el cuerpo que
    trae no puede convertir el rechazo en una conexión cortada a RST.

    Medido el 2026-10-26 en la CI (Windows 3.10, corrida `40420024458`): el
    servicio respondía 403 cerrando la conexión con el cuerpo SIN LEER, el
    núcleo respondía RST (WinError 10053) y el cliente veía
    `ConnectionAbortedError` en vez del 403 — solo en 1 de 8 columnas, porque
    es la carrera del RST contra la lectura del cliente. El servicio ahora
    drena el cuerpo antes de responder; el test lo pide varias veces para que
    la carrera, si volviera, no se esconda tras el azar.
    """
    for _ in range(5):
        estado, _ = servicio.pedir("POST", "/stop", {**CON_TOKEN, "Origin": "https://evil.example"}, {})
        assert estado == 403


# ── QA-R13-06: el cuerpo se consume UNA vez, con techo de bytes y plazo ──────

def test_post_autenticado_a_ruta_desconocida_con_json_da_404_pronto(servicio):
    """QA-R13-06 (1): POST autenticado a ruta inexistente con JSON no vacío
    responde 404 PRONTO. Con la corrección R13-05 tal cual, el cuerpo se
    consumía DOS veces (`_payload` y el 404 re-drenando) y la segunda lectura,
    sin bytes, bloqueaba al worker: el 404 no llegaba nunca. El plazo del test
    (8 s) es más holgado que el del servicio (5 s): un cuelgue se ve como
    timeout, no como un 404 tarde.
    """
    with socket.create_connection(("127.0.0.1", servicio.port), timeout=8) as s:
        cuerpo = b'{"x": "y"}'
        cab = (f"POST /ruta-que-no-existe HTTP/1.0\r\n"
               f"Host: 127.0.0.1:{servicio.port}\r\n"
               f"Authorization: {CON_TOKEN['Authorization']}\r\n"
               f"Content-Length: {len(cuerpo)}\r\n\r\n").encode("utf-8")
        s.sendall(cab + cuerpo)
        t0 = time.monotonic()
        s.settimeout(8)
        datos = b""
        while b"\r\n\r\n" not in datos:
            pedazo = s.recv(65536)
            if not pedazo:
                break
            datos += pedazo
        primera = datos.split(b"\r\n", 1)[0].decode("latin-1")
        tardado = time.monotonic() - t0
    assert " 404 " in primera, primera
    assert tardado < 8.0, f"el 404 tardó {tardado:.1f} s: el worker se quedó esperando"


def test_rechazo_con_cuerpo_declarado_incompleto_no_retien_el_worker(servicio):
    """QA-R13-06 (2, 4): un cliente que declara más cuerpo del que envía no
    retiene al worker más allá del plazo del servicio (5 s): la respuesta
    llega dentro del plazo del test y el servicio sigue vivo después.
    """
    with socket.create_connection(("127.0.0.1", servicio.port), timeout=12) as s:
        cab = (f"POST /events HTTP/1.0\r\n"
               f"Host: 127.0.0.1:{servicio.port}\r\n"
               f"Content-Length: 100\r\n\r\n").encode("utf-8")
        s.sendall(cab + b'{"x": "y", "pa')  # 15 de los 100 bytes declarados
        t0 = time.monotonic()
        s.settimeout(12)
        datos = b""
        while b"\r\n\r\n" not in datos:
            pedazo = s.recv(65536)
            if not pedazo:
                break
            datos += pedazo
        primera = datos.split(b"\r\n", 1)[0].decode("latin-1")
        tardado = time.monotonic() - t0
    assert " 401 " in primera, primera
    assert tardado < 12.0, f"el rechazo tardó {tardado:.1f} s: el plazo no mordió"
    assert servicio.proc.poll() is None, "el servicio murió durante el drenaje"


def test_get_con_cuerpo_declarado_incompleto_no_retien(servicio):
    """QA-R13-06 (4): un GET con cuerpo declarado y no enviado tampoco retiene
    al worker: drena con el mismo presupuesto y responde 200 de /status.
    """
    with socket.create_connection(("127.0.0.1", servicio.port), timeout=12) as s:
        cab = (f"GET /status HTTP/1.0\r\n"
               f"Host: 127.0.0.1:{servicio.port}\r\n"
               f"Authorization: {CON_TOKEN['Authorization']}\r\n"
               f"Content-Length: 10\r\n\r\n").encode("utf-8")
        s.sendall(cab + b"abc")
        t0 = time.monotonic()
        s.settimeout(12)
        datos = b""
        while b"\r\n\r\n" not in datos:
            pedazo = s.recv(65536)
            if not pedazo:
                break
            datos += pedazo
        primera = datos.split(b"\r\n", 1)[0].decode("latin-1")
        tardado = time.monotonic() - t0
    assert " 200 " in primera, primera
    assert tardado < 12.0, f"/status tardó {tardado:.1f} s con un GET cuerpo roto"


def test_cuerpo_mayor_que_el_limite_da_413_sin_bloquear(servicio):
    """QA-R13-06 (3): un cuerpo mayor que el techo (1 MiB) no se lee entero ni
    bloquea: el drenaje para en el techo, `_payload` lo marca y responde 413.
    El cliente envía poco (200 KiB) pero declara 2 MiB: el drenaje espera su
    plazo, no hay bytes en vuelo y la respuesta llega sin carrera de RST.
    """
    with socket.create_connection(("127.0.0.1", servicio.port), timeout=12) as s:
        cuerpo = b'{"nota": "' + b"x" * (200 * 1024) + b'"}'
        cab = (f"POST /flows/start HTTP/1.0\r\n"
               f"Host: 127.0.0.1:{servicio.port}\r\n"
               f"Authorization: {CON_TOKEN['Authorization']}\r\n"
               f"Content-Length: {2 * 1024 * 1024}\r\n\r\n").encode("utf-8")
        s.sendall(cab + cuerpo)
        t0 = time.monotonic()
        s.settimeout(12)
        datos = b""
        while b"\r\n\r\n" not in datos:
            pedazo = s.recv(65536)
            if not pedazo:
                break
            datos += pedazo
        primera = datos.split(b"\r\n", 1)[0].decode("latin-1")
        tardado = time.monotonic() - t0
    assert " 413 " in primera, primera
    assert tardado < 12.0, f"el 413 tardó {tardado:.1f} s"


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


def test_el_arranque_que_falla_dice_el_codigo_y_el_stderr(tmp_path):
    """Un arranque que no llega tiene que explicar por que, no solo fallar.

    Medido el 2026-10-26 en la CI (macOS): `RuntimeError: el servicio no
    abrió el puerto` y nada mas —ni codigo de salida, ni si el proceso
    seguía vivo, ni su stderr— en 12 arranques por job. Aquí el servicio
    recibe un puerto YA OCUPADO: no puede enlazar y muere; el diagnostico
    tiene que decir el codigo, la salida y que el fichero de puerto no esta
    (el servicio lo escribe DESPUES de enlazar).
    """
    vault = _vault(tmp_path)
    with socket.socket() as ocupado:
        ocupado.bind(("127.0.0.1", 0))
        puerto = ocupado.getsockname()[1]
        with pytest.raises(RuntimeError) as exc:
            Servicio(vault, token=TOKEN, port=puerto)
    mensaje = str(exc.value)
    assert "el proceso termino" in mensaje, mensaje
    assert "codigo=" in mensaje, mensaje
    assert "fichero de puerto" in mensaje, mensaje
    # El token NO sale en el diagnostico.
    assert TOKEN not in mensaje, mensaje


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
