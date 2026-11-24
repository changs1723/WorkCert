"""Build the R1 article, technical notes, response, and optional marked copy.

Run from the fixed original source root after overlaying Supplementary S2:
    python revision_r1/build_revision.py --marked
Add --figures to redraw the two new figures from saved numerical results.
TeX Live (pdflatex, bibtex and optionally latexdiff) is required.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARTICLE = HERE / "article"

def executable(name):
    found=shutil.which(name)
    fallback=Path(r"C:\texlive\2025\bin\windows")/(name+".exe")
    if found:return found
    if fallback.is_file():return str(fallback)
    raise RuntimeError("Install TeX Live and put "+name+" on PATH")

def run(command, label, env, logdir, cwd=ARTICLE):
    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True)
    (logdir/(label+".log")).write_bytes(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError("Build failed: "+label+"; see "+str(logdir/(label+".log")))
    return result.stdout

def compile_document(name, bib, env, logdir):
    pdflatex=executable("pdflatex")
    run([pdflatex,"-interaction=nonstopmode","-halt-on-error",name+".tex"],name+"_1",env,logdir)
    if bib:run([executable("bibtex"),name],name+"_bib",env,logdir)
    for i in (2,3):run([pdflatex,"-interaction=nonstopmode","-halt-on-error",name+".tex"],name+"_"+str(i),env,logdir)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marked",action="store_true")
    parser.add_argument("--figures",action="store_true")
    args=parser.parse_args()
    env=dict(os.environ,SOURCE_DATE_EPOCH="1795392000",FORCE_SOURCE_DATE="1",PYTHONIOENCODING="utf-8")
    logs=HERE/"build_logs";logs.mkdir(exist_ok=True)
    if args.figures:run([sys.executable,"-B",str(HERE/"build_revision_figures.py")],"figures",env,logs,ROOT)
    for name in ("fig01_architecture.pdf","fig05_exchange_scale.pdf"):
        shutil.copy2(HERE/"figures"/name,ARTICLE/"figures"/name)
    for name in ("fig01_numerics.pdf","fig02_decisions.pdf","fig03_cyclic.pdf","fig04_selectors.pdf","fig05_scaling.pdf"):
        shutil.copy2(ROOT/"figures"/name,ARTICLE/"figures"/name)
    for name in ("main","supplement","cover_letter","response"):
        if (ARTICLE/(name+".tex")).is_file():compile_document(name,name=="main",env,logs)
    if args.marked:
        marked=run([executable("latexdiff"),"--type=CFONT","--no-label","--disable-citation-markup","--graphics-markup=none",str(ROOT/"article/main.tex"),str(ARTICLE/"main.tex")],"latexdiff",env,logs)
        marked_text=marked.decode("utf8").replace("\r\n", "\n").replace("\r", "")
        # The deleted precision figure has no label in the revised article.
        # Its deleted prose refers to Figure 1 in the initial submission.
        marked_text=marked_text.replace(r"\ref{fig:numeric}","1")
        old_text=(ROOT/"article/main.tex").read_text(encoding="utf8")
        new_text=(ARTICLE/"main.tex").read_text(encoding="utf8")
        old_code=re.search(r"(?s)\\begin\{verbatim\}(.*?)\\end\{verbatim\}",old_text).group(1)
        new_code=re.search(r"(?s)\\begin\{verbatim\}(.*?)\\end\{verbatim\}",new_text).group(1)
        block=("\\Needspace{6\\baselineskip}\\textbf{Original example}\\par\n{\\color{red}\\begin{verbatim}"+old_code+
               "\\end{verbatim}}\n\\Needspace{6\\baselineskip}\\textbf{Revised example}\\par\n{\\color{blue}\\begin{verbatim}"+new_code+"\\end{verbatim}}")
        marked_text=re.sub(r"(?s)\\DIFmodbegin\s*\\begin\{DIFverbatim\}.*?\\end\{DIFverbatim\}\s*\\DIFmodend",lambda _:block,marked_text)
        marked_text=marked_text.replace(r"\begin{document}",r"\usepackage{needspace}\begin{document}\sloppy",1)
        marked_text=marked_text.replace(r"\end{frontmatter}",r"\end{frontmatter}\noindent{\small Marked revision: blue text is added or rewritten; red text is removed.}\par",1)
        (ARTICLE/"marked.tex").write_text(marked_text,encoding="utf8")
        compile_document("marked",True,env,logs)
    from pypdf import PdfReader
    names=[n for n in ("main","supplement","cover_letter","response","marked") if (ARTICLE/(n+".pdf")).is_file()]
    report={"status":"PASS","software_version":"0.3.0","article_revision":"R1","build_epoch":env['SOURCE_DATE_EPOCH'],"pdfs":{}}
    for name in names:
        p=ARTICLE/(name+".pdf");reader=PdfReader(p)
        report['pdfs'][name]={'pages':len(reader.pages),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        log=(ARTICLE/(name+".log")).read_text(encoding='utf8',errors='replace')
        report['pdfs'][name]['overfull_lines']=[line for line in log.splitlines() if 'Overfull' in line]
        if report['pdfs'][name]['overfull_lines']:
            raise RuntimeError('Overfull layout in '+name)
        if 'There were undefined references' in log or 'Citation' in log and 'undefined' in log:
            raise RuntimeError('Unresolved cross-reference in '+name)
    if report['pdfs']['main']['pages']>15:raise RuntimeError('Clean article exceeds 15 pages')
    (HERE/'article_build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
