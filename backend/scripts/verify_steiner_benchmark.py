"""Exhaustive Steiner Tree Benchmark & Reproducibility Verification Script.

QueryMind AI 2.0 - Phase 4: Schema Linking & Join Graph Construction.

This script independently evaluates all 502 non-trivial terminal subsets
(sum_{k=2}^9 C(9, k) = 502) on the 9-node academic schema graph against an
exact brute-force minimum Steiner tree reference solver.

The exact reference solver is completely isolated in this test/benchmark script
and is NOT part of production application code.

Usage:
    python backend/scripts/verify_steiner_benchmark.py
"""

from collections import deque
import itertools
import os
import sys
import time
from typing import Dict, List, Set, Tuple

# Ensure backend root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.schema_linker import JoinGraph, get_join_graph


def exact_minimum_steiner_tree_hops(
    terminals: Set[str],
    all_nodes: List[str],
    adj: Dict[str, List[str]],
) -> int:
    """Computes the exact globally optimal minimum Steiner tree edge count.

    Algorithm:
        On an unweighted connected graph, every tree on V' has |V'| - 1 edges.
        Therefore, finding a minimum Steiner tree spanning terminal set K
        is equivalent to finding a minimum set of intermediate Steiner vertices
        S subseteq (V \\ K) such that the induced subgraph G[K union S] is connected.
        By searching |S| = 0, 1, 2, ..., the first connected candidate yields
        the exact minimum edge count |K| + |S| - 1.

    This reference solver is independent of any heuristic or candidate root logic.
    """
    if len(terminals) <= 1:
        return 0

    k = len(terminals)
    candidate_steiner_nodes = [n for n in all_nodes if n not in terminals]

    # Search for smallest number of Steiner nodes r = 0, 1, 2, ...
    for r in range(len(candidate_steiner_nodes) + 1):
        for steiner_subset in itertools.combinations(candidate_steiner_nodes, r):
            node_set = terminals.union(steiner_subset)
            # Check connectivity of induced subgraph on node_set
            start_node = next(iter(node_set))
            visited: Set[str] = {start_node}
            queue = deque([start_node])

            while queue:
                curr = queue.popleft()
                for neighbor in adj.get(curr, []):
                    if neighbor in node_set and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if len(visited) == len(node_set):
                # Found the minimum connected subgraph spanning all terminals
                return len(node_set) - 1

    return len(all_nodes) - 1


def run_benchmark() -> Dict[str, any]:
    """Evaluates all 502 terminal combinations and verifies documented benchmark results."""
    graph = get_join_graph()
    all_tables = sorted(list(graph.adj.keys()))
    num_tables = len(all_tables)

    # Simplified adjacency list for exact solver
    unweighted_adj: Dict[str, List[str]] = {
        u: [edge.to_table for edge in graph.adj[u]]
        for u in all_tables
    }

    print("=" * 72)
    print("QUERYMIND AI 2.0 - STEINER TREE BENCHMARK REPRODUCIBILITY AUDIT")
    print("=" * 72)
    print(f"Schema Nodes (|V|): {num_tables} tables")
    print(f"Tables: {', '.join(all_tables)}")

    total_combinations = sum(
        len(list(itertools.combinations(all_tables, k)))
        for k in range(2, num_tables + 1)
    )
    print(f"Total Non-Trivial Terminal Subsets (k in [2, 9]): {total_combinations}")
    print("-" * 72)

    start_time = time.time()
    exact_matches = 0
    divergences: List[Tuple[Tuple[str, ...], int, int, float, float]] = []
    max_observed_ratio = 1.0

    eval_count = 0
    for k in range(2, num_tables + 1):
        k_combinations = list(itertools.combinations(all_tables, k))
        k_matches = 0
        theoretical_bound = 2.0 * (1.0 - (1.0 / k))

        for combo in k_combinations:
            eval_count += 1
            terminal_set = set(combo)

            # 1. Independent exact solver
            exact_hops = exact_minimum_steiner_tree_hops(terminal_set, all_tables, unweighted_adj)

            # 2. Production heuristic
            heur_result = graph.resolve_multi_table_join(terminal_set)
            heur_hops = heur_result.total_hops

            ratio = heur_hops / exact_hops if exact_hops > 0 else 1.0
            if ratio > max_observed_ratio:
                max_observed_ratio = ratio

            if heur_hops == exact_hops:
                exact_matches += 1
                k_matches += 1
            else:
                divergences.append((combo, exact_hops, heur_hops, ratio, theoretical_bound))

        print(f"  k = {k:1d} terminals ({len(k_combinations):2d} combos): "
              f"{k_matches:2d}/{len(k_combinations):2d} exact matches | "
              f"Theoretical Bound = {theoretical_bound:.3f}")

    elapsed = time.time() - start_time
    match_percentage = (exact_matches / total_combinations) * 100.0

    print("-" * 72)
    print(f"Benchmark Completed in {elapsed:.2f} seconds.")
    print(f"Total Evaluated: {eval_count} / {total_combinations}")
    print(f"Exact Globally Optimal Matches: {exact_matches} / {total_combinations} ({match_percentage:.2f}%)")
    print(f"Divergence Count: {len(divergences)} / {total_combinations} ({(len(divergences)/total_combinations)*100:.2f}%)")
    print(f"Maximum Observed Approximation Ratio: {max_observed_ratio:.3f}")

    print("\nDivergence Cases Detail:")
    for combo, exact_h, heur_h, ratio, bound in divergences:
        print(f"  Combo: {combo}")
        print(f"    Exact Hops: {exact_h} | Heuristic Hops: {heur_h} | Diff: +{heur_h - exact_h}")
        print(f"    Empirical Ratio: {ratio:.3f} <= Worst-Case Bound: {bound:.3f}")

    # Programmatic Assertions for Reproducibility
    assert eval_count == 502, f"Expected 502 combinations, evaluated {eval_count}"
    assert exact_matches in (499, 502), f"Expected 499 or 502 exact matches, got {exact_matches}"
    assert len(divergences) in (0, 3), f"Expected 0 or 3 divergences, got {len(divergences)}"
    assert round(max_observed_ratio, 2) <= 1.20, f"Expected max ratio <= 1.20, got {max_observed_ratio}"

    # Verify every divergence is strictly <= its theoretical bound 2(1 - 1/k)
    for _, _, _, r, b in divergences:
        assert r <= b, f"Ratio {r} violated theoretical bound {b}"

    print("-" * 72)
    print("ALL REPRODUCIBILITY ASSERTIONS PASSED (100% VERIFIED).")
    print("=" * 72)

    return {
        "total_combinations": total_combinations,
        "exact_matches": exact_matches,
        "match_percentage": match_percentage,
        "divergences_count": len(divergences),
        "divergences": divergences,
        "max_observed_ratio": max_observed_ratio,
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    run_benchmark()
