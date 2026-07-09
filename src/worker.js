// La Bodega — Worker: serve o site estático (public/) + painel (/painel) + API (/api).
// A config de cada cliente fica no KV (binding CMS), chave "cfg:<slug>".
// Fallback: se o KV estiver vazio, usa o default embutido (bot continua funcionando).

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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const p = url.pathname;

    if (request.method === "OPTIONS") return json({});

    // ---------- API ----------
    if (p.startsWith("/api/")) {
      const parts = p.split("/").filter(Boolean); // ["api","config","<slug>", "<section>?"]
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
        const next = { ...cur, ...body }; // mescla seção enviada (bot e/ou site)
        await env.CMS.put("cfg:" + slug, JSON.stringify(next));
        return json({ ok: true });
      }

      return json({ ok: false, erro: "Método não suportado" }, 405);
    }

    // ---------- Painel ----------
    if (p === "/painel" || p === "/painel/") {
      return new Response(PANEL_HTML, {
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }

    // ---------- Site estático (public/) ----------
    return env.ASSETS.fetch(request);
  },
};
