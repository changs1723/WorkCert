"""Build the article and cover letter with TeX Live."""
from pathlib import Path
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
TEX=Path(r'C:\texlive\2025\bin\windows')
def executable(name):
    found=shutil.which(name)
    if found:return found
    fallback=TEX/(name+'.exe')
    if fallback.exists():return str(fallback)
    raise RuntimeError('Install TeX Live and place '+name+' on PATH')

def main():
    (ROOT/'qa').mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(ROOT/'authoring/collect_v02_values.py')],check=True)
    subprocess.run([sys.executable,str(ROOT/'authoring/build_v02_manuscript.py')],check=True)
    output=[]
    for name in ('main','cover_letter'):
        commands=[('pdflatex','-interaction=nonstopmode','-halt-on-error',name+'.tex')]
        if name=='main':commands.append(('bibtex',name))
        commands += [('pdflatex','-interaction=nonstopmode','-halt-on-error',name+'.tex')]*2
        for command in commands:
            result=subprocess.run([executable(command[0]),*command[1:]],
                                  cwd=ROOT/'manuscript',capture_output=True,text=True,errors='replace')
            output.append(result.stdout+'\n'+result.stderr)
            if result.returncode:
                (ROOT/'qa/compile.log').write_text('\n'.join(output),encoding='utf8')
                raise RuntimeError('TeX compilation failed: '+name)
    (ROOT/'qa/compile.log').write_text('\n'.join(output),encoding='utf8')
    try:
        import fitz
        pages={name:len(fitz.open(ROOT/'manuscript'/(name+'.pdf'))) for name in ('main','cover_letter')}
    except ImportError:
        pages={'note':'Install PyMuPDF to collect page counts; PDFs were compiled successfully'}
    (ROOT/'qa/page_counts.json').write_text(json.dumps(pages,indent=2),encoding='utf8')
    print(pages)

if __name__=='__main__':main()
