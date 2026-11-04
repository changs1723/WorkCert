"""Rebuild the article from pinned inputs with TeX Live.

Run from the complete source root:
    python authoring/build_documents_v03.py
Use --keep-figures to reuse the supplied exact figure PDFs. Publication state
comes from article_inputs/publication_snapshot.json, never the network.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEX = Path(r"C:\texlive\2025\bin\windows")


def executable(name):
    path = shutil.which(name)
    if path:
        return path
    fallback = TEX / (name + ".exe")
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("Install TeX Live and place " + name + " on PATH")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-figures", action="store_true")
    args = parser.parse_args()
    snapshot = json.loads((ROOT / "article_inputs/publication_snapshot.json").read_text(encoding="utf8"))
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = str(snapshot.get("build_epoch", 1793664000))
    env["FORCE_SOURCE_DATE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    output = ROOT / snapshot.get("audit_directory", "qa/round5")
    output.mkdir(parents=True, exist_ok=True)
    commands = [(sys.executable, str(ROOT / "authoring/collect_values.py"))]
    if not args.keep_figures:
        commands.append((sys.executable, str(ROOT / "authoring/build_figures.py")))
    commands.append((sys.executable, str(ROOT / "authoring/build_manuscript.py")))
    logs = []
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, errors="replace")
        logs.append(result.stdout + "\n" + result.stderr)
        if result.returncode:
            (output / "paper_compile.log").write_text("\n".join(logs), encoding="utf8")
            raise RuntimeError("Article input/figure generation failed: " + str(command[-1]))
    for name in ("main", "cover_letter"):
        texcommands = [("pdflatex", "-interaction=nonstopmode", "-halt-on-error", name + ".tex")]
        if name == "main":
            texcommands.append(("bibtex", name))
        texcommands += [("pdflatex", "-interaction=nonstopmode", "-halt-on-error", name + ".tex")] * 2
        for command in texcommands:
            result = subprocess.run([executable(command[0]), *command[1:]], cwd=ROOT / "manuscript", env=env,
                                    capture_output=True, text=True, errors="replace")
            logs.append(result.stdout + "\n" + result.stderr)
            if result.returncode:
                (output / "paper_compile.log").write_text("\n".join(logs), encoding="utf8")
                raise RuntimeError("TeX compilation failed: " + name)
    (output / "paper_compile.log").write_text("\n".join(logs), encoding="utf8")
    pages = {}
    try:
        import fitz
        pages = {name: len(fitz.open(ROOT / "manuscript" / (name + ".pdf"))) for name in ("main", "cover_letter")}
        (ROOT / "qa/page_counts.json").write_text(json.dumps(pages, indent=2) + "\n", encoding="utf8")
    except ImportError:
        pdfinfo = shutil.which("pdfinfo")
        fallback = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdfinfo.exe"
        if not pdfinfo and fallback.is_file():
            pdfinfo = str(fallback)
        if pdfinfo:
            for name in ("main", "cover_letter"):
                information = subprocess.check_output([pdfinfo, str(ROOT / "manuscript" / (name + ".pdf"))], text=True, errors="replace")
                pages[name] = int(re.search(r"(?m)^Pages:\s+(\d+)", information).group(1))
            (ROOT / "qa/page_counts.json").write_text(json.dumps(pages, indent=2) + "\n", encoding="utf8")
    proof = {"status": "PASS", "source_date_epoch": env["SOURCE_DATE_EPOCH"],
             "pdf_dates_and_trailer_ids_suppressed": True, "pages": pages,
             "pdfs": {name + ".pdf": hashlib.sha256((ROOT / "manuscript" / (name + ".pdf")).read_bytes()).hexdigest()
                      for name in ("main", "cover_letter")},
             "publication_snapshot_sha256": hashlib.sha256((ROOT / "article_inputs/publication_snapshot.json").read_bytes()).hexdigest()}
    (output / "paper_build.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
