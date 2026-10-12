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
<meta name="theme-color" content="#04050b">
<title>GhostPad</title>
<style>
  :root { --bg:#000; --panel:#0a0a0b; --line:#27272a; --fg:#fafafa; --mut:#a1a1aa;
          --cy:#3b9dff; --ok:#22c55e; --err:#ef4444; }
  * { box-sizing:border-box; }
  html, body { margin:0; min-height:100%; color:var(--fg); background:#000;
               font-family:system-ui,-apple-system,"Segoe UI",sans-serif; }
  body { padding:max(22px, env(safe-area-inset-top)) 18px max(22px, env(safe-area-inset-bottom)); }
  h1 { font-size:2rem; letter-spacing:-.03em; margin:8px 0 4px; font-weight:700; }
  .sub { color:var(--mut); font-size:.95rem; margin-bottom:22px; }
  .row { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:14px 16px;
         background:var(--panel); border:1px solid var(--line); border-radius:14px; margin-bottom:10px; }
  .row small { color:var(--mut); font-size:.85rem; }
  .row .v { font-family:ui-monospace,Consolas,monospace; font-weight:600; font-size:.85rem;
            text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:60%; }
  .ok { color:var(--ok); } .err { color:var(--err); }
  .sticks { display:flex; gap:14px; justify-content:center; margin:22px 0; }
  .stick { width:112px; height:112px; border-radius:50%; background:var(--panel); border:1px solid var(--line);
           position:relative; }
  .dot { width:22px; height:22px; border-radius:50%; background:#fff; position:absolute; left:44px; top:44px;
         box-shadow:0 0 16px rgba(59,157,255,.85); }
  pre { background:var(--panel); border:1px solid var(--line); padding:14px; border-radius:14px;
        font-size:.75rem; color:var(--mut); white-space:pre-wrap; margin:0 0 16px; }
  button { width:100%; padding:15px; font-size:1rem; font-weight:600; border:0; border-radius:999px;
           color:#000; background:#fff; }
</style>
</head>
<body>
<h1>GhostPad</h1>
<div class="sub">Ponte de controle: celular &rarr; PC</div>

<div class="row"><small>PC</small><span id="sPc" class="v err">desconectado</span></div>
<div class="row"><small>CONTROLE</small><span id="sPad" class="v err">aperte um botao</span></div>

<div class="sticks">
  <div class="stick"><div class="dot" id="dL"></div></div>
  <div class="stick"><div class="dot" id="dR"></div></div>
</div>

<pre id="log">Pareie o controle no Bluetooth do celular e aperte qualquer botao.</pre>
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

    $("dL").style.transform = `translate(${a[0]*34}px,${a[1]*34}px)`;
    $("dR").style.transform = `translate(${a[2]*34}px,${a[3]*34}px)`;
    $("log").textContent = `botoes: [${b}]\nLT: ${lt}  RT: ${rt}\neixos: ${a}`;
  } else {
    $("sPad").textContent = "aperte um botao";
    $("sPad").className = "v err";
  }
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);

$("btn").onclick = async () => {
  try { wake = await navigator.wakeLock.request("screen"); $("btn").textContent = "Tela ligada \u2714"; }
  catch (e) { $("btn").textContent = "Wake Lock indisponivel"; }
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
# Interface (Flet) - estilo minimalista escuro
# --------------------------------------------------------------------------------------
BG = "#000000"
CARD = "#0A0A0B"
BORDA = "#27272A"
BORDA_SUAVE = "#1C1C1F"
TEXTO = "#FAFAFA"
MUDO = "#A1A1AA"
MUDO2 = "#71717A"
AZUL = "#3B9DFF"
VERDE, VERMELHO, AMBAR = "#22C55E", "#EF4444", "#F59E0B"
FONTE = "Segoe UI"
MONO = "Consolas"

COR_ESTADO = {"ok": VERDE, "off": VERMELHO, "warn": AMBAR, "idle": MUDO2}
W = ft.FontWeight

# Ilustracao (WebP em base64): camadas isometricas; ligada = camada azul acesa
HERO_ON = "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"
HERO_OFF = "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"


def txt(valor, size=14, cor=TEXTO, peso=W.W_400, mono=False, ls=None, h=None, **kw):
    estilo = ft.TextStyle(letter_spacing=ls, height=h) if (ls is not None or h is not None) else None
    return ft.Text(
        valor,
        size=size,
        color=cor,
        weight=peso,
        font_family=MONO if mono else FONTE,
        style=estilo,
        **kw,
    )


def ponto(cor: str, tam: int = 8) -> ft.Container:
    return ft.Container(width=tam, height=tam, border_radius=ft.BorderRadius.all(tam / 2), bgcolor=cor)


class Pilula:
    """Botao em formato de pilula: 'claro' (branco) ou 'escuro'."""

    def __init__(self, texto, on_click, claro=True, altura=38):
        self.claro, self.ativo = claro, True
        self.rotulo = txt(texto, 13, "#000000" if claro else TEXTO, W.W_600)
        self.control = ft.Container(
            content=self.rotulo,
            height=altura,
            padding=ft.Padding.symmetric(horizontal=18),
            alignment=ft.Alignment.CENTER,
            border_radius=ft.BorderRadius.all(altura / 2),
            bgcolor="#FFFFFF" if claro else "#18181B",
            border=ft.Border.all(1, "#FFFFFF" if claro else BORDA),
            ink=True,
            on_click=on_click,
            on_hover=self._hover,
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        )

    def _hover(self, e):
        if not self.ativo:
            return
        sobre = str(e.data).lower() == "true"
        if self.claro:
            self.control.bgcolor = "#E4E4E7" if sobre else "#FFFFFF"
        else:
            self.control.bgcolor = "#27272A" if sobre else "#18181B"
        self.control.update()

    def set(self, texto=None, claro=None, ativo=None):
        if texto is not None:
            self.rotulo.value = texto
        if claro is not None:
            self.claro = claro
        if ativo is not None:
            self.ativo = ativo
        self.rotulo.color = "#000000" if self.claro else TEXTO
        self.control.bgcolor = "#FFFFFF" if self.claro else "#18181B"
        self.control.border = ft.Border.all(1, "#FFFFFF" if self.claro else BORDA)
        self.control.opacity = 1 if self.ativo else 0.5


class Link:
    """Item de navegacao (texto cinza que fica branco ao passar o mouse/selecionar)."""

    def __init__(self, texto, on_click):
        self.ativo = False
        self.t = txt(texto, 14, MUDO, W.W_500)
        self.control = ft.Container(
            content=self.t,
            padding=ft.Padding.symmetric(horizontal=4, vertical=8),
            on_click=on_click,
            on_hover=self._hover,
        )

    def _hover(self, e):
        if not self.ativo:
            self.t.color = TEXTO if str(e.data).lower() == "true" else MUDO
            self.t.update()

    def marcar(self, ativo: bool):
        self.ativo = ativo
        self.t.color = TEXTO if ativo else MUDO


class LinhaStatus:
    """Linha da lista de status: LED, titulo, detalhe, valor e area extra."""

    def __init__(self, titulo):
        self.led = ponto(MUDO2)
        self.valor = txt("—", 13, MUDO, W.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.RIGHT)
        self.detalhe = txt("", 12, MUDO2, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.extra = ft.Column([], spacing=8, visible=False)
        self.control = ft.Container(
            content=ft.Row(
                [
                    ft.Container(self.led, padding=ft.Padding.only(top=6)),
                    ft.Column(
                        [txt(titulo, 14, TEXTO, W.W_500), self.detalhe, self.extra],
                        spacing=3,
                        expand=True,
                    ),
                    ft.Container(self.valor, width=170, padding=ft.Padding.only(top=2)),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=14,
            ),
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
        )

    def set(self, estado: str, valor: str, detalhe: str = ""):
        cor = COR_ESTADO[estado]
        self.led.bgcolor = cor
        self.led.shadow = (
            ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.8, cor), offset=ft.Offset(0, 0))
            if estado in ("ok", "warn")
            else None
        )
        self.valor.value = valor
        self.valor.color = MUDO if estado == "idle" else TEXTO
        self.detalhe.value = detalhe


def cartao(conteudo, padding=0) -> ft.Container:
    return ft.Container(
        content=conteudo,
        padding=padding,
        bgcolor=CARD,
        border=ft.Border.all(1, BORDA),
        border_radius=ft.BorderRadius.all(16),
    )


def divisor() -> ft.Divider:
    return ft.Divider(height=1, thickness=1, color=BORDA_SUAVE)


def passo(numero: int, titulo: str, texto: str) -> ft.Container:
    selo = ft.Container(
        content=txt(str(numero), 13, TEXTO, W.W_600, mono=True),
        width=30,
        height=30,
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(15),
        border=ft.Border.all(1, BORDA),
    )
    return ft.Container(
        content=ft.Row(
            [
                selo,
                ft.Column(
                    [txt(titulo, 15, TEXTO, W.W_600), txt(texto, 13, MUDO, h=1.45)],
                    spacing=4,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
            spacing=16,
        ),
        padding=ft.Padding.symmetric(horizontal=18, vertical=16),
    )


def dica(titulo: str, texto: str, cor: str = AZUL) -> ft.Container:
    return ft.Container(
        content=ft.Column([txt(titulo, 13, cor, W.W_600), txt(texto, 13, MUDO, h=1.45)], spacing=4),
        padding=16,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, cor)),
        bgcolor=ft.Colors.with_opacity(0.05, cor),
    )


def main(page: ft.Page):
    page.title = f"{APP_NOME}"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.window.width = 1120
    page.window.height = 760
    page.window.min_width = 860
    page.window.min_height = 600

    clip = ft.Clipboard()
    page.services.append(clip)

    st = {"ocupado": False, "instalando": False, "driver": False, "qr_url": "", "hero": ""}

    # ---------------- acoes ----------------
    erro_txt = txt("", 13, VERMELHO, max_lines=4)
    erro_box = ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.ERROR_OUTLINE, color=VERMELHO, size=18), ft.Container(erro_txt, expand=True)],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=14,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.45, VERMELHO)),
        bgcolor=ft.Colors.with_opacity(0.07, VERMELHO),
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
        btn_servidor.set("Aguarde...", claro=True, ativo=False)
        page.update()
        try:
            if PONTE.rodando:
                await asyncio.to_thread(PONTE.parar)
            else:
                if not st["driver"]:
                    raise RuntimeError(
                        "Instale o driver primeiro (botão na linha \"Driver ViGEmBus\") e reinicie o PC se o instalador pedir."
                    )
                await asyncio.to_thread(PONTE.iniciar)
        except Exception as ex:
            mostrar_erro(str(ex))
        finally:
            st["ocupado"] = False
        page.update()

    async def copiar(e):
        if PONTE.url:
            await clip.set(PONTE.url)
            page.show_dialog(ft.SnackBar(txt("Endereço copiado", 13, "#000000", W.W_600), bgcolor="#FFFFFF", duration=1500))

    drv_msg = txt("", 12, MUDO2)
    drv_barra = ft.ProgressBar(color=AZUL, bgcolor="#18181B", visible=False)

    async def instalar_driver(e):
        if st["instalando"]:
            return
        st["instalando"] = True
        drv_barra.visible = True
        drv_msg.value = "Baixando o driver..."
        drv_msg.color = MUDO2
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

    btn_servidor = Pilula("Iniciar servidor", alternar, claro=True, altura=38)
    btn_driver = Pilula("Instalar driver", instalar_driver, claro=True, altura=34)

    # ---------------- barra superior ----------------
    marca = ft.Container(
        content=ft.Icon(ft.Icons.SPORTS_ESPORTS, color="#000000", size=16),
        width=28,
        height=28,
        alignment=ft.Alignment.CENTER,
        border_radius=ft.BorderRadius.all(8),
        bgcolor="#FFFFFF",
    )
    chip_led = ponto(VERMELHO)
    chip_txt = txt("Offline", 12, TEXTO, W.W_500)
    chip = ft.Container(
        content=ft.Row([chip_led, chip_txt], spacing=8, tight=True),
        padding=ft.Padding.symmetric(horizontal=12, vertical=7),
        border_radius=ft.BorderRadius.all(16),
        border=ft.Border.all(1, BORDA),
        bgcolor="#0F0F11",
    )

    link_painel = Link("Painel", lambda e: trocar_aba("painel"))
    link_tutorial = Link("Tutorial", lambda e: trocar_aba("tutorial"))

    barra = ft.Container(
        content=ft.Row(
            [
                ft.Row([marca, txt("GhostPad", 17, TEXTO, W.W_700)], spacing=10),
                ft.Container(width=28),
                link_painel.control,
                ft.Container(width=8),
                link_tutorial.control,
                ft.Container(expand=True),
                chip,
                ft.Container(width=6),
                btn_servidor.control,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
        padding=ft.Padding.symmetric(horizontal=32, vertical=16),
    )

    # ---------------- painel: texto principal ----------------
    titulo = ft.Container(
        txt("Seu controle no PC, com o celular como ponte.", 54, TEXTO, W.W_600, ls=-1.6, h=1.05),
        width=560,
    )
    paragrafos = ft.Container(
        ft.Column(
            [
                txt(
                    "O GhostPad lê o seu controle Bluetooth pelo navegador do celular e cria um Xbox 360 virtual "
                    "no Windows. Sem cabo e sem adaptador.",
                    16,
                    MUDO,
                    h=1.5,
                ),
                txt(
                    "Instale o driver uma vez, inicie o servidor e abra o endereço no celular. "
                    "Steam e jogos enxergam um controle de verdade.",
                    16,
                    MUDO,
                    h=1.5,
                ),
            ],
            spacing=16,
        ),
        width=520,
    )

    # ---------------- painel: endereco para o celular ----------------
    url_txt = txt("", 20, TEXTO, W.W_600, mono=True, selectable=True)
    qr_img = ft.Image(src=PNG_VAZIO, width=118, height=118, fit=ft.BoxFit.CONTAIN)
    bloco_url = cartao(
        ft.Row(
            [
                ft.Column(
                    [
                        txt("Abra no navegador do celular", 12, MUDO2, W.W_500),
                        ft.Row(
                            [url_txt, ft.IconButton(icon=ft.Icons.CONTENT_COPY, icon_color=MUDO, icon_size=18, tooltip="Copiar endereço", on_click=copiar)],
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [
                                txt(f"Porta {PORTA}", 12, TEXTO, W.W_500, mono=True),
                                txt("·", 12, MUDO2),
                                txt("HTTPS", 12, TEXTO, W.W_500, mono=True),
                            ],
                            spacing=8,
                        ),
                        txt(
                            "Mesmo Wi-Fi do PC. Aviso de certificado? Avançado › continuar (o certificado é local).",
                            12,
                            MUDO2,
                            h=1.4,
                        ),
                    ],
                    spacing=8,
                    expand=True,
                ),
                ft.Container(
                    qr_img,
                    padding=8,
                    bgcolor="#FFFFFF",
                    border_radius=ft.BorderRadius.all(12),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        ),
        padding=20,
    )
    bloco_url.visible = False

    # ---------------- painel: status ----------------
    l_driver = LinhaStatus("Driver ViGEmBus")
    l_driver.extra.controls = [ft.Row([btn_driver.control]), drv_barra, drv_msg]
    l_servidor = LinhaStatus("Servidor")
    l_celular = LinhaStatus("Celular")
    l_controle = LinhaStatus("Controle Bluetooth")
    l_virtual = LinhaStatus("Controle virtual no PC")

    status_card = cartao(
        ft.Column(
            [
                l_driver.control,
                divisor(),
                l_servidor.control,
                divisor(),
                l_celular.control,
                divisor(),
                l_controle.control,
                divisor(),
                l_virtual.control,
            ],
            spacing=0,
        )
    )

    log_txt = txt("Aguardando...", 11, MUDO2, mono=True, h=1.5)
    log_box = cartao(ft.Column([txt("Console", 12, MUDO2, W.W_500), log_txt], spacing=8), padding=18)

    coluna_esquerda = ft.Container(
        content=ft.Column(
            [titulo, paragrafos, ft.Container(height=4), erro_box, bloco_url, status_card, log_box],
            spacing=22,
        ),
        width=560,
    )

    hero = ft.Image(src=HERO_OFF, width=440, height=511, fit=ft.BoxFit.CONTAIN)
    hero_box = ft.Container(
        content=hero,
        expand=True,
        alignment=ft.Alignment.TOP_CENTER,
        padding=ft.Padding.only(top=12),
    )

    view_painel = ft.Row(
        [coluna_esquerda, hero_box],
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=24,
    )

    # ---------------- tutorial ----------------
    view_tutorial = ft.Container(
        width=700,
        visible=False,
        content=ft.Column(
            [
                txt("Como usar", 44, TEXTO, W.W_600, ls=-1.2, h=1.1),
                txt("Seis passos e o seu controle aparece como um Xbox 360 no PC.", 16, MUDO, h=1.5),
                ft.Container(height=4),
                cartao(
                    ft.Column(
                        [
                            passo(1, "Instale o driver (uma vez)", "No Painel, clique em Instalar driver e confirme o aviso do Windows. Reinicie o PC se o instalador pedir. A linha do driver passa a mostrar INSTALADO."),
                            divisor(),
                            passo(2, "Pareie o controle no celular", "No Bluetooth do celular, coloque o controle em modo de pareamento (no PS4: segure PS + Share até a luz piscar rápido) e conecte."),
                            divisor(),
                            passo(3, "Inicie o servidor", "Clique em Iniciar servidor, no canto superior direito. O app mostra o endereço, a porta e um QR Code."),
                            divisor(),
                            passo(4, "Abra o endereço no celular", "Use o Chrome (Android) ou o Safari (iPhone), no mesmo Wi-Fi do PC. Aceite o aviso de certificado (Avançado › continuar). Se o Firewall do Windows perguntar, permita em rede privada."),
                            divisor(),
                            passo(5, "Mantenha a tela ligada", "Na página do celular, toque em Manter tela ligada e deixe o navegador aberto em primeiro plano."),
                            divisor(),
                            passo(6, "Aperte um botão no controle", "No Painel, Celular, Controle e Controle virtual ficam ativos. Teste no Windows (Win+R › joy.cpl) ou direto no Steam e nos jogos."),
                        ],
                        spacing=0,
                    )
                ),
                dica("Dica", "Wi-Fi de 5 GHz reduz a latência. Evite o modo de economia de bateria no celular."),
                dica("Duas entradas no joy.cpl?", "Há duas abas do navegador conectadas. Feche as extras no celular.", AMBAR),
                dica("Não conecta?", "Confira se PC e celular estão na mesma rede, se o servidor está online e se o IP mudou. Se mudou, abra o novo endereço."),
                txt(f"{APP_NOME} v{VERSAO} · driver ViGEmBus por Nefarius (projeto sem manutenção, mas funcional)", 11, MUDO2),
            ],
            spacing=18,
        ),
    )

    # ---------------- raiz ----------------
    corpo = ft.Container(
        content=ft.Column([view_painel, view_tutorial], scroll=ft.ScrollMode.AUTO, expand=True),
        padding=ft.Padding.only(left=32, right=32, top=36, bottom=32),
        expand=True,
    )
    page.add(ft.Column([barra, corpo], spacing=0, expand=True))

    def trocar_aba(chave: str):
        view_painel.visible = chave == "painel"
        view_tutorial.visible = chave == "tutorial"
        link_painel.marcar(chave == "painel")
        link_tutorial.marcar(chave == "tutorial")
        page.update()

    def ajustar(_=None):
        largura = getattr(page, "width", None) or 1120
        hero_box.visible = largura >= 980

    try:
        page.on_resize = ajustar
    except Exception:
        pass

    # ---------------- atualizacao periodica ----------------
    def aplicar(s: dict):
        rodando, n = s["rodando"], s["clientes"]
        drv = st["driver"]

        # driver
        if drv:
            l_driver.set("ok", "Instalado", "Necessário para criar o controle virtual")
        else:
            l_driver.set("off", "Não instalado", "Necessário para criar o controle virtual")
        l_driver.extra.visible = not drv

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
                l_virtual.set("warn", "Sem comandos", "Xbox 360 virtual criado, aguardando entrada")
        else:
            l_virtual.set("idle", "Inativo", "Nenhum controle virtual criado")

        # botao principal + chip
        if not st["ocupado"]:
            if rodando:
                btn_servidor.set("Parar servidor", claro=False, ativo=True)
            else:
                btn_servidor.set("Iniciar servidor", claro=True, ativo=True)

        if rodando and n and s["controle"]:
            cor, texto = VERDE, "Pronto para jogar"
        elif rodando:
            cor, texto = AMBAR, "Aguardando"
        else:
            cor, texto = VERMELHO, "Offline"
        chip_txt.value = texto
        chip_led.bgcolor = cor
        chip_led.shadow = ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.8, cor), offset=ft.Offset(0, 0))

        # ilustracao: camada azul acesa quando o servidor esta online
        alvo = "on" if rodando else "off"
        if st["hero"] != alvo:
            hero.src = HERO_ON if rodando else HERO_OFF
            st["hero"] = alvo

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
    ajustar()
    page.run_task(atualizar)


if __name__ == "__main__":
    try:
        ft.run(main)
    finally:
        PONTE.parar()
        os._exit(0)
