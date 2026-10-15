"""Weighted open postman routes over existing ink, component by component."""

from __future__ import annotations

import heapq
import math

import networkx as nx

_EXACT_ODD_LIMIT = 40


def _pair_odd(graph: nx.MultiGraph, odd: list) -> list[tuple]:
    if len(odd) <= 2:
        return []
    if len(odd) <= _EXACT_ODD_LIMIT:
        # Two zero-cost dummy vertices leave the best two real endpoints open.
        # Matching the remaining odds gives minimum retrace distance, rather
        # than treating a 100mm stroke as one "hop" like a 1mm stroke.
        matching = nx.Graph()
        for i, node in enumerate(odd):
            distances = nx.single_source_dijkstra_path_length(graph, node, weight="weight")
            for j in range(i + 1, len(odd)):
                matching.add_edge(i, j, weight=distances[odd[j]])
            matching.add_edge(i, len(odd), weight=0)
            matching.add_edge(i, len(odd) + 1, weight=0)
        pairs = nx.min_weight_matching(matching, weight="weight")
        return [
            (odd[a], odd[b])
            for a, b in sorted(tuple(sorted(pair)) for pair in pairs)
            if a < len(odd) and b < len(odd)
        ]

    # Bound matching cost on large drawings. Keep far-apart endpoints open,
    # then pair other odd nodes by weighted Dijkstra with early termination.
    def farthest(source):
        distances = nx.single_source_dijkstra_path_length(graph, source, weight="weight")
        return max(odd, key=lambda p: distances[p])

    start = farthest(odd[0])
    end = farthest(start)
    remaining = set(odd) - {start, end}
    pairs = []
    while remaining:
        source = min(remaining)
        remaining.remove(source)
        queue = [(0.0, source)]
        distances = {source: 0.0}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            if node in remaining:
                remaining.remove(node)
                pairs.append((source, node))
                break
            for nb, edges in graph[node].items():
                candidate = distance + min(edge["weight"] for edge in edges.values())
                if candidate < distances.get(nb, math.inf):
                    distances[nb] = candidate
                    heapq.heappush(queue, (candidate, nb))
    return pairs


def stroke_components(lines: list) -> list[tuple[list, list]]:
    graph = nx.MultiGraph()
    for line in lines:
        points = [tuple(p) for p in line]
        graph.add_nodes_from(points)
        for a, b in zip(points, points[1:], strict=False):
            if a != b and not graph.has_edge(a, b):
                graph.add_edge(a, b, weight=math.dist(a, b))
    components = list(nx.connected_components(graph))
    component_of = {node: i for i, nodes in enumerate(components) for node in nodes}
    originals: list[list] = [[] for _ in components]
    for line in lines:
        originals[component_of[tuple(line[0])]].append(line)

    result = []
    for nodes, original in zip(components, originals, strict=True):
        sub = nx.MultiGraph(graph.subgraph(nodes))
        if not sub.number_of_edges():
            result.append((original, original))
            continue
        odd = sorted(node for node, degree in sub.degree() if degree % 2)
        for a, b in _pair_odd(sub, odd):
            path = nx.shortest_path(sub, a, b, weight="weight")
            for u, v in zip(path, path[1:], strict=False):
                weight = min(edge["weight"] for edge in sub[u][v].values())
                sub.add_edge(u, v, weight=weight)
        trail = list(nx.eulerian_path(sub, keys=True))
        route = [list(trail[0][0]), *[list(v) for _, v, _ in trail]]
        result.append((original, [route]))
    return result
