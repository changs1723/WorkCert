S1-L1 cyclic-bending source

Version-specific dataset DOI: 10.5281/zenodo.10829958.
The unmodified original XLSX is cyclic_RHS.xlsx; its deposited original filename,
repository MD5, byte size and SHA-256 are in download_manifest.json.
Official metadata, creators, description and CC BY 4.0 license are preserved in
repository_metadata.json. Full attribution and transformation rules appear in
../DATA_ATTRIBUTION.txt.

The workbook INFO sheet explicitly states displacement [mm] and force [kN].
S1_L1 contains 125,157 finite data rows starting at Excel row 4, columns B/C.
cyclic_RHS_raw.csv is a derived numeric convenience copy; user_workflow.py reads
and verifies the original XLSX before reconstructing its chronological path.

Reproduce:
  python validation/user_workflow.py --case cyclic
from the project root, or use the absolute script path from another directory.
All required numerical inputs are provided with this project.
