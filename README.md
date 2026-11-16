# Recursive multiresolution Leiden taxonomy of circular-economy patent vocabulary (2026)

This repository contains the code, figures, selected analytic output, naming register and source-grounded manuscript associated with a Lens patent phrase-network study. Source retrieval date: **14 September 2026**; reported query: **Circular economy**.

## Observed evidence

The archived analytical corpus comprises 42,410 source units and the retained graph contains 4,975 phrase vertices and 62,267 weighted edges. The completed optimized hierarchy has 231 observed nodes (including the root and residual nodes), 41 accepted splits and 159 nonresidual terminal communities. The stability-selected root resolution is 0.70. These are computed network groupings, not independently validated circularity claims.

## Repository organization

- `code/`: archived extraction/optimization and resume-capable Leiden implementation.
- `data/COMPLETE_231_NODE_NAMING_REGISTER.csv`: all 231 nodes, edited English labels, exact leading phrases, parents, depth, status and observed support.
- `data/APPENDIX_A1_ALL_190_TERMINAL_PATHS_RENAMED.csv`: complete terminal path table in the paper appendix.
- `data/TABLE_7_ROOT_BRANCH_SUMMARY.csv`: the concise Table 7 included in the article body.
- `figures/FULL_231_NODE_INTERACTIVE_TAXONOMY.html`: interactive full tree with hoverable evidence.
- `figures/FIGURE_6_RENAMED_ROOT_COMMUNITIES.*` and `FIGURE_8_FULL_DEPTH_TREE_RENAMED.*`: updated publication figures.
- `prompts/`: prompts for all eight final manuscript figures.
- `manuscript/`: polished Word draft containing the updated table and Appendix A.
- `docs/`: original recovered structure and new curated labels.

## Naming protocol

The Leiden clustering, node IDs, counts, parent–child paths and support figures were not altered. Labels were curated from each community’s own top-20 exact patent phrases, with distinct technical foci within sibling groups. Generic and residual lexical clusters retain explicitly descriptive labels. The naming procedure is interpretive and has not been externally validated; readers should not treat label uniqueness as proof of semantic exclusivity in patent inventions.

## Access and reuse

The raw Lens archive is **not** included in this GitHub upload package; distribution of source patent data remains subject to Lens terms and the authors' data availability policy. Code and derived output require appropriate citation. The repository address is the **intended publication location**; preparing this archive does not create or publish an online GitHub repository.

## Replication

Run the notebook in `code/` on the same exported source and reuse original input checksums; see the notebook for configured Resume checkpoints and optimizer settings. For visual verification, open the self-contained HTML figure; the CSVs contain the precise rows shown in the manuscript.

## Revised manuscript (16 November 2026)

The updated manuscript incorporates publication-oriented formatting, an evidence-based Results narrative, revised editable equations, concise section headings and separate ID columns in the example and appendix tables. Figure numbers remain 1–8. The EndNote library is provided as RIS; in-text references are not live EndNote CWYW fields.


## Final hierarchy revision (16 November 2026)

The **authoritative manuscript** is `manuscript/CE_Circular_Economy_JCP_FINAL.docx`.
The **authoritative Table 7** is `tables/TABLE_7_RECURSIVE_TOP_THREE.csv`,
which reports at most three leading nonresidual children recursively for each parent;
the unabridged terminal paths are in the manuscript appendix and derived data files.
The **authoritative full-depth figure** is `figures/FIGURE_8_FULL_TREE_REDESIGNED.svg`
(PNG counterpart provided); edge and vertex-coordinate tables are in `data/`.
All 231 nodes are reported in `data/FULL_231_NODE_REGISTER.csv`.

The accompanying private delivery ZIP contains the original Lens export and the complete
analysis bundle, but these are intentionally **not uploaded to GitHub**; Lens-export
redistribution requires checking the data provider's terms, and the 36.5 MiB analysis ZIP
exceeds GitHub browser upload's usual single-file limit.

**Repository publishing:** This ZIP is ready for the ResearchRepro owner to publish.
The URL above is a planned destination, not evidence that the repository is live.
The EndNote RIS file is an import file; the Word manuscript's bibliographic citations
may still require binding to live EndNote citation fields before submission.
