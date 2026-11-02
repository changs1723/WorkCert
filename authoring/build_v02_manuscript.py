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
            'TESTS':str(evidence['package_tests']), 'PLATFORMS':evidence['tested_platform_statement'],
            'CISTATUS':evidence['ci_statement'],
            'SCALEENV':evidence['scaling_platform'],
            'WORKFLOWPOINTS':str(pla['retained_nodes']),
            'MAXEA':'%.3f'%pla['maximum_actual_EA_error_J'],
            'CYCLERETAINED':format(cyc['sum_retained_branch_nodes'],','),
            'CYCLEERROR':'%.2f'%cyc['maximum_continuous_chronological_work_error_J'],
            'CYCLEBOUND':'%.2f'%cyc['sum_branch_window_bounds_J'],
            'PUBLICLINE':('The fixed public source version is '+r'\url{'+source+'}.') if source else ''}
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
WorkCert attaches reconstruction-error metadata to reduced force--displacement tables used for structural-response queries. Its Python interface combines explicit point budgets, interchangeable selectors, checked persistence and directed cyclic branches. A public-data workflow evaluates energy-absorption indicators for 46 specimens representing 42 configurations, compares reconstruction errors with control-specimen scatter, and checks the reported workbook indicators. Preserved peaks tighten crush-force-efficiency intervals. Comparative tests include geometric selectors and exact dynamic-programming controls. For the same interval-work requirement, direct error evaluation reduces median point counts from 27 to 14. Incremental aggregation supports million-point references. Inputs, preprocessing, numerical outputs and plotting programs accompany the software.
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
Structural-response data are frequently converted into tabulated laws for subsequent calculations. In the documented Abaqus bushing-calibration workflow, reaction-force and relative-motion histories define connector behavior in a later assembly analysis \cite{AbaqusBushing}. Such reuse makes the accuracy of a chosen table a practical numerical question. WorkCert evaluates the force and work errors introduced by a user-specified point budget. The budget is an application choice. An accompanying example writes a 33-point nonlinear connector table and checks its coordinates and work queries with a separate reader on the loading domain.

Energy absorption (EA), specific energy absorption (SEA), mean crushing force (MCF) and crush-force efficiency (CFE) depend on the selected stroke. A reusable table supports changing limits and peak queries while retaining explicit numerical error information. The public-data example here is small enough to exchange in full. Its purpose is to evaluate reduced-table fidelity and its relation to specimen variability, with the complete source retained for audit.

Geometric simplification includes Ramer and Douglas--Peucker, Visvalingam--Whyatt, and sliding-window, top-down and bottom-up segmentation \cite{Ramer1972,DouglasPeucker1973,Visvalingam1993,Keogh2001}. Optimal polygonal approximation depends on its objective \cite{Imai1988}. Sum-, max- and difference-area objectives are established in area-based simplification \cite{Bose2006,Daneshpajouh2012}. WorkCert combines these residual summaries with exact continuous work-query extrema, persistence and branch handling. It accepts external selections and provides strict coordinate-to-index mapping for geometric tools such as \path{rdp}, \path{simplification} and \path{shapely.simplify} \cite{rdpSoftware,Hugel2021,ShapelySoftware}.

\section{Software description}
\subsection{Software architecture}
The package separates input checks, node selection, error evaluation, query construction, serialization and branch preprocessing (Fig.~\ref{fig:architecture}). NumPy is its only runtime dependency. Research scripts, plotting tools and source datasets are outside the runtime package. The Python API and command line expose explicit selection methods, units and stopping criteria. Response arrays have immutable backing storage, keeping their coordinates consistent with cached primitives.

A JSON response stores retained coordinates, reference indices, unit labels, reconstruction errors, provenance and a versioned schema. A source hash identifies the complete float64 reference. A payload digest checks accidental file changes; \path{verify_reference} compares a received table with the corresponding source and recomputes its errors. Loading also validates internal numerical relationships. These checks support reproducible exchange between the construction and query stages.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig01_architecture.pdf}
\caption{Producer, exchange and consumer stages. OpenAI Codex (OpenAI, local CLI version 0.166.0-alpha.5.1) assisted the Python code for this explanatory diagram.}\label{fig:architecture}\end{figure}

\subsection{Software functionalities}
Let $F$ be the supplied piecewise-linear reference with $n$ nodes on $[0,U]$ and $\widehat F$ the interpolant through $K$ retained nodes, with the initial coordinate shifted to zero for notation. Define $r=F-\widehat F$ and $D(u)=\int_0^u r(s)\,ds$. WorkCert evaluates
\begin{align}
\eta&=\int_0^U|r(s)|\,ds,&\xi&=(\eta+|D(U)|)/2,\\
E_p&=\max_{0\leq u\leq U}|D(u)|,&E_w&=\max D-\min D,\qquad
\delta=\max|r|.
\end{align}
For any interval $[a,b]$, the reconstruction error in work equals $D(b)-D(a)$. Thus $E_p$ and $E_w$ are the exact continuous prefix and interval maxima of the specified piecewise-linear references, evaluated analytically in float64; $\eta$ and $\xi$ are conservative bounds. All satisfy $E_p\leq E_w\leq\xi\leq\eta$. The metadata describe numerical reconstruction rather than measurement uncertainty. Reference nodes and interior residual zeros determine the extrema, including extrema missed by a query grid.

The selector is explicit. Work and vertical priorities split an interval at its largest vertical residual and differ in how they prioritize intervals. Effective-area Visvalingam--Whyatt and uniform alternatives are also available. Endpoints are retained. Peak modes preserve the maximum absolute force, maximum signed force or minimum signed force. Nonnegative node values give a nonnegative linear interpolant. Labels describe native units without rescaling; omitted labels remain unspecified. The engineering example supplies mm and kN explicitly, giving work in J.

Tolerance stopping evaluates each current representation because a greedy refinement need not decrease its error. An augmented balanced tree stores each interval's cumulative residual-work primitive initialized at zero: its terminal value $d$, minimum $l$ and maximum $h$, together with absolute area and force deviation. Concatenating intervals $A$ and $B$ gives
\begin{equation}
d=d_A+d_B,\quad l=\min(l_A,d_A+l_B),\quad h=\max(h_A,d_A+h_B).
\end{equation}
Only the two new interval summaries and their tree ancestors change after a split. Aggregation costs $O(\log K)$ per insertion and uses $O(K)$ tree storage; residual scans still give $O(nK)$ worst-case selection work. The final representation is checked by a complete reference evaluation. Relative bounds divide by absolute terminal work; zero terminal work requires absolute tolerances. The VW selector uses $O(n\log n)$ time and $O(n)$ storage.

Queries use cached node primitives and binary interval searches. Prefix work is quadratic within a retained linear-force segment, and interval work is the difference between two primitives. Non-finite and out-of-domain requests raise errors. For cyclic records, \path{split_monotone_branches} retains chronological direction, reversal endpoints and equal-displacement events. A descending branch is stored with increasing coordinates but queried with its original start and end, preserving the sign of $\int F\,dx$. Equal-displacement force changes contribute zero work and remain separate events. The procedure does not fold hysteresis into a single-valued envelope.

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
The executable \path{examples/query_exchange.py} additionally evaluates peaks, CFE and their intervals from the received JSON. This client--producer agreement checks interoperability. A separate comparison uses indicators supplied in the original experimental workbook. The API parameter name \path{certificate=} is retained for compatibility and selects the reconstruction-error quantity.

\subsection{Verification and AI-assisted implementation}\label{sec:verification}
The @@TESTS@@ package tests cover analytical errors, cancellation, interior extrema, arbitrary-node integration, branch orientation, source identity, persistence, unit labels, peak conventions and the CLI. @@PLATFORMS@@ @@CISTATUS@@ Exact dynamic-programming results are checked against exhaustive small-reference enumeration and analytical interval costs. The archived benchmark verifies actual serialized tables, query errors and source hashes.

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted research planning and drafted implementations of the reconstruction-error routines, incremental tree, selectors, preprocessing, validation and plotting programs. Numerical checks use analytical fixtures, exact rational integration, exhaustive enumeration and third-party simplification libraries. Source acquisition and preparation are scripted; plotting programs read the archived numerical outputs directly. The source tree, input hashes, environment records and executable checks specify the reproducible computational workflow. Saisai Hou independently wrote verification tests; Yunzhi Zhu checked dynamic-programming results against exhaustive enumeration; Sen Zhang reviewed the full manuscript. The distributed automated suite was developed within the AI-assisted workflow. The complete assistance scope is declared at the end of the article, and author roles are stated in CRediT.

\section{Illustrative examples}
\subsection{Specimen queries, repeatability and source indicators}
The PLA+ dataset contains 40 singly tested Latin-hypercube configurations and two triplicate controls, STWC and nominal SCMC: 42 configurations and 46 specimens \cite{Saber2026,Guler2026}. Measured masses and indicators accompany the force histories. Tables constructed with a 1 J interval-work budget retain @@WORKFLOWPOINTS@@ of 46,000 reference nodes. A consumer queries strokes of 10, 20, 30 and 40 mm and the intervening work windows.

At stroke $u$, $EA=W(u)$, $SEA=EA/m$, $MCF=EA/u$ and $CFE=MCF/P(u)$, with $P(u)$ the prefix maximum force. Work intervals propagate through the fixed reported mass and stroke. If the source global maximum is retained at $x_p$, linear interpolation gives $\widehat P(u)=P(u)$ for $u\geq x_p$. WorkCert stores this source-derived summary, checks its retained-node consistency on loading, and recomputes it in \path{verify_reference}. After $x_p$, the CFE interval is $(\widehat W\pm E_p)/(uP)$. Earlier queries combine $\widehat P\pm\delta$ with available source-maximum and retained-node anchors; CFE bounds require a positive lower peak bound. Table~\ref{tab:example} uses the sharper post-peak result.

\begin{table}[!htbp]\small\centering
\caption{Consumer outputs for \texttt{STWC-1}, mass 16.2 g. Units: stroke mm, EA J, SEA kJ/kg and MCF kN.}\label{tab:example}
\begin{tabular}{rrrrrl}\toprule Stroke&EA&SEA&MCF&CFE&CFE interval\\\midrule
@@METRICS@@
\bottomrule\end{tabular}\end{table}

All 184 requested indicator sets contain their dense-reference values. Across the two triplicate controls and four strokes, the largest stored prefix bound is below the observed sample EA standard deviation in all eight comparisons. Those deviations range from 0.993 to 3.350 J. These are descriptive estimates for the two controls, with no variance assigned to the 40 singleton designs. Averaging the triplicate controls produces 3444 configuration-level comparisons, using control means and singleton values; 3345 have separate reconstruction intervals at 1 J. Their numerical separation alone does not establish experimental distinguishability. A separate $\pm0.05$ g rounding sensitivity is provided for masses reported to 0.1 g.

External checks evaluate the workbook indicators at its stated assessment strokes. The intervals cover 45 of 46 EA, SEA, MCF and CFE entries, and all 46 peak forces. For specimen 05, the dense-reference $EA(50)$ is 290.800436 J and the workbook value is 290.865173 J. The latter equals integration to the archived endpoint, 50.009 mm. The same endpoint convention explains all 13 nonzero EA discrepancies: their terminal displacements are 50.004--50.009 mm whereas the workbook lists 50 mm. Nominal-stroke coverage and this endpoint audit are reported separately (Fig.~\ref{fig:workflow}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig02_workflow.pdf}
\caption{Reduced-table reuse: (a) reference and exchanged STWC-1 response; (b) queried EA errors; (c) triplicate-control scatter and reconstruction bounds; (d) EA intervals compared with source-workbook values at the stated strokes. OpenAI Codex assisted the archived plotting code.}\label{fig:workflow}\end{figure}

\subsection{A signed cyclic response}
The stainless-steel bending record contains 125,157 chronological pairs \cite{CyclicDataset2024,CyclicPaper2022}. Exact preprocessing retains 2971 monotone branches and 1984 zero-displacement events. Branch node-count quartiles are 2, 9 and 26, with a maximum of 2555. Ignoring zero steps leaves 1242 direction changes; 67.4\% of the resulting runs span at most 0.1 mm. These are numerical direction changes, rather than a count of loading cycles.

A running-extremum deadband diagnostic detects 94 reversals throughout the range 0.1--5 mm, consistent with the paper's 47-cycle failure record. The command history is unavailable for event-by-event attribution. This diagnostic does not filter or merge the reference path, so its reconstruction errors continue to refer to the original observations (Fig.~\ref{fig:cyclic}).

Each branch uses work priority, absolute-peak retention, a 129-point cap and interval tolerance $0.001|W_b|$, where $W_b$ is the directed reference branch work. The tables retain @@CYCLERETAINED@@ nodes; one branch reaches the cap before meeting tolerance. Reference signed path work is 92.034 kJ. Terminal reconstruction deficit is 68.529 J (0.0745\%); maximum continuous error is @@CYCLEERROR@@ J (0.0747\%), below the summed interval bound @@CYCLEBOUND@@ J (0.1135\%). The cumulative error has both increasing and decreasing increments. Its net positive bias is an observed property of this representation, not a universal sign rule for vertex-subset interpolation. Descending branches transform their summaries to $(-d,l-d,h-d)$ before chronological composition. This recovers the exact global prefix error from stored metadata without summing branch bounds. Signed path work is kept distinct from closed-cycle dissipation.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig05_cyclic.pdf}
\caption{Cyclic history, branch sizes, deadband reversal counts and chronological work error. The deadband is diagnostic only; the original path is retained. Shading shows $\pm\sum_b E_{w,b}$. OpenAI Codex assisted the archived plotting code.}\label{fig:cyclic}\end{figure}

\section{Impact}
\subsection{Research tasks and intended users}
WorkCert supports structural-data curators and analysts building tabulated response models. Its contribution is a queryable reduced representation with explicit reference-relative errors. The examples connect those errors to common indicators, repeated-specimen scatter, source-protocol checks and cyclic path accounting. Fixed terminal indicators can be stored directly; reusable tables support varying strokes and force queries. The supplied public-data workflows establish numerical functionality; external laboratory adoption has not been documented.

Vertex-subset interpolation can retain a signed area bias. Each stored branch requires increasing coordinates, while the branch sequence preserves cyclic chronology. Measurement uncertainty is separate from reconstruction, and adaptive refinement retains $O(nK)$ worst-case scanning cost. These properties delimit the error information returned by the software.

\subsection{Selectors and objective-matched optima}
The main comparison uses 23 stainless-steel honeycomb records of commercial grade CX, one enhanced double-arrow honeycomb (EDAH) record and the 46 PLA+ curves \cite{Afkhami2022,Afkhami2023,AfkhamiDataset2022,WuDataset2025,Wu2026,Saber2026}. Cohort summaries accompany pooled values. Preparation rules, including the CX 0.5 kN contact threshold and endpoint at 40\% of the nominal loaded dimension, are executable and archived with the original acquisition records.

Six force selectors are tested at 9, 17, 33, 65 and 129 nodes; all six appear in Table~\ref{tab:selectors}. Geometric RDP uses dimensionless displacement and force coordinates; its fixed-count best-first form and peak constraints are specified in the benchmark. Visvalingam--Whyatt uses progressive effective-area elimination. Native tolerance implementations are cross-checked against \path{rdp} and \path{simplification}. The complete comparison contains 2100 force tables, 350 work-only tables, 560 stopping cases and 70 scalar controls. The work-only control serves integral queries without providing the same retained force response.

At 33 nodes, Visvalingam--Whyatt has the lowest pooled median prefix and interval errors among the force selectors (Table~\ref{tab:selectors}). Work priority improves prefix error over vertical priority in 45 of 70 records and over Visvalingam--Whyatt in 33. Accordingly, method selection is explicit, and external nodes can be passed to \path{from_indices}; the software does not prescribe a universally preferred selector.

\begin{table}[!htbp]\small\centering
\caption{Median 33-point errors normalized by $|W(U)|$ over 70 records. The final columns give objective-matched optimality ratios on 58 references with at most 1000 nodes. Plain uniform sampling lacks the common peak constraint and is excluded from these ratios.}\label{tab:selectors}
\begin{tabular}{lrrrr}\toprule Selector&$E_p$ (\%)&$E_w$ (\%)&$\eta/\eta^*$&$\delta/\delta^*$\\\midrule
@@METHODS@@
\bottomrule\end{tabular}\end{table}

The optimal controls minimize additive area cost $\eta$ or maximum vertical error $\delta$ with identical endpoint and peak constraints. They use exact interval costs and fixed-count dynamic programming, producing 580 optimal paths across 58 references and all five budgets, including 129 nodes. At 33 nodes, work priority's median $\eta/\eta^*$ is 1.319, whereas vertical priority's median $\delta/\delta^*$ is 1.663. These ratios quantify greedy gaps for their respective objectives. Prefix error depends on cumulative signed residuals and is reported separately, without an optimality claim (Fig.~\ref{fig:selectors}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig03_selectors.pdf}
\caption{Cohort-specific interval errors and objective-matched optimality gaps. OpenAI Codex assisted the archived plotting code.}\label{fig:selectors}\end{figure}

\subsection{Stopping budgets and construction scale}
For the same requirement on every work interval, a 1\% tolerance using $E_w$ retains a median of 14 nodes under work priority, compared with 27 using $\eta$. The corresponding vertical-priority counts are 15 and 28. Prefix-only requests have a different requirement and are reported in their own tables. Direct evaluation tightens stopping decisions because the full reference is already available during construction.

Incremental aggregation addresses repeated whole-reference evaluation. A deterministic synthetic scaling study covers $10^3$ to $10^6$ samples and three tolerances, separately from the experimental validation. At $10^6$ samples and a 0.1\% interval-work tolerance, three independent paired runs take a median @@OLDTIME@@ s for version 0.1 and @@NEWTIME@@ s for version 0.2; ranges are [@@OLDMIN@@, @@OLDMAX@@] and [@@NEWMIN@@, @@NEWMAX@@] s on the recorded @@SCALEENV@@ environment. Both retain 107 nodes. Whole-reference error evaluations fall from 105 to one. Small cases can incur tree overhead. The source signal, complete timings and retained-node checks accompany the results (Fig.~\ref{fig:scale}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig04_stopping_scaling.pdf}
\caption{Identical interval-work stopping requirements and construction time versus reference size. Boxes show quartiles and medians; whiskers reach the extreme observations within the 1.5-interquartile-range fences, and circles mark outliers. Lines in (b) show single runs; squares and bars at $10^6$ samples show the medians and minimum--maximum ranges of three paired runs. OpenAI Codex assisted the plotting code.}\label{fig:scale}\end{figure}

\section{Conclusions}
WorkCert provides reusable force--displacement tables with explicit reconstruction errors. Peak retention sharpens indicator intervals, while source-workbook audits distinguish reconstruction from assessment conventions. Repeat measurements place numerical resolution in an experimental context. Interchangeable selectors and objective-matched controls expose approximation trade-offs; incremental aggregation and chronological branch summaries support larger references and signed paths. The accompanying inputs, programs and outputs make these operations reproducible.

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
2 November 2026

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
