"""Painel do La Bodega (cPanel / Passenger).

Roda em labodegapetropolis.com.br/painel. Edita o BOT e o SITE:
- Dados em data/labodega.json (não sobrescrito pelo deploy do Git).
- Ao salvar, regenera o index.html a partir de site_template.html e grava
  em ~/public_html (o site continua 100% estático e rápido).
- /painel/editor = editor VISUAL: o site renderizado em modo edição
  (clica no texto pra editar, clica na foto pra trocar, salva e publica).
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
    # Textos menores espalhados pelo site (títulos de seção, botões, rótulos)
    "textos": {
        "eyebrow_menu": "O cardápio",
        "eyebrow_drinks": "Pra beber",
        "eyebrow_combo": "Combinação da casa",
        "eyebrow_visita": "Onde nos encontrar",
        "eyebrow_bot": "Fale com a gente",
        "visita_h2": "Suba e fique à vontade",
        "card_endereco": "Endereço",
        "card_horarios": "Horários",
        "combo_h1": "Entradas",
        "combo_h2": "Principal",
        "combo_h3": "Sobremesas",
        "btn_cardapio": "Ver cardápio",
        "btn_falar": "Falar com a gente",
        "btn_carta": "Ver a carta completa",
        "btn_conversa": "Abrir conversa no Telegram",
        "maps_txt": "Abrir no Google Maps →",
        "conf_horario": "Confirmar horário no Telegram →",
        "bot_h2": "O La Bodega <em>no seu bolso</em>",
        "bot_p": "Aponte a câmera pro código ou toque no botão. Você cai direto numa conversa com o nosso atendente no Telegram — sem instalar nada além do app.",
        "bot_f1": "Ver o cardápio e as promoções do dia",
        "bot_f2": "Fazer reserva e tirar dúvidas",
        "bot_f3": "Conferir horários e como chegar",
        "qr_cap": "Aponte a câmera",
        "qr_sub": "Leva direto pro nosso atendimento",
        "qr_handle": "t.me/labodegapatio_bot",
        "canal": "Telegram",
        "direitos": "Todos os direitos reservados.",
        "foot_tag": "Petrópolis · Cidade Imperial",
        "nav_casa": "A casa",
        "nav_cardapio": "Cardápio",
        "nav_drinks": "Pra beber",
        "nav_visite": "Visite",
        "foot_visita": "Onde estamos",
        "foot_h_nav": "Navegação",
        "foot_h_contato": "Contato",
        "foot_h_endereco": "Endereço",
    },
}

# textos com formatação leve permitida no editor visual
TEXTOS_RICOS = {"bot_h2"}

# Campos de texto editáveis no editor visual: marcador -> (caminho, aceita html leve)
EDIT_TEXT = {
    "HERO_TITULO": ("site.hero.titulo", True),
    "HERO_SUB": ("site.hero.sub", False),
    "CASA_QUOTE": ("site.casa.quote", True),
    "CASA1_T": ("site.casa.cards.0.t", False),
    "CASA1_D": ("site.casa.cards.0.d", False),
    "CASA2_T": ("site.casa.cards.1.t", False),
    "CASA2_D": ("site.casa.cards.1.d", False),
    "CASA3_T": ("site.casa.cards.2.t", False),
    "CASA3_D": ("site.casa.cards.2.d", False),
    "MENU_TITULO": ("site.menu.titulo", False),
    "MENU_DESC": ("site.menu.desc", False),
    "COMBO_TITULO": ("site.combo.titulo", False),
    "COMBO_PRECO": ("site.combo.preco", False),
    "COMBO_SUB": ("site.combo.sub", False),
    "COMBO_NOTA": ("site.combo.nota", False),
    "DRINK_TITULO": ("site.drink.titulo", False),
    "DRINK_NOME": ("site.drink.nome", True),
    "DRINK_DESC": ("site.drink.desc", False),
    "ENDERECO_BR": ("site.visita.endereco", True),
    "ENDERECO_OBS": ("site.visita.obs_endereco", False),
    "HORARIO_OBS": ("site.visita.obs_horario", False),
    "TEL": ("site.contato.tel", False),
    "EMAIL": ("site.contato.email", False),
    "INSTA": ("site.contato.insta", False),
    "NOME": ("bot.nome", False),
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


def _menu_cols(cardapio, subs, edit=False):
    grupos, ordem = {}, []
    for idx, it in enumerate(cardapio or []):
        cat = it.get("categoria") or "Outros"
        if cat not in grupos:
            grupos[cat] = []
            ordem.append(cat)
        grupos[cat].append((idx, it))
    parts = ['<div class="menu-cols">']
    for cat in ordem:
        parts.append('      <div class="menu-group reveal">')
        parts.append(f"        <h3>{_esc(cat)}</h3>")
        sub = (subs or {}).get(cat, "")
        if sub:
            s = f'<span data-key="site.menu.subs.{_esc(cat)}">{_esc(sub)}</span>' if edit else _esc(sub)
            parts.append(f'        <p class="gh-sub">{s}</p>')
        for idx, it in grupos[cat]:
            nome = _esc(it.get("nome"))
            if edit:
                nome = f'<span data-key="bot.cardapio.{idx}.nome">{nome}</span>'
            tags = (it.get("tags") or "").lower()
            if "vegano" in tags:
                nome += ' <span class="veg">Vegano</span>'
            elif "vegetariano" in tags:
                nome += ' <span class="veg">Vegetariano</span>'
            preco = _preco(it.get("preco", 0))
            if edit:
                preco = f'<span data-key="bot.cardapio.{idx}.preco">{preco}</span>'
            desc = _esc(it.get("desc"))
            linha = (f'        <div class="item"><div class="item-row">'
                     f'<span class="item-name">{nome}</span>'
                     f'<span class="item-lead"></span>'
                     f'<span class="item-price">{preco}</span></div>')
            if desc:
                d = f'<span data-key="bot.cardapio.{idx}.desc">{desc}</span>' if edit else desc
                linha += f'<p class="item-desc">{d}</p>'
            linha += "</div>"
            parts.append(linha)
        parts.append("      </div>")
    parts.append("    </div>")
    return "\n".join(parts)


def _ul(linhas, path=None):
    itens = []
    for i, l in enumerate((linhas or "").splitlines()):
        if not l.strip():
            continue
        t = _esc(l.strip())
        if path:
            t = f'<span data-key="{path}.{i}">{t}</span>'
        itens.append(f"<li>{t}</li>")
    return "<ul>" + "".join(itens) + "</ul>"


def _vrows(rows, edit=False):
    out = []
    for i, r in enumerate(rows or []):
        if not r or not (r[0] or r[1]):
            continue
        a, b = _esc(r[0]), _esc(r[1])
        if edit:
            a = f'<span data-key="site.visita.horarios.{i}.0">{a}</span>'
            b = f'<span data-key="site.visita.horarios.{i}.1">{b}</span>'
        out.append(f'<div class="vrow"><span>{a}</span><span>{b}</span></div>')
    return "".join(out)


def _tel_link(tel):
    dig = re.sub(r"\D", "", tel or "")
    if dig and not dig.startswith("55"):
        dig = "55" + dig
    return "+" + dig if dig else ""


def render_site(cfg, edit=False):
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
        "COMBO_UL1": _ul(site["combo"]["entradas"], "site.combo.entradas" if edit else None),
        "COMBO_UL2": _ul(site["combo"]["principal"], "site.combo.principal" if edit else None),
        "COMBO_UL3": _ul(site["combo"]["sobremesas"], "site.combo.sobremesas" if edit else None),
        "COMBO_NOTA": site["combo"]["nota"],
        "MENU_COLS": _menu_cols(bot.get("cardapio"), site["menu"].get("subs"), edit),
        "DRINK_TITULO": site["drink"]["titulo"],
        "DRINK_NOME": site["drink"]["nome"],
        "DRINK_DESC": site["drink"]["desc"],
        "DRINK_INT": d_int.strip() or "0",
        "DRINK_CENTS": ("," + d_cents.strip()) if d_cents.strip() else ",00",
        "ENDERECO_BR": "<br>".join(endereco_lines),
        "ENDERECO_OBS": site["visita"]["obs_endereco"],
        "VISITA_HORARIOS": _vrows(site["visita"].get("horarios"), edit),
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
    for k, v in (site.get("textos") or {}).items():
        valores[f"TXT_{k.upper()}"] = v

    if edit:
        # imagens clicáveis (troca por upload)
        html = html.replace('src="@@IMG_LOGO@@"', f'src="{valores["IMG_LOGO"]}" data-cms-img="logo" title="Clique para trocar a logo"')
        html = html.replace('src="@@IMG_HERO@@"', f'src="{valores["IMG_HERO"]}" data-cms-img="hero" title="Clique para trocar a foto do topo"')
        html = html.replace('src="@@IMG_DRINKS@@"', f'src="{valores["IMG_DRINKS"]}" data-cms-img="drinks" title="Clique para trocar a foto"')
        # marcadores dentro de atributos não podem virar <span>: resolve antes
        html = html.replace("mailto:@@EMAIL@@", "mailto:" + valores["EMAIL"])
        html = html.replace("https://instagram.com/@@INSTA@@", "https://instagram.com/" + valores["INSTA"])
        # preço do drink vira um campo só ("24,90") no modo edição
        html = html.replace(
            '<span class="big">@@DRINK_INT@@</span><span class="cents">@@DRINK_CENTS@@</span>',
            f'<span class="big" data-key="site.drink.preco">{preco_drink}</span>')
        for marker, (path, rich) in EDIT_TEXT.items():
            extra = ' data-rich="1"' if rich else ""
            valores[marker] = f'<span data-key="{path}"{extra}>{valores[marker]}</span>'
        for k in (site.get("textos") or {}):
            marker = f"TXT_{k.upper()}"
            extra = ' data-rich="1"' if k in TEXTOS_RICOS else ""
            valores[marker] = f'<span data-key="site.textos.{k}"{extra}>{valores[marker]}</span>'
        # endereço do rodapé edita junto com o do bloco "Visita"
        valores["FOOT_ENDERECO"] = (
            f'<span data-key="site.visita.endereco" data-rich="1">{valores["FOOT_ENDERECO"]}</span>')

    for k, v in valores.items():
        html = html.replace(f"@@{k}@@", str(v))

    if edit:
        html = html.replace("</body>", EDITOR_UI + "\n</body>")
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
# Editor visual — barra, estilos e script injetados na página em modo edição
# --------------------------------------------------------------------------
EDITOR_UI = """
<style>
  /* modo edição: congela os efeitos de hover pra dar pra clicar e digitar */
  a, .btn, .tg-btn, .vlink, .item, .exp-card { transition: none !important; }
  .btn:hover, .tg-btn:hover, .btn-gold:hover, .btn-ghost:hover, .exp-card:hover { transform: none !important; }
  .item:hover { padding-left: 0 !important; }
  [data-key]{transition:outline .15s,background .15s;cursor:text;min-width:8px}
  [data-key]:hover{outline:2px dashed #c89a3e;background:rgba(200,154,62,.10);border-radius:3px}
  [data-key]:focus{outline:2px solid #c89a3e;background:rgba(200,154,62,.14);border-radius:3px}
  [data-cms-img]{cursor:pointer}
  [data-cms-img]:hover{outline:3px dashed #c89a3e;outline-offset:-3px;filter:brightness(1.06)}
  #cms-bar{position:fixed;left:0;right:0;bottom:0;z-index:9999;background:rgba(15,17,21,.96);
    backdrop-filter:blur(8px);border-top:1px solid #333;display:flex;gap:16px;align-items:center;
    justify-content:center;padding:12px 16px;font-family:system-ui,sans-serif;font-size:14px;color:#e8eaed;flex-wrap:wrap}
  #cms-bar button{background:#25D366;color:#06210f;font-weight:700;border:0;border-radius:10px;
    padding:11px 26px;cursor:pointer;font-size:15px}
  #cms-bar button:hover{filter:brightness(1.08)}
  #cms-bar a{color:#9aa0ab;text-decoration:none;font-size:13px}
  #cms-hint{position:fixed;top:74px;right:14px;z-index:9999;background:rgba(15,17,21,.92);color:#cfd3da;
    padding:10px 14px;border-radius:10px;font:13px system-ui;border:1px solid #3a4150;max-width:240px}
  body{padding-bottom:70px}
</style>
<div id="cms-hint">🖌️ <b>Modo edição</b><br>Clique num texto para alterar.<br>Clique numa foto para trocar.</div>
<div id="cms-bar">
  <button onclick="cmsSave()">💾 Salvar alterações</button>
  <span id="cms-st"></span>
  <a href="./">← voltar ao painel</a>
</div>
<input type="file" id="cms-file" accept="image/*" style="display:none">
<script>
(function(){
  var slotAtual = null;
  document.querySelectorAll("[data-key]").forEach(function(n){
    n.setAttribute("contenteditable","true");
    n.setAttribute("spellcheck","false");
  });
  // sincroniza campos repetidos (mesmo data-key em mais de um lugar)
  document.addEventListener("input", function(e){
    var t = e.target.closest ? e.target.closest("[data-key]") : null;
    if(!t) return;
    var k = t.getAttribute("data-key");
    document.querySelectorAll('[data-key="'+k+'"]').forEach(function(o){
      if(o !== t){ o.innerHTML = t.innerHTML; }
    });
  });
  // no modo edição, links não navegam; clique em foto abre o seletor
  document.addEventListener("click", function(e){
    var img = e.target.closest ? e.target.closest("[data-cms-img]") : null;
    if(img){
      slotAtual = img.getAttribute("data-cms-img");
      document.getElementById("cms-file").click();
      e.preventDefault(); return;
    }
    var a = e.target.closest ? e.target.closest("a") : null;
    if(a && !a.closest("#cms-bar")){ e.preventDefault(); }
  }, true);
  function key(){
    var k = localStorage.getItem("panelKey");
    if(!k){ k = prompt("Chave do painel:") || ""; if(k) localStorage.setItem("panelKey", k); }
    return k;
  }
  document.getElementById("cms-file").addEventListener("change", function(){
    var f = this.files[0]; if(!f || !slotAtual) return;
    var st = document.getElementById("cms-st");
    st.textContent = "enviando foto...";
    var fd = new FormData(); fd.append("arquivo", f);
    fetch("api/upload/" + slotAtual, {method:"POST", headers:{"x-panel-key": key()}, body: fd})
      .then(function(r){return r.json();}).then(function(j){
        if(j.ok){
          document.querySelectorAll('[data-cms-img="'+slotAtual+'"]').forEach(function(i){ i.src = j.path; });
          st.textContent = "✅ foto trocada e publicada!";
        } else {
          st.textContent = "❌ " + (j.erro || "erro");
          if(j.erro && j.erro.indexOf("Chave") >= 0) localStorage.removeItem("panelKey");
        }
      }).catch(function(e){ st.textContent = "❌ " + e; });
    this.value = "";
  });
  window.cmsSave = function(){
    var st = document.getElementById("cms-st");
    st.textContent = "salvando...";
    var patch = {};
    document.querySelectorAll("[data-key]").forEach(function(n){
      var k = n.getAttribute("data-key");
      patch[k] = n.getAttribute("data-rich") ? "__RICH__" + n.innerHTML : n.textContent;
    });
    fetch("api/save-visual", {method:"POST",
      headers:{"content-type":"application/json","x-panel-key": key()},
      body: JSON.stringify(patch)})
      .then(function(r){return r.json();}).then(function(j){
        if(j.ok){
          st.textContent = "✅ salvo e publicado!";
          setTimeout(function(){ location.reload(); }, 900);
        } else {
          st.textContent = "❌ " + (j.erro || "erro");
          if(j.erro && j.erro.indexOf("Chave") >= 0) localStorage.removeItem("panelKey");
        }
      }).catch(function(e){ st.textContent = "❌ " + e; });
  };
})();
</script>"""


def _clean_rich(v):
    """Permite só formatação leve (em/br/span/b/strong/i); remove o resto."""
    v = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", "", v, flags=re.S | re.I)
    v = re.sub(r"<(?!/?(em|br|span|b|strong|i)\b)[^>]*>", "", v, flags=re.I)
    return v.replace(" ", " ").strip()


def _plain(v):
    v = re.sub(r"<[^>]+>", "", str(v))
    return re.sub(r"\s+", " ", v.replace(" ", " ")).strip()


def _apply_visual(cfg, key, raw):
    """Aplica um campo do editor visual (caminho pontilhado) na config."""
    rich = isinstance(raw, str) and raw.startswith("__RICH__")
    v = raw[8:] if rich else str(raw)
    v = _clean_rich(v) if rich else _plain(v)
    parts = key.split(".")
    if parts[0] not in ("site", "bot") or len(parts) < 2:
        return
    if key == "site.visita.endereco":
        v = re.sub(r"<br\s*/?>|</p>|</div>", "\n", v, flags=re.I)
        v = re.sub(r"<[^>]+>", "", v)
        cfg["site"]["visita"]["endereco"] = "\n".join(
            l.strip() for l in v.splitlines() if l.strip())
        return
    if parts[:2] == ["site", "combo"] and len(parts) == 4 and parts[2] in ("entradas", "principal", "sobremesas"):
        i = int(parts[3])
        lines = (cfg["site"].setdefault("combo", {}).get(parts[2]) or "").splitlines()
        while len(lines) <= i:
            lines.append("")
        lines[i] = v
        cfg["site"]["combo"][parts[2]] = "\n".join(lines)
        return
    if key.startswith("bot.cardapio.") and key.endswith(".preco"):
        num = re.sub(r"[^\d,]", "", v).replace(",", ".")
        try:
            cfg["bot"]["cardapio"][int(parts[2])]["preco"] = float(num) if num else 0.0
        except (ValueError, IndexError, KeyError):
            pass
        return
    if key == "site.drink.preco":
        cfg["site"].setdefault("drink", {})["preco"] = v.replace("R$", "").strip()
        return
    node = cfg[parts[0]]
    try:
        for p in parts[1:-1]:
            node = node[int(p)] if isinstance(node, list) else node.setdefault(p, {})
        last = parts[-1]
        if isinstance(node, list):
            node[int(last)] = v
        elif isinstance(node, dict):
            node[last] = v
    except (ValueError, IndexError, KeyError, TypeError, AttributeError):
        pass


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


@app.get("/editor")
def editor():
    return Response(render_site(load_cfg(), edit=True), mimetype="text/html")


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


@app.post("/api/save-visual")
def api_save_visual():
    if not _auth_ok():
        return _json({"ok": False, "erro": "Chave do painel inválida."}, 401)
    try:
        patch = request.get_json(force=True) or {}
    except Exception:
        return _json({"ok": False, "erro": "JSON inválido"}, 400)
    cfg = load_cfg()
    for k, v in patch.items():
        try:
            _apply_visual(cfg, str(k), v)
        except Exception:
            pass
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
