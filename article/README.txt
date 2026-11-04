Frozen WorkCert article object

This folder identifies the article PDF and editable sources, separately from the software package.
The article_manifest.json file records the actual PDF, source, figures, software modules and pinned inputs.
It does not claim that a previous software DOI archived this manuscript.

MIT terms apply to software code. This article snapshot is supplied for review and reproducibility;
it does not assign a journal publication license to the manuscript.

Compile here: pdflatex main.tex; bibtex main; pdflatex main.tex twice; pdflatex cover_letter.tex.
Regenerate from the complete source root: python authoring/build_documents_v03.py --keep-figures
Recreate plots too: python authoring/build_documents_v03.py
Publication state is read only from article_inputs/publication_snapshot.json.
Recorded inputs must match article_inputs/scientific_fingerprints.json before regeneration.
Exact PDF byte identity is checked in the recorded TeX environment; other TeX/font versions may differ.
