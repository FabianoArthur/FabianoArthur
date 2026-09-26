"""Build the animated "how I ship" diagram used by the profile README.

Writes four self-contained SVGs to docs/assets/ (English and pt-BR, light and
dark). The travelling dots are CSS @keyframes on stroke-dashoffset: no SMIL,
no JavaScript, no external fonts, so GitHub renders them through <img>.

    python3 scripts/build_diagram.py           # regenerate
    python3 scripts/build_diagram.py --check   # fail if the committed SVGs are stale
"""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "assets"
W, H = 800, 484
CYCLE = 9  # seconds for one full order → PR → review loop

THEMES = {
    "dark": {
        "bg": "#161b22",
        "bg_stroke": "#30363d",
        "card": "#0d1117",
        "card_stroke": "#3d444d",
        "text": "#e6edf3",
        "muted": "#9198a1",
        "zone": "#1b2040",
        "zone_stroke": "#3a4386",
        "zone_text": "#aab2ff",
        "edge": "#6e7681",
        "accent": "#fb923c",
    },
    "light": {
        "bg": "#ffffff",
        "bg_stroke": "#d1d9e0",
        "card": "#f6f8fa",
        "card_stroke": "#d1d9e0",
        "text": "#1f2328",
        "muted": "#59636e",
        "zone": "#eef0ff",
        "zone_stroke": "#b4bcf5",
        "zone_text": "#4450c8",
        "edge": "#8c959f",
        "accent": "#ea580c",
    },
}

COPY = {
    "en": {
        "suffix": "",
        "title": "How I ship with Claude Code",
        "desc": (
            "You place an order: an idea or a bug report. The waiter, the main Claude Code session, "
            "takes the order and writes a task doc, then dispatches it to kitchens that cook in "
            "parallel, each one a tmux session with its own git worktree. Every kitchen's work "
            "passes the gates (tests, lint and build, a secret scan, and an independent review) "
            "and becomes a pull request with green CI. The loop closes with you: you review and merge."
        ),
        "you": ("you", "place an order"),
        "waiter": ("waiter", "main session", "takes the order,", "writes the task doc"),
        "zone": "kitchens · in parallel",
        "kitchen": "kitchen",
        "kitchen_sub": "tmux + git worktree",
        "gates": ("gates", "tests · lint · build", "secret scan", "independent review"),
        "pr": ("pull request", "CI green, ready to merge"),
        "back": "you review and merge",
    },
    "pt-BR": {
        "suffix": ".pt-BR",
        "title": "Como eu entrego com o Claude Code",
        "desc": (
            "Você faz o pedido: uma ideia ou um bug. O garçom, a sessão principal do Claude Code, "
            "anota o pedido e escreve o doc da tarefa, depois o manda para cozinhas que trabalham "
            "em paralelo, cada uma numa sessão tmux com o seu próprio git worktree. O trabalho de "
            "cada cozinha passa pelas checagens (testes, lint e build, varredura de segredos e "
            "review independente) e vira um pull request com CI verde. O ciclo fecha em você: "
            "você revisa e faz o merge."
        ),
        "you": ("você", "faz o pedido"),
        "waiter": ("garçom", "sessão principal", "anota o pedido,", "escreve o doc da tarefa"),
        "zone": "cozinhas · em paralelo",
        "kitchen": "cozinha",
        "kitchen_sub": "tmux + git worktree",
        "gates": ("checagens", "testes · lint · build", "varredura de segredos", "review independente"),
        "pr": ("pull request", "CI verde, pronto para merge"),
        "back": "você revisa e faz o merge",
    },
}

# Geometry. Centre line of the flow is y=225; kitchens sit at y=108/225/342.
KITCHEN_Y = (108, 225, 342)
EDGES = [
    # (name, path, start %, end %) in the order the work really moves.
    ("order", "M136,225 H170", 0, 7),
    ("send-a", "M332,225 H350 V108 H378", 9, 19),
    ("send-b", "M332,225 H378", 9, 19),
    ("send-c", "M332,225 H350 V342 H378", 9, 19),
    ("done-a", "M532,108 H560 V125 H582", 40, 50),
    ("done-b", "M532,225 H560 V125 H582", 40, 50),
    ("done-c", "M532,342 H560 V125 H582", 40, 50),
    ("open-pr", "M684,210 V248", 57, 63),
    ("review", "M684,340 V436 H76 V277", 69, 88),
]
# Boxes that light up while they work: (x, y, w, h, start %, end %).
GLOWS = [(378, 70 + i * 117, 154, 76, 19, 40) for i in range(3)] + [
    (584, 40, 200, 170, 50, 57),
    (584, 250, 200, 90, 63, 69),
]


def pct(x):
    return f"{x:g}%"


def edge_keyframes(i, start, end):
    fade_in, fade_out = start + 0.8, min(end + 2.5, 99)
    return (
        f"@keyframes m{i}{{0%,{pct(start)}{{stroke-dashoffset:0;opacity:0}}"
        f"{pct(fade_in)}{{stroke-dashoffset:-2;opacity:1}}"
        f"{pct(end)}{{stroke-dashoffset:-99.9;opacity:1}}"
        f"{pct(fade_out)},100%{{stroke-dashoffset:-99.9;opacity:0}}}}"
        f"@keyframes h{i}{{0%,{pct(start)}{{opacity:0}}{pct(fade_in)},{pct(end)}{{opacity:.9}}"
        f"{pct(min(end + 6, 99))},100%{{opacity:0}}}}"
    )


def glow_keyframes(i, start, end):
    return (
        f"@keyframes g{i}{{0%,{pct(start)}{{opacity:0}}{pct(start + 2)},{pct(end - 1)}{{opacity:1}}"
        f"{pct(min(end + 5, 99))},100%{{opacity:0}}}}"
    )


def style(t):
    mono = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
    sans = "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
    rules = [
        f"text{{font-family:{sans};fill:{t['text']}}}",
        ".b{font-size:15px;font-weight:600}",
        f".m{{font-size:12.5px;fill:{t['muted']}}}",
        f".code{{font-family:{mono};font-size:12.5px}}",
        f".h{{font-size:11.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;fill:{t['zone_text']}}}",
        f".bg{{fill:{t['bg']};stroke:{t['bg_stroke']}}}",
        f".card{{fill:{t['card']};stroke:{t['card_stroke']}}}",
        f".zone{{fill:{t['zone']};stroke:{t['zone_stroke']}}}",
        f".e{{fill:none;stroke:{t['edge']};stroke-width:1.5;stroke-linejoin:round}}",
        f".hl{{fill:none;stroke:{t['accent']};stroke-width:2;stroke-linejoin:round;opacity:0}}",
        f".pk,.halo{{fill:none;stroke:{t['accent']};stroke-linecap:round;stroke-dasharray:.1 400;opacity:0}}",
        ".pk{stroke-width:9}",
        ".halo{stroke-width:19;stroke-opacity:.25}",
        f".glow{{fill:none;stroke:{t['accent']};stroke-width:1.5;opacity:0}}",
        f".ok{{fill:{t['accent']}}}",
    ]
    for i, (_, _, start, end) in enumerate(EDGES):
        rules.append(edge_keyframes(i, start, end))
        anim = f"{CYCLE}s ease-in-out infinite"
        rules.append(f".a{i} .pk,.a{i} .halo{{animation:m{i} {anim}}}.a{i} .hl{{animation:h{i} {anim}}}")
    for i, (*_, start, end) in enumerate(GLOWS):
        rules.append(glow_keyframes(i, start, end))
        rules.append(f".g{i}{{animation:g{i} {CYCLE}s ease-in-out infinite}}")
    rules.append("@media (prefers-reduced-motion:reduce){.pk,.halo,.hl,.glow{animation:none;display:none}}")
    return "\n".join(rules)


def text(x, y, body, cls, anchor="middle"):
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(body)}</text>'


def build(lang, theme):
    c, t = COPY[lang], THEMES[theme]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-labelledby="title desc" lang="{lang}">',
        f'<title id="title">{escape(c["title"])}</title>',
        f'<desc id="desc">{escape(c["desc"])}</desc>',
        f"<style>\n{style(t)}\n</style>",
        '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z" fill="{t["edge"]}"/></marker></defs>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" class="bg"/>',
    ]

    # you
    out.append('<rect x="16" y="177" width="120" height="96" rx="12" class="card"/>')
    out.append(text(76, 220, c["you"][0], "b"))
    out.append(text(76, 244, c["you"][1], "m"))

    # waiter
    title, sub, line1, line2 = c["waiter"]
    out.append('<rect x="170" y="160" width="162" height="130" rx="12" class="card"/>')
    out.append(text(251, 192, title, "b"))
    out.append(text(251, 214, sub, "code"))
    out.append(text(251, 246, line1, "m"))
    out.append(text(251, 266, line2, "m"))

    # kitchens
    out.append('<rect x="362" y="24" width="186" height="380" rx="14" class="zone"/>')
    out.append(text(455, 50, c["zone"], "h"))
    for i, cy in enumerate(KITCHEN_Y):
        out.append(f'<rect x="378" y="{cy - 38}" width="154" height="76" rx="10" class="card"/>')
        out.append(text(455, cy - 4, f"{c['kitchen']}-{'abc'[i]}", "code"))
        out.append(text(455, cy + 18, c["kitchen_sub"], "m"))

    # gates
    g_title, *checks = c["gates"]
    out.append('<rect x="584" y="40" width="200" height="170" rx="12" class="card"/>')
    out.append(text(684, 74, g_title, "b"))
    for i, check in enumerate(checks):
        y = 110 + i * 32
        out.append(f'<circle cx="610" cy="{y - 4}" r="4" class="ok"/>')
        out.append(text(624, y, check, "m", anchor="start"))

    # pull request
    out.append('<rect x="584" y="250" width="200" height="90" rx="12" class="card"/>')
    out.append(text(684, 286, c["pr"][0], "b"))
    out.append(text(684, 310, c["pr"][1], "m"))

    # static edges, then the back-to-you label
    for _, d, _, _ in EDGES:
        out.append(f'<path d="{d}" class="e" marker-end="url(#ah)"/>')
    out.append(f'<rect x="{380 - 110}" y="448" width="220" height="24" rx="12" class="card"/>')
    out.append(text(380, 465, c["back"], "m"))

    # animation layer
    for i, (x, y, w, h, _, _) in enumerate(GLOWS):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" class="glow g{i}"/>')
    for i, (_, d, _, _) in enumerate(EDGES):
        out.append(
            f'<g class="a{i}"><path d="{d}" class="hl"/>'
            f'<path d="{d}" pathLength="100" class="halo"/>'
            f'<path d="{d}" pathLength="100" class="pk"/></g>'
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def targets():
    for lang, c in COPY.items():
        for theme in THEMES:
            yield OUT / f"how-i-ship{c['suffix']}-{theme}.svg", build(lang, theme)


def main(argv):
    check = "--check" in argv
    stale = []
    for path, svg in targets():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != svg:
                stale.append(path.name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg, encoding="utf-8")
            print(f"wrote {path.relative_to(OUT.parent.parent)}")
    if stale:
        print("stale diagrams, run scripts/build_diagram.py:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
