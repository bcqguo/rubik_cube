"""Draw the cube as 9 intersecting circles with live node colors.

Layout comes from the geometry itself, not from hand-placed art. Every node (sticker) is
put on the unit sphere so that it lies on the two layer-planes it belongs to; each of the
9 layers then cuts the sphere in a circle. Stereographic projection from the (1,1,1) axis
maps those sphere circles to true circles in the plane and gives the picture its 3-fold
symmetry, so the 54 nodes land exactly on the circle intersections.

Usage:
    python renderer.py                    # solved cube
    python renderer.py "R U F"            # after a move sequence
    python renderer.py "R U F" --highlight R
"""

import sys

import numpy as np

import cube as C

OFFSET = 0.3  # how far the three layer-planes of each axis sit from the origin
POLE = np.array([1.0, 1.0, 1.0]) / np.sqrt(3)
E1 = np.array([1.0, -1.0, 0.0]) / np.sqrt(2)
E2 = np.cross(POLE, E1)

COLORS = {"U": "#f8f8f8", "D": "#ffd500", "F": "#009b48", "B": "#0046ad",
          "R": "#b71234", "L": "#ff5800"}

CIRCLES = [(axis, layer) for axis in range(3) for layer in (-1, 0, 1)]
CIRCLE_NAME = {(0, 1): "R", (0, 0): "M", (0, -1): "L",
               (1, 1): "U", (1, 0): "E", (1, -1): "D",
               (2, 1): "F", (2, 0): "S", (2, -1): "B"}


def sphere_point(pos, normal):
    """Place a node on the unit sphere, on both of the layer-planes it belongs to."""
    n = next(i for i in range(3) if normal[i] != 0)
    p = np.zeros(3)
    for axis in range(3):
        if axis != n:
            p[axis] = OFFSET * pos[axis]
    p[n] = np.sign(normal[n]) * np.sqrt(max(1.0 - p @ p, 0.0))
    return p


def project(p):
    """Stereographic projection from POLE onto the plane through the origin."""
    q = (p - (p @ POLE) * POLE) / (1.0 - p @ POLE)
    return np.array([q @ E1, q @ E2])


NODE_XY = np.array([project(sphere_point(pos, nrm)) for pos, nrm in C.STICKERS])
# stereographic projection stretches near the pole and compresses opposite it; sizing nodes
# by a damped conformal factor keeps the crowded middle legible without ballooning the rim
NODE_SCALE = np.array([1.0 / (1.0 - sphere_point(pos, nrm) @ POLE)
                       for pos, nrm in C.STICKERS]) ** 0.3


def _fit_circle(pts):
    """Least-squares circle through projected points (their image is an exact circle)."""
    a = np.c_[2 * pts, np.ones(len(pts))]
    b = (pts ** 2).sum(1)
    cx, cy, c0 = np.linalg.lstsq(a, b, rcond=None)[0]
    return np.array([cx, cy]), np.sqrt(c0 + cx ** 2 + cy ** 2)


def circle_geometry(axis, layer, samples=512):
    c = OFFSET * layer
    r = np.sqrt(1.0 - c * c)
    th = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    pts = np.zeros((samples, 3))
    pts[:, axis] = c
    pts[:, (axis + 1) % 3] = r * np.cos(th)
    pts[:, (axis + 2) % 3] = r * np.sin(th)
    return _fit_circle(np.array([project(p) for p in pts]))


CIRCLE_GEOM = {cl: circle_geometry(*cl) for cl in CIRCLES}


def circle_nodes(axis, layer):
    return [i for i, (pos, nrm) in enumerate(C.STICKERS)
            if pos[axis] == layer and nrm[axis] == 0]


def draw(state=C.SOLVED, ax=None, highlight=None, title=None):
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 8))

    for (axis, layer), (center, radius) in CIRCLE_GEOM.items():
        hot = highlight is not None and CIRCLE_NAME[(axis, layer)] == highlight
        ax.add_patch(plt.Circle(center, radius, fill=False,
                                color="#d4531f" if hot else "#b0a999",
                                lw=2.2 if hot else 1.0, zorder=2 if hot else 1))

    for i, (x, y) in enumerate(NODE_XY):
        ax.add_patch(plt.Circle((x, y), 0.052 * NODE_SCALE[i], facecolor=COLORS[state[i]],
                                edgecolor="#33312c", lw=0.9, zorder=3))

    span = np.abs(NODE_XY).max() * 1.12  # frame the nodes; the widest circles run off-canvas
    ax.set_xlim(-span, span)
    ax.set_ylim(-span, span)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("#faf7f0")
    if title:
        ax.set_title(title, fontsize=13)
    return ax


def selftest():
    """The layout must reproduce the cube's actual structure."""
    # every node sits on exactly the two circles it belongs to
    worst = 0.0
    for cl in CIRCLES:
        center, radius = CIRCLE_GEOM[cl]
        for i in circle_nodes(*cl):
            worst = max(worst, abs(np.linalg.norm(NODE_XY[i] - center) - radius))
    print(f"max node-to-circle distance error: {worst:.2e}")

    # a quarter turn must shift that circle's nodes by 3 places in angular order
    ok = True
    for cl in CIRCLES:
        axis, layer = cl
        center, _ = CIRCLE_GEOM[cl]
        nodes = circle_nodes(axis, layer)
        ang = {i: np.arctan2(*(NODE_XY[i] - center)[::-1]) for i in nodes}
        ring = sorted(nodes, key=lambda i: ang[i])
        perm = C.MOVES[CIRCLE_NAME[cl]]
        dest = {perm[d]: d for d in range(54)}  # source -> destination
        shifts = {(ring.index(dest[i]) - ring.index(i)) % 12 for i in ring}
        ok &= len(shifts) == 1 and shifts.pop() in (3, 9)
    print("quarter turn = 3-step rotation along every circle:", ok)
    return worst < 1e-9 and ok


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seq = args[0] if args else ""
    highlight = None
    if "--highlight" in sys.argv:
        highlight = sys.argv[sys.argv.index("--highlight") + 1]

    state = C.apply_moves(C.SOLVED, seq) if seq else C.SOLVED
    draw(state, highlight=highlight, title=f"after: {seq}" if seq else "solved")
    out = "cube_circles.png"
    plt.savefig(out, dpi=140, bbox_inches="tight", facecolor="#faf7f0")
    print("wrote", out)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
