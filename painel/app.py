"""Painel do La Bodega (cPanel / Passenger).

Roda em labodegapetropolis.com.br/painel. Edita a config do bot (e, em breve,
o conteúdo do site). Os dados ficam em data/labodega.json (não é sobrescrito
pelo deploy do Git). O bot lê essa config em /painel/api/config/bot.

Proteção de escrita: header x-panel-key == variável de ambiente PANEL_KEY
(defina no cPanel → Setup Python App → Environment variables).
"""
import json
import os
from flask import Flask, request, jsonify, Response

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CFG = os.path.join(DATA_DIR, "labodega.json")
PANEL_KEY = os.environ.get("PANEL_KEY", "").strip()

DEFAULT_BOT = {
    "slug": "labodega",
    "nome": "La Bodega",
    "telefone": "(24) 2017-9899",
    "endereco": "Pátio Petrópolis, na Área de alimentação",
    "horarios": {
        "seg": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "ter": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "qua": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "qui": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "sex": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "sab": {"abre": True, "ini": "10:00", "fim": "22:00"},
        "dom": {"abre": True, "ini": "10:00", "fim": "21:00"},
    },
    "reservas": {"aceita": False, "max_pessoas": 12, "antecedencia": "até 2 horas antes"},
    "delivery": {"faz": False, "bairros": "", "taxa": "", "tempo": ""},
    "pagamento": ["Pix", "Cartão de crédito", "Cartão de débito", "Dinheiro"],
    "cardapio": [],
    "faq": [],
    "cardapio_pdf": "",
}


def load_cfg():
    if os.path.exists(CFG):
        try:
            with open(CFG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"bot": DEFAULT_BOT}


def save_cfg(cfg):
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


app = Flask(__name__)


def _json(obj, status=200):
    return Response(json.dumps(obj, ensure_ascii=False), status=status,
                    mimetype="application/json")


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
    key = request.headers.get("x-panel-key", "")
    if not PANEL_KEY or key != PANEL_KEY:
        return _json({"ok": False, "erro": "Chave do painel inválida ou não configurada."}, 401)
    try:
        body = request.get_json(force=True)
    except Exception:
        return _json({"ok": False, "erro": "JSON inválido"}, 400)
    cfg = load_cfg()
    cfg.update(body or {})
    save_cfg(cfg)
    return _json({"ok": True})


if __name__ == "__main__":
    app.run(port=5001, debug=True)
