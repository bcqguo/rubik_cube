"""3x3x3 cube modeled as 3 axes x 3 circles, each circle cycling 4 node-groups of 3 nodes.

Geometry is the single source of truth: a sticker ("node") is a (cubie position, outward
normal) pair with coordinates in {-1,0,1}^3. A move rotates every cubie sitting in one
layer, carrying its stickers with it. Everything else (facelet strings, cubie-level
permutations, move tables) is derived from that.
"""

AXIS_X, AXIS_Y, AXIS_Z = 0, 1, 2

FACE_ORDER = ("U", "R", "F", "D", "L", "B")

# face -> (outward normal, row direction, column direction) in the standard viewing
# orientation for that face; facelet (r, c) of a face sits at normal + row*(r-1) + col*(c-1)
FACE_BASIS = {
    "U": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "R": ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
    "F": ((0, 0, 1), (0, -1, 0), (1, 0, 0)),
    "D": ((0, -1, 0), (0, 0, -1), (1, 0, 0)),
    "L": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
    "B": ((0, 0, -1), (0, -1, 0), (-1, 0, 0)),
}


def _add(*vecs):
    return tuple(sum(c) for c in zip(*vecs))


def _scale(v, k):
    return tuple(k * c for c in v)


def _build_stickers():
    """54 nodes in standard URFDLB facelet order."""
    stickers = []
    for face in FACE_ORDER:
        normal, row, col = FACE_BASIS[face]
        for r in range(3):
            for c in range(3):
                pos = _add(normal, _scale(row, r - 1), _scale(col, c - 1))
                stickers.append((pos, normal))
    return tuple(stickers)


STICKERS = _build_stickers()
STICKER_INDEX = {s: i for i, s in enumerate(STICKERS)}
NORMAL_FACE = {FACE_BASIS[f][0]: f for f in FACE_ORDER}

SOLVED = "".join(f * 9 for f in FACE_ORDER)


def rotate(vec, axis, quarters):
    """Rotate a vector by `quarters` * 90 deg about +axis (right-hand rule)."""
    x, y, z = vec
    for _ in range(quarters % 4):
        if axis == AXIS_X:
            x, y, z = x, -z, y
        elif axis == AXIS_Y:
            x, y, z = z, y, -x
        else:
            x, y, z = -y, x, z
    return (x, y, z)


def layer_permutation(axis, layer, quarters):
    """Permutation of the 54 nodes when one circle (axis, layer) turns."""
    perm = list(range(54))
    for i, (pos, normal) in enumerate(STICKERS):
        if pos[axis] != layer:
            continue
        dest = STICKER_INDEX[(rotate(pos, axis, quarters), rotate(normal, axis, quarters))]
        perm[dest] = i
    return tuple(perm)


# --- the 9 circles: 3 axes x 3 layers, named by the face turn that drives them ----------
# quarters is negated for the positive-normal faces because a clockwise turn seen from
# outside is a negative (clockwise) rotation about the outward-pointing axis.
FACE_LAYER = {
    "U": (AXIS_Y, 1, -1),
    "D": (AXIS_Y, -1, 1),
    "R": (AXIS_X, 1, -1),
    "L": (AXIS_X, -1, 1),
    "F": (AXIS_Z, 1, -1),
    "B": (AXIS_Z, -1, 1),
    "M": (AXIS_X, 0, 1),   # middle circles, follow L / D / F respectively
    "E": (AXIS_Y, 0, 1),
    "S": (AXIS_Z, 0, -1),
}

MOVES = {}
for _name, (_axis, _layer, _sign) in FACE_LAYER.items():
    for _suffix, _turns in (("", 1), ("2", 2), ("'", 3)):
        MOVES[_name + _suffix] = layer_permutation(_axis, _layer, _sign * _turns)

FACE_MOVES = tuple(f + s for f in "URFDLB" for s in ("", "2", "'"))


def apply_move(state, move):
    perm = MOVES[move]
    return "".join(state[perm[i]] for i in range(54))


def apply_moves(state, moves):
    if isinstance(moves, str):
        moves = moves.split()
    for m in moves:
        state = apply_move(state, m)
    return state


def invert(moves):
    if isinstance(moves, str):
        moves = moves.split()
    flip = {"": "'", "'": "", "2": "2"}
    return [m[0] + flip[m[1:]] for m in reversed(moves)]


def node_groups(face):
    """The 4 node-groups of 3 that this circle cycles (the 'belt' around the layer).

    Returns a list of 4 lists of facelet indices; a quarter turn maps group i -> group i+1.
    """
    axis, layer, sign = FACE_LAYER[face]
    perm = MOVES[face]
    # belt nodes are the moved nodes whose normal is perpendicular to the turning axis
    belt = [i for i, (pos, normal) in enumerate(STICKERS)
            if pos[axis] == layer and normal[axis] == 0]
    forward = {perm[d]: d for d in range(54)}  # source -> destination
    groups, seen = [], set()
    for start in belt:
        if start in seen:
            continue
        group = [i for i in belt if STICKERS[i][1] == STICKERS[start][1]]
        seen.update(group)
        groups.append(sorted(group))
    # order groups so that each maps onto the next
    ordered = [groups[0]]
    while len(ordered) < 4:
        nxt = sorted(forward[i] for i in ordered[-1])
        ordered.append(next(g for g in groups if sorted(g) == nxt))
    return ordered


def face_rename(axis, quarters):
    """Where each face ends up when the whole cube is turned."""
    return {f: NORMAL_FACE[rotate(FACE_BASIS[f][0], axis, quarters)] for f in FACE_ORDER}


def rotate_cube(state, axis, quarters):
    """Turn the whole cube, relabelling colours so a solved cube stays solved."""
    ren = face_rename(axis, quarters)
    perm = list(range(54))
    for i, (pos, normal) in enumerate(STICKERS):
        dest = STICKER_INDEX[(rotate(pos, axis, quarters), rotate(normal, axis, quarters))]
        perm[dest] = i
    return "".join(ren[state[perm[i]]] for i in range(54))


def scramble(n=25, seed=None):
    import random

    rng = random.Random(seed)
    moves, last = [], ""
    while len(moves) < n:
        m = rng.choice(FACE_MOVES)
        if m[0] == last:
            continue
        last = m[0]
        moves.append(m)
    return moves


def show(state):
    """ASCII net of the cube."""
    def row(face, r):
        i = FACE_ORDER.index(face) * 9 + r * 3
        return " ".join(state[i:i + 3])

    lines = [" " * 6 + row("U", r) for r in range(3)]
    for r in range(3):
        lines.append("  ".join(row(f, r) for f in ("L", "F", "R", "B")))
    lines += [" " * 6 + row("D", r) for r in range(3)]
    return "\n".join(lines)
