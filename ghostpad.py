"""
GhostPad - use o celular como ponte Bluetooth para jogar com o seu controle no PC.

Controle (Bluetooth) -> celular (navegador) -> Wi-Fi -> GhostPad (PC) -> Xbox 360 virtual.

Arquivo unico: interface (Flet) + servidor da ponte + pagina do celular embutida.
Requisitos: pip install flet aiohttp vgamepad cryptography segno
"""
import asyncio
import base64
import ctypes
import datetime
import io
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

# Sem console (exe empacotado) o stdout/stderr podem ser None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import flet as ft
from aiohttp import web, WSMsgType

APP_NOME = "GhostPad"
VERSAO = "1.0.0"
PORTA = 8443

DRIVER_URLS = [
    "https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe",
    "https://github.com/ViGEm/ViGEmBus/releases/download/v1.21.442.0/ViGEmBus_1.21.442_x64_x86_arm64.exe",
]

# --------------------------------------------------------------------------------------
# Pagina que roda no navegador do celular (embutida)
# --------------------------------------------------------------------------------------
HTML_CELULAR = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#000000">
<title>GhostPad</title>
<style>
  :root { color-scheme:dark; --bg:#000; --glass:rgba(32,32,36,.52); --fill-1:rgba(255,255,255,.06);
          --fill-2:rgba(255,255,255,.10); --fill-3:rgba(255,255,255,.16); --stroke:rgba(255,255,255,.10);
          --hl:rgba(255,255,255,.18); --text:#f5f5f7; --text-2:rgba(245,245,247,.70); --text-3:rgba(245,245,247,.44);
          --ok:#8fe3ac; --err:#ff8f8f; }
  * { box-sizing:border-box; }
  html { background:var(--bg); }
  body { margin:0; min-height:100dvh; color:var(--text); -webkit-font-smoothing:antialiased;
         font-family:"SF Pro Display",-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",system-ui,sans-serif;
         font-size:14px; line-height:1.5; letter-spacing:-.006em;
         background:radial-gradient(900px 560px at 50% -10%, rgba(255,255,255,.10), transparent 62%),
                    radial-gradient(700px 500px at 105% 105%, rgba(150,150,160,.07), transparent 62%), var(--bg);
         padding:max(18px, env(safe-area-inset-top)) 16px max(18px, env(safe-area-inset-bottom)); }
  .brand { display:flex; align-items:center; gap:12px; margin:6px 0 20px; }
  .mark { width:40px; height:40px; border-radius:12px; display:grid; place-items:center;
          background:linear-gradient(135deg,#55555e,#17171b); border:1px solid var(--stroke); box-shadow:inset 0 1px 0 var(--hl); }
  .mark svg { width:22px; height:22px; fill:none; stroke:#f5f5f7; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
  h1 { font-size:1.35rem; margin:0; font-weight:650; letter-spacing:-.02em; }
  .sub { color:var(--text-3); font-size:.75rem; }
  .glass { background:linear-gradient(180deg, rgba(255,255,255,.07), rgba(255,255,255,0) 38%), var(--glass);
           -webkit-backdrop-filter:blur(30px) saturate(1.8); backdrop-filter:blur(30px) saturate(1.8);
           border:1px solid var(--stroke); box-shadow:inset 0 1px 0 var(--hl), 0 30px 80px -34px rgba(0,0,0,.75); border-radius:22px; }
  .row { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:14px 16px; margin-bottom:10px; }
  .row small { color:var(--text-2); font-weight:500; font-size:.8rem; }
  .row .v { font-family:ui-monospace,"SF Mono",Consolas,monospace; font-weight:600; font-size:.8rem;
            text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:60%; }
  .ok { color:var(--ok); } .err { color:var(--err); }
  .sticks { display:flex; gap:14px; justify-content:center; margin:20px 0; }
  .stick { width:120px; height:120px; border-radius:50%; position:relative; background:var(--fill-1);
           border:1px solid var(--stroke); box-shadow:inset 0 1px 0 var(--hl); }
  .dot { width:24px; height:24px; border-radius:50%; background:#fff; position:absolute; left:47px; top:47px;
         box-shadow:0 1px 6px rgba(0,0,0,.5); }
  pre { padding:14px 16px; font-size:.75rem; color:var(--text-3); white-space:pre-wrap; margin:0 0 14px;
        font-family:ui-monospace,"SF Mono",Consolas,monospace; }
  button { width:100%; height:50px; font:inherit; font-size:1rem; font-weight:600; border:0; border-radius:999px;
           color:#0b0b0c; background:#f5f5f7; box-shadow:inset 0 1px 0 rgba(255,255,255,.35); transition:transform .12s, filter .16s; }
  button:active { transform:scale(.975); }
</style>
</head>
<body>
<div class="brand">
  <div class="mark"><svg viewBox="0 0 24 24"><path d="M6 11h4M8 9v4M15.5 12h.01M18 10h.01M17.3 7H6.7a3.7 3.7 0 0 0-3.6 4.6l1 4a2.6 2.6 0 0 0 4.5 1l1.1-1.6h6.6l1.1 1.6a2.6 2.6 0 0 0 4.5-1l1-4A3.7 3.7 0 0 0 17.3 7Z"/></svg></div>
  <div><h1>GhostPad</h1><div class="sub">Celular &rarr; PC &middot; ponte de controle</div></div>
</div>

<div class="glass row"><small>PC</small><span id="sPc" class="v err">desconectado</span></div>
<div class="glass row"><small>Controle</small><span id="sPad" class="v err">aperte um botão</span></div>

<div class="sticks">
  <div class="stick"><div class="dot" id="dL"></div></div>
  <div class="stick"><div class="dot" id="dR"></div></div>
</div>

<pre id="log" class="glass">Pareie o controle no Bluetooth do celular e aperte qualquer botão.</pre>
<button id="btn">Manter tela ligada</button>

<script>
const $ = id => document.getElementById(id);
let ws, last = "", lastPad = undefined, wake = null;

function conectar() {
  ws = new WebSocket(`wss://${location.host}/ws`);
  ws.onopen  = () => { $("sPc").textContent = "conectado"; $("sPc").className = "v ok"; lastPad = undefined; };
  ws.onclose = () => { $("sPc").textContent = "desconectado"; $("sPc").className = "v err"; setTimeout(conectar, 1000); };
}
conectar();

const dz = v => Math.abs(v) < 0.08 ? 0 : v;

function loop() {
  const gp = [...navigator.getGamepads()].find(g => g);
  const atual = gp ? gp.id : null;

  if (atual !== lastPad && ws.readyState === 1) {
    ws.send(JSON.stringify({ info: { controle: atual } }));
    lastPad = atual;
  }

  if (gp) {
    $("sPad").textContent = gp.id.split(" (")[0].slice(0, 32);
    $("sPad").className = "v ok";

    const b = [];
    gp.buttons.forEach((bt, i) => { if (i !== 6 && i !== 7 && bt.pressed) b.push(i); });
    const a = [0, 1, 2, 3].map(i => +dz(gp.axes[i] || 0).toFixed(3));
    const lt = +(gp.buttons[6]?.value || 0).toFixed(3);
    const rt = +(gp.buttons[7]?.value || 0).toFixed(3);

    const msg = JSON.stringify({ b, a, lt, rt });
    if (msg !== last && ws.readyState === 1) { ws.send(msg); last = msg; }

    $("dL").style.transform = `translate(${a[0]*36}px,${a[1]*36}px)`;
    $("dR").style.transform = `translate(${a[2]*36}px,${a[3]*36}px)`;
    $("log").textContent = `botoes: [${b}]\nLT: ${lt}  RT: ${rt}\neixos: ${a}`;
  } else {
    $("sPad").textContent = "aperte um botão";
    $("sPad").className = "v err";
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

$("btn").onclick = async () => {
  try { wake = await navigator.wakeLock.request("screen"); $("btn").textContent = "Tela ligada \u2714"; }
  catch (e) { $("btn").textContent = "Indisponível neste navegador"; }
};
document.addEventListener("visibilitychange", async () => {
  if (wake && document.visibilityState === "visible")
    wake = await navigator.wakeLock.request("screen").catch(() => null);
});
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------------------
# Utilitarios do Windows / rede
# --------------------------------------------------------------------------------------
def pasta_dados() -> Path:
    p = Path(os.environ.get("APPDATA", Path.home())) / APP_NOME
    p.mkdir(parents=True, exist_ok=True)
    return p


def ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def gerar_cert(ip: str):
    cert_f = pasta_dados() / f"cert-{ip}.pem"
    key_f = pasta_dados() / f"key-{ip}.pem"
    if cert_f.exists() and key_f.exists():
        return cert_f, key_f
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ghostpad")])
    agora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - datetime.timedelta(days=1))
        .not_valid_after(agora + datetime.timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_f.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_f.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_f, key_f


def driver_instalado() -> bool:
    """True se o servico do ViGEmBus existe no Windows."""
    if sys.platform != "win32":
        return False
    try:
        r = subprocess.run(
            ["sc", "query", "ViGEmBus"],
            capture_output=True,
            timeout=4,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception:
        return False


def baixar_driver() -> Path:
    destino = Path(tempfile.gettempdir()) / "GhostPad_ViGEmBus_Setup.exe"
    ultimo = None
    for url in DRIVER_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NOME}/{VERSAO}"})
            with urllib.request.urlopen(req, timeout=30) as r, open(destino, "wb") as f:
                while True:
                    bloco = r.read(1 << 16)
                    if not bloco:
                        break
                    f.write(bloco)
            if destino.stat().st_size > 1_000_000:
                return destino
        except Exception as e:
            ultimo = e
    raise RuntimeError(
        f"não foi possível baixar ({ultimo}). Baixe manualmente em github.com/nefarius/ViGEmBus/releases"
    )


def abrir_como_admin(caminho: Path) -> bool:
    if sys.platform != "win32":
        return False
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(caminho), None, None, 1)
    return r > 32


def qr_base64(texto: str) -> str:
    import segno

    buf = io.BytesIO()
    segno.make(texto, error="m").save(buf, kind="png", scale=7, border=2, dark="#000000", light="#FFFFFF")
    return base64.b64encode(buf.getvalue()).decode()


# 1x1 PNG transparente (placeholder do QR)
PNG_VAZIO = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


# --------------------------------------------------------------------------------------
# Servidor da ponte (WebSocket + controle Xbox 360 virtual)
# --------------------------------------------------------------------------------------
class Ponte:
    def __init__(self):
        self.rodando = False
        self.url = ""
        self.ip = ""
        self.clientes = 0
        self.controle = ""
        self.ultimo_cmd = 0.0
        self._log: list[str] = []
        self._lock = threading.Lock()
        self._thread = None
        self._loop = None
        self._stop = None
        self._wss = set()
        self._pad = None
        self._mapa = {}
        self._erro = None

    # ---- estado para a interface ----
    def log(self, msg: str):
        self._log.append(f"{datetime.datetime.now():%H:%M:%S}  {msg}")
        self._log = self._log[-40:]

    def status(self) -> dict:
        return {
            "rodando": self.rodando,
            "url": self.url,
            "ip": self.ip,
            "porta": PORTA,
            "clientes": self.clientes,
            "controle": self.controle,
            "ultimo_cmd": self.ultimo_cmd,
            "log": self._log[-8:],
        }

    # ---- controle virtual ----
    def _criar_pad(self):
        try:
            import vgamepad as vg
        except Exception as e:
            raise RuntimeError(f"Biblioteca vgamepad indisponível: {e}")
        try:
            pad = vg.VX360Gamepad()
        except Exception:
            raise RuntimeError(
                "Driver ViGEmBus não encontrado. Clique em INSTALAR DRIVER e reinicie o PC."
            )
        B = vg.XUSB_BUTTON
        self._mapa = {
            0: B.XUSB_GAMEPAD_A, 1: B.XUSB_GAMEPAD_B,
            2: B.XUSB_GAMEPAD_X, 3: B.XUSB_GAMEPAD_Y,
            4: B.XUSB_GAMEPAD_LEFT_SHOULDER, 5: B.XUSB_GAMEPAD_RIGHT_SHOULDER,
            8: B.XUSB_GAMEPAD_BACK, 9: B.XUSB_GAMEPAD_START,
            10: B.XUSB_GAMEPAD_LEFT_THUMB, 11: B.XUSB_GAMEPAD_RIGHT_THUMB,
            12: B.XUSB_GAMEPAD_DPAD_UP, 13: B.XUSB_GAMEPAD_DPAD_DOWN,
            14: B.XUSB_GAMEPAD_DPAD_LEFT, 15: B.XUSB_GAMEPAD_DPAD_RIGHT,
            16: B.XUSB_GAMEPAD_GUIDE,
        }
        return pad

    def _soltar_pad(self):
        pad, self._pad = self._pad, None
        if pad is not None:
            try:
                pad.reset()
                pad.update()
            except Exception:
                pass
            del pad  # desconecta o controle virtual

    def _aplicar(self, d):
        pad = self._pad
        if pad is None:
            return
        if d is None:
            pad.reset()
            pad.update()
            return

        info = d.get("info")
        if info is not None:
            nome = info.get("controle")
            self.controle = (str(nome).split(" (")[0].strip()[:42] or "Controle") if nome else ""
            self.log(f"Controle detectado: {self.controle}" if self.controle else "Controle desconectado do celular")
            return

        pad.reset()
        for i in d.get("b", []):
            if i in self._mapa:
                pad.press_button(self._mapa[i])
        a = d.get("a", [0, 0, 0, 0])
        # Eixo Y do navegador: baixo = positivo; XInput: cima = positivo
        pad.left_joystick_float(a[0], -a[1])
        pad.right_joystick_float(a[2], -a[3])
        pad.left_trigger_float(d.get("lt", 0))
        pad.right_trigger_float(d.get("rt", 0))
        pad.update()
        self.ultimo_cmd = time.time()

    # ---- ciclo de vida ----
    def iniciar(self):
        with self._lock:
            if self.rodando:
                return
            self._pad = self._criar_pad()
            self._erro = None
            pronto = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(pronto,), daemon=True)
            self._thread.start()
            pronto.wait(15)
            if self._erro or not self.rodando:
                msg = self._erro or "Tempo esgotado ao iniciar o servidor."
                self._soltar_pad()
                raise RuntimeError(msg)
            self.log("Servidor iniciado")

    def parar(self):
        with self._lock:
            if self.rodando and self._loop and self._stop:
                self._loop.call_soon_threadsafe(self._stop.set)
                if self._thread:
                    self._thread.join(8)
            self._soltar_pad()
            if self.url:
                self.log("Servidor parado")
            self.rodando = False
            self.url = ""
            self.clientes = 0
            self.controle = ""
            self.ultimo_cmd = 0.0

    def _run(self, pronto: threading.Event):
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._main(pronto))
        except OSError as e:
            self._erro = f"Não foi possível abrir a porta {PORTA} (já está em uso?): {e}"
            pronto.set()
        except Exception as e:
            self._erro = f"Falha ao iniciar: {e}"
            pronto.set()
        finally:
            self.rodando = False
            self._loop.close()

    async def _main(self, pronto: threading.Event):
        ip = ip_local()
        cert, key = gerar_cert(ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)

        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._ws)
        app.on_shutdown.append(self._fechar_sockets)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORTA, ssl_context=ctx).start()

        self._stop = asyncio.Event()
        self.ip = ip
        self.url = f"https://{ip}:{PORTA}"
        self.rodando = True
        pronto.set()
        await self._stop.wait()
        await runner.cleanup()

    async def _fechar_sockets(self, _app):
        for ws in set(self._wss):
            await ws.close(code=1001)

    async def _index(self, _request):
        return web.Response(text=HTML_CELULAR, content_type="text/html")

    async def _ws(self, request):
        ws = web.WebSocketResponse(heartbeat=10)
        await ws.prepare(request)
        self._wss.add(ws)
        self.clientes = len(self._wss)
        self.log(f"Celular conectado: {request.remote}")
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        self._aplicar(json.loads(msg.data))
                    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                        pass
        finally:
            self._wss.discard(ws)
            self.clientes = len(self._wss)
            if not self._wss:
                self.controle = ""
                self.ultimo_cmd = 0.0
            self._aplicar(None)
            self.log("Celular desconectado")
        return ws


PONTE = Ponte()

# --------------------------------------------------------------------------------------
# Interface (Flet) - visual futurista
# --------------------------------------------------------------------------------------
BG0, BG1 = "#000000", "#0B0B0D"
PAINEL = "#202024"
BORDA = "#1A1A1A"  # branco ~10% sobre preto
CIANO, MAGENTA = "#F5F5F7", "#A1A1A8"  # destaque (branco) e secundario (cinza)
VERDE, VERMELHO, AMBAR = "#8FE3AC", "#FF8F8F", "#FFD479"
TEXTO, MUDO = "#F5F5F7", "#8B8B90"
MONO = "Consolas"
FONTE = "Segoe UI Variable Display, Segoe UI, Inter, sans-serif"
BRANCO = "#FFFFFF"

COR_ESTADO = {"ok": VERDE, "off": VERMELHO, "warn": AMBAR, "idle": MUDO}


def op(cor: str, alfa: float) -> str:
    return ft.Colors.with_opacity(alfa, cor)


def txt(valor, size=13, cor=TEXTO, peso=ft.FontWeight.W_400, mono=False, ls=None, **kw):
    return ft.Text(
        valor,
        size=size,
        color=cor,
        weight=peso,
        font_family=MONO if mono else None,
        style=None,  # Silhueta nao usa tracking aberto
        **kw,
    )


def glow(cor: str, forca: float = 0.35, raio: int = 22):
    # tema grafite: sem brilho colorido (--accent-glow transparente)
    return None


def painel(conteudo, cor_borda=op(BRANCO, 0.10), brilho: str | None = None, padding=16) -> ft.Container:
    return ft.Container(
        content=conteudo,
        padding=padding,
        border_radius=ft.BorderRadius.all(22),
        border=ft.Border.all(1, cor_borda),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER,
            end=ft.Alignment.BOTTOM_CENTER,
            colors=[op(BRANCO, 0.07), op(PAINEL, 0.55)],
        ),
        shadow=ft.BoxShadow(blur_radius=40, color=op("#000000", 0.6), offset=ft.Offset(0, 18)),
    )


class BotaoNeon:
    """Botao grande com brilho; muda texto/cor/icone conforme o estado."""

    def __init__(self, texto, icone, cor, on_click, altura=54):
        self.cor = cor
        self.ativo = True
        self.icone = ft.Icon(icone, color=BG0, size=22)
        self.rotulo = txt(texto, 14, BG0, ft.FontWeight.W_600)
        self.control = ft.Container(
            content=ft.Row(
                [self.icone, self.rotulo],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
            height=altura,
            border_radius=ft.BorderRadius.all(999),
            bgcolor=cor,
            ink=True,
            on_click=on_click,
            on_hover=self._hover,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        )

    def _hover(self, e):
        if not self.ativo:
            return
        forte = str(e.data).lower() == "true"
        self.control.opacity = 0.9 if forte else 1
        self.control.update()

    def set(self, texto, icone, cor, ativo=True):
        self.cor, self.ativo = cor, ativo
        self.rotulo.value = texto
        self.icone.icon = icone
        self.control.bgcolor = cor if ativo else op(cor, 0.35)


class LinhaStatus:
    """Linha de status: icone, titulo, valor, detalhe e LED."""

    def __init__(self, icone, titulo):
        self.icone = ft.Icon(icone, color=MUDO, size=22)
        self.led = ft.Container(width=10, height=10, border_radius=ft.BorderRadius.all(5), bgcolor=MUDO)
        self.valor = txt("—", 13, MUDO, ft.FontWeight.W_700, mono=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.detalhe = txt("", 11, MUDO, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.control = ft.Container(
            content=ft.Row(
                [
                    self.icone,
                    ft.Column(
                        [txt(titulo, 12, TEXTO, ft.FontWeight.W_500), self.valor, self.detalhe],
                        spacing=2,
                        expand=True,
                    ),
                    self.led,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=14,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1, op(BRANCO, 0.10)),
            bgcolor=op(BRANCO, 0.06),
        )

    def set(self, estado: str, valor: str, detalhe: str = ""):
        cor = COR_ESTADO[estado]
        self.valor.value = valor
        self.valor.color = cor if estado != "idle" else MUDO
        self.detalhe.value = detalhe
        self.icone.color = cor
        self.led.bgcolor = cor
        self.led.shadow = None
        self.control.border = ft.Border.all(1, op(cor, 0.30) if estado != "idle" else op(BRANCO, 0.10))


def passo(numero: int, titulo: str, texto: str) -> ft.Container:
    selo = ft.Container(
        content=txt(str(numero), 15, BG0, ft.FontWeight.W_700, mono=True),
        width=36,
        height=36,
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(18),
        bgcolor=CIANO,
    )
    return painel(
        ft.Row(
            [
                selo,
                ft.Column(
                    [txt(titulo, 14, TEXTO, ft.FontWeight.W_600), txt(texto, 12, MUDO)],
                    spacing=4,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=14,
        ),
        padding=14,
    )


def dica(titulo: str, texto: str, cor: str = AMBAR) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [txt(titulo, 12.5, cor, ft.FontWeight.W_600), txt(texto, 12, MUDO)],
            spacing=4,
        ),
        padding=14,
        border_radius=ft.BorderRadius.all(18),
        border=ft.Border.all(1, op(cor, 0.30)),
        bgcolor=op(cor, 0.06),
    )


def main(page: ft.Page):
    page.title = f"{APP_NOME} — ponte de controle"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG0
    page.theme = ft.Theme(font_family="Segoe UI")
    page.padding = 0
    page.window.width = 540
    page.window.height = 920
    page.window.min_width = 480
    page.window.min_height = 720

    clip = ft.Clipboard()
    page.services.append(clip)

    st = {"ocupado": False, "instalando": False, "driver": False, "qr_url": ""}

    # ---------------- cabecalho ----------------
    logo = ft.Container(
        content=ft.Icon(ft.Icons.SPORTS_ESPORTS_OUTLINED, color=TEXTO, size=26),
        width=48,
        height=48,
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, op(BRANCO, 0.10)),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=["#55555E", "#17171B"]
        ),
    )
    titulo = ft.Text("GhostPad", size=26, weight=ft.FontWeight.W_700, color=TEXTO)
    chip_texto = txt("Offline", 12, VERMELHO, ft.FontWeight.W_600)
    chip_led = ft.Container(width=8, height=8, border_radius=ft.BorderRadius.all(4), bgcolor=VERMELHO)
    chip = ft.Container(
        content=ft.Row([chip_led, chip_texto], spacing=8, tight=True),
        padding=ft.Padding.symmetric(horizontal=12, vertical=7),
        border_radius=ft.BorderRadius.all(999),
        border=ft.Border.all(1, op(VERMELHO, 0.35)),
        bgcolor=op(VERMELHO, 0.08),
    )
    cabecalho = ft.Row(
        [
            logo,
            ft.Column(
                [titulo, txt("Bluetooth › Wi-Fi › PC", 12, MUDO)],
                spacing=0,
                expand=True,
            ),
            chip,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=14,
    )

    # ---------------- abas ----------------
    aba_estado = {"atual": "painel"}

    def pilula(texto, chave):
        c = ft.Container(
            content=txt(texto, 13, MUDO, ft.FontWeight.W_500),
            padding=ft.Padding.symmetric(horizontal=18, vertical=8),
            border_radius=ft.BorderRadius.all(10),
            expand=True,
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda e: trocar_aba(chave),
        )
        return c

    pil_painel, pil_tutorial = pilula("Painel", "painel"), pilula("Tutorial", "tutorial")

    def trocar_aba(chave: str):
        aba_estado["atual"] = chave
        view_painel.visible = chave == "painel"
        view_tutorial.visible = chave == "tutorial"
        for c, k in ((pil_painel, "painel"), (pil_tutorial, "tutorial")):
            ativo = k == chave
            c.bgcolor = op(BRANCO, 0.16) if ativo else None
            c.content.color = TEXTO if ativo else MUDO
        page.update()

    abas = ft.Container(
        content=ft.Row([pil_painel, pil_tutorial], spacing=2),
        padding=3,
        border_radius=ft.BorderRadius.all(13),
        border=ft.Border.all(1, op(BRANCO, 0.10)),
        bgcolor=op(BRANCO, 0.06),
    )

    # ---------------- painel: botao principal ----------------
    erro_txt = txt("", 12, VERMELHO, max_lines=4)
    erro_box = ft.Container(
        content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=VERMELHO, size=18), ft.Container(erro_txt, expand=True)], spacing=10),
        padding=12,
        border_radius=ft.BorderRadius.all(18),
        border=ft.Border.all(1, op(VERMELHO, 0.35)),
        bgcolor=op(VERMELHO, 0.08),
        visible=False,
    )

    def mostrar_erro(msg: str):
        erro_txt.value = msg
        erro_box.visible = bool(msg)

    async def alternar(e):
        if st["ocupado"]:
            return
        st["ocupado"] = True
        mostrar_erro("")
        btn_servidor.set("Aguarde...", ft.Icons.HOURGLASS_TOP, AMBAR, ativo=False)
        page.update()
        try:
            if PONTE.rodando:
                await asyncio.to_thread(PONTE.parar)
            else:
                if not st["driver"]:
                    raise RuntimeError("Instale o driver primeiro (botão Instalar driver abaixo) e reinicie o PC se o instalador pedir.")
                await asyncio.to_thread(PONTE.iniciar)
        except Exception as ex:
            mostrar_erro(str(ex))
        finally:
            st["ocupado"] = False
        page.update()

    btn_servidor = BotaoNeon("Iniciar servidor", ft.Icons.POWER_SETTINGS_NEW, CIANO, alternar, altura=56)

    # ---------------- painel: endereco para o celular ----------------
    url_txt = txt("", 19, TEXTO, ft.FontWeight.W_600, mono=True, selectable=True)
    chip_porta = ft.Container(
        content=txt(f"Porta {PORTA}", 11, TEXTO, ft.FontWeight.W_500),
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=ft.BorderRadius.all(999),
        border=ft.Border.all(1, op(BRANCO, 0.16)),
        bgcolor=op(BRANCO, 0.06),
    )
    chip_https = ft.Container(
        content=txt("HTTPS", 11, TEXTO, ft.FontWeight.W_500),
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=ft.BorderRadius.all(999),
        border=ft.Border.all(1, op(BRANCO, 0.16)),
        bgcolor=op(BRANCO, 0.06),
    )

    async def copiar(e):
        if PONTE.url:
            await clip.set(PONTE.url)
            page.show_dialog(ft.SnackBar(txt("Endereço copiado", 12, BG0, ft.FontWeight.W_600), bgcolor=CIANO, duration=1500))

    qr_img = ft.Image(src=PNG_VAZIO, width=168, height=168, border_radius=ft.BorderRadius.all(12))

    bloco_url = painel(
        ft.Column(
            [
                txt("Abra no navegador do celular", 12, MUDO, ft.FontWeight.W_500),
                ft.Row(
                    [ft.Container(url_txt, expand=True), ft.IconButton(icon=ft.Icons.CONTENT_COPY, icon_color=CIANO, tooltip="Copiar endereço", on_click=copiar)],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row([chip_porta, chip_https], spacing=8),
                ft.Row(
                    [
                        ft.Container(
                            qr_img,
                            padding=6,
                            border_radius=ft.BorderRadius.all(18),
                            bgcolor="#FFFFFF",
                        ),
                        ft.Column(
                            [
                                txt("Escaneie o QR Code ou digite o endereço.", 12, TEXTO),
                                txt("Celular e PC precisam estar no mesmo Wi-Fi.", 11, MUDO),
                                txt("Aviso de certificado? Avançado › continuar. É normal: o certificado é local.", 11, MUDO),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                    ],
                    spacing=16,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=12,
        ),
    )
    bloco_url.visible = False

    # ---------------- painel: status ----------------
    l_driver = LinhaStatus(ft.Icons.DEVELOPER_BOARD, "Driver ViGEmBus")
    l_servidor = LinhaStatus(ft.Icons.DNS, "Servidor")
    l_celular = LinhaStatus(ft.Icons.SMARTPHONE, "Celular")
    l_controle = LinhaStatus(ft.Icons.SPORTS_ESPORTS, "Controle (Bluetooth)")
    l_virtual = LinhaStatus(ft.Icons.COMPUTER, "Controle virtual no PC")

    drv_msg = txt("", 11, MUDO)
    drv_barra = ft.ProgressBar(color=CIANO, bgcolor=op(BRANCO, 0.14), visible=False)

    async def instalar_driver(e):
        if st["instalando"]:
            return
        st["instalando"] = True
        drv_barra.visible = True
        drv_msg.value = "Baixando o driver..."
        drv_msg.color = MUDO
        page.update()
        try:
            caminho = await asyncio.to_thread(baixar_driver)
            drv_msg.value = "Instalador aberto. Aceite o aviso do Windows e conclua. Se pedir, reinicie o PC."
            ok = await asyncio.to_thread(abrir_como_admin, caminho)
            if not ok:
                drv_msg.value = "Instalação cancelada (permissão de administrador negada)."
                drv_msg.color = AMBAR
        except Exception as ex:
            drv_msg.value = f"Falha: {ex}"
            drv_msg.color = VERMELHO
        finally:
            drv_barra.visible = False
            st["instalando"] = False
        page.update()

    btn_driver = BotaoNeon("Instalar driver", ft.Icons.DOWNLOAD, CIANO, instalar_driver, altura=46)
    bloco_driver = ft.Column([btn_driver.control, drv_barra, drv_msg], spacing=8, visible=False)

    log_txt = txt("Aguardando...", 11, MUDO, mono=True)
    log_box = painel(
        ft.Column(
            [txt("Console", 12, MUDO, ft.FontWeight.W_500), log_txt],
            spacing=8,
        ),
        padding=14,
    )

    view_painel = ft.Column(
        [
            btn_servidor.control,
            erro_box,
            bloco_url,
            txt("Status do sistema", 13, TEXTO, ft.FontWeight.W_600),
            l_driver.control,
            bloco_driver,
            l_servidor.control,
            l_celular.control,
            l_controle.control,
            l_virtual.control,
            log_box,
        ],
        spacing=12,
    )

    # ---------------- tutorial ----------------
    view_tutorial = ft.Column(
        [
            txt("Como usar", 13, TEXTO, ft.FontWeight.W_600),
            passo(1, "Instale o driver (uma vez)", "No Painel, clique em Instalar driver e confirme o aviso do Windows. Reinicie o PC se o instalador pedir. O status do driver fica verde."),
            passo(2, "Pareie o controle no celular", "No Bluetooth do celular, coloque o controle em modo de pareamento (no PS4: segure PS + Share até a luz piscar rápido) e conecte."),
            passo(3, "Inicie o servidor", "Clique em Iniciar servidor. O app mostra o endereço, a porta e um QR Code."),
            passo(4, "Abra o endereço no celular", "Use o Chrome (Android) ou o Safari (iPhone), no mesmo Wi-Fi do PC. Aceite o aviso de certificado (Avançado › continuar). Se o Firewall do Windows perguntar, permita em rede privada."),
            passo(5, "Mantenha a tela ligada", "Na página do celular, toque em Manter tela ligada e deixe o navegador aberto em primeiro plano."),
            passo(6, "Aperte um botão no controle", "No painel, Celular, Controle e Controle virtual ficam verdes. Teste no Windows (Win+R › joy.cpl) ou direto no Steam e nos jogos."),
            dica("Dica", "Wi-Fi de 5 GHz reduz a latência. Evite deixar o celular em economia de bateria."),
            dica("2 controles no joy.cpl?", "Há duas abas do navegador conectadas. Feche as extras no celular.", MAGENTA),
            dica("Não conecta?", "Confira se PC e celular estão na mesma rede, se o servidor está online e se o IP mostrado mudou. Se mudou, abra o novo endereço.", CIANO),
            txt(f"{APP_NOME} v{VERSAO} · driver ViGEmBus por Nefarius (projeto sem manutenção, mas funcional)", 10, MUDO),
        ],
        spacing=12,
        visible=False,
    )

    # ---------------- raiz ----------------
    page.add(
        ft.Container(
            expand=True,
            gradient=ft.RadialGradient(
                center=ft.Alignment(0, -1.1), radius=1.3, colors=[op(BRANCO, 0.10), BG0], stops=[0, 0.62]
            ),
            padding=ft.Padding.all(20),
            content=ft.Column(
                [cabecalho, abas, view_painel, view_tutorial],
                spacing=18,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        )
    )

    # ---------------- atualizacao periodica ----------------
    def aplicar(s: dict):
        rodando, n = s["rodando"], s["clientes"]
        drv = st["driver"]

        # driver
        if drv:
            l_driver.set("ok", "Instalado", "Controle virtual disponível")
        else:
            l_driver.set("off", "Não instalado", "Necessário para criar o controle virtual")
        bloco_driver.visible = not drv

        # servidor
        if rodando:
            l_servidor.set("ok", "Online", f"{s['ip']} · porta {s['porta']} · HTTPS")
        else:
            l_servidor.set("off", "Offline", "Clique em Iniciar servidor")

        # celular
        if n:
            l_celular.set("ok", "Conectado", f"{n} dispositivo(s) na ponte")
        elif rodando:
            l_celular.set("warn", "Aguardando", "Abra o endereço no navegador do celular")
        else:
            l_celular.set("idle", "—", "Servidor desligado")

        # controle
        if s["controle"]:
            l_controle.set("ok", s["controle"], "Detectado pelo celular via Bluetooth")
        elif n:
            l_controle.set("warn", "Não detectado", "Pareie o controle no celular e aperte um botão")
        else:
            l_controle.set("idle", "—", "Aguardando o celular")

        # controle virtual
        if rodando:
            if s["ultimo_cmd"]:
                seg = time.time() - s["ultimo_cmd"]
                if seg < 3:
                    l_virtual.set("ok", "Recebendo comandos", "Xbox 360 virtual ativo no Windows")
                else:
                    l_virtual.set("ok", "Ativo", f"Último comando há {int(seg)} s")
            else:
                l_virtual.set("warn", "Criado · sem comandos", "Xbox 360 virtual aguardando entrada")
        else:
            l_virtual.set("idle", "Inativo", "Nenhum controle virtual criado")

        # botao principal + cabecalho
        if not st["ocupado"]:
            if rodando:
                btn_servidor.set("Parar servidor", ft.Icons.STOP_CIRCLE, VERMELHO)
            else:
                btn_servidor.set("Iniciar servidor", ft.Icons.POWER_SETTINGS_NEW, CIANO)

        if rodando and n and s["controle"]:
            cor, texto = VERDE, "Pronto para jogar"
        elif rodando:
            cor, texto = AMBAR, "Aguardando"
        else:
            cor, texto = VERMELHO, "Offline"
        chip_texto.value, chip_texto.color = texto, cor
        chip_led.bgcolor = cor
        chip.border = ft.Border.all(1, op(cor, 0.35))
        chip.bgcolor = op(cor, 0.08)

        # endereco + QR
        bloco_url.visible = rodando
        if rodando:
            url_txt.value = s["url"]
            if st["qr_url"] != s["url"]:
                try:
                    qr_img.src = qr_base64(s["url"])
                    st["qr_url"] = s["url"]
                except Exception:
                    pass

        log_txt.value = "\n".join(s["log"]) if s["log"] else "Aguardando..."

    async def atualizar():
        n = 0
        while True:
            if n % 8 == 0:
                st["driver"] = await asyncio.to_thread(driver_instalado)
            n += 1
            aplicar(PONTE.status())
            try:
                page.update()
            except Exception:
                return  # janela fechada
            await asyncio.sleep(0.4)

    trocar_aba("painel")
    page.run_task(atualizar)


if __name__ == "__main__":
    try:
        ft.run(main)
    finally:
        PONTE.parar()
        os._exit(0)
