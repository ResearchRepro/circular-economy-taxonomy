# Figure 8 — full recursive technology tree

## Purpose
Create a single, print-ready academic node–link illustration for the Discussion of a *Journal of Cleaner Production* manuscript. It must be a genuine parent–child tree, not a word cloud, heat map, treemap, or decorative branching metaphor.

## Authoritative data and cardinalities
- Use `FIGURE_8_ALL_TREE_EDGES.csv` and `FIGURE_8_EXACT_PLOT_COORDINATES.csv` verbatim.
- 231 distinct computational nodes in total, one ROOT node and 230 parent–child edges.
- Depth breakdown: 1 ROOT node, 10 first-level nodes, 60 second-level nodes, 160 third-level nodes.
- 41 internal nodes have accepted children; 190 terminal nodes consist of 159 regular leaves and 31 residual terminals.
- First-level branches: T01 through T09 plus TR (residual root). Their exact labels are in `FULL_231_NODE_REGISTER.csv`.
- Preserve every code and parent_id; do not merge communities, fabricate descendants, relabel nodes, or imply a fourth depth.
- Node labels are classifications derived from shared phrases, not certificates that every patent implements a circular action. Patent-unit supports overlap across branches.

## Composition and visual grammar
Use a circular radial dendrogram with three concentric depth rings. Put a small dark slate-blue root circle at the center, colored first-level domain nodes at the inner ring, second-level descendants in the middle, and third-level termini on the outer ring. Draw a clear continuous line for each recorded parent–child relation; show a tiny solid dot at each regular node and a hollow dot for residual nodes. Keep stroke and point sizes consistent, and visually emphasize root-to-primary-domain lines. The radial angular ordering is provided in the coordinate CSV. Retain adequate separation between the root sectors; no edge is allowed to change parent.

## Color palette
T01 navy blue #2563A6; T02 slate #4F6D7A; T03 teal #07988A; T04 purple #A35FBB; T05 copper #D27836; T06 royal blue #3966CB; T07 rose #B24D70; T08 aqua #3297A4; T09 gray #7A7D85; TR pale gray #89919A. Background white, support rings #E4EBF0, legends dark slate #304558. The color map is categorical only, never an inference about environmental performance or community quality.

## Labels and caption
Write ROOT/Circular economy at the center and show T01–T09 and TR as separate short IDs near primary nodes. Place full domain names in a two-column legend BELOW the tree; keep the ID visually separate from the domain label. Explain in the main manuscript, not in a figure Note, that solid points are regular and hollow points residual, and that hierarchy depth determines radial distance. The Word caption is exactly: `Figure 8. Full recursive technology tree`.

## Delivery and legibility
Export a sharply antialiased PNG (at least 2860 × 3224 px), an editable vector SVG, and all exact source CSV data. Avoid overlapping labels, truncated domains, decorative photographs, artificial drop shadows, inaccurate branch counts, or AI-invented data. Full third-level text labels belong in Appendix A or an interactive supplement, because 231 long labels cannot be printed legibly on a normal journal page. The finished visualization must faithfully reveal all paths and their relative depths at journal page width.

## Negative prompt
No fictitious community names; no extra colored branches; no invented counts; no percentage signs on nodes; no unsourced patent totals; no labels pasted across edges; no microscopic paragraphs embedded in the plot; no human or expert-review stage; no journal publisher logo; no 3D gradients; no background textures.
