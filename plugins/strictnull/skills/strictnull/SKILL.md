---
name: strictnull
description: Build the control before you compare. Use whenever a claim says a graph, network, connectome, wiring diagram, or interaction map is "structured", "non-random", "more clustered than chance", or "beats a random network" - run degree-preserving null models and report what survives.
metadata:
  trigger: Any comparison of a graph against "random", "chance", or "a shuffled network"; any claim that wiring, topology, or connectivity explains a result
  author: Tsuruta Lab (https://tsurutalab.org)
---

# strictnull

A graph only looks special against the right control. Most papers compare against an Erdős–Rényi graph
(same node count, same edge count). That control cannot tell wiring from degree: a heavy-tailed degree
distribution alone produces clustering, short paths, reciprocity, and communities. The claim "the wiring
matters" needs a control that keeps every node's degree and rewires everything else.

## When this skill applies

- A network statistic is reported as evidence of structure (clustering, motifs, reciprocity, modularity,
  path length, rich club, assortativity, "small world").
- A model built from a real graph (a connectome as a fixed layer, a knowledge graph as a prior, a social
  graph as a feature) is said to beat a random one.
- Any sentence of the form "X is significantly higher than expected by chance" where "chance" is not defined.

## What to do

1. Install: `pip install strictnull` (needs numpy and igraph; networkx optional).
2. Build the graph from what the user has (edge list CSV, adjacency matrix, networkx graph).
3. Run the comparison with at least 20 draws per control:

   ```python
   import strictnull as sn
   g = sn.Graph.from_csv("edges.csv", directed=True)      # or from_edges / from_adjacency / from_networkx
   rep = sn.compare(g, stats=["clustering", "reciprocity", "avg_path", "assortativity"], n_null=20)
   print(rep)
   ```

   or from the shell: `strictnull edges.csv --n-null 20 --json report.json`

4. Read three numbers per statistic and report all three:
   - `z(weak)`: distance from the edge-count control. This is what the paper probably reported.
   - `z(strict)`: distance from the degree-preserving control. This is the evidence for wiring.
   - `by degree`: the fraction of the weak-control gap that the degree sequence alone reproduces.
     Near 100% means the "structure" is the degree distribution.

5. If the claim is about a model that uses the graph (not a statistic), swap the graph for each
   strict null draw, retrain, and compare the model's outcome against the spread over draws.
   `sn.ensemble(g, n=5)` yields independent draws; `sn.verify(g, draw)` proves each one kept the degrees.

## Rules the tool enforces, and why

- **One draw is not a control.** `compare` refuses `n_null < 2`. Report mean and sd over draws.
- **Every null is verified** before it is used: exact degree match, no self-loops, no multi-edges,
  fraction of edges actually rewired. If less than 80% rewired, the report warns; say so.
- **Invariant statistics are flagged.** If a statistic comes out identical, to the last digit, on the
  graph and on every null, the control did not touch what it measures. That is not "no effect"; it is
  "nothing was tested". Do not report such a row as a result. Common cases: anything that is a
  function of the degree sequence (max degree, degree variance) is invariant under the strict null;
  anything that is a function of the edge count or the weight multiset is invariant under both.

## How to write it up

State the control explicitly: "against 20 degree-preserving rewirings (double-edge swaps, 20 per edge,
97% of edges rewired)". Give real value, control mean ± sd, and z for both controls. If the effect
vanishes under the strict control, say the property belongs to the degree sequence. If it survives,
say what the strict control still does not rule out (weights, spatial embedding, node types).

## Worked example

The larval Drosophila connectome (2,952 neurons, 110,140 edges) has clustering 0.235. The weak control
gives 0.025; the strict control gives 0.054 ± 0.0001. The wiring is real here (z ≈ 1,400 against the
strict control). But when that same connectome was used as a fixed recurrent layer in an MNIST
classifier, accuracy did not change when the layer was replaced by a strict null: the structure exists
and the task does not use it. Both facts needed the strict control to be seen.
