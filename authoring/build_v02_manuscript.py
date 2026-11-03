"""Build the revised SoftwareX paper from the frozen v0.2 case studies."""
from pathlib import Path
import json
import re
import shutil
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'manuscript'

def read(path):return json.loads((ROOT/path).read_text(encoding='utf8'))

def main():
    meta=read('release_metadata.json')
    comparison=read('validation/results_v02/comparative_summary.json')
    dp=read('validation/results_v02/dp_summary.json')
    workflow=read('validation/workflow_results/summary_all.json')
    pla=read('validation/workflow_results_round2/summary.json')
    cyc=workflow['cyclic_path']
    headline=read('validation/results/scaling/headline_repeats.json')
    install=read('software/release_validation.json')
    connector=read('validation/connector_results/verification.json')
    connector_lines=(ROOT/'validation/connector_results/STWC1_connector.inp').read_text().splitlines()
    connector_rows=[line for line in connector_lines if not line.startswith('*')]
    def printed_row(line):
        force, displacement=map(float,line.split(','))
        return '%.6f, %.6f'%(force,displacement)
    connector_excerpt='\n'.join([printed_row(connector_rows[0]),printed_row(connector_rows[1]),
                                '** intervening rows omitted',printed_row(connector_rows[-1])])
    q=pd.read_csv(ROOT/'validation/workflow_results_round2/queries.csv')
    selected=q[q.specimen=='STWC-1'].sort_values('stroke_mm')
    rows=['%.0f & %.3f & %.3f & %.3f & %.3f & [%.3f, %.3f] \\\\'%(r.stroke_mm,r.EA_J,r.SEA_kJ_kg,r.MCF_kN,r.CFE,r.CFE_lower,r.CFE_upper) for r in selected.itertuples()]
    methodrows=[]
    for key,label in [('work','Work priority'),('vertical','Vertical priority'),('rdp','RDP, fixed count'),('vw','Visvalingam--Whyatt'),('uniform_peak','Uniform + peak'),('uniform','Uniform')]:
        v=comparison['ALL']['at33'][key]
        ratios = ('%.3f'%dp['eta']['33'][key]['median_ratio'], '%.3f'%dp['vertical']['33'][key]['median_ratio']) if key!='uniform' else ('--','--')
        methodrows.append(('%s & %.3f & %.3f & %s & %s '+r'\\')%(label,v['prefix_error_percent'],v['window_error_percent'],*ratios))
    # Scaling JSON is deliberately normalized by a separate results collector.
    evidence=read('authoring/final_values.json')
    source=meta.get('permanent_code_url')
    codelink=r'\url{'+source+'}' if source else r'\emph{Source version awaiting public verification}'
    docurl=meta.get('documentation_url')
    docs=r'\url{'+docurl+'}' if docurl else r'\path{software/docs/API.md} in the accompanying source'
    values={'TITLE':meta['title'].replace('–','--'),'AI':meta['ai_disclosure'],'CODE':codelink,'DOCS':docs,
            'METRICS':'\n'.join(rows),'METHODS':'\n'.join(methodrows),
            'OLDTIME':'%.2f'%evidence['headline_old_median_seconds'],
            'NEWTIME':'%.2f'%evidence['headline_new_median_seconds'],
            'OLDMIN':'%.2f'%evidence['headline_old_min_seconds'],'OLDMAX':'%.2f'%evidence['headline_old_max_seconds'],
            'NEWMIN':'%.2f'%evidence['headline_new_min_seconds'],'NEWMAX':'%.2f'%evidence['headline_new_max_seconds'],
            'TESTS':str(evidence['package_tests']),
            'BASELINETESTS':str(evidence['original_package_tests']),
            'ACCEPTANCETESTS':str(evidence['independent_acceptance_tests']),
            'ACCEPTANCE':evidence['independent_acceptance_statement'],
            'PLATFORMS':evidence['tested_platform_statement'],
            'CISTATUS':evidence['ci_statement'],
            'SCALEENV':evidence['scaling_platform'],
            'WORKFLOWPOINTS':str(pla['retained_nodes']),
            'MAXEA':'%.3f'%pla['maximum_actual_EA_error_J'],
            'CYCLERETAINED':format(cyc['sum_retained_branch_nodes'],','),
            'CYCLEERROR':'%.2f'%cyc['maximum_continuous_chronological_work_error_J'],
            'CYCLEBOUND':'%.2f'%cyc['sum_branch_window_bounds_J'],
            'PUBLICLINE':('The fixed public source version is '+r'\url{'+source+'}.') if source else ''}
    values.update(CONNECTORROWS=connector_excerpt,
                  CONNECTORDELTA='%.3f'%connector['maximum_force_error_kN'],
                  CONNECTOREP='%.3f'%connector['stored_prefix_bound_J'],
                  CONNECTOREW='%.3f'%connector['stored_window_bound_J'])
    hardware=ROOT/'validation/results/scaling/hardware.json'
    if hardware.exists():
        hw=json.loads(hardware.read_text(encoding='utf8'))
        cpu=hw['cpu_model'].replace('(R)','').replace('(TM)','').replace('_',r'\_').replace('&',r'\&')
        os_name=' '.join(hw['platform'].split('-')[:2])
        values['HARDWARE']=(
            '%s, a %s CPU, %.2f GiB of OS-visible RAM, '
            'Python %s and NumPy %s' %
            (os_name, cpu, hw['physical_memory_GiB'], hw['python'].split()[0], hw['numpy']))
    else:
        raise RuntimeError('Capture the hardware of the current timing run first')
    def fill(text):
        for k,v in values.items():text=text.replace('@@'+k+'@@',v)
        assert '@@' not in text
        return text
    OUT.mkdir(exist_ok=True);(OUT/'figures').mkdir(exist_ok=True)
    for p in (ROOT/'figures').glob('fig*.pdf'):shutil.copy2(p,OUT/'figures'/p.name)
    (OUT/'main.tex').write_text(fill(MAIN),encoding='utf8')
    (OUT/'cover_letter.tex').write_text(fill(COVER),encoding='utf8')
    bibliography=(ROOT/'references/original_sources.bib').read_text(encoding='utf8')+'\n'+(ROOT/'references/additions.bib').read_text(encoding='utf8')+'\n'+DATA_BIB
    bibliography=bibliography.replace('author={wuqiang, Wu}','author={Wu, Wuqiang}').replace('3D-printed','{3D}-printed')
    cited=set()
    for group in re.findall(r'\\cite\{([^}]+)\}',MAIN):cited.update(group.split(','))
    bibliography='\n\n'.join(e.strip() for e in re.split(r'(?=@\w+\{)',bibliography)
        if re.match(r'@\w+\{([^,]+),',e) and re.match(r'@\w+\{([^,]+),',e).group(1) in cited)+'\n'
    bibliography=re.sub(r'note=\{Version (?:v1|1); CC BY 4\.0;[^}]+\}',r'note={Version 1; CC BY 4.0}',bibliography)
    (OUT/'references.bib').write_text(bibliography,encoding='utf8')
    (ROOT/'authoring/manuscript_values.json').write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf8')
    print('Revised manuscript generated from v0.2 results.')

MAIN=r'''\documentclass[preprint,12pt,a4paper]{elsarticle}
\usepackage{amssymb,amsmath,booktabs,array,float,hyperref,xurl}
\newcolumntype{P}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\parindent}{0pt}\setlength{\emergencystretch}{1.5em}
\setlength{\abovecaptionskip}{9pt}\setlength{\belowcaptionskip}{8pt}
\hypersetup{hidelinks}\journal{SoftwareX}
\renewcommand{\topfraction}{.9}\renewcommand{\textfraction}{.05}\renewcommand{\floatpagefraction}{.8}
\renewcommand{\bibfont}{\footnotesize}
\begin{document}\begin{frontmatter}
\title{@@TITLE@@}
\author[inst]{Saisai Hou}\author[inst]{Yunzhi Zhu}\author[inst]{Sen Zhang\corref{cor1}}
\ead{szhang@niit.edu.cn}\cortext[cor1]{Corresponding author.}
\address[inst]{Department of Public Basic Courses, Nanjing University of Industry Technology, Nanjing, China}
\begin{abstract}
WorkCert stores error metadata with reduced tables of force and displacement. Its Python interface combines explicit point budgets, interchangeable selectors, checked persistence and directed cyclic branches. A public-data workflow evaluates energy-absorption indicators for 46 specimens representing 42 configurations, compares reconstruction errors with control-specimen scatter, and checks the reported workbook indicators. Preserved peaks tighten crush-force-efficiency intervals. Comparative tests include geometric selectors and exact dynamic-programming controls. For the same interval-work requirement, direct error evaluation reduces median point counts from 27 to 14. Incremental aggregation supports million-point references. Inputs, preprocessing, numerical outputs and plotting programs accompany the software.
\end{abstract}

\begin{keyword}Research software\sep Force--displacement data\sep Reconstruction error\sep Energy absorption\sep Curve simplification\sep Cyclic response\end{keyword}
\end{frontmatter}\clearpage
\section*{Required Metadata}\section*{Current code version}
\begin{table}[H]\small\centering
\begin{tabular}{|P{.05\linewidth}|P{.39\linewidth}|P{.425\linewidth}|}\hline
\textbf{Nr.}&\textbf{Code metadata description}&\textbf{Metadata}\\\hline
C1&Current code version&0.2.0\\\hline
C2&Permanent GitHub link to code/repository used for this code version&@@CODE@@\\\hline
C3&Legal Code License&MIT License\\\hline
C4&Code versioning system used&Git\\\hline
C5&Software code languages, tools, and services used&Python; NumPy; command-line interface\\\hline
C6&Compilation requirements, operating environments \& dependencies&Python $\geq$3.10; NumPy $\geq$1.24. No compiled runtime extension. Validation dependencies are separate.\\\hline
C7&If available Link to developer documentation/manual&@@DOCS@@\\\hline
C8&Support email for questions&\href{mailto:szhang@niit.edu.cn}{szhang@niit.edu.cn}\\\hline
\end{tabular}\caption{Code metadata.}\label{tab:code}\end{table}

\section{Motivation and significance}
Tabulated structural laws support subsequent calculations. The Abaqus bushing example transfers force--motion histories from detailed simulations to connector definitions in an assembly analysis \cite{AbaqusBushing}. WorkCert quantifies force and work errors at a chosen table size. Section~\ref{sec:connector} demonstrates the corresponding loading-branch input interface.

Energy absorption (EA), specific energy absorption (SEA), mean crushing force (MCF) and crush-force efficiency (CFE) vary with stroke. Reusable tables support changing limits and peak queries. Although the example dataset can be exchanged in full, it allows reconstruction errors to be compared with specimen variability.

Ramer, Douglas--\allowbreak Peucker, Visvalingam--\allowbreak Whyatt and time-series segmentation provide established simplification strategies \cite{Ramer1972,DouglasPeucker1973,Visvalingam1993,Keogh2001}. Optimal approximation depends on its objective \cite{Imai1988}, including established area measures \cite{Bose2006,Daneshpajouh2012}. WorkCert combines these summaries with continuous work-query extrema, persistence and branches. It accepts external nodes from tools including \path{rdp}, \path{simplification} and \path{shapely.simplify} \cite{rdpSoftware,Hugel2021,ShapelySoftware}.

\section{Software description}
\subsection{Software architecture}
NumPy is the sole runtime dependency. Separate modules handle validation, selection, errors, queries, persistence and branches (Fig.~\ref{fig:architecture}). Immutable arrays protect cached primitives; research dependencies are separate.

JSON stores nodes, units, errors and provenance in a versioned schema. Source and payload hashes identify changes; loading checks consistency and \path{verify_reference} recomputes errors against the source.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig01_architecture.pdf}
\caption{Producer, exchange and consumer stages. OpenAI Codex (OpenAI, local CLI version 0.166.0-alpha.5.1) assisted the Python code for this explanatory diagram.}\label{fig:architecture}\end{figure}

\subsection{Software functionalities}
Let $F$ be the supplied piecewise-linear reference with $n$ nodes on $[0,U]$ and $\widehat F$ the interpolant through $K$ retained nodes, with the initial coordinate shifted to zero for notation. Define $r=F-\widehat F$ and $D(u)=\int_0^u r(s)\,ds$. WorkCert evaluates
\begin{align}
\eta&=\int_0^U|r(s)|\,ds,&\xi&=(\eta+|D(U)|)/2,\\
E_p&=\max_{0\leq u\leq U}|D(u)|,&E_w&=\max D-\min D,\qquad
\delta=\max|r|.
\end{align}
For any interval $[a,b]$, work error is $D(b)-D(a)$. Analytical float64 evaluation gives the continuous maxima $E_p$ and $E_w$, whereas $\eta$ and $\xi$ are bounds: $E_p\leq E_w\leq\xi\leq\eta$. Reference nodes and interior zeros of $r$ locate the extrema. These quantities describe reconstruction relative to the numerical reference, not measurement uncertainty.

Users choose work priority, vertical priority, effective-area Visvalingam--Whyatt or uniform selection. Both priority methods split at the largest vertical residual but rank intervals differently. Endpoints are retained; peak modes preserve the largest absolute force, signed maximum or signed minimum. Nonnegative nodes give nonnegative interpolants. Native units remain unspecified unless supplied; mm and kN give work in J.

Tolerance stopping evaluates each current representation because a greedy refinement need not decrease its error. An augmented balanced tree stores each interval's cumulative residual-work primitive initialized at zero: its terminal value $d$, minimum $l$ and maximum $h$, together with absolute area and force deviation. Concatenating intervals $A$ and $B$ gives
\begin{equation}
d=d_A+d_B,\quad l=\min(l_A,d_A+l_B),\quad h=\max(h_A,d_A+h_B).
\end{equation}
Only the two new interval summaries and their tree ancestors change after a split. Aggregation costs $O(\log K)$ per insertion and uses $O(K)$ tree storage; residual scans still give $O(nK)$ worst-case selection work. The final representation is checked by a complete reference evaluation. Relative bounds divide by absolute terminal work; zero terminal work requires absolute tolerances. The VW selector uses $O(n\log n)$ time and $O(n)$ storage.

Queries use cached primitives and binary interval searches. Prefix work is quadratic within each linear segment; interval work is a primitive difference. Non-finite or out-of-domain queries raise errors. \path{split_monotone_branches} retains reversal endpoints, chronological orientation and zero-work equal-displacement events. Descending branches store increasing coordinates but use their original direction for $\int F\,dx$.

\begin{minipage}{\linewidth}
\subsection{Sample code snippets}
The following construction reads the public \path{STWC-1} reference; the separate consumer needs only the saved table and its measured mass of 16.2 g:
\begin{verbatim}
from workcert import reduce_response, ReducedResponse
import numpy as np
a = np.loadtxt("data/prepared/PLA_STWC-1.csv",
               delimiter=",", skiprows=1)
t = reduce_response(a[:, 0], a[:, 1], method="work",
    max_points=129, tolerance=1.0, certificate="window",
    x_unit="mm", force_unit="kN")
t.save("STWC-1.json")
c = ReducedResponse.load("STWC-1.json")
q = np.array([10., 20., 30., 40.])
ea = c.work(q)          # J
sea = ea / 16.2         # J/g = kJ/kg
mcf = ea / q           # J/mm = kN
\end{verbatim}
\end{minipage}
The consumer \path{examples/query_exchange.py} also evaluates peak forces and CFE intervals; source-workbook indicators provide an external check. The API parameter \path{certificate=} selects the reconstruction-error quantity.

\subsection{Verification and AI-assisted implementation}\label{sec:verification}
The regression suite adds @@ACCEPTANCETESTS@@ additional tests in \path{software/tests/test_hou_analytic.py}, \path{test_hou_cycles_io.py} and \path{test_hou_paper.py} to @@BASELINETESTS@@ existing tests. @@ACCEPTANCE@@ @@CISTATUS@@ Dynamic-programming controls are checked against exhaustive enumeration and analytical costs; serialized tables are checked against their references.

OpenAI Codex assisted research planning and implementation of error routines, the incremental tree, selectors, preprocessing, validation and plotting. Acquisition and analysis are scripted from archived inputs. Saisai Hou developed and executed the additional tests with Codex assistance and manually verified the results; Yunzhi Zhu checked dynamic programming against exhaustive enumeration; Sen Zhang reviewed the manuscript. Expected values use analytical fixtures, rational integration and source-workbook calculations. The complete AI assistance scope and CRediT roles appear below.

\section{Illustrative examples}
\subsection{A loading-branch connector table}\label{sec:connector}
The measured \texttt{STWC-1} loading domain is $0\leq u\leq50.005$ mm. \path{validation/connector_exchange.py} exports 33 retained points as nonlinear connector-elasticity data, with force preceding displacement. An excerpt, rounded here to six decimals, is:
\begin{verbatim}
*CONNECTOR ELASTICITY, COMPONENT=1, NONLINEAR
@@CONNECTORROWS@@
\end{verbatim}
Vertical priority gives $\delta=@@CONNECTORDELTA@@$ kN, $E_p=@@CONNECTOREP@@$ J and $E_w=@@CONNECTOREW@@$ J. A separate reader integrates the exported 17-digit values and reproduces the table's work at 10--40 mm. This checks data exchange on the measured loading branch; an assembly analysis would additionally need a constitutive model for unloading. For force-table fidelity, vertical priority or the archived $\delta$-optimal nodes supplied through \path{from_indices} are appropriate: their matched force objective differs from work priority (Table~\ref{tab:selectors}).

\subsection{Specimen queries, repeatability and source indicators}
The PLA+ dataset contains 40 singly tested Latin-hypercube configurations and two triplicate controls, STWC and nominal SCMC: 42 configurations and 46 specimens \cite{Saber2026,Guler2026}. Measured masses and indicators accompany the force histories. Tables constructed with a 1 J interval-work budget retain @@WORKFLOWPOINTS@@ of 46,000 reference nodes. A consumer queries strokes of 10, 20, 30 and 40 mm and the intervening work windows.

At stroke $u$, $EA=W(u)$, $SEA=EA/m$, $MCF=EA/u$ and $CFE=MCF/P(u)$, with $P(u)$ the prefix maximum force. Work intervals propagate through the fixed reported mass and stroke. If the source global maximum is retained at $x_p$, linear interpolation gives $\widehat P(u)=P(u)$ for $u\geq x_p$. WorkCert stores this source-derived summary, checks its retained-node consistency on loading, and recomputes it in \path{verify_reference}. After $x_p$, the CFE interval is $(\widehat W\pm E_p)/(uP)$. Earlier queries combine $\widehat P\pm\delta$ with available source-maximum and retained-node anchors; CFE bounds require a positive lower peak bound. Table~\ref{tab:example} uses the sharper post-peak result.

\begin{table}[!htbp]\small\centering
\caption{Consumer outputs for \texttt{STWC-1}, mass 16.2 g. Units: stroke mm, EA J, SEA kJ/kg and MCF kN.}\label{tab:example}
\begin{tabular}{rrrrrl}\toprule Stroke&EA&SEA&MCF&CFE&CFE interval\\\midrule
@@METRICS@@
\bottomrule\end{tabular}\end{table}

All 184 indicator sets contain their dense-reference values. The largest prefix bound is below the observed EA sample standard deviation in all eight control/stroke comparisons. The closest is nominal SCMC at 10 mm: 0.915 J versus 0.993 J. With three observations per control, these scatter estimates are descriptive. A control-mean interval averages the specimen endpoints, $[\sum_i L_i/3,\sum_i U_i/3]$; deterministic bounds receive no $\sqrt{3}$ reduction. Using these means and the 40 singletons gives 3444 configuration comparisons, 3345 with separate numerical intervals. Experimental distinguishability requires specimen-variability information. A $\pm0.05$ g mass-rounding scenario gives a maximum mass-only relative SEA change of 0.310\% and reduces separated specimen pairs from 4001 to 3937 of 4140.

At the workbook's stated strokes, intervals cover 45 of 46 EA, SEA, MCF and CFE entries and all 46 peak forces. For specimen 05, reference $EA(50)=290.800436$ J; the workbook's 290.865173 J equals integration to 50.009 mm. This endpoint convention explains all 13 nonzero EA discrepancies: archived endpoints are 50.004--50.009 mm, whereas the workbook lists 50 mm. Figure~\ref{fig:workflow} distinguishes nominal-stroke coverage from this endpoint audit.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig02_workflow.pdf}
\caption{Reduced-table reuse: (a) reference and exchanged STWC-1 response; (b) queried EA errors; (c) triplicate-control scatter and reconstruction bounds; (d) EA intervals compared with source-workbook values at the stated strokes. OpenAI Codex assisted the archived plotting code.}\label{fig:workflow}\end{figure}

\subsection{A signed cyclic response}
The stainless-steel bending record contains 125,157 chronological pairs \cite{CyclicDataset2024,CyclicPaper2022}. Exact preprocessing retains 2971 monotone branches and 1984 zero-displacement events. Branch node-count quartiles are 2, 9 and 26, with a maximum of 2555. Ignoring zero steps leaves 1242 direction changes; 67.4\% of the resulting runs span at most 0.1 mm. These are numerical direction changes, rather than a count of loading cycles.

A running-extremum deadband diagnostic detects 94 reversals throughout 0.1--5 mm, consistent with the 47-cycle failure of specimen S1-L1 in Table~3 of \cite{CyclicPaper2022}; its loading protocol is described in Section~2.4. The diagnostic leaves the reference path unchanged (Fig.~\ref{fig:cyclic}) and does not synchronize reversals with unavailable command events.

Branches use work priority, absolute-peak retention, a 129-point cap and interval tolerance $0.001|W_b|$ for directed reference work $W_b$. They retain @@CYCLERETAINED@@ nodes; one reaches the cap before tolerance. Against 92.034 kJ of signed path work, terminal deficit is 68.529 J (0.0745\%), maximum continuous error @@CYCLEERROR@@ J (0.0747\%) and summed interval bound @@CYCLEBOUND@@ J (0.1135\%). Cumulative error rises and falls; its net positive bias is specific to this representation. Descending summaries become $(-d,l-d,h-d)$ before chronological composition, recovering global prefix error from metadata. Signed path work differs from closed-cycle dissipation.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig05_cyclic.pdf}
\caption{Cyclic history, branch sizes, deadband reversal counts and chronological work error. The deadband is diagnostic only; the original path is retained. Shading shows $\pm\sum_b E_{w,b}$. OpenAI Codex assisted the archived plotting code.}\label{fig:cyclic}\end{figure}

\subsection{Selectors and objective-matched optima}
The main comparison uses 23 stainless-steel honeycomb records of commercial grade CX, one enhanced double-arrow honeycomb (EDAH) record and the 46 PLA+ curves \cite{Afkhami2022,Afkhami2023,AfkhamiDataset2022,WuDataset2025,Wu2026,Saber2026}. Cohort summaries accompany pooled values. Preparation rules, including the CX 0.5 kN contact threshold and endpoint at 40\% of the nominal loaded dimension, are executable and archived with the original acquisition records.

Six force selectors are tested at 9, 17, 33, 65 and 129 nodes (Table~\ref{tab:selectors}). RDP uses dimensionless coordinates and a fixed-count best-first rule; VW progressively removes effective-area vertices. Native tolerance implementations are cross-checked against \path{rdp} and \path{simplification}. The archive contains 2100 force tables, 350 work-only tables, 560 stopping cases and 70 scalar controls, with algorithm and peak constraints specified for each comparison.

At 33 nodes, Visvalingam--Whyatt has the lowest pooled median prefix and interval errors among the force selectors (Table~\ref{tab:selectors}). Work priority improves prefix error over vertical priority in 45 of 70 records and over Visvalingam--Whyatt in 33. Accordingly, method selection is explicit, and external nodes can be passed to \path{from_indices}; the software does not prescribe a universally preferred selector.

\begin{table}[!htbp]\small\centering
\caption{Median 33-point errors normalized by $|W(U)|$ over 70 records. The final columns give objective-matched optimality ratios on 58 references with at most 1000 nodes. Plain uniform sampling lacks the common peak constraint and is excluded from these ratios.}\label{tab:selectors}
\begin{tabular}{lrrrr}\toprule Selector&$E_p$ (\%)&$E_w$ (\%)&$\eta/\eta^*$&$\delta/\delta^*$\\\midrule
@@METHODS@@
\bottomrule\end{tabular}\end{table}

Dynamic programming minimizes $\eta$ or $\delta$ with identical endpoint and peak constraints, producing 580 optimal paths across 58 references and all five budgets. At 33 nodes, work priority has median $\eta/\eta^*=1.319$. For the force objective, vertical priority gives $\delta/\delta^*=1.663$, versus 2.615 for work priority. These objective-specific gaps support selector choice; they do not establish prefix-error optimality (Fig.~\ref{fig:selectors}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig03_selectors.pdf}
\caption{Cohort-specific interval errors and objective-matched optimality gaps. OpenAI Codex assisted the archived plotting code.}\label{fig:selectors}\end{figure}

\subsection{Stopping budgets and construction scale}
At the same 1\% interval-work tolerance, $E_w$ stopping retains a median of 14 nodes under work priority, compared with 27 using $\eta$; vertical-priority counts are 15 and 28. Prefix-only results are tabulated separately. Construction-time reference access enables these direct error evaluations.

Synthetic scaling covers $10^3$--$10^6$ samples and three tolerances. Timings use @@HARDWARE@@. At $10^6$ samples and 0.1\% interval tolerance, three independent paired runs take median @@OLDTIME@@ s for version 0.1 and @@NEWTIME@@ s for version 0.2, retaining the same 107 nodes. Whole-reference evaluations fall from 105 to one; small cases incur tree overhead. The archive supplies per-run timings, ranges and host details (Fig.~\ref{fig:scale}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig04_stopping_scaling.pdf}
\caption{Identical interval-work stopping requirements and construction time versus reference size. Boxes show quartiles and medians; whiskers reach the extreme observations within the 1.5-interquartile-range fences, and circles mark outliers. Lines in (b) show single runs; squares and bars at $10^6$ samples show the medians and minimum--maximum ranges of three paired runs. OpenAI Codex assisted the plotting code.}\label{fig:scale}\end{figure}

\section{Impact}
Finite-element analysts can export a chosen-size loading table and inspect both its force deviation and work-query errors before incorporating it in a response model. The connector example separates these two objectives: selecting for force fidelity can require different nodes from selecting for integral accuracy. Existing optimal-node or geometric tools can share the same query and persistence interface.

Experimental-data curators can exchange a reduced record once and support later stroke-dependent EA, SEA, MCF and CFE calculations. Stored bounds identify which close numerical comparisons need finer tables; the source-workbook audit identifies endpoint conventions that refinement cannot resolve. Researchers reusing cyclic records can compose directed branch summaries to recover continuous path-work error without reloading the dense reference. These workflows serve table construction, database reuse and method comparison. Independent laboratory adoption has not yet been documented.

Vertex-subset tables can retain signed area bias. Each branch requires increasing coordinates, with chronology stored separately. Reconstruction errors do not quantify measurement uncertainty; adaptive selection retains $O(nK)$ worst-case scanning cost.

\section{Conclusions}
WorkCert combines reusable force--displacement tables, explicit reconstruction errors and checked persistence. Peak summaries sharpen indicator intervals; source audits distinguish endpoint conventions from reconstruction error. Matched-objective controls guide selector choice, while incremental aggregation and directed branch summaries support large and cyclic references. Archived inputs, programs and outputs reproduce these workflows.

\section*{CRediT authorship contribution statement}
\textbf{Saisai Hou:} Conceptualization, Methodology, Software, Formal analysis, Visualization, Writing -- original draft.
\textbf{Yunzhi Zhu:} Methodology, Validation, Data curation, Writing -- review \& editing.
\textbf{Sen Zhang:} Conceptualization, Supervision, Resources, Writing -- review \& editing, Project administration.
\section*{Declaration of competing interest}
The authors declare no competing interests.
\section*{Funding}
This work was supported by the General Program of Natural Science Research (Basic Science) in Higher Education Institutions of Jiangsu Province (Grant No. 25KJD110002).
\section*{Acknowledgements}
The authors thank the contributors of the public compression and cyclic-loading datasets.
\section*{Data and code availability}
The four CC BY 4.0 experimental sources are \url{https://doi.org/10.17632/8bxkdw4nfw.1}, \url{https://doi.org/10.5281/zenodo.16399749}, \url{https://doi.org/10.17632/v7p6y654ft.4} and \url{https://doi.org/10.5281/zenodo.10829958}. The software repository is \url{https://github.com/changs1723/WorkCert}. The accompanying validation archive contains the fixed inputs, preparation scripts, executable comparisons, per-case outputs and plotting programs. Runtime and research environments are documented separately.
\section*{Declaration of generative AI and AI-assisted technologies in the manuscript preparation process}
@@AI@@
\bibliographystyle{elsarticle-num}{\small\bibliography{references}}
\end{document}
'''

COVER=r'''\documentclass[11pt,a4paper]{article}
\usepackage[margin=25mm]{geometry}\usepackage[T1]{fontenc}\usepackage{mathpazo,hyperref,xurl}
\hypersetup{hidelinks}\setlength{\parindent}{0pt}\setlength{\parskip}{7pt}\setlength{\emergencystretch}{2em}
\begin{document}
3 November 2026

Dear SoftwareX Editors,

Please consider \emph{@@TITLE@@} as an Original Software Publication.

WorkCert provides reconstruction-error metadata and reusable queries for tabulated structural responses. A public-data workflow computes variable-stroke energy-absorption indicators, compares reconstruction errors with repeated-specimen scatter, and checks the reported experimental-workbook indicators. A separate full cyclic-bending history demonstrates directed branches and zero-displacement events.

The implementation accepts nodes from external simplifiers, requires explicit method selection and handles force conventions and unit labels directly. Evaluation includes geometric selectors, exact dynamic-programming controls for matched objectives, continuous work-query checks and million-sample construction tests. The accompanying source contains the original numerical data, preprocessing, comparison and plotting programs, per-case outputs, installation instructions and tests. @@PUBLICLINE@@

\textbf{Use of artificial intelligence.} @@AI@@

The authors are Saisai Hou, Yunzhi Zhu and Sen Zhang, all affiliated with the Department of Public Basic Courses, Nanjing University of Industry Technology. Sen Zhang is the corresponding author. The work is supported by Grant No. 25KJD110002 of the General Program of Natural Science Research (Basic Science) in Higher Education Institutions of Jiangsu Province.

Sincerely,

Sen Zhang\\Corresponding author\\\href{mailto:szhang@niit.edu.cn}{szhang@niit.edu.cn}
\end{document}
'''

DATA_BIB=r'''
@misc{Saber2026,author={Saber, Ahmed},title={Quasi-static compression test dataset of sinusoidally-corrugated multi-cell {PLA+} energy absorbers fabricated by fused deposition modeling ({FDM})},year={2026},publisher={Mendeley Data},doi={10.17632/v7p6y654ft.4},note={Version 4; CC BY 4.0}}
@misc{CyclicDataset2024,author={González-de-León, Isabel and Nastri, Elide and Arrayago, Itsaso and Montuori, Rosario and Piluso, Vincenzo and Real, Esther},title={Experimental load-displacement response of a stainless steel specimen under cyclic loading},year={2024},publisher={Zenodo},doi={10.5281/zenodo.10829958},note={Version 1; CC BY 4.0}}
@article{CyclicPaper2022,author={González-de-León, Isabel and Nastri, Elide and Arrayago, Itsaso and Montuori, Rosario and Piluso, Vincenzo and Real, Esther},title={Experimental study on stainless steel tubular members under cyclic loading},journal={Thin-Walled Structures},year={2022},volume={181},pages={109969},doi={10.1016/j.tws.2022.109969}}
'''

if __name__=='__main__':main()
