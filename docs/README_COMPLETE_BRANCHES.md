# Complete recursive Leiden hierarchy – revision notes

The manuscript’s original Figure 7 visualized only T03 as a selected example. The actual optimized hierarchy expanded **T01, T03, T04, T05, T06, T07 and T08** at the next level. **T02 and T09** terminate at the first level; **TR** is a residual root community.

The revised manuscript replaces the selective figure with a complete Figure 7: a root index followed by all seven expanded branch panels, each displaying every direct child, full node ID, term count, overlapping patent-unit support and third-level descendant count.

The accompanying atlas includes the complete 231-node hierarchical register with depth, exact leading terms, terminal or residual status. No unobserved splits are added. Every value comes from `FULL_HIERARCHY_NODE_TABLE.csv`. Figures are supplied as reproducible PNG and SVG for journal production.

## Reproduction
Run `build_all_figures.py` with `FULL_HIERARCHY_NODE_TABLE.csv` in the relative `03_taxonomy` directory. Do not change graph labels or add technology claims not in the archive.

## Figure 7 prompt / vector production specification
Design an academic multi-panel taxonomy diagram using EXACTLY the values in `ALL_ROOT_BRANCH_DEPTH_COUNTS.csv` and `FULL_HIERARCHY_NODE_TABLE.csv`. Include separate panels for T01, T03, T04, T05, T06, T07 and T08; show all immediate children of each parent with node ID, leading exact phrase label, phrase count, patent support and count of third-level descendants. Show T02 and T09 in a root summary as unsplit terminal branches, and TR as residual. Retain all residual nodes of expanded branches in neutral grey. Use a white background, high-contrast navy typography, distinct muted blue/teal/purple/ochre/rose/green/steel accent colors per root, no decorative pictograms, and no unverified engineering terminology. Never change, simplify or invent any numeric evidence. Layout in printable panels (roughly 7 inches wide) and deliver vector SVG plus high-resolution PNG.
