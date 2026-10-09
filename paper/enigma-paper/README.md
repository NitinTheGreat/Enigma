# Enigma paper, LaTeX source

Single-file IEEE conference paper.

## Overleaf

Upload the whole folder, or upload `enigma-paper.zip` directly
(New Project, Upload Project). Set the main document to `main.tex`.
Compiler: pdfLaTeX. Bibliography: BibTeX, which Overleaf runs automatically.

## Layout

    main.tex     the entire paper, nothing is \input from elsewhere
    refs.bib     18 entries, all cited, all real
    figures/     four PDFs, referenced by the filenames below

| In the paper | File |
| --- | --- |
| Figure 1, architecture | `figures/fig1_architecture.pdf` |
| Figure 2, ablation main effects | `figures/fig3_ablation_main_effects.pdf` |
| Figure 3, belief trajectory | `figures/fig6_belief_trajectory.pdf` |
| Figure 4, clock collapse | `figures/fig2_clock_collapse.pdf` |

The filenames keep their internal numbering from the experiment scripts,
which is why they do not match the figure numbers. LaTeX assigns the figure
numbers from document order, so do not rename them.

## Regenerating the figures

From the project root, not this folder:

    ./reproduce.sh

That redraws all four PDFs and recomputes the numbers quoted in the paper.
Copy the refreshed PDFs from `figures/` into `figures/` here.

## Before submission

- Replace the author block in `main.tex`.
- `\balance` is loaded for the final column balance; remove it if the venue
  objects.
- Check the page count against the venue limit. The body is about 5400
  words with four floats and three tables.
