"""Two-phase (Kociemba) solver targeting solutions of at most 20 face turns.

Phase 1 drives the cube into the subgroup G1 = <U, D, R2, L2, F2, B2>, where every corner
is untwisted, every edge unflipped, and the four middle-slice edges are back in the middle
slice. Phase 2 solves it inside G1. Both phases are IDA* searches guided by pruning tables
built by breadth-first search over coordinate spaces.
"""

import os
import time
from itertools import combinations
from math import factorial

import numpy as np

import cube as C
from cubie import CubieCube, MOVE_CUBES, from_facelets, inverse as cubie_inverse

TABLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tables.npz")

# ---------------------------------------------------------------- move sets
P1_MOVES = tuple(f + s for f in "URFDLB" for s in ("", "2", "'"))
P1_FACE = tuple("URFDLB".index(m[0]) for m in P1_MOVES)
P2_MOVES = ("U", "U2", "U'", "D", "D2", "D'", "R2", "L2", "F2", "B2")
P2_FACE = tuple("URFDLB".index(m[0]) for m in P2_MOVES)
P2_IN_P1 = tuple(P1_MOVES.index(m) for m in P2_MOVES)
OPPOSITE = {0: 3, 3: 0, 1: 4, 4: 1, 2: 5, 5: 2}

N_TWIST, N_FLIP, N_SLICE = 2187, 2048, 495
N_CPERM, N_EPERM, N_SPERM = 40320, 40320, 24

SLICE_SETS = list(combinations(range(12), 4))
SLICE_INDEX = {s: i for i, s in enumerate(SLICE_SETS)}
SLICE_SOLVED = SLICE_INDEX[(8, 9, 10, 11)]


# ---------------------------------------------------------------- coordinates
def perm_rank(p):
    n, r = len(p), 0
    for i in range(n):
        r = r * (n - i) + sum(1 for j in range(i + 1, n) if p[j] < p[i])
    return r


def perm_unrank(r, n):
    avail, p = list(range(n)), []
    for i in range(n):
        f = factorial(n - 1 - i)
        p.append(avail.pop(r // f))
        r %= f
    return p


def get_twist(cc):
    t = 0
    for i in range(7):
        t = t * 3 + cc.co[i]
    return t


def get_flip(cc):
    f = 0
    for i in range(11):
        f = f * 2 + cc.eo[i]
    return f


def get_slice(cc):
    return SLICE_INDEX[tuple(i for i in range(12) if cc.ep[i] >= 8)]


def get_cperm(cc):
    return perm_rank(cc.cp)


def get_eperm(cc):
    return perm_rank(cc.ep[:8])


def get_sperm(cc):
    return perm_rank([e - 8 for e in cc.ep[8:]])


def _cube_with_twist(t):
    co, rest = [], t
    for _ in range(7):
        co.append(rest % 3)
        rest //= 3
    co.reverse()
    co.append((-sum(co)) % 3)
    return CubieCube(co=co)


def _cube_with_flip(f):
    eo, rest = [], f
    for _ in range(11):
        eo.append(rest % 2)
        rest //= 2
    eo.reverse()
    eo.append(sum(eo) % 2)
    return CubieCube(eo=eo)


def _cube_with_slice(s):
    positions = SLICE_SETS[s]
    ep, others, k = [0] * 12, [i for i in range(8)], 0
    for i in range(12):
        if i in positions:
            ep[i] = 8 + k
            k += 1
        else:
            ep[i] = others.pop(0)
    return CubieCube(ep=ep)


def _cube_with_cperm(p):
    return CubieCube(cp=perm_unrank(p, 8))


def _cube_with_eperm(p):
    return CubieCube(ep=perm_unrank(p, 8) + [8, 9, 10, 11])


def _cube_with_sperm(p):
    return CubieCube(ep=list(range(8)) + [8 + x for x in perm_unrank(p, 4)])


# ---------------------------------------------------------------- tables
def _build_move_table(size, builder, getter, moves):
    table = np.zeros((size, len(moves)), dtype=np.uint16)
    for i in range(size):
        cc = builder(i)
        for j, m in enumerate(moves):
            table[i, j] = getter(cc.apply(MOVE_CUBES[m]))
    return table


def _build_pruning(move_a, move_b, start_a, start_b, n_b):
    """BFS over the product of two coordinates (vectorised)."""
    size = move_a.shape[0] * n_b
    dist = np.full(size, 255, dtype=np.uint8)
    start = start_a * n_b + start_b
    dist[start] = 0
    frontier = np.array([start], dtype=np.int64)
    depth = 0
    while frontier.size:
        a, b = frontier // n_b, frontier % n_b
        nxt = []
        for j in range(move_a.shape[1]):
            idx = move_a[a, j].astype(np.int64) * n_b + move_b[b, j]
            nxt.append(idx[dist[idx] == 255])
        if not nxt:
            break
        cand = np.unique(np.concatenate(nxt))
        cand = cand[dist[cand] == 255]
        if cand.size == 0:
            break
        depth += 1
        dist[cand] = depth
        frontier = cand
    return dist


def build_tables(verbose=True):
    if os.path.exists(TABLE_FILE):
        return dict(np.load(TABLE_FILE))

    def log(msg):
        if verbose:
            print(msg, flush=True)

    t = {}
    log("building phase-1 move tables ...")
    t["twist"] = _build_move_table(N_TWIST, _cube_with_twist, get_twist, P1_MOVES)
    t["flip"] = _build_move_table(N_FLIP, _cube_with_flip, get_flip, P1_MOVES)
    t["slice"] = _build_move_table(N_SLICE, _cube_with_slice, get_slice, P1_MOVES)

    log("building phase-2 move tables ...")
    t["cperm"] = _build_move_table(N_CPERM, _cube_with_cperm, get_cperm, P2_MOVES)
    t["eperm"] = _build_move_table(N_EPERM, _cube_with_eperm, get_eperm, P2_MOVES)
    t["sperm"] = _build_move_table(N_SPERM, _cube_with_sperm, get_sperm, P2_MOVES)

    log("building pruning tables ...")
    t["pt_flip_slice"] = _build_pruning(t["flip"], t["slice"], 0, SLICE_SOLVED, N_SLICE)
    t["pt_twist_slice"] = _build_pruning(t["twist"], t["slice"], 0, SLICE_SOLVED, N_SLICE)
    t["pt_cperm_sperm"] = _build_pruning(t["cperm"], t["sperm"], 0, 0, N_SPERM)
    t["pt_eperm_sperm"] = _build_pruning(t["eperm"], t["sperm"], 0, 0, N_SPERM)

    np.savez_compressed(TABLE_FILE, **t)
    log(f"tables cached in {TABLE_FILE}")
    return t


_T = None
_MV = {}
_PT = {}


def _load():
    global _T
    if _T is not None:
        return
    _T = build_tables()
    for k in ("twist", "flip", "slice", "cperm", "eperm", "sperm"):
        _MV[k] = [list(map(int, row)) for row in _T[k]]
    for k in ("pt_flip_slice", "pt_twist_slice", "pt_cperm_sperm", "pt_eperm_sperm"):
        _PT[k] = bytes(_T[k])


# ---------------------------------------------------------------- search
def _phase1_solutions(twist, flip, slc, limit):
    """Yield phase-1 move-index sequences of exactly `limit` moves."""
    twist_mv, flip_mv, slice_mv = _MV["twist"], _MV["flip"], _MV["slice"]
    pt_fs, pt_ts = _PT["pt_flip_slice"], _PT["pt_twist_slice"]
    path = []

    def rec(twist, flip, slc, depth, last_face):
        if depth == 0:
            if twist == 0 and flip == 0 and slc == SLICE_SOLVED:
                # a phase-1 solution ending in a G1 move is redundant: the prefix is
                # already a phase-1 solution and phase 2 can absorb that last move
                if not path or path[-1] not in P2_IN_P1:
                    yield tuple(path)
            return
        if max(pt_fs[flip * N_SLICE + slc], pt_ts[twist * N_SLICE + slc]) > depth:
            return
        for j in range(18):
            face = P1_FACE[j]
            if face == last_face or (OPPOSITE[face] == last_face and face < last_face):
                continue
            path.append(j)
            yield from rec(twist_mv[twist][j], flip_mv[flip][j], slice_mv[slc][j],
                           depth - 1, face)
            path.pop()

    yield from rec(twist, flip, slc, limit, -1)


def _phase2_solve(cperm, eperm, sperm, limit, last_face):
    cperm_mv, eperm_mv, sperm_mv = _MV["cperm"], _MV["eperm"], _MV["sperm"]
    pt_cs, pt_es = _PT["pt_cperm_sperm"], _PT["pt_eperm_sperm"]
    path = []

    def rec(cperm, eperm, sperm, depth, last_face):
        if cperm == 0 and eperm == 0 and sperm == 0:
            return list(path)
        if depth == 0:
            return None
        if max(pt_cs[cperm * N_SPERM + sperm], pt_es[eperm * N_SPERM + sperm]) > depth:
            return None
        for j in range(10):
            face = P2_FACE[j]
            if face == last_face or (OPPOSITE[face] == last_face and face < last_face):
                continue
            path.append(j)
            found = rec(cperm_mv[cperm][j], eperm_mv[eperm][j], sperm_mv[sperm][j],
                        depth - 1, face)
            path.pop()
            if found is not None:
                return found
        return None

    for depth in range(limit + 1):
        found = rec(cperm, eperm, sperm, depth, last_face)
        if found is not None:
            return found
    return None


# phase 1 aims at G1, which is defined relative to the U/D axis, so a cube that resists a
# short two-phase solution in one frame usually yields in another. Searching all three axis
# frames and the inverse cube (six searches, interleaved by depth) is the standard fix.
ORIENTATIONS = ((None, 0), (2, 1), (0, 1))


def _frames(facelets):
    frames = []
    for axis, q in ORIENTATIONS:
        state = facelets if axis is None else C.rotate_cube(facelets, axis, q)
        back = None if axis is None else {v: k for k, v in C.face_rename(axis, q).items()}
        cc = from_facelets(state)
        for inverted in (False, True):
            frame_cc = cubie_inverse(cc) if inverted else cc
            frames.append((frame_cc, back, inverted,
                           get_twist(frame_cc), get_flip(frame_cc), get_slice(frame_cc)))
    return frames


def _translate(moves, back, inverted):
    out = [(back[m[0]] if back else m[0]) + m[1:] for m in moves]
    return C.invert(out) if inverted else out


def solve(facelets, max_length=20, max_phase1_depth=13, improve_seconds=0.0):
    """Return a solution of at most `max_length` face turns, or None.

    With improve_seconds > 0 the search keeps going after the first hit, returning the
    shortest solution it can find within that extra time budget.
    """
    _load()
    if from_facelets(facelets).is_solved():
        return []

    frames = _frames(facelets)
    best, deadline = None, None

    for depth in range(max_phase1_depth + 1):
        if depth > max_length or (best is not None and depth >= len(best)):
            break
        for cc, back, inverted, twist, flip, slc in frames:
            for p1 in _phase1_solutions(twist, flip, slc, depth):
                budget = (len(best) - 1 if best is not None else max_length) - depth
                if budget < 0:
                    continue
                mid = cc
                for j in p1:
                    mid = mid.apply(MOVE_CUBES[P1_MOVES[j]])
                last_face = P1_FACE[p1[-1]] if p1 else -1
                p2 = _phase2_solve(get_cperm(mid), get_eperm(mid), get_sperm(mid),
                                   budget, last_face)
                if p2 is not None:
                    best = _translate([P1_MOVES[j] for j in p1]
                                      + [P2_MOVES[j] for j in p2], back, inverted)
                    if improve_seconds <= 0:
                        return best
                    if deadline is None:
                        deadline = time.time() + improve_seconds
                if deadline is not None and time.time() > deadline:
                    return best
    return best


def verify(facelets, solution):
    return C.apply_moves(facelets, solution) == C.SOLVED
