"""Generate the PCCMA logos: the full logo (letters with the full wording), the letters alone, and the icon (the flower in the
first C, in bronze lead), each for light and dark backgrounds, as SVG and PNG.

Each letter is built from ring-style pieces (arcs and bars of one thickness) in the tissue-site colors, with the gaps between
the pieces left transparent (negative space). The counters hold glass: fanlights in the P, M and A and a flower in each C. The
geometry is regular on purpose: equal pieces, seams mirrored where a letter is symmetric, gaps of one width (parallel-sided),
and aligned seams (the P's stem is cut where its bowl ends; the M's legs and the A's legs and crossbar share one seam).
Color shares follow the tissue-site cell line counts.

Writes, each as SVG and PNG (the PNGs at 2x, rendered with headless Chrome in a window of exactly the SVG's size):
  pccma_logo_{light,dark}                     the letters with the full wording, on a white / #14161F background
  pccma_logo_transparent_on_{light,dark}      the same on a transparent background, the wording dark / light for the background it sits on
  pccma_logo_letters_{light,dark}             the letters alone, on a white / #14161F background
  pccma_logo_letters_transparent              the letters alone, transparent (the same on any background)
  pccma_icon_{light,dark,transparent}         the flower in the first C, in bronze lead
The wording is converted to outlines, so the SVG needs no installed font, and is sized to span the letters exactly.

Usage: python make_pccma_logo.py [output folder]   (needs fontTools and Google Chrome; set CHROME to its path outside macOS)
"""
import math, os, random, re, subprocess, sys
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTCollection

# tissue site, color (Okabe-Ito based), cell line count
SITES = [("Adrenal gland", "#E69F00", 12), ("Bone", "#D55E00", 12), ("Central nervous system", "#0072B2", 11), ("Soft tissue", "#CC79A7", 9),
         ("Eye", "#56B4E9", 4), ("Kidney", "#009E73", 3), ("Ovary", "#D6BC00", 1), ("Normal reference", "#8C8C8C", 4)]
W, G, H = 38, 4.2, 200          # stroke width, gap between pieces, letter height (all in logo units)
PAD, SUB_GAP, SEED = 34, 36, 11     # margin around the logo, gap above the wording, seed of the color shades
WORDS = "PEDIATRIC CANCER CELL MORPHOLOGY ATLAS"
SPACING = 3.2 / 15              # letter spacing of the wording, as a share of its font size
CAP_HEIGHT = 0.717              # cap height of Helvetica Bold, as a share of its font size
FONT = "/System/Library/Fonts/Helvetica.ttc"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
TEXT_COLORS = {"light": "#3A3A3A", "dark": "#E6E6E6"}       # wording color on a light / dark background
BACKGROUNDS = {"light": "#FFFFFF", "dark": "#14161F", "transparent": None}


# ---- shapes ----
def pt(cx: float, cy: float, r: float, t: float) -> tuple[float, float]:
    """Point at radius r and angle t (degrees, clockwise from the +x axis because y points down) around (cx, cy)."""
    return cx + r * math.cos(math.radians(t)), cy + r * math.sin(math.radians(t))


def rect(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"M{x0:.2f},{y0:.2f} H{x1:.2f} V{y1:.2f} H{x0:.2f} Z"


def circle(cx: float, cy: float, r: float) -> str:
    return f"M{cx - r:.2f},{cy:.2f} a{r:.2f},{r:.2f} 0 1,0 {2 * r:.2f},0 a{r:.2f},{r:.2f} 0 1,0 {-2 * r:.2f},0 Z"


def sector(cx: float, cy: float, r0: float, r1: float, a0: float, a1: float) -> str:
    """Annular sector between radii r0 < r1 and angles a0 < a1, with radial side edges."""
    large = 1 if (a1 - a0) % 360 > 180 else 0
    x0, y0 = pt(cx, cy, r1, a0); x1, y1 = pt(cx, cy, r1, a1); x2, y2 = pt(cx, cy, r0, a1); x3, y3 = pt(cx, cy, r0, a0)
    return f"M{x0:.2f},{y0:.2f} A{r1:.2f},{r1:.2f} 0 {large} 1 {x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f} A{r0:.2f},{r0:.2f} 0 {large} 0 {x3:.2f},{y3:.2f} Z"


def parallel_sector(cx: float, cy: float, r0: float, r1: float, a0: float, a1: float, d_lo: float, d_hi: float) -> str:
    """An annular sector between angles a0 and a1 whose side edges are straight and parallel to the radial lines at a0 and a1,
    pulled in by d_lo and d_hi: two neighbors then have a seam of the same width G along its whole length (a plain radial cut
    tapers toward the center). r0 = 0 closes the piece in a point at the center (a half disc or a wedge of a fan)."""
    lo, hi = a0 + math.degrees(math.asin(d_lo / r1)), a1 - math.degrees(math.asin(d_hi / r1))
    large = 1 if (hi - lo) % 360 > 180 else 0
    x0, y0 = pt(cx, cy, r1, lo); x1, y1 = pt(cx, cy, r1, hi)
    if r0 > 1:
        lo2, hi2 = a0 + math.degrees(math.asin(d_lo / r0)), a1 - math.degrees(math.asin(d_hi / r0))
        x2, y2 = pt(cx, cy, r0, hi2); x3, y3 = pt(cx, cy, r0, lo2)
        return (f"M{x0:.2f},{y0:.2f} A{r1:.2f},{r1:.2f} 0 {large} 1 {x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f} "
                f"A{r0:.2f},{r0:.2f} 0 {large} 0 {x3:.2f},{y3:.2f} Z")

    def side(a: float, d: float, sgn: int) -> tuple[tuple[float, float], tuple[float, float]]:
        t = math.radians(a)
        return (cx - sgn * d * math.sin(t), cy + sgn * d * math.cos(t)), (math.cos(t), math.sin(t))
    (px, py), (ux, uy) = side(a0, d_lo, 1); (qx, qy), (vx, vy) = side(a1, d_hi, -1)     # the two pulled-in side lines meet in a point
    den = ux * vy - uy * vx
    s = ((qx - px) * vy - (qy - py) * vx) / den if abs(den) > 1e-9 else 0.0
    return f"M{x0:.2f},{y0:.2f} A{r1:.2f},{r1:.2f} 0 {large} 1 {x1:.2f},{y1:.2f} L{px + s * ux:.2f},{py + s * uy:.2f} Z"


def bar(x0: float, x1: float, y0: float, y1: float, rng: random.Random, pieces: int = 1, seam: float | None = None,
        tag: str = "body") -> list[tuple]:
    """A rectangle in one piece or, with pieces == 2 and a `seam`, in two pieces cut at the seam (the y of the middle of the gap).
    One random draw per piece is kept so that the color shades stay what they were when the pieces were cut unevenly."""
    for _ in range(1 + pieces):
        rng.uniform(0.7, 1.3)
    if seam is not None and pieces == 2:
        return [(rect(x0, y0, x1, seam - G / 2), None, tag), (rect(x0, seam + G / 2, x1, y1), None, tag)]
    return [(rect(x0, y0, x1, y1), None, tag)]


def arc(cx: float, cy: float, r: float, R: float, a0: float, a1: float, n: int, rng: random.Random) -> list[tuple]:
    """A ring segment from r to R and from a0 to a1, cut into n equal pieces with parallel-sided seams.
    Each piece is (path, clip, tag, middle angle)."""
    for _ in range(2 * n):
        rng.uniform(0.8, 1.2)
    step = (a1 - a0) / n
    return [(parallel_sector(cx, cy, r, R, a0 + i * step, a0 + (i + 1) * step, G / 2 if i else 0, G / 2 if i < n - 1 else 0), None, "body",
             a0 + (i + 0.5) * step) for i in range(n)]


def fan(cx: float, cy: float, R0: float, a0: float, a1: float, n: int, rng: random.Random, dot: float | None = None) -> list[tuple]:
    """Equal wedges of a half disc of radius R0 (a fanlight), around a half-disc dot of radius `dot` when given."""
    for _ in range(n):
        rng.uniform(0.8, 1.2)
    step = (a1 - a0) / n
    r_in = (dot + G / 2) if dot else 0
    out = [(parallel_sector(cx, cy, r_in, R0, a0 + i * step, a0 + (i + 1) * step, G / 2 if i else 0, G / 2 if i < n - 1 else 0), None, "counter")
           for i in range(n)]
    if dot: out.append((parallel_sector(cx, cy, 0, dot - G / 2, a0, a1, 0, 0), None, "counter"))
    return out


def petal(cx: float, cy: float, theta: float, r0: float, r1: float, half_w: float) -> str:
    """A teardrop petal along direction theta (degrees) from radius r0 to a pointed tip at r1."""
    t = math.radians(theta); u = (math.cos(t), math.sin(t)); n = (-u[1], u[0]); a = half_w / 0.75

    def P(r: float, off: float = 0.0) -> tuple[float, float]:
        return (cx + u[0] * r + n[0] * off, cy + u[1] * r + n[1] * off)
    base, tip = P(r0), P(r1); c1, c2 = P(r0 + 0.25 * (r1 - r0), a), P(r0 + 0.8 * (r1 - r0), a * 0.85)
    d1, d2 = P(r0 + 0.8 * (r1 - r0), -a * 0.85), P(r0 + 0.25 * (r1 - r0), -a)
    return (f"M{base[0]:.2f},{base[1]:.2f} C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} {tip[0]:.2f},{tip[1]:.2f} "
            f"C{d1[0]:.2f},{d1[1]:.2f} {d2[0]:.2f},{d2[1]:.2f} {base[0]:.2f},{base[1]:.2f} Z")


def flower(cx: float, cy: float, R0: float, n: int) -> list[tuple]:
    """A flower in a glass disc: n petals, each set in a wedge-shaped pane (the wedge with the petal cut out, even-odd fill)."""
    out = [(circle(cx, cy, 6.5), None, "petal")]
    step = 360 / n; r_in = 6.5 + 1.8
    for i in range(n):
        theta = i * step
        pet = petal(cx, cy, theta, r_in + 1.2, R0 - 5, 4.6)
        gap = math.degrees(1.8 / R0)
        wedge = sector(cx, cy, r_in, R0, theta - step / 2 + gap / 2, theta + step / 2 - gap / 2)
        out.append((wedge + " " + pet, None, "ground"))
        out.append((pet, None, "petal"))
    return out


# ---- letters: each returns its pieces and its width ----
def datum() -> float:
    """y of the seam shared by the M's three legs and the A's two legs (and the top of the A's crossbar): the middle of the M's legs."""
    return (60 + H) / 2 + G / 2


def letter_P(x: float, rng: random.Random) -> tuple[list, float]:
    R = 72; r = R - W; cx, cy = x + W + G, R
    parts = bar(x, x + W, 0, H, rng, 2, seam=2 * R + G / 2) + arc(cx, cy, r, R, -90, 90, 2, rng)     # the stem's upper piece ends where the bowl does
    parts += fan(cx, cy, r - G, -90, 90, 3, rng, dot=9)
    return parts, W + R + G


def letter_C(x: float, rng: random.Random) -> tuple[list, float]:
    R = 100; r = R - W; cx = x + R
    parts = arc(cx, R, r, R, 42, 318, 4, rng) + flower(cx, R, 38, 8)
    return parts, R + R * math.cos(math.radians(42))


def letter_M(x: float, rng: random.Random) -> tuple[list, float]:
    r = 22; R = r + W; c1 = x + W + r; c2 = x + 2 * W + 3 * r; mid = (c1 + c2) / 2
    a1 = arc(c1, R, r, R, 180, 360, 2, rng); a2 = arc(c2, R, r, R, 180, 360, 2, rng)
    parts = []
    for (p, _, t, m) in a1: parts.append((p, ("le", mid - G / 2) if m > 270 else None, t))     # right half of the first arch, cut short of the middle
    for (p, _, t, m) in a2: parts.append((p, ("ge", mid + G / 2) if m < 270 else None, t))     # left half of the second arch
    seam = datum()
    parts += bar(x, x + W, R + G, H, rng, 2, seam=seam) + bar(x + W + 2 * r, x + 2 * W + 2 * r, R + G, H, rng, 2, seam=seam) \
           + bar(x + 2 * W + 4 * r, x + 3 * W + 4 * r, R + G, H, rng, 2, seam=seam)
    parts += fan(c1, R, r - G, 180, 360, 3, rng) + fan(c2, R, r - G, 180, 360, 3, rng)
    return parts, 3 * W + 4 * r


def letter_A(x: float, rng: random.Random) -> tuple[list, float]:
    r = 32; R = r + W; cx = x + R
    parts = arc(cx, R, r, R, 180, 360, 3, rng)
    # three equal panes stacked between the legs (two in the counter, the crossbar below), each a gap G from the legs and from each
    # other; the legs are cut at the gap above the crossbar
    top, end = R + G, 160.0; h = (end - top - 2 * G) / 3; seam = top + 2 * h + 1.5 * G
    x0, x1 = x + W + G, x + 2 * R - W - G
    parts += bar(x, x + W, top, H, rng, 2, seam=seam) + bar(x + 2 * R - W, x + 2 * R, top, H, rng, 2, seam=seam)
    parts += bar(x0, x1, seam + G / 2, end, rng, 1)
    parts += fan(cx, R, r - G, 180, 360, 5, rng, dot=9)
    pane_top, pane_bottom = top, seam - G / 2           # the two counter panes, equal, a gap G apart
    parts += bar(x0, x1, pane_top, pane_bottom, rng, 2, seam=(pane_top + pane_bottom) / 2, tag="counter")
    return parts, 2 * R


# ---- colors ----
def seats(n: int, weights: list[int]) -> list[int]:
    """Largest-remainder allocation: the site index for each of n pieces, in proportion to the weights."""
    tot = sum(weights); got = [0] * len(weights); seq = []
    for i in range(n):
        j = max(range(len(weights)), key=lambda j: weights[j] * (i + 1) / tot - got[j]); got[j] += 1; seq.append(j)
    return seq


def shade(hexc: str, f: float) -> str:
    """Darken (f <= 1) or lighten (f > 1) a #RRGGBB color."""
    c = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    c = [max(0, min(255, round(v * f if f <= 1 else v + (255 - v) * (f - 1)))) for v in c]
    return "#%02X%02X%02X" % tuple(c)


# ---- wording ----
def _font():
    return next(f for f in TTCollection(FONT).fonts if f["name"].getDebugName(4) == "Helvetica Bold")


def fit_size(width: float) -> float:
    """Font size at which the wording's ink (first glyph's left edge to last glyph's right edge) is `width` units wide."""
    font = _font(); cmap, hmtx, glyf, upem = font.getBestCmap(), font["hmtx"], font["glyf"], font["head"].unitsPerEm
    adv = [hmtx[cmap[ord(c)]][0] for c in WORDS]
    first, last = cmap[ord(WORDS[0])], cmap[ord(WORDS[-1])]
    lsb = hmtx[first][1]; rsb = hmtx[last][0] - glyf[last].xMax
    return width / ((sum(adv) - lsb - rsb) / upem + SPACING * (len(WORDS) - 1))


def wording_path(cx: float, baseline: float, size: float, fill: str) -> str:
    """The wording as one filled path, its ink centered on cx."""
    font = _font()
    cmap, glyphs, hmtx, glyf = font.getBestCmap(), font.getGlyphSet(), font["hmtx"], font["glyf"]
    scale, spacing = size / font["head"].unitsPerEm, SPACING * size
    advances = [hmtx[cmap[ord(c)]][0] * scale for c in WORDS]
    lsb = hmtx[cmap[ord(WORDS[0])]][1] * scale; rsb = (hmtx[cmap[ord(WORDS[-1])]][0] - glyf[cmap[ord(WORDS[-1])]].xMax) * scale
    left = cx - (sum(advances) + spacing * (len(WORDS) - 1) - lsb - rsb) / 2 - lsb      # center the ink, not the advance box
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}")
    for c, adv in zip(WORDS, advances):
        if c != " ": glyphs[cmap[ord(c)]].draw(TransformPen(pen, (scale, 0, 0, -scale, left, baseline)))
        left += adv + spacing
    return f'<path d="{pen.getCommands()}" fill="{fill}"/>'


# ---- logo ----
def layout() -> tuple[list, dict, float, list[float]]:
    """All the pieces of the five letters, the color of each piece (by index), the width of the letters and each letter's left x."""
    rng = random.Random(SEED)
    x = 0; pieces = []; lefts = []
    for fn in (letter_P, letter_C, letter_C, letter_M, letter_A):
        lefts.append(x); parts, w = fn(x, rng); pieces += parts; x += w + 30
    total_w = x - 30

    body = [i for i, p in enumerate(pieces) if p[2] == "body"]; counter = [i for i, p in enumerate(pieces) if p[2] == "counter"]
    petals = [i for i, p in enumerate(pieces) if p[2] == "petal"]; ground = [i for i, p in enumerate(pieces) if p[2] == "ground"]
    weights = [s[2] for s in SITES]
    body_sites, counter_sites = seats(len(body), weights), seats(len(counter), weights[::-1])
    color = {}
    for k, i in enumerate(body): color[i] = shade(SITES[body_sites[k]][1], rng.uniform(0.88, 1.0))
    for k, i in enumerate(counter): color[i] = shade(SITES[::-1][counter_sites[k]][1], rng.uniform(1.35, 1.55))      # lighter, thinner glass
    flower_rng = random.Random(SEED + 100)
    warm = [SITES[k][1] for k in (1, 3, 0, 6)]       # bone, soft tissue, adrenal, ovary: the flowers
    cool = [SITES[k][1] for k in (4, 5, 2, 7)]       # eye, kidney, CNS, normal: the panes around them
    for k, i in enumerate(petals): color[i] = shade(warm[k % len(warm)], flower_rng.uniform(1.1, 1.3))
    for k, i in enumerate(ground): color[i] = shade(cool[(k * 3) % len(cool)], flower_rng.uniform(1.3, 1.5))
    return pieces, color, total_w, lefts


def build(text_color: str, wording: bool, background: str | None = None) -> str:
    """The logo as an SVG string, on a transparent background or a filled one, with the wording under the letters or without it."""
    pieces, color, total_w, _ = layout()

    size = fit_size(total_w); cap = CAP_HEIGHT * size
    sub_h = SUB_GAP + cap if wording else 0
    vw, vh = total_w + 2 * PAD, H + 2 * PAD + sub_h
    padx, pady = PAD + (math.ceil(vw) - vw) / 2, PAD + (math.ceil(vh) - vh) / 2      # a whole-unit canvas, content centered
    vw, vh = math.ceil(vw), math.ceil(vh)
    defs = []
    fills, cuts = [], []
    for i, (p, clip, kind, *_) in enumerate(pieces):
        attr = ""
        if clip:
            side, xc = clip; a, b = (-10, xc) if side == "le" else (xc, total_w + 10)
            defs.append(f'<clipPath id="k{i}"><rect x="{a:.2f}" y="-10" width="{b - a:.2f}" height="{H + 20}"/></clipPath>')
            attr = f' clip-path="url(#k{i})"'
        if kind == "ground": attr += ' fill-rule="evenodd"'
        fills.append(f'<path d="{p}" fill="{color[i]}"{attr}/>')
        if kind in ("petal", "ground"):
            cuts.append(f'<path d="{p}" fill="none" stroke="#000" stroke-width="1.5" stroke-linejoin="round"{attr}/>')     # the fine gaps in the flowers
    mask = (f'<mask id="cut" maskUnits="userSpaceOnUse" x="-40" y="-40" width="{total_w + 80:.0f}" height="{H + 80}">'
            f'<rect x="-40" y="-40" width="{total_w + 80:.0f}" height="{H + 80}" fill="#fff"/>' + "".join(cuts) + "</mask>")
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw * 2}" height="{vh * 2}">',
           "<defs>" + "".join(defs) + "</defs>"]
    if background: svg.append(f'<rect width="{vw}" height="{vh}" fill="{background}"/>')
    svg += [f'<g transform="translate({padx:.2f},{pady:.2f})">', mask, '<g mask="url(#cut)">' + "".join(fills) + "</g>", "</g>"]
    if wording: svg.append(wording_path(vw / 2, pady + H + sub_h, size, text_color))
    svg.append("</svg>")
    return "\n".join(svg)


# ---- icon: the flower in the first C, in bronze lead ----
ICON_SIZE, FLOWER_R = 100, 38      # canvas of the icon and radius of the flower's glass disc (units)
BRONZE = ["#E8B77F", "#B0702F", "#DDA063", "#82491B", "#D49A5A", "#9C5F26"]      # bands of polished bronze
BRONZE_SHADOW, BRONZE_LIGHT = "#3A2211", "#FFE3B8"
EVEN_ODD = ' fill-rule="evenodd"'      # a wedge pane is the wedge with its petal cut out


def flower_in_c() -> tuple[list[tuple[str, str, str]], tuple[float, float]]:
    """(path, kind, color) of each piece of the first C's flower (its center disc, then each wedge pane and petal) and its center."""
    pieces, color, _, lefts = layout()
    idx = [i for i, p in enumerate(pieces) if p[2] in ("petal", "ground")][:17]      # the disc, then 8 x (pane, petal)
    return [(pieces[i][0], pieces[i][2], color[i]) for i in idx], (lefts[1] + 100, 100)      # the C has radius 100: center = left edge + 100


def build_icon(background: str | None = None) -> str:
    """The flower as a square icon, on a filled or a transparent background: the logo's glass, in exactly its colors, held by
    bronze lead with a bronze rim."""
    flower, (cx, cy) = flower_in_c()
    half = ICON_SIZE / 2
    stops = "".join(f'<stop offset="{k / (len(BRONZE) - 1):.2f}" stop-color="{c}"/>' for k, c in enumerate(BRONZE))
    defs = [f'<linearGradient id="bronze" gradientUnits="userSpaceOnUse" x1="{cx - FLOWER_R}" y1="{cy - FLOWER_R}" '
            f'x2="{cx + FLOWER_R}" y2="{cy + FLOWER_R}" spreadMethod="reflect">{stops}</linearGradient>',
            # the lead is one shape (every piece's outline plus the rim), lit from the top left as a whole and casting one soft shadow
            '<filter id="came" x="-5%" y="-5%" width="110%" height="110%" color-interpolation-filters="sRGB">'
            '<feGaussianBlur in="SourceAlpha" stdDeviation="0.5" result="blur"/>'
            f'<feSpecularLighting in="blur" surfaceScale="1.6" specularConstant="0.9" specularExponent="16" lighting-color="{BRONZE_LIGHT}" result="spec">'
            '<feDistantLight azimuth="225" elevation="55"/></feSpecularLighting>'
            '<feComposite in="spec" in2="SourceAlpha" operator="in" result="spec2"/>'
            '<feComposite in="SourceGraphic" in2="spec2" operator="arithmetic" k1="0" k2="1" k3="0.7" k4="0" result="lit"/>'
            f'<feDropShadow in="lit" dx="0.7" dy="0.7" stdDeviation="0.5" flood-color="{BRONZE_SHADOW}" flood-opacity="0.55"/></filter>']
    glass = [f'<path d="{p}" fill="{c}"{EVEN_ODD if kind == "ground" else ""}/>' for p, kind, c in flower]      # exactly the C's colors
    lead = [f'<path d="{p}" fill="none" stroke="url(#bronze)" stroke-width="2.2" stroke-linejoin="round"/>' for p, _, _ in flower]
    rim = f'<circle cx="{cx}" cy="{cy}" r="{FLOWER_R + 0.5}" fill="none" stroke="url(#bronze)" stroke-width="3.2"/>'
    plate = f'<rect width="{ICON_SIZE}" height="{ICON_SIZE}" fill="{background}"/>\n' if background else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ICON_SIZE} {ICON_SIZE}" width="{ICON_SIZE * 4}" height="{ICON_SIZE * 4}">\n'
            f'<defs>{"".join(defs)}</defs>\n{plate}'
            f'<g transform="translate({half},{half}) translate({-cx},{-cy})">' + "".join(glass) + '<g filter="url(#came)">' + "".join(lead) + rim
            + "</g></g>\n</svg>")


def render_png(svg_path: str, png_path: str) -> None:
    """Screenshot the SVG with headless Chrome at 2x, in a window of exactly the SVG's size, on a transparent background."""
    w, h = (int(v) for v in re.search(r'width="(\d+)" height="(\d+)"', open(svg_path).read(400)).groups())
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                    f"--screenshot={png_path}", "--force-device-scale-factor=2", f"--window-size={w},{h}", f"file://{os.path.abspath(svg_path)}"],
                   check=True, capture_output=True)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    files = {}
    for mode in ("light", "dark"):
        files[f"pccma_logo_{mode}"] = build(TEXT_COLORS[mode], True, BACKGROUNDS[mode])
        files[f"pccma_logo_transparent_on_{mode}"] = build(TEXT_COLORS[mode], True)
        files[f"pccma_logo_letters_{mode}"] = build("", False, BACKGROUNDS[mode])
    files["pccma_logo_letters_transparent"] = build("", False)
    for mode, background in BACKGROUNDS.items():
        files[f"pccma_icon_{mode}"] = build_icon(background)
    for name, svg in files.items():
        open(f"{out}/{name}.svg", "w").write(svg)
        render_png(f"{out}/{name}.svg", f"{out}/{name}.png")
