"""Run the solver over many random scrambles and report the solution-length distribution.

Usage:
    python demo.py [n_scrambles] [improve_seconds]
"""

import sys
import time
from collections import Counter

import cube as C
import solver


def main(n=100, improve=1.0):
    solver._load()  # build/load tables once, outside the timing
    lengths, times, failures = Counter(), [], []

    for seed in range(n):
        moves = C.scramble(25, seed=seed)
        state = C.apply_moves(C.SOLVED, moves)

        t0 = time.time()
        solution = solver.solve(state, max_length=20, improve_seconds=improve)
        elapsed = time.time() - t0

        if solution is None or not solver.verify(state, solution):
            failures.append((seed, solution))
            print(f"  [{seed:3d}] FAILED", flush=True)
            continue

        lengths[len(solution)] += 1
        times.append(elapsed)
        print(f"  [{seed:3d}] {len(solution):2d} moves  {elapsed:6.2f}s   "
              f"{' '.join(solution)}", flush=True)

    solved = sum(lengths.values())
    print(f"\nscrambles solved and verified: {solved}/{n}")
    print(f"longest solution found: {max(lengths)} moves   (bound asked for: 20)")
    print(f"mean solution length: {sum(k * v for k, v in lengths.items()) / solved:.2f}")
    print(f"median solve time: {sorted(times)[len(times) // 2]:.2f}s   max: {max(times):.2f}s")
    print("\nlength distribution:")
    for k in sorted(lengths):
        print(f"  {k:2d} moves: {'#' * lengths[k]} ({lengths[k]})")
    if failures:
        print(f"\nFAILURES: {failures}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    improve = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    main(n, improve)
