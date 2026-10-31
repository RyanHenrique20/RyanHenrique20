#!/usr/bin/env python3
"""Gera tudo que o jogo precisa a partir da API do GitHub (sem servicos de terceiros):

  1. assets/asteroid-counter.svg  -> placar (pontuacao, asteroides, nivel, combo)
  2. assets/battle-map.svg        -> Mapa de Batalha (cada quadradinho = 1 dia)
  3. README.md                    -> tabela de Missoes (repositorios) entre os marcadores
                                     <!-- MISSOES:START --> e <!-- MISSOES:END -->

Regras (iguais as do README):
  - 1 contribuicao (quadradinho/commit) = 1 asteroide destruido = +100 pontos
  - 7+ dias seguidos  -> combo x2  (vale para as contribuicoes da sequencia atual)
  - 30+ dias seguidos -> combo x5  (vale para as contribuicoes da sequencia atual)
  - 1 estrela recebida (nos repositorios proprios) = +500 pontos

Teste local sem token (dados de mentira):
  COUNTER_OVERRIDE=62 COUNTER_STARS=0 COUNTER_STREAK=1 python3 gen_counter.py
"""
import datetime
import json
import os
import random
import re
import urllib.request

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "RyanHenrique20")
OUT_COUNTER = os.environ.get("COUNTER_OUT", "assets/asteroid-counter.svg")
OUT_MAP = os.environ.get("MAP_OUT", "assets/battle-map.svg")
README = os.environ.get("COUNTER_README", "README.md")

PTS_PER_ASTEROID = 100
PTS_PER_STAR = 500

# (minimo de asteroides, nivel, patente)
LEVELS = [
    (0, 1, "CADETE ESPACIAL"),
    (100, 2, "PILOTO DE COMBATE"),
    (500, 3, "CAPITAO DA FROTA"),
    (1000, 4, "COMANDANTE ESTELAR"),
    (2500, 5, "ALMIRANTE DO ESPACO PROFUNDO"),
]
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

DEFS = ('<defs><filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="0.9" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.4" fill="#fff" opacity="0.06"/></pattern></defs>')


# --------------------------------------------------------------------------- dados
def gql(query, variables):
    token = os.environ["GH_TOKEN"]
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"Erro GraphQL: {data['errors']}")
    return data["data"]


def fake_data():
    """Dados de mentira, so para testar o visual localmente."""
    rnd = random.Random(3)
    today = datetime.date.today()
    start = today - datetime.timedelta(days=364)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)  # volta ate o domingo
    weeks, d = [], start
    while d <= today:
        week = []
        for _ in range(7):
            if d <= today:
                c = rnd.choice([0, 0, 0, 0, 1, 1, 2, 3, 5, 8]) if rnd.random() < 0.5 else 0
                week.append({"date": d.isoformat(), "weekday": (d.weekday() + 1) % 7, "contributionCount": c})
            d += datetime.timedelta(days=1)
        weeks.append(week)
    repos = [
        {"name": "projeto-exemplo", "description": "Descricao de teste | com pipe", "url": "https://github.com/x/y",
         "stargazerCount": 2, "isArchived": False, "pushedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "primaryLanguage": {"name": "JavaScript"}},
        {"name": "site-antigo", "description": None, "url": "https://github.com/x/z",
         "stargazerCount": 0, "isArchived": False, "pushedAt": "2026-05-01T10:00:00Z", "primaryLanguage": None},
    ]
    return weeks, repos


def fetch():
    if os.environ.get("COUNTER_OVERRIDE"):
        total = int(os.environ["COUNTER_OVERRIDE"])
        stars = int(os.environ.get("COUNTER_STARS", "0"))
        streak = int(os.environ.get("COUNTER_STREAK", "0"))
        streak_c = min(total, int(os.environ.get("COUNTER_STREAK_CONTRIB", str(streak))))
        weeks, repos = fake_data()
        if os.environ.get("COUNTER_PLACEHOLDER"):
            for w in weeks:
                for d in w:
                    d["contributionCount"] = 0
            repos = []
        return dict(total=total, stars=stars, streak=streak, streak_c=streak_c, weeks=weeks, repos=repos)

    q = """
    query($login:String!){
      user(login:$login){
        contributionsCollection{
          contributionCalendar{
            totalContributions
            weeks{contributionDays{date weekday contributionCount}}
          }
        }
        repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC,
                     orderBy:{field:PUSHED_AT, direction:DESC}){
          nodes{name description url stargazerCount isArchived pushedAt primaryLanguage{name}}
        }
      }
    }"""
    u = gql(q, {"login": OWNER})["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    repos = u["repositories"]["nodes"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]

    days = sorted((d for w in weeks for d in w), key=lambda d: d["date"])
    if days and days[-1]["contributionCount"] == 0:  # hoje zerado nao quebra a sequencia
        days = days[:-1]
    streak = streak_c = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            streak += 1
            streak_c += d["contributionCount"]
        else:
            break
    return dict(total=cal["totalContributions"], stars=sum(r["stargazerCount"] for r in repos),
                streak=streak, streak_c=streak_c, weeks=weeks, repos=repos)


# --------------------------------------------------------------------------- regras
def combo_mult(streak):
    return 5 if streak >= 30 else 2 if streak >= 7 else 1


def level_info(n):
    cur = LEVELS[0]
    for lv in LEVELS:
        if n >= lv[0]:
            cur = lv
    idx = LEVELS.index(cur)
    return cur, (LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None)


# --------------------------------------------------------------------------- 1) placar
def build_counter(s):
    total, stars, streak, streak_c = s["total"], s["stars"], s["streak"], s["streak_c"]
    mult = combo_mult(streak)
    points = (total - streak_c) * PTS_PER_ASTEROID + streak_c * PTS_PER_ASTEROID * mult + stars * PTS_PER_STAR

    D, COUNT_T = 8.0, 3.0
    steps = min(points // 100, 60) if points else 0
    values = [round(i * points / steps) for i in range(steps + 1)] if steps else [points]
    dt = COUNT_T / max(len(values) - 1, 1)

    cur, nxt = level_info(total)
    _, lvl, rank = cur
    if nxt:
        frac = (total - cur[0]) / (nxt[0] - cur[0])
        prox = f"PROXIMO NIVEL: FALTAM {nxt[0] - total} ASTEROIDES"
    else:
        frac, prox = 1.0, "NIVEL MAXIMO!"
    cells, filled = 20, int(frac * 20)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    k = lambda t: f"{min(max(t / D, 0), 1):.4f}"
    fmt = lambda v: f"{v:06d}"
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 140" width="800" height="140" font-family="Courier New, Courier, monospace">',
         DEFS,
         '<rect width="800" height="140" fill="#000"/>',
         '<rect x="2" y="2" width="796" height="136" fill="none" stroke="#fff" stroke-width="2" opacity="0.85"/>']

    pts = " ".join(f"{x},{y}" for x, y in [(-24, -8), (-12, -26), (6, -22), (26, -6), (20, 18), (0, 26), (-20, 16)])
    o.append('<g transform="translate(70,70)" filter="url(#glow)" stroke="#fff" fill="none" stroke-width="2" stroke-linejoin="round">'
             f'<polygon points="{pts}"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="12s" repeatCount="indefinite"/></polygon></g>')

    o.append('<g fill="#fff" font-weight="bold" filter="url(#glow)">')
    o.append('<text x="130" y="30" font-size="15">PONTUACAO</text>')
    for i, v in enumerate(values):
        st = i * dt
        e = (i + 1) * dt if i < len(values) - 1 else None
        if len(values) == 1:
            o.append(f'<text x="130" y="82" font-size="48">{fmt(v)}</text>')
            continue
        if i == 0:
            kt, vv = f"0;{k(e)}", "1;0"
        elif e is None:
            kt, vv = f"0;{k(st)}", "0;1"
        else:
            kt, vv = f"0;{k(st)};{k(e)}", "0;1;0"
        o.append(f'<text x="130" y="82" font-size="48" opacity="{"1" if i == 0 else "0"}">{fmt(v)}'
                 f'<animate attributeName="opacity" calcMode="discrete" keyTimes="{kt}" values="{vv}" dur="{D}s" repeatCount="indefinite"/></text>')
    o.append('</g>')

    conta = f"{total} ASTEROIDES x {PTS_PER_ASTEROID}  +  {stars} ESTRELAS x {PTS_PER_STAR}"
    if mult > 1:
        conta += f"  +  COMBO x{mult}"
    o.append(f'<text x="130" y="104" fill="#fff" font-size="12" font-weight="bold">{conta}</text>')
    o.append(f'<text x="130" y="126" fill="#fff" opacity="0.6" font-size="10">{PTS_PER_ASTEROID} PTS POR ASTEROIDE · 12 MESES · ATUALIZADO {today}</text>')

    o.append('<g fill="#fff" font-weight="bold" text-anchor="end" filter="url(#glow)">')
    o.append(f'<text x="770" y="30" font-size="16">LV.{lvl:02d}  ·  {total} ASTEROIDES</text>')
    o.append(f'<text x="770" y="52" font-size="13">{rank}</text>')
    o.append('</g>')
    cw, gap, x0, y0 = 11, 3, 770 - (20 * 14 - 3), 62
    o.append('<g stroke="#fff" stroke-width="1.5" fill="none">')
    for c in range(cells):
        o.append(f'<rect x="{x0 + c * (cw + gap)}" y="{y0}" width="{cw}" height="14"{" fill=" + chr(34) + "#fff" + chr(34) if c < filled else ""}/>')
    o.append('</g>')
    o.append(f'<text x="770" y="96" fill="#fff" font-size="11" text-anchor="end">{prox}</text>')
    o.append(f'<text x="770" y="118" fill="#fff" font-size="13" font-weight="bold" text-anchor="end">COMBO x{mult}  ·  SEQUENCIA: {streak} DIAS</text>')
    o.append('<rect width="800" height="140" fill="url(#scan)" pointer-events="none"/>')
    o.append('</svg>')
    return "\n".join(o), points


# --------------------------------------------------------------------------- 2) mapa de batalha
def build_map(s):
    weeks, total = s["weeks"], s["total"]
    placeholder = bool(os.environ.get("COUNTER_PLACEHOLDER"))
    cell, gap, x0, y0 = 11, 3, 29, 52
    step = cell + gap
    grid_w = max(len(weeks), 1) * step - gap
    counts = [d["contributionCount"] for w in weeks for d in w]
    active = sum(1 for c in counts if c > 0)
    best = max(counts) if counts else 0

    def opacity(c):
        if c <= 0:
            return None
        return 0.35 if c == 1 else 0.6 if c <= 3 else 0.82 if c <= 6 else 1.0

    title = "AGUARDANDO RADAR..." if placeholder else f"MAPA DE BATALHA · {total} ASTEROIDES DESTRUIDOS"
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 190" width="800" height="190" font-family="Courier New, Courier, monospace">',
         DEFS,
         '<rect width="800" height="190" fill="#000"/>',
         '<rect x="2" y="2" width="796" height="186" fill="none" stroke="#fff" stroke-width="2" opacity="0.85"/>',
         f'<text x="29" y="30" fill="#fff" font-size="15" font-weight="bold" filter="url(#glow)">{title}</text>']

    changes, last_month = [], None
    for wi, week in enumerate(weeks):
        if not week:
            continue
        m = int(week[0]["date"][5:7])
        if m != last_month:
            changes.append((wi, m))
            last_month = m
    if len(changes) > 1 and changes[1][0] - changes[0][0] < 3:  # evita "OUT" colado em "NOV"
        changes = changes[1:]
    for wi, m in changes:
        o.append(f'<text x="{x0 + wi * step}" y="46" fill="#fff" opacity="0.7" font-size="9">{MESES[m - 1]}</text>')

    o.append('<g filter="url(#glow)" stroke="#fff" stroke-width="1">')
    for wi, week in enumerate(weeks):
        for d in week:
            x, y = x0 + wi * step, y0 + d["weekday"] * step
            op = opacity(d["contributionCount"])
            if op is None:
                o.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="none" stroke-opacity="0.22"/>')
            else:
                o.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="#fff" fill-opacity="{op}" stroke-opacity="{op}"/>')
    o.append('</g>')

    # varredura do radar
    o.append(f'<rect x="{x0 - 2}" y="{y0 - 3}" width="2" height="{7 * step + 3}" fill="#fff" opacity="0.45">'
             f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{grid_w} 0" dur="7s" repeatCount="indefinite"/></rect>')

    o.append(f'<text x="29" y="170" fill="#fff" font-size="12" font-weight="bold">DIAS DE COMBATE: {active}  ·  MELHOR DIA: {best} ASTEROIDES</text>')
    lx = 771 - 5 * step - 90
    o.append(f'<text x="{lx}" y="170" fill="#fff" opacity="0.7" font-size="10" text-anchor="end">MENOS</text>')
    for i, op in enumerate([None, 0.35, 0.6, 0.82, 1.0]):
        x = lx + 6 + i * step
        if op is None:
            o.append(f'<rect x="{x}" y="160" width="{cell}" height="{cell}" fill="none" stroke="#fff" stroke-opacity="0.22"/>')
        else:
            o.append(f'<rect x="{x}" y="160" width="{cell}" height="{cell}" fill="#fff" fill-opacity="{op}" stroke="#fff" stroke-opacity="{op}"/>')
    o.append(f'<text x="{lx + 6 + 5 * step + 4}" y="170" fill="#fff" opacity="0.7" font-size="10">MAIS</text>')
    o.append('<rect width="800" height="190" fill="url(#scan)" pointer-events="none"/>')
    o.append('</svg>')
    return "\n".join(o)


# --------------------------------------------------------------------------- 3) missoes (repositorios)
def build_missions(repos):
    repos = [r for r in repos if r["name"].lower() != OWNER.lower()][:8]
    if not repos:
        return "> 🛰️ *Nenhuma missão no radar ainda. Crie um repositório público para abrir a primeira missão!*"
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = ["| # | 🎯 Missão (Repositório) | 📋 Objetivo | 🔫 Arma | ⭐ | 📊 Status |",
            "|:-:|:--|:--|:--|:-:|:--|"]
    for i, r in enumerate(repos, 1):
        desc = (r.get("description") or "Missão secreta (sem descrição ainda)").replace("|", "/").replace("\n", " ").strip()
        if len(desc) > 80:
            desc = desc[:77].rstrip() + "..."
        lang = (r.get("primaryLanguage") or {}).get("name") or "—"
        pushed = datetime.datetime.fromisoformat(r["pushedAt"].replace("Z", "+00:00"))
        days = (now - pushed).days
        if r.get("isArchived"):
            status = "✅ CONCLUÍDA"
        elif days <= 30:
            status = "🔥 EM COMBATE"
        else:
            status = "🛰️ EM ÓRBITA"
        rows.append(f"| {i:02d} | [**{r['name']}**]({r['url']}) | {desc} | {lang} | {r['stargazerCount']} | {status} · `{pushed.date()}` |")
    legenda = "\n\n<sub>🔥 mexi nos últimos 30 dias · 🛰️ parada em órbita · ✅ arquivada/concluída · lista atualizada automaticamente</sub>"
    return "\n".join(rows) + legenda


def update_readme(block):
    if not os.path.exists(README):
        print(f"(sem {README} aqui, pulando as missões)")
        return
    text = open(README, encoding="utf-8").read()
    pat = re.compile(r"(<!-- MISSOES:START -->).*?(<!-- MISSOES:END -->)", re.S)
    if not pat.search(text):
        print("(marcadores MISSOES não encontrados no README, pulando)")
        return
    new = pat.sub(lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)


def main():
    s = fetch()
    svg, points = build_counter(s)
    for path, content in ((OUT_COUNTER, svg), (OUT_MAP, build_map(s))):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    update_readme(build_missions(s["repos"]))
    print(f"{s['total']} asteroides, {s['stars']} estrelas, sequencia {s['streak']} dias -> {points} pontos; "
          f"{len(s['repos'])} repositórios")


if __name__ == "__main__":
    main()
