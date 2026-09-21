"""Cubie-level view of the cube, derived from the geometric node model in cube.py.

A cube state is (cp, co, ep, eo): which corner/edge piece sits in each slot, and how it
is twisted/flipped. This is the representation the two-phase solver needs; it is built
from the same geometry as the facelet model, so there is only one source of truth.
"""

from cube import FACE_BASIS, STICKER_INDEX, SOLVED, MOVES, apply_move

CORNER_NAMES = ("URF", "UFL", "ULB", "UBR", "DFR", "DLF", "DBL", "DRB")
EDGE_NAMES = ("UR", "UF", "UL", "UB", "DR", "DF", "DL", "DB", "FR", "FL", "BL", "BR")


def _slot_facelets(name):
    """Facelet indices of a slot, in the slot's canonical order (U/D first, else F/B)."""
    pos = tuple(sum(FACE_BASIS[f][0][i] for f in name) for i in range(3))
    return tuple(STICKER_INDEX[(pos, FACE_BASIS[f][0])] for f in name)


CORNER_FACELETS = tuple(_slot_facelets(n) for n in CORNER_NAMES)
EDGE_FACELETS = tuple(_slot_facelets(n) for n in EDGE_NAMES)
CORNER_BY_COLORS = {frozenset(n): i for i, n in enumerate(CORNER_NAMES)}
EDGE_BY_COLORS = {frozenset(n): i for i, n in enumerate(EDGE_NAMES)}


class CubieCube:
    __slots__ = ("cp", "co", "ep", "eo")

    def __init__(self, cp=None, co=None, ep=None, eo=None):
        self.cp = list(cp) if cp else list(range(8))
        self.co = list(co) if co else [0] * 8
        self.ep = list(ep) if ep else list(range(12))
        self.eo = list(eo) if eo else [0] * 12

    def copy(self):
        return CubieCube(self.cp, self.co, self.ep, self.eo)

    def is_solved(self):
        return (self.cp == list(range(8)) and self.co == [0] * 8
                and self.ep == list(range(12)) and self.eo == [0] * 12)

    def apply(self, m):
        """Return the state after applying move-cube `m` to this state."""
        cp = [self.cp[m.cp[i]] for i in range(8)]
        co = [(self.co[m.cp[i]] + m.co[i]) % 3 for i in range(8)]
        ep = [self.ep[m.ep[i]] for i in range(12)]
        eo = [(self.eo[m.ep[i]] + m.eo[i]) % 2 for i in range(12)]
        return CubieCube(cp, co, ep, eo)

    def __repr__(self):
        return f"CubieCube(cp={self.cp}, co={self.co}, ep={self.ep}, eo={self.eo})"


def from_facelets(state):
    cp, co, ep, eo = [0] * 8, [0] * 8, [0] * 12, [0] * 12

    for slot, facelets in enumerate(CORNER_FACELETS):
        colors = [state[f] for f in facelets]
        ori = next(i for i, c in enumerate(colors) if c in "UD")
        cp[slot] = CORNER_BY_COLORS[frozenset(colors)]
        co[slot] = ori

    for slot, facelets in enumerate(EDGE_FACELETS):
        colors = [state[f] for f in facelets]
        piece = EDGE_BY_COLORS[frozenset(colors)]
        ep[slot] = piece
        # oriented when the piece's own first color sits on the slot's first facelet
        eo[slot] = 0 if colors[0] == EDGE_NAMES[piece][0] else 1

    return CubieCube(cp, co, ep, eo)


def to_facelets(cc):
    state = [None] * 54
    for slot, facelets in enumerate(CORNER_FACELETS):
        name = CORNER_NAMES[cc.cp[slot]]
        for i, f in enumerate(facelets):
            state[f] = name[(i - cc.co[slot]) % 3]
    for slot, facelets in enumerate(EDGE_FACELETS):
        name = EDGE_NAMES[cc.ep[slot]]
        for i, f in enumerate(facelets):
            state[f] = name[(i + cc.eo[slot]) % 2]
    for face, basis in FACE_BASIS.items():  # centers are fixed
        state[STICKER_INDEX[(basis[0], basis[0])]] = face
    return "".join(state)


def inverse(cc):
    inv = CubieCube()
    for i in range(8):
        inv.cp[cc.cp[i]] = i
        inv.co[cc.cp[i]] = (-cc.co[i]) % 3
    for i in range(12):
        inv.ep[cc.ep[i]] = i
        inv.eo[cc.ep[i]] = cc.eo[i]
    return inv


MOVE_CUBES = {m: from_facelets(apply_move(SOLVED, m)) for m in MOVES}


def from_moves(moves):
    if isinstance(moves, str):
        moves = moves.split()
    cc = CubieCube()
    for m in moves:
        cc = cc.apply(MOVE_CUBES[m])
    return cc
