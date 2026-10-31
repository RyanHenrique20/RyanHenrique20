#!/usr/bin/env python3
"""Gera assets/asteroid-counter.svg: contador animado de asteroides destruidos.

1 contribuicao (quadradinho do grafico) = 1 asteroide destruido.
O numero vem da API GraphQL do GitHub (ultimos 12 meses, o mesmo periodo
que o gh-space-shooter usa para montar o jogo).

Uso local para testar sem token:  COUNTER_OVERRIDE=62 python3 scripts/gen_counter.py
"""
import datetime
import json
import math
import os
import urllib.request

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "RyanHenrique20")
OUT = os.environ.get("COUNTER_OUT", "assets/asteroid-counter.svg")

# (limite minimo, nivel, patente, multiplicador) -> igual a tabela do README
LEVELS = [
    (0, 1, "CADETE ESPACIAL", 1),
    (100, 2, "PILOTO DE COMBATE", 2),
    (500, 3, "CAPITAO DA FROTA", 3),
    (1000, 4, "COMANDANTE ESTELAR", 5),
    (2500, 5, "ALMIRANTE DO ESPACO PROFUNDO", 10),
]


def fetch_total():
    override = os.environ.get("COUNTER_OVERRIDE")
    if override:
        return int(override)
    token = os.environ["GH_TOKEN"]
    query = (
        "query($login:String!){user(login:$login){contributionsCollection{"
        "contributionCalendar{totalContributions}}}}"
    )
    body = json.dumps({"query": query, "variables": {"login": OWNER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"Erro GraphQL: {data['errors']}")
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def level_info(n):
    cur = LEVELS[0]
    for lv in LEVELS:
        if n >= lv[0]:
            cur = lv
    idx = LEVELS.index(cur)
    nxt = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None
    return cur, nxt


def build(n):
    D = 8.0          # duracao total do loop (s)
    COUNT_T = 3.0    # tempo contando
    steps = min(n, 60)
    values = [round(i * n / steps) for i in range(steps + 1)] if steps else [0]
    dt = COUNT_T / max(len(values) - 1, 1)

    cur, nxt = level_info(n)
    _, lvl, rank, mult = cur
    if nxt:
        span = nxt[0] - cur[0]
        frac = (n - cur[0]) / span
        missing = nxt[0] - n
        prox = f"PROXIMO NIVEL: FALTAM {missing}"
    else:
        frac, prox = 1.0, "NIVEL MAXIMO!"
    cells = 20
    filled = int(frac * cells)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    k = lambda t: f"{min(max(t / D, 0), 1):.4f}"
    o = []
    o.append('<?xml version="1.0" encoding="UTF-8"?>')
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 130" width="800" height="130" font-family="Courier New, Courier, monospace">')
    o.append('<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="0.9" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
             '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.4" fill="#fff" opacity="0.06"/></pattern></defs>')
    o.append('<rect width="800" height="130" fill="#000"/>')
    o.append('<rect x="2" y="2" width="796" height="126" fill="none" stroke="#fff" stroke-width="2" opacity="0.85"/>')

    # asteroide girando
    random_pts = [(-24, -8), (-12, -26), (6, -22), (26, -6), (20, 18), (0, 26), (-20, 16)]
    pts = " ".join(f"{x},{y}" for x, y in random_pts)
    o.append('<g transform="translate(70,65)" filter="url(#glow)" stroke="#fff" fill="none" stroke-width="2" stroke-linejoin="round">'
             f'<polygon points="{pts}"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite"/></polygon></g>')

    o.append('<g fill="#fff" font-weight="bold" filter="url(#glow)">')
    o.append('<text x="130" y="38" font-size="16">ASTEROIDES DESTRUIDOS</text>')

    # numero contando
    for i, v in enumerate(values):
        s = i * dt
        e = (i + 1) * dt if i < len(values) - 1 else None
        init = "1" if i == 0 else "0"
        if len(values) == 1:
            o.append(f'<text x="130" y="95" font-size="48">{v:05d}</text>')
            continue
        if i == 0:
            kt, vv = f"0;{k(e)}", "1;0"
        elif e is None:
            kt, vv = f"0;{k(s)}", "0;1"
        else:
            kt, vv = f"0;{k(s)};{k(e)}", "0;1;0"
        o.append(f'<text x="130" y="95" font-size="48" opacity="{init}">{v:05d}'
                 f'<animate attributeName="opacity" calcMode="discrete" keyTimes="{kt}" values="{vv}" dur="{D}s" repeatCount="indefinite"/></text>')
    o.append('</g>')

    # nivel + barra de progresso (direita)
    o.append('<g fill="#fff" font-weight="bold" text-anchor="end" filter="url(#glow)">')
    o.append(f'<text x="770" y="38" font-size="16">LV.{lvl:02d}  ·  x{mult}</text>')
    o.append(f'<text x="770" y="62" font-size="13">{rank}</text>')
    o.append('</g>')
    cw, gap, x0, y0 = 11, 3, 770 - (20 * 14 - 3), 74
    o.append('<g stroke="#fff" stroke-width="1.5" fill="none">')
    for c in range(cells):
        fill = ' fill="#fff"' if c < filled else ""
        o.append(f'<rect x="{x0 + c * (cw + gap)}" y="{y0}" width="{cw}" height="14"{fill}/>')
    o.append('</g>')
    o.append(f'<text x="770" y="108" fill="#fff" font-size="12" text-anchor="end">{prox}</text>')
    o.append(f'<text x="130" y="118" fill="#fff" opacity="0.6" font-size="10">1 QUADRADINHO = 1 ASTEROIDE · ULTIMOS 12 MESES · ATUALIZADO {today}</text>')
    o.append('<rect width="800" height="130" fill="url(#scan)" pointer-events="none"/>')
    o.append('</svg>')
    return "\n".join(o)


def main():
    n = fetch_total()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build(n))
    print(f"{n} asteroides destruidos -> {OUT}")


if __name__ == "__main__":
    main()
