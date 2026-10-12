<div align="center">

<img src="assets/icon.png" width="120" alt="GhostPad">

# GHOSTPAD

**Use o celular como ponte Bluetooth para jogar no PC com o seu controle.**

Pareie o controle no celular, abra uma página no navegador e o Windows enxerga um controle Xbox 360 de verdade.

![Python](https://img.shields.io/badge/Python-3.12+-00E5FF?style=flat-square&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/UI-Flet-FF2BD6?style=flat-square)
![Windows](https://img.shields.io/badge/Windows-10%2F11-39FF88?style=flat-square&logo=windows&logoColor=black)
![License](https://img.shields.io/badge/licença-MIT-6F7FA3?style=flat-square)

</div>

---

## O problema

Você tem um controle (PS4, genérico, etc.) que só conecta por **Bluetooth**, o PC não tem Bluetooth (ou o controle não pareia direito) e não há cabo à mão.

## A solução

O **GhostPad** transforma o celular em uma ponte:

```
Controle ──Bluetooth──▶ Celular (navegador) ──Wi-Fi──▶ GhostPad (PC) ──▶ Xbox 360 virtual
```

1. O celular lê o controle pela **Gamepad API** do navegador (nada para instalar no celular).
2. Envia o estado dos botões e analógicos ao PC por **WebSocket seguro (HTTPS)**.
3. O GhostPad cria um **controle Xbox 360 virtual** no Windows (via ViGEmBus). Steam e jogos o reconhecem como um controle real.

## Recursos

- Interface desktop futurista (Flet) com botão **Iniciar/Parar servidor**
- Mostra o **endereço, a porta e um QR Code** para abrir no celular
- **Painel de status** em tempo real: driver, servidor, celular, controle detectado e controle virtual
- Botão para **baixar e instalar o driver** (ViGEmBus) automaticamente
- **Tutorial** dentro do app
- Página do celular embutida: nenhum arquivo extra para hospedar
- Funciona em Android (Chrome) e iPhone (Safari)

## Requisitos

- Windows 10/11
- Celular e PC no **mesmo Wi-Fi**
- Driver **ViGEmBus** (o app instala para você)

## Instalação

### Opção 1: executável

Baixe o `GhostPad.exe` em **Releases** e execute. Na primeira vez, o Windows Firewall pode perguntar: permita em **rede privada**.

### Opção 2: rodar pelo código

```bash
git clone https://github.com/pedaeadr-hash/ghostpad.git
cd ghostpad
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python ghostpad.py
```

### Gerar o seu próprio `.exe`

Dê duplo clique em `build.bat`. O executável sai em `dist\GhostPad.exe`.

## Como usar

1. **Instale o driver**: no painel, clique em **INSTALAR DRIVER**, confirme o aviso do Windows e reinicie o PC se pedir (só uma vez).
2. **Pareie o controle no celular** (Configurações › Bluetooth). No controle de PS4: segure `PS + Share` até a luz piscar rápido.
3. **Inicie o servidor** no GhostPad. Ele mostra o endereço (`https://IP:8443`) e o QR Code.
4. **Abra o endereço no celular** (Chrome no Android, Safari no iPhone). Aceite o aviso de certificado: *Avançado › continuar*. É esperado, pois o certificado é gerado localmente.
5. Toque em **MANTER TELA LIGADA** na página do celular e deixe o navegador em primeiro plano.
6. **Aperte um botão no controle.** No painel, Celular, Controle e Controle virtual ficam verdes. Teste em `Win + R › joy.cpl` ou direto no Steam.

## Mapeamento

Os botões seguem o mapeamento *standard* do navegador e viram botões do Xbox 360:

| Controle PS4 | Xbox 360 |
|---|---|
| ✕ / ○ / □ / △ | A / B / X / Y |
| L1 / R1 | LB / RB |
| L2 / R2 | LT / RT (analógicos) |
| Share / Options | Back / Start |
| L3 / R3 | LS / RS |
| Direcional | Direcional |
| PS | Guide |

Controles genéricos podem ter mapeamento diferente. Se algum botão estiver trocado, ajuste o dicionário `_mapa` em `ghostpad.py`.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| "Driver não instalado" | Use o botão **INSTALAR DRIVER** e reinicie o PC |
| Celular não abre o endereço | Confirme o mesmo Wi-Fi, o servidor ONLINE e se o IP mudou |
| Duas entradas no `joy.cpl` | Há duas abas do navegador conectadas; feche as extras |
| Controle "NÃO DETECTADO" | Aperte um botão no controle; confirme que ele está pareado no celular |
| Porta 8443 em uso | Feche outro programa que use a porta ou outra instância do GhostPad |
| Comandos param de chegar | A tela do celular apagou ou o navegador foi para segundo plano |
| iPhone não reconhece o controle | O iOS só reconhece alguns controles (DualShock/DualSense originais); clones genéricos podem não funcionar |

## Limitações

- Sem giroscópio, touchpad, vibração ou LED do controle
- Precisa manter o navegador aberto e a tela do celular ligada
- Latência típica de poucos milissegundos em Wi-Fi 5 GHz, mas depende da sua rede
- O ViGEmBus foi descontinuado pelo autor (a última versão, 1.22.0, continua funcionando)

## Estrutura

```
ghostpad/
├── ghostpad.py        # app (interface Flet + servidor + página do celular)
├── assets/            # ícone
├── requirements.txt
├── build.bat          # gera o .exe
└── README.md
```

## Tecnologias

[Flet](https://flet.dev) · [aiohttp](https://docs.aiohttp.org) · [vgamepad](https://github.com/yannbouteiller/vgamepad) · [ViGEmBus](https://github.com/nefarius/ViGEmBus) · [segno](https://github.com/heuer/segno) · [cryptography](https://cryptography.io)

## Licença

MIT. Veja [LICENSE](LICENSE). O driver ViGEmBus tem licença e autoria próprias (Nefarius Software Solutions).
