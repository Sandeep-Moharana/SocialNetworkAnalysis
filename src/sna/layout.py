"""
2-D positions for drawing the graph in the dashboard (ui/index.html).

Force-directed layout (Fruchterman-Reingold), the classic way to draw networks:
    - every pair of users PUSHES apart      (like magnets of the same pole)
    - every friendship PULLS its two ends together (like a spring)
After enough rounds the forces balance: friends sit close, groups of friends
form visible clusters, and hubs end up in the middle of their group.

Runs on the DRIVER with numpy (no Spark): the graph has only a few thousand
vertices, and the browser then just draws the finished positions.
Cost: n^2 pushes per round, so this is fine up to ~10,000 vertices. A much larger
graph (Phase 3) would need a sample or an approximation (Barnes-Hut).
"""
import numpy as np

GOLDEN_ANGLE = np.pi * (3 - np.sqrt(5))


def initial_positions(groups: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Start each community around its own spot, largest communities first on a
    sunflower spiral. The layout then settles faster and groups don't tangle."""
    n = len(groups)
    labels, sizes = np.unique(groups, return_counts=True)
    order = np.argsort(-sizes)
    pos = np.zeros((n, 2))
    used = 0.0
    for rank, gi in enumerate(order):
        members = groups == labels[gi]
        # Spiral: each group gets area proportional to its size.
        r = np.sqrt(used + sizes[gi] / 2)
        center = r * np.array([np.cos(rank * GOLDEN_ANGLE), np.sin(rank * GOLDEN_ANGLE)])
        pos[members] = center + rng.normal(scale=0.5 * np.sqrt(sizes[gi]), size=(members.sum(), 2))
        used += sizes[gi]
    return pos


def force_layout(n: int, edges: np.ndarray, groups: np.ndarray = None,
                 iterations: int = 120, seed: int = 42, chunk: int = 512) -> np.ndarray:
    """Positions (n x 2) for vertices 0..n-1.

    edges   array of shape (m, 2) with vertex INDICES, each connection once
    groups  optional community per vertex, used only for the starting positions
    seed    fixed, so the picture is the same on every run
    """
    rng = np.random.default_rng(seed)
    if n == 0:
        return np.zeros((0, 2))
    groups = np.zeros(n, dtype=np.int64) if groups is None else np.asarray(groups)
    pos = initial_positions(groups, rng).astype(np.float32)
    u, v = edges[:, 0], edges[:, 1]

    k = 1.0                              # ideal distance between neighbors
    temperature = np.sqrt(n) / 4         # max move per round; "cools" to 0
    cooling = temperature / (iterations + 1)
    for _ in range(iterations):
        disp = np.zeros_like(pos)

        # Push: every pair, k^2 / distance. In chunks of rows to keep memory small.
        for a in range(0, n, chunk):
            d = pos[a:a + chunk, None, :] - pos[None, :, :]          # (rows, n, 2)
            dist2 = (d * d).sum(-1) + 1e-3
            disp[a:a + chunk] += (d * (k * k / dist2)[..., None]).sum(1)

        # Pull: every friendship, distance^2 / k, along the edge.
        delta = pos[u] - pos[v]
        dist = np.sqrt((delta * delta).sum(-1)) + 1e-9
        f = delta * (dist / k)[:, None]
        np.subtract.at(disp, u, f)
        np.add.at(disp, v, f)

        # Weak gravity to the center keeps separate pieces from drifting away.
        disp -= 0.05 * pos

        # Move each vertex along its total force, at most `temperature`.
        length = np.sqrt((disp * disp).sum(-1)) + 1e-9
        pos += disp / length[:, None] * np.minimum(length, temperature)[:, None]
        temperature = max(temperature - cooling, 0.01)

    return pos - pos.mean(0)
