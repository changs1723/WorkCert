Original-source context for the fixed benchmark references

The benchmark runs from ../reference_inputs/, ../prepared/ and the PLA+ XLSX
files under ../raw/. The files here document the original steel and EDAH
acquisition records behind the 24 fixed reference inputs. They do not change
the 70-reference benchmark or its numerical windows.

Contents
steel/: 36 unmodified force/displacement/time CSVs and CX_Tensile.xlsx from
Mendeley Data DOI 10.17632/8bxkdw4nfw.1. The tensile workbook is auxiliary;
23 X/Y compression windows are included in the benchmark. The 12 Z records
use a TestInput-labelled displacement channel and are excluded. E_Y_0.1
starts after the initial loading segment and is also excluded.
EDAH/: the unmodified EDAH4_52_35(3.3).csv from Zenodo
DOI 10.5281/zenodo.16399749, with its recorded signs and original encoding.
steel_repository_metadata.json and EDAH_repository_metadata.json: unchanged
official repository metadata, including licensing and source-file checksums.
source_manifest.json: source-copy byte sizes and SHA-256 values; steel copies
match repository SHA-256 values, and the EDAH copy matches repository MD5.
preparation_inventory.json: source channels, eligibility and the mapping to
the fixed reference-input and prepared-CSV hashes. Included steel windows also
record the contact row, origin, endpoint, loaded nominal dimension and counts
of chronological reverse-motion rows removed by first-passage extraction.
verify_preparation.py: read-only re-extraction and checksum audit.
preparation_verification.json: recorded output of that audit.

Steel window preparation
Reverse the signs of the source force and encoder displacement so compression
is positive. Truncate at the first global maximum displacement. Contact is the
first of three consecutive samples whose force is at least 0.5 kN; subtract
that sample's displacement. Starting there, retain chronological record-high
displacements separated by more than 1e-9 mm. Keep the window up to 0.4 times
the nominal loaded CAD envelope dimension, adding the linearly interpolated
endpoint. The nonnegative projection in the archived preparation changes zero
retained steel values. The endpoint and nominal dimension for each curve are
recorded in preparation_inventory.json. No smoothing is applied.

EDAH preparation
The first three source rows contain a record label, channel labels and units.
Numeric columns are time (s), load (N), travel (mm). Convert N to kN and subtract
the first travel. Preserve the complete 7,817-point chronological record and
all 60 negative forces. No contact threshold or nominal specimen volume is
assigned. These steps retain the supplied source units and avoid relying on
an interpretation of the specimen filename.

The steel and EDAH reference inputs are fixed archived numerical inputs to the
new benchmark. The verification script compares an independent re-extraction
with them to floating-point precision; it does not overwrite the fixed inputs.
The numerical certificates refer to the corresponding PL response windows.

Run, from this directory or another working directory:
  python path/to/source_context/verify_preparation.py

PLA+ provenance is separate: ../metadata/mendeley_v7p6y654ft_v4.json,
../metadata/pla_download_manifest.json and ../raw/pla_v7p6y654ft_v4/ retain the
version-4 metadata, all 55 original numeric XLSX files and repository hashes.

All included experimental data use CC BY 4.0. Attribution, transformations
and links to the source creators are in ../DATA_ATTRIBUTION.txt.
