"""Painel do La Bodega (cPanel / Passenger).

Roda em labodegapetropolis.com.br/painel. Edita o BOT e o SITE:
- Dados em data/labodega.json (não sobrescrito pelo deploy do Git).
- Ao salvar, regenera o index.html a partir de site_template.html e grava
  em ~/public_html (o site continua 100% estático e rápido).
- Upload de imagens grava em ~/public_html/img/ com nome único por slot.
- O bot lê a config em /painel/api/config/bot.

Proteção de escrita: header x-panel-key == env PANEL_KEY (Setup Python App).
"""
import glob
import json
import os
import re
import time
from flask import Flask, request, jsonify, Response

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CFG = os.path.join(DATA_DIR, "labodega.json")
TEMPLATE = os.path.join(BASE, "site_template.html")
PUBLIC_HTML = os.environ.get("PUBLIC_HTML_DIR") or os.path.expanduser("~/public_html")
PANEL_KEY = os.environ.get("PANEL_KEY", "").strip()

# --------------------------------------------------------------------------
# Padrões — espelham exatamente o conteúdo atual do site (primeira publicação
# não muda nada visualmente).
# --------------------------------------------------------------------------
MENU_REAL = [
    {"categoria": "Executivos", "nome": "Frango com Caesar", "preco": 29.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Strogonoff de frango", "preco": 34.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Strogonoff de camarão", "preco": 44.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Tilápia", "preco": 44.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Chorizo", "preco": 49.90, "desc": "Por mais R$ 5,00, acompanha ovo a cavalo.", "tags": ""},
    {"categoria": "Executivos", "nome": "Risoto de mignon", "preco": 54.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Parmegiana de mignon", "preco": 59.90, "desc": "", "tags": ""},
    {"categoria": "Executivos", "nome": "Mignon com piamontese", "preco": 69.90, "desc": "", "tags": ""},
    {"categoria": "Pratos", "nome": "Picadinho carioca", "preco": 59.90, "desc": "Carne angus picada e refogada na hora. Acompanha arroz, feijão, banana à milanesa e ovo pochê.", "tags": ""},
    {"categoria": "Pratos", "nome": "Lasagna", "preco": 54.90, "desc": "Queijo, presunto e bolonhesa.", "tags": ""},
    {"categoria": "Pratos", "nome": "Gnocchi de batata baroa selado", "preco": 79.90, "desc": "Fondue de tomates, manjericão, presunto cru de parma e queijo grana padano.", "tags": ""},
    {"categoria": "Pratos", "nome": "Risoto de cogumelos", "preco": 79.90, "desc": "Shiitake e Paris.", "tags": ""},
    {"categoria": "Pratos", "nome": "Strogonoff russo", "preco": 54.90, "desc": "Carne seleção angus, creme de leite, mostarda e cogumelos. Acompanha batata palha da casa e arroz branco.", "tags": ""},
    {"categoria": "Pratos", "nome": "Fetuccine", "preco": 44.90, "desc": "Molho vermelho, bechamel ou alho e óleo.", "tags": ""},
    {"categoria": "Pratos", "nome": "Espaguete de legumes", "preco": 49.90, "desc": "Refogado no azeite.", "tags": "vegano"},
    {"categoria": "Pratos", "nome": "Arroz caldoso de costela", "preco": 79.90, "desc": "Costela desfiada, linguiça defumada, cogumelos frescos e cebolinha.", "tags": ""},
    {"categoria": "Pratos", "nome": "Risoto caprese", "preco": 69.90, "desc": "Tomates frescos, mussarela de búfala, pesto de manjericão e azeite extravirgem.", "tags": ""},
    {"categoria": "Pratos", "nome": "Boeuf bourguignon", "preco": 69.90, "desc": "Carne cozida ao vinho tinto, cenouras, cebolas glaceadas e bacon. Acompanha purê de batatas.", "tags": ""},
    {"categoria": "Pratos", "nome": "Prato infantil", "preco": 34.90, "desc": "Arroz, feijão, carne ou frango e batata frita. Pode trocar arroz e feijão por massa.", "tags": ""},
]

DEFAULT_BOT = {
    "slug": "labodega",
    "nome": "La Bodega",
    "telefone": "(24) 2017-9899",
    "endereco": "Pátio Petrópolis Shopping — Rooftop, Centro, Petrópolis",
    "horarios": {
        "seg": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "ter": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "qua": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "qui": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "sex": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "sab": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "dom": {"abre": True, "ini": "11:00", "fim": "21:00"},
    },
    "reservas": {"aceita": False, "max_pessoas": 12, "antecedencia": "até 2 horas antes"},
    "delivery": {"faz": False, "bairros": "", "taxa": "", "tempo": ""},
    "pagamento": ["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"],
    "cardapio": MENU_REAL,
    "faq": [],
    "cardapio_pdf": "",
}

DEFAULT_SITE = {
    "emBreve": False,
    "emBreveMsg": "Estamos preparando algo especial. Volte logo!",
    "meta_title": "La Bodega · Rooftop · Pátio Petrópolis",
    "meta_desc": "O rooftop mais charmoso de Petrópolis. Cozinha autoral, do almoço ao happy hour, no Pátio Petrópolis Shopping. Veja o cardápio e fale com a gente no Telegram.",
    "hero": {
        "titulo": "Existem lugares para uma refeição, e lugares onde você <em>vive uma experiência.</em><br>Bem-vindo ao La Bodega.",
        "sub": "Rooftop · Pátio Petrópolis",
    },
    "casa": {
        "quote": "No alto do Pátio Petrópolis, do almoço ao happy hour: cozinha autoral, chopp gelado e o <span>rooftop mais charmoso da cidade.</span>",
        "cards": [
            {"t": "Cozinha de verdade", "d": "Carne angus, risotos cremosos, massas e clássicos preparados na hora. Da feijoada de fim de semana ao mignon ao ponto."},
            {"t": "Do almoço ao happy hour", "d": "Executivo no almoço, petiscos e chopp Brahma na taça à tarde. Um lugar pra começar e terminar o dia bem."},
            {"t": "No coração da cidade", "d": "Rooftop do Pátio Petrópolis Shopping, no Centro Histórico. Fácil de chegar, com estacionamento e vista de quem está no alto."},
        ],
    },
    "menu": {
        "titulo": "O que sai da cozinha",
        "desc": "Uma seleção da casa. O cardápio completo, com drinks e vinhos, você confere no salão ou direto com o nosso bot.",
        "subs": {"Executivos": "Pratos individuais, servidos no almoço", "Pratos": "À la carte, o dia todo"},
    },
    "combo": {
        "titulo": "Menu Executivo · 3 tempos",
        "preco": "R$ 74,90",
        "sub": "Escolha 1 de cada",
        "entradas": "Salada Caesar\nBruschetta caprese\nLinguiça de pernil grelhada",
        "principal": "Picadinho carioca\nFrango desossado à provençal\nRisoto caprese",
        "sobremesas": "Frutas da estação\nMousse de chocolate aerada\nPudim da Vó",
        "nota": "Disponível de segunda a sexta, no almoço. Consulte a disponibilidade do dia com o nosso bot.",
    },
    "drink": {
        "titulo": "Chopp gelado, do jeito certo",
        "nome": "Salsichão <em>+</em> Chopp Brahma",
        "desc": "A dupla certa pro happy hour: salsichão na chapa com mostarda da casa e um chopp Brahma tirado na hora.",
        "preco": "24,90",
    },
    "visita": {
        "endereco": "Rua Marechal Deodoro, 153\nPátio Petrópolis Shopping — Rooftop\nCentro, Petrópolis — RJ · 25620-150",
        "obs_endereco": "No alto do shopping, com acesso pelos elevadores e escadas rolantes. Estacionamento no local.",
        "horarios": [
            ["Segunda a sábado", "10h — 22h"],
            ["Domingos e feriados", "11h — 21h"],
            ["Menu executivo", "Seg a sex, almoço"],
            ["Happy hour", "Todos os dias"],
        ],
        "obs_horario": "Horários seguem o funcionamento do shopping e podem variar em datas especiais. Confirme o dia com o nosso bot.",
    },
    "contato": {"tel": "(24) 2017-9899", "email": "labodegapetropolis@gmail.com", "insta": "labodegapetropolis"},
    "bot_link": "https://t.me/labodegapatio_bot?start=qr",
    "img": {"logo": "/img/logo.png", "hero": "/img/hero-bg.jpg", "drinks": "/img/drinks.jpg"},
}


def _merge(base, extra):
    """Merge raso por seção: extra sobrepõe base, preservando chaves novas do default."""
    out = json.loads(json.dumps(base))
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def load_cfg():
    cfg = {}
    if os.path.exists(CFG):
        try:
            with open(CFG, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    migrated = False
    if "site" not in cfg:
        # primeira vez na versão com editor de site: seta defaults do site e
        # troca o cardápio demo do bot pelo cardápio REAL (o do site).
        cfg["site"] = DEFAULT_SITE
        bot = cfg.get("bot") or {}
        bot["cardapio"] = MENU_REAL
        cfg["bot"] = _merge(DEFAULT_BOT, bot)
        migrated = True
    if "bot" not in cfg:
        cfg["bot"] = DEFAULT_BOT
        migrated = True
    if migrated:
        save_cfg(cfg)
    return cfg


def save_cfg(cfg):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Geração do site
# --------------------------------------------------------------------------
def _preco(v):
    try:
        return ("R$ %.2f" % float(v)).replace(".", ",")
    except Exception:
        return str(v)


def _esc(s):
    return str(s or "")


def _menu_cols(cardapio, subs):
    grupos, ordem = {}, []
    for it in cardapio or []:
        cat = it.get("categoria") or "Outros"
        if cat not in grupos:
            grupos[cat] = []
            ordem.append(cat)
        grupos[cat].append(it)
    parts = ['<div class="menu-cols">']
    for cat in ordem:
        parts.append('      <div class="menu-group reveal">')
        parts.append(f"        <h3>{_esc(cat)}</h3>")
        sub = (subs or {}).get(cat, "")
        if sub:
            parts.append(f'        <p class="gh-sub">{_esc(sub)}</p>')
        for it in grupos[cat]:
            nome = _esc(it.get("nome"))
            tags = (it.get("tags") or "").lower()
            if "vegano" in tags:
                nome += ' <span class="veg">Vegano</span>'
            elif "vegetariano" in tags:
                nome += ' <span class="veg">Vegetariano</span>'
            desc = _esc(it.get("desc"))
            linha = (f'        <div class="item"><div class="item-row">'
                     f'<span class="item-name">{nome}</span>'
                     f'<span class="item-lead"></span>'
                     f'<span class="item-price">{_preco(it.get("preco", 0))}</span></div>')
            if desc:
                linha += f'<p class="item-desc">{desc}</p>'
            linha += "</div>"
            parts.append(linha)
        parts.append("      </div>")
    parts.append("    </div>")
    return "\n".join(parts)


def _ul(linhas):
    itens = "".join(f"<li>{_esc(l.strip())}</li>" for l in (linhas or "").splitlines() if l.strip())
    return f"<ul>{itens}</ul>"


def _vrows(rows):
    return "".join(
        f'<div class="vrow"><span>{_esc(r[0])}</span><span>{_esc(r[1])}</span></div>'
        for r in (rows or []) if r and (r[0] or r[1])
    )


def _tel_link(tel):
    dig = re.sub(r"\D", "", tel or "")
    if dig and not dig.startswith("55"):
        dig = "55" + dig
    return "+" + dig if dig else ""


def render_site(cfg):
    site = _merge(DEFAULT_SITE, cfg.get("site"))
    bot = _merge(DEFAULT_BOT, cfg.get("bot"))
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    preco_drink = (site["drink"].get("preco") or "0,00").replace("R$", "").strip()
    d_int, _, d_cents = preco_drink.partition(",")
    endereco_lines = [l.strip() for l in (site["visita"].get("endereco") or "").splitlines() if l.strip()]
    valores = {
        "META_TITLE": site["meta_title"],
        "META_DESC": site["meta_desc"],
        "NOME": bot.get("nome", "La Bodega"),
        "LINK_BOT": site["bot_link"],
        "IMG_LOGO": site["img"].get("logo", "/img/logo.png"),
        "IMG_HERO": site["img"].get("hero", "/img/hero-bg.jpg"),
        "IMG_DRINKS": site["img"].get("drinks", "/img/drinks.jpg"),
        "HERO_TITULO": site["hero"]["titulo"],
        "HERO_SUB": site["hero"]["sub"],
        "CASA_QUOTE": site["casa"]["quote"],
        "MENU_TITULO": site["menu"]["titulo"],
        "MENU_DESC": site["menu"]["desc"],
        "COMBO_TITULO": site["combo"]["titulo"],
        "COMBO_PRECO": site["combo"]["preco"],
        "COMBO_SUB": site["combo"]["sub"],
        "COMBO_UL1": _ul(site["combo"]["entradas"]),
        "COMBO_UL2": _ul(site["combo"]["principal"]),
        "COMBO_UL3": _ul(site["combo"]["sobremesas"]),
        "COMBO_NOTA": site["combo"]["nota"],
        "MENU_COLS": _menu_cols(bot.get("cardapio"), site["menu"].get("subs")),
        "DRINK_TITULO": site["drink"]["titulo"],
        "DRINK_NOME": site["drink"]["nome"],
        "DRINK_DESC": site["drink"]["desc"],
        "DRINK_INT": d_int.strip() or "0",
        "DRINK_CENTS": ("," + d_cents.strip()) if d_cents.strip() else ",00",
        "ENDERECO_BR": "<br>".join(endereco_lines),
        "ENDERECO_OBS": site["visita"]["obs_endereco"],
        "VISITA_HORARIOS": _vrows(site["visita"].get("horarios")),
        "HORARIO_OBS": site["visita"]["obs_horario"],
        "TEL": site["contato"]["tel"],
        "TEL_LINK": _tel_link(site["contato"]["tel"]),
        "EMAIL": site["contato"]["email"],
        "INSTA": site["contato"]["insta"],
        "FOOT_ENDERECO": "".join(f"<p>{l}</p>" for l in endereco_lines),
    }
    cards = site["casa"].get("cards") or []
    for i in range(3):
        c = cards[i] if i < len(cards) else {"t": "", "d": ""}
        valores[f"CASA{i+1}_T"] = c.get("t", "")
        valores[f"CASA{i+1}_D"] = c.get("d", "")
    for k, v in valores.items():
        html = html.replace(f"@@{k}@@", str(v))
    return html


def render_embreve(cfg):
    site = _merge(DEFAULT_SITE, cfg.get("site"))
    bot = _merge(DEFAULT_BOT, cfg.get("bot"))
    nome = bot.get("nome", "La Bodega")
    msg = site.get("emBreveMsg") or "Estamos preparando algo especial."
    logo = site["img"].get("logo", "/img/logo.png")
    sub = site["hero"].get("sub", "")
    return f"""<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nome} · Em breve</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,500&family=Montserrat:wght@400;600&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
    background:radial-gradient(90% 90% at 50% 20%,#2c2823,#1b1916 70%);color:#e8e1d0;
    font-family:"Montserrat",system-ui,sans-serif;text-align:center;padding:32px}}
  img{{width:130px;height:130px;border-radius:50%;box-shadow:0 30px 80px -30px rgba(0,0,0,.8);margin-bottom:34px}}
  .eyebrow{{font-size:.72rem;letter-spacing:.34em;text-transform:uppercase;color:#c89a3e;font-weight:600;margin-bottom:18px}}
  h1{{font-family:"Playfair Display",serif;font-style:italic;font-weight:500;font-size:clamp(2rem,6vw,3.2rem);color:#e2bd62;margin-bottom:16px}}
  p{{color:#ada592;max-width:440px;font-size:1rem;line-height:1.6}}
  .brand{{margin-top:40px;font-size:.8rem;letter-spacing:.3em;text-transform:uppercase;color:#ada592}}
</style></head><body>
  <img src="{logo}" alt="{nome}">
  <div class="eyebrow">Em breve</div>
  <h1>{nome}</h1>
  <p>{msg}</p>
  <div class="brand">{sub}</div>
</body></html>"""


def publish_site(cfg):
    """Gera e grava o index.html no public_html. Retorna (ok, msg)."""
    if not os.path.isdir(PUBLIC_HTML):
        return False, f"pasta do site não encontrada ({PUBLIC_HTML})"
    site = cfg.get("site") or {}
    html = render_embreve(cfg) if site.get("emBreve") else render_site(cfg)
    if "@@" in html:
        sobras = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", html)))
        return False, "marcadores sem valor: " + ", ".join(sobras[:5])
    with open(os.path.join(PUBLIC_HTML, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return True, "site publicado"


# --------------------------------------------------------------------------
# Flask
# --------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB p/ upload


def _json(obj, status=200):
    return Response(json.dumps(obj, ensure_ascii=False), status=status,
                    mimetype="application/json")


def _auth_ok():
    key = request.headers.get("x-panel-key", "")
    return bool(PANEL_KEY) and key == PANEL_KEY


@app.get("/")
def painel():
    with open(os.path.join(BASE, "painel.html"), encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/html")


@app.get("/api/config")
def api_config():
    return _json(load_cfg())


@app.get("/api/config/bot")
def api_config_bot():
    return _json(load_cfg().get("bot", DEFAULT_BOT))


@app.post("/api/save")
def api_save():
    if not _auth_ok():
        return _json({"ok": False, "erro": "Chave do painel inválida ou não configurada."}, 401)
    try:
        body = request.get_json(force=True)
    except Exception:
        return _json({"ok": False, "erro": "JSON inválido"}, 400)
    cfg = load_cfg()
    cfg.update(body or {})
    save_cfg(cfg)
    ok, msg = publish_site(cfg)
    return _json({"ok": True, "publicado": ok, "msg": msg})


@app.post("/api/publish")
def api_publish():
    if not _auth_ok():
        return _json({"ok": False, "erro": "Chave do painel inválida."}, 401)
    ok, msg = publish_site(load_cfg())
    return _json({"ok": ok, "msg": msg})


ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
SLOTS = {"logo", "hero", "drinks"}


@app.post("/api/upload/<slot>")
def api_upload(slot):
    if not _auth_ok():
        return _json({"ok": False, "erro": "Chave do painel inválida."}, 401)
    if slot not in SLOTS:
        return _json({"ok": False, "erro": "Slot desconhecido."}, 400)
    f = request.files.get("arquivo")
    if not f or not f.filename:
        return _json({"ok": False, "erro": "Nenhum arquivo enviado."}, 400)
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return _json({"ok": False, "erro": "Use JPG, PNG ou WEBP."}, 400)
    img_dir = os.path.join(PUBLIC_HTML, "img")
    if not os.path.isdir(img_dir):
        return _json({"ok": False, "erro": f"pasta de imagens não encontrada ({img_dir})"}, 500)
    fname = f"u-{slot}-{int(time.time())}.{ext}"
    f.save(os.path.join(img_dir, fname))
    # remove uploads antigos do mesmo slot
    for velho in glob.glob(os.path.join(img_dir, f"u-{slot}-*")):
        if os.path.basename(velho) != fname:
            try:
                os.remove(velho)
            except OSError:
                pass
    cfg = load_cfg()
    cfg.setdefault("site", {}).setdefault("img", {})[slot] = "/img/" + fname
    save_cfg(cfg)
    ok, msg = publish_site(cfg)
    return _json({"ok": True, "path": "/img/" + fname, "publicado": ok, "msg": msg})


if __name__ == "__main__":
    app.run(port=5001, debug=True)
