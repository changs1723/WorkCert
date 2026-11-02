"""Effective-area Visvalingam--Whyatt removal for fixed-size vertex tables."""
import heapq
import numpy as np


def _vw_indices(x, force, budget, protected):
    """Protect anchors and remove the smallest current triangle, ties by index."""
    n = len(x)
    xn = (x - x[0]) / (x[-1] - x[0])
    with np.errstate(over="ignore", invalid="ignore"):
        span = float(np.ptp(force))
    if np.isfinite(span):
        yn = (force - np.min(force)) / (span or 1.0)
    else:
        scaled = force / np.max(np.abs(force))
        yn = (scaled - np.min(scaled)) / np.ptp(scaled)
    previous, following = np.arange(n) - 1, np.arange(n) + 1
    alive = np.ones(n, dtype=bool)
    generation = np.zeros(n, dtype=np.int64)
    heap = []

    def add(i):
        if i in protected or not alive[i]:
            return
        a, b = int(previous[i]), int(following[i])
        area = .5 * abs((xn[i] - xn[a]) * (yn[b] - yn[a]) -
                        (xn[b] - xn[a]) * (yn[i] - yn[a]))
        generation[i] += 1
        heapq.heappush(heap, (float(area), i, int(generation[i])))

    for i in range(1, n - 1):
        add(i)
    count = n
    while count > budget:
        _, i, stamp = heapq.heappop(heap)
        if not alive[i] or stamp != generation[i]:
            continue
        alive[i] = False
        count -= 1
        a, b = int(previous[i]), int(following[i])
        following[a], previous[b] = b, a
        add(a)
        add(b)
    return np.flatnonzero(alive)
