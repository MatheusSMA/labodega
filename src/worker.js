// La Bodega — Worker: site estático (public/) + painel (/painel) + API (/api).
// Config no KV (binding CMS), chave "cfg:<slug>": { bot:{...}, site:{ emBreve, msg } }.
// Se site.emBreve = true, a home mostra uma página "Em breve" (logo + mensagem).

import PANEL_HTML from "./painel.html";
import DEFAULT_BOT from "../data/default-labodega.json";

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "access-control-allow-headers": "content-type, x-panel-key",
      "access-control-allow-methods": "GET, POST, OPTIONS",
    },
  });

async function loadCfg(env, slug) {
  const cfg = await env.CMS.get("cfg:" + slug, "json");
  if (cfg && Object.keys(cfg).length) return cfg;
  return { bot: DEFAULT_BOT };
}

function comingSoonPage(site, bot) {
  const nome = (bot && bot.nome) || "La Bodega";
  const msg = (site && site.msg) || "Estamos preparando algo especial.";
  return `<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${nome} · Em breve</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,500&family=Montserrat:wght@400;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;
    background:radial-gradient(90% 90% at 50% 20%,#2c2823,#1b1916 70%);color:#e8e1d0;
    font-family:"Montserrat",system-ui,sans-serif;text-align:center;padding:32px}
  img{width:130px;height:130px;border-radius:50%;box-shadow:0 30px 80px -30px rgba(0,0,0,.8);margin-bottom:34px}
  .eyebrow{font-size:.72rem;letter-spacing:.34em;text-transform:uppercase;color:#c89a3e;font-weight:600;margin-bottom:18px}
  h1{font-family:"Playfair Display",serif;font-style:italic;font-weight:500;font-size:clamp(2rem,6vw,3.2rem);color:#e2bd62;margin-bottom:16px}
  p{color:#ada592;max-width:440px;font-size:1rem;line-height:1.6}
  .brand{margin-top:40px;font-size:.8rem;letter-spacing:.3em;text-transform:uppercase;color:#ada592}
</style></head><body>
  <img src="/img/logo.png" alt="${nome}">
  <div class="eyebrow">Em breve</div>
  <h1>${nome}</h1>
  <p>${msg}</p>
  <div class="brand">Rooftop · Pátio Petrópolis</div>
</body></html>`;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const p = url.pathname;

    if (request.method === "OPTIONS") return json({});

    // ---------- API ----------
    if (p.startsWith("/api/")) {
      const parts = p.split("/").filter(Boolean); // ["api","config","<slug>","<section>?"]
      const slug = parts[2] || "labodega";
      const section = parts[3];

      if (request.method === "GET") {
        const cfg = await loadCfg(env, slug);
        if (section === "bot") return json(cfg.bot || DEFAULT_BOT);
        if (section === "site") return json(cfg.site || {});
        return json(cfg);
      }

      if (request.method === "POST") {
        const key = request.headers.get("x-panel-key") || "";
        if (!env.PANEL_KEY || key !== env.PANEL_KEY)
          return json({ ok: false, erro: "Chave do painel inválida ou não configurada." }, 401);
        let body;
        try { body = await request.json(); } catch { return json({ ok: false, erro: "JSON inválido" }, 400); }
        const cur = (await env.CMS.get("cfg:" + slug, "json")) || {};
        const next = { ...cur, ...body };
        await env.CMS.put("cfg:" + slug, JSON.stringify(next));
        return json({ ok: true });
      }

      return json({ ok: false, erro: "Método não suportado" }, 405);
    }

    // ---------- Painel ----------
    if (p === "/painel" || p === "/painel/") {
      return new Response(PANEL_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
    }

    // ---------- Home: checa modo "Em breve" ----------
    const isPage = p === "/" || p === "" || p === "/index.html";
    if (isPage) {
      const cfg = await loadCfg(env, "labodega");
      const site = cfg.site || {};
      if (site.emBreve) {
        return new Response(comingSoonPage(site, cfg.bot || DEFAULT_BOT), {
          headers: { "content-type": "text/html; charset=utf-8" },
        });
      }
    }

    // ---------- Site estático (public/) ----------
    return env.ASSETS.fetch(request);
  },
};
