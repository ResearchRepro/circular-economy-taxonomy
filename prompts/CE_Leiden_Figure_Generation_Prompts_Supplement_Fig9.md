# Supplementary prompt additions for the final manuscript revision

## Figure 9. Full recursive technology tree through the deepest accepted layer

### Exact-generation prompt
Create a landscape academic tree diagram that displays the **entire recovered Leiden hierarchy** from the root to the deepest accepted level. The visual must show all observed depth-1, depth-2, and depth-3 communities from the final node table. Organize the figure in three readable columns labelled **Depth 1**, **Depth 2**, and **Depth 3**. Use the exact node IDs, short exact-phrase labels, patent-support counts, and term counts from `FULL_HIERARCHY_NODE_TABLE.csv`. Draw connectors from each parent to every accepted child. Distinguish residual groups from regular groups using a clearly explained contrasting fill. Distinguish terminal groups that stop before depth 3 from those that continue to depth 3. Preserve the actual branching logic; do not invent missing descendants for branches that stopped earlier. Use a clean white background, publication-grade typography, and thin connector lines. Export as high-resolution PNG and editable SVG.

**Primary data files:** `FULL_HIERARCHY_NODE_TABLE.csv`, `TABLE_7_COMPLETE_HIERARCHY_PATHS.csv`.

**QA acceptance criteria:** every displayed node exists in the source data; every parent-child connection is valid; no branch continues beyond the recorded terminal depth; residual groups are visually distinguished but retained; all text is legible at full-page journal scale.

## Table 7. Consolidated hierarchy paths

This table is not an AI-generated illustration. It is a structured tabular rendering of `TABLE_7_COMPLETE_HIERARCHY_PATHS.csv` and should preserve the exact recorded values.