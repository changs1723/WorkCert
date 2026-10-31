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
    pla=workflow['pla_exchange']
    cyc=workflow['cyclic_path']
    headline=read('validation/results/scaling/headline_repeats.json')
    install=read('software/release_validation.json')
    q=pd.read_csv(ROOT/'validation/workflow_results/pla_exchange/queries_stage_0.csv')
    selected=q[q.curve=='STWC-1'].sort_values('stroke_mm')
    rows=['%.0f & %.3f & %.3f & %.3f & %.3f & [%.3f, %.3f] \\\\'%(r.stroke_mm,r.reduced_EA_J,r.reduced_SEA_kJ_kg,r.reduced_MCF_kN,r.reduced_CFE,r.CFE_lower,r.CFE_upper) for r in selected.itertuples()]
    methodrows=[]
    for key,label in [('work','Work priority'),('vertical','Vertical priority'),('rdp','RDP, fixed count'),('vw','Visvalingam--Whyatt'),('uniform_peak','Uniform + peak')]:
        v=comparison['ALL']['at33'][key]
        methodrows.append('%s & %.3f & %.3f & %.3f \\\\'%(label,v['prefix_error_percent'],v['window_error_percent'],dp['eta']['33'][key]['median_ratio']))
    # Scaling JSON is deliberately normalized by a separate results collector.
    evidence=read('authoring/final_values.json')
    source=meta.get('permanent_code_url')
    codelink=r'\url{'+source+'}' if source else r'\emph{Revised source version awaiting public verification}'
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
            'WORKFLOWPOINTS':str(pla['stages'][0]['total_retained_points']),
            'MAXEA':'%.3f'%pla['stages'][0]['EA_maximum_absolute_error_J'],
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
\begin{document}\begin{frontmatter}
\title{@@TITLE@@}
\author[inst]{Saisai Hou}\author[inst]{Yunzhi Zhu}\author[inst]{Sen Zhang\corref{cor1}}
\ead{szhang@niit.edu.cn}\cortext[cor1]{Corresponding author.}
\address[inst]{Department of Public Basic Courses, Nanjing University of Industry Technology, Nanjing, China}
\begin{abstract}
Structural-response databases are reused to compare energy absorption at changing displacement limits. WorkCert attaches reconstruction-error metadata to reduced force--displacement tables and supports force, work and interval queries after exchange. It accepts externally selected nodes, preserves explicit units and separates cyclic histories into directed monotone branches. A public-data example computes crashworthiness indicators and resolves design comparisons through selective refinement and targeted source queries. Comparative tests include geometric selectors and objective-matched dynamic programming. For identical interval-work requests, direct error evaluation reduces the median point count at a 1\% tolerance from 27 to 14. Incremental aggregation supports million-point construction. Data, preprocessing, programs and per-case outputs accompany the software.
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
Compression responses collected for one test programme may later be queried at different stroke limits, compared with responses from a new design, or exchanged with a collaborator. Energy absorption (EA), specific energy absorption (SEA), mean crushing force (MCF) and crush-force efficiency (CFE) depend on the selected response window. A terminal scalar serves a fixed request; a reusable response table supports changing limits and retains the force history needed for peak-force queries. The scientific problem addressed here is to preserve that query capability while making the consequences of table reduction explicit.

WorkCert connects a reduced piecewise-linear response to its complete numerical reference through stored integral and force errors. A database producer constructs the table, records its units and source identity, and sends it to a consumer. The consumer can calculate indicators, compare non-overlapping error intervals and request more information only when a comparison remains unresolved. Section~3 implements this exchange using public polymer-absorber measurements and reported specimen masses. WorkCert makes this exchange and evaluation procedure reproducible; direct source integration provides the reference values.

Node selection itself has a substantial literature. Ramer and Douglas--Peucker use geometric deviation \cite{Ramer1972,DouglasPeucker1973}; Visvalingam--Whyatt removes points through effective triangle area \cite{Visvalingam1993}. Time-series segmentation includes sliding-window, top-down and bottom-up approaches \cite{Keogh2001}. Optimal polygonal approximation depends on the chosen error criterion and constraints \cite{Imai1988}. Existing Python tools include \path{rdp}, \path{simplification} and \path{shapely.simplify} \cite{rdpSoftware,Hugel2021,ShapelySoftware}. WorkCert adds reference-relative integral-error evaluation, directed-branch handling, query primitives and checked persistence to this ecosystem. Its \path{from_indices} interface accepts nodes produced by other selectors, so applications can choose a simplifier separately from the error and query layer.

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

The selector is explicit. Work and vertical priorities split an interval at its largest vertical residual and differ in how they prioritize intervals. Uniform alternatives are also available. Endpoints are retained. Peak modes preserve the maximum absolute force, maximum signed force or minimum signed force. Nonnegative node values give a nonnegative linear interpolant. Labels describe native units without rescaling; omitted labels remain unspecified. The engineering example supplies mm and kN explicitly, giving work in J.

Tolerance stopping evaluates each current representation because a greedy refinement need not decrease its error. An augmented balanced tree stores each interval's cumulative residual-work primitive initialized at zero: its terminal value $d$, minimum $l$ and maximum $h$, together with absolute area and force deviation. Concatenating intervals $A$ and $B$ gives
\begin{equation}
d=d_A+d_B,\quad l=\min(l_A,d_A+l_B),\quad h=\max(h_A,d_A+h_B).
\end{equation}
Only the two new interval summaries and their tree ancestors change after a split. Aggregation costs $O(\log K)$ per insertion and uses $O(K)$ tree storage; residual scans still give $O(nK)$ worst-case selection work. The final representation is checked by a complete reference evaluation. Relative bounds divide by absolute terminal work; zero terminal work requires absolute tolerances.

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
The executable \path{examples/query_exchange.py} additionally calculates prefix peaks, CFE and propagated intervals. Its input consists of one received JSON file, the mass and requested strokes. A recorded independent consumer check reproduces 28 producer quantities across the four strokes to within $1.8\times10^{-15}$ in their reported units.

\subsection{Verification and AI-assisted implementation}\label{sec:verification}
The @@TESTS@@ package tests cover analytical errors, cancellation, interior extrema, arbitrary-node integration, branch orientation, source identity, persistence, unit labels, peak conventions and the CLI. @@PLATFORMS@@ @@CISTATUS@@ Exact dynamic-programming results are independently checked by exhaustive small-reference enumeration. The archived benchmark verifies actual serialized tables, query errors and source hashes.

OpenAI Codex (OpenAI; local CLI version 0.166.0-alpha.5.1) assisted research planning and drafted implementations of the reconstruction-error routines, incremental tree, selectors, preprocessing, validation and plotting programs. Numerical checks use analytical fixtures, an independent primitive, exhaustive enumeration and third-party simplification libraries. Source acquisition and preparation are scripted; plotting programs read the archived numerical outputs directly. The source tree, input hashes, environment records and executable checks specify the reproducible computational workflow. The complete scope of AI assistance is declared at the end of the article; human contribution roles are stated in CRediT.

\section{Illustrative examples}
\subsection{Exchange and variable-stroke design screening}
The database example uses 46 poly(lactic acid)-based (PLA+) absorber curves and measured masses deposited by Saber \cite{Saber2026}. A producer constructs tables under an absolute interval-work budget of 1 J. The consumer requests four strokes, 10, 20, 30 and 40 mm, and three intervening work windows. These strokes lie within every specimen's reported assessment window. The source workbook's terminal indicators use its specified maximum displacement, which can differ from the complete archived curve endpoint; the preprocessing audit retains this distinction.

At stroke $u$, the consumer calculates $EA=W(u)$, $SEA=EA/m$, $MCF=EA/u$ and $CFE=MCF/P(u)$, where $P(u)$ is the peak force up to that stroke. The interval $\widehat W(u)\pm E_p$ propagates directly to SEA and MCF for the fixed reported mass. The force-error bound gives $|P(u)-\widehat P(u)|\leq\delta$ and provides a CFE interval when its lower denominator is positive. Table~\ref{tab:example} gives actual outputs for one exchanged response. Every requested EA, SEA, MCF and CFE reference value lies within its reported interval.

\begin{table}[!htbp]\small\centering
\caption{Consumer outputs for \texttt{STWC-1}, mass 16.2 g, from the initial 1 J table. Units: stroke mm, EA J, SEA kJ/kg and MCF kN.}\label{tab:example}
\begin{tabular}{rrrrrl}\toprule Stroke&EA&SEA&MCF&CFE&CFE interval\\\midrule
@@METRICS@@
\bottomrule\end{tabular}\end{table}

The initial library retains @@WORKFLOWPOINTS@@ nodes from 46,000 reference nodes and resolves 4001 of 4140 pairwise SEA comparisons across the four strokes (Fig.~\ref{fig:workflow}). Maximum queried EA error is @@MAXEA@@ J. Responses involved in comparisons with overlapping SEA intervals are then rebuilt at 0.25 J and 0.0625 J budgets. The resolved counts rise to 4107 and 4129. Fourteen responses reach the 129-point cap at the last stage, and their actual error metadata remain available. The remaining eleven comparisons are answered through 22 requested source-work scalars. This final targeted exchange resolves all 4140 comparisons without an incorrect resolved ordering. Full arrays, intermediate tables, client outputs and scalar requests are retained.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig02_workflow.pdf}
\caption{Public-data exchange: (a) a reference response and its reduced table; (b) client energy-absorption queries and their error bounds; (c) unresolved SEA comparisons after each stage; and (d) node allocations across the table collection. OpenAI Codex assisted the archived plotting code.}\label{fig:workflow}\end{figure}

\subsection{A signed cyclic response}
A separate stainless-steel rectangular hollow-section bending record contains 125,157 force--displacement pairs \cite{CyclicDataset2024,CyclicPaper2022}. Its full chronological path includes positive and negative forces, reversals and dwells. Preprocessing produces 2971 monotone branches and 1984 zero-displacement events, covering each original chronological interval exactly once. Branch-work sums agree with the original signed trapezoidal path integral to floating-point precision.

Each branch uses work priority, absolute-force peak retention and a maximum of 129 retained nodes. Its absolute interval-work tolerance is $0.001|W_b|$, where $W_b$ is the directed source work on that branch. Reduction retains @@CYCLERETAINED@@ branch nodes; one branch reaches the cap before meeting its assigned tolerance. Maximum continuous chronological work error is @@CYCLEERROR@@ J, bounded by the sum of stored branch-window bounds, @@CYCLEBOUND@@ J (Fig.~\ref{fig:cyclic}). Direction changes and dwell events remain explicit. The reported quantity is signed path work; no closed-cycle dissipation is inferred. This record is assessed separately from the compression collection.

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig05_cyclic.pdf}
\caption{Full cyclic loading history, a directed branch and chronological work reconstruction. Shading in (c) shows $\pm\sum_b E_{w,b}$. OpenAI Codex assisted the archived plotting code.}\label{fig:cyclic}\end{figure}

\section{Impact}
\subsection{Research tasks and intended users}
WorkCert supports researchers curating structural-test databases and analysts comparing responses at changing travel limits. The demonstrated improvement is an explicit route from an exchanged table to indicator intervals, unresolved comparisons, selective refinement and targeted source queries. A user can assess how many design decisions survive a chosen representation budget and determine which source responses require another query. These operations are reproducible from the saved files, including cases that reach a point cap. A fixed terminal indicator can be served by its exact scalar, as in the follow-up exchange.

The examples establish this workflow on public measurements. Independent laboratory adoption and commercial deployment have not been documented.

\subsection{Selectors and objective-matched optima}
The main comparison uses 23 stainless-steel honeycomb records of commercial grade CX, one enhanced double-arrow honeycomb (EDAH) record and the 46 PLA+ curves \cite{Afkhami2022,Afkhami2023,AfkhamiDataset2022,WuDataset2025,Saber2026}. Cohort summaries accompany pooled values. Preparation rules, including the CX 0.5 kN contact threshold and endpoint at 40\% of the nominal loaded dimension, are executable and archived with the original acquisition records.

Six force selectors are tested at five point budgets. Geometric RDP uses dimensionless displacement and force coordinates; its fixed-count best-first form and peak constraints are specified in the benchmark. Visvalingam--Whyatt uses progressive effective-area elimination. Native tolerance implementations are cross-checked against \path{rdp} and \path{simplification}. The complete comparison contains 2100 force tables, 350 work-only tables, 560 stopping cases and 70 scalar controls. The work-only control serves integral queries without providing the same retained force response.

At 33 nodes, Visvalingam--Whyatt has the lowest pooled median prefix and interval errors among the force selectors (Table~\ref{tab:selectors}). Work priority improves prefix error over vertical priority in 45 of 70 records and over Visvalingam--Whyatt in 33. Accordingly, method selection is explicit, and external nodes can be passed to \path{from_indices}; the software does not prescribe a universally preferred selector.

\begin{table}[!htbp]\small\centering
\caption{Median 33-point errors over 70 compression records. The final column compares each selector's absolute-area cost with its exact fixed-count optimum on the 58 eligible original references with at most 1000 nodes.}\label{tab:selectors}
\begin{tabular}{lrrr}\toprule Selector&$E_p/|W(U)|$ (\%)&$E_w/|W(U)|$ (\%)&$\eta/\eta^*$ (58)\\\midrule
@@METHODS@@
\bottomrule\end{tabular}\end{table}

The optimal controls minimize additive area cost $\eta$ or maximum vertical error $\delta$ with identical endpoint and peak constraints. They use exact interval costs and fixed-count dynamic programming, producing 464 optimal paths across 58 references and four budgets. At 33 nodes, work priority's median $\eta/\eta^*$ is 1.319, whereas vertical priority's median $\delta/\delta^*$ is 1.663. These ratios quantify greedy gaps for their respective objectives. Prefix error depends on cumulative signed residuals and is reported separately, without an optimality claim (Fig.~\ref{fig:selectors}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig03_selectors.pdf}
\caption{Cohort-specific interval errors and objective-matched optimality gaps. OpenAI Codex assisted the archived plotting code.}\label{fig:selectors}\end{figure}

\subsection{Stopping budgets and construction scale}
For the same requirement on every work interval, a 1\% tolerance using $E_w$ retains a median of 14 nodes under work priority, compared with 27 using $\eta$. The corresponding vertical-priority counts are 15 and 28. Prefix-only requests have a different requirement and are reported in their own tables. Direct evaluation tightens stopping decisions because the full reference is already available during construction.

Incremental aggregation addresses repeated whole-reference evaluation. A deterministic synthetic scaling study covers $10^3$ to $10^6$ samples and three tolerances, separately from the experimental validation. At $10^6$ samples and a 0.1\% interval-work tolerance, three independent paired runs take a median @@OLDTIME@@ s for version 0.1 and @@NEWTIME@@ s for version 0.2; ranges are [@@OLDMIN@@, @@OLDMAX@@] and [@@NEWMIN@@, @@NEWMAX@@] s on the recorded @@SCALEENV@@ environment. Both retain 107 nodes. Whole-reference error evaluations fall from 105 to one. Small cases can incur tree overhead. The source signal, complete timings and retained-node checks accompany the results (Fig.~\ref{fig:scale}).

\begin{figure}[!htbp]\centering\includegraphics[width=\linewidth]{figures/fig04_stopping_scaling.pdf}
\caption{Identical interval-work stopping requirements and construction time versus reference size. Boxes show quartiles and medians; whiskers reach the extreme observations within the 1.5-interquartile-range fences, and circles mark outliers. Lines in (b) show single runs; squares and bars at $10^6$ samples show the medians and minimum--maximum ranges of three paired runs. OpenAI Codex assisted the plotting code.}\label{fig:scale}\end{figure}

\section{Conclusions}
WorkCert links reusable response tables to explicit force and work reconstruction errors. The database exchange demonstrates how these quantities support variable-stroke indicators, design comparisons and requests for additional source information. External selectors, directed branches and native-unit labels extend the workflow beyond one greedy algorithm and one loading convention. Objective-matched comparisons expose the limits of point selection, while incremental aggregation improves large-reference construction. The release supplies the data, preparation programs, tests, examples and numerical outputs needed to inspect and reproduce these operations.

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
The four experimental sources use CC BY 4.0 licenses and retain their creator attribution. @@PUBLICLINE@@
The repository and accompanying validation archive contain source workbooks and acquisition records, preparation scripts, per-case outputs, optimal-path controls and plotting programs. Runtime installation and the research reproduction environment are documented separately.
\section*{Declaration of generative AI and AI-assisted technologies in the manuscript preparation process}
@@AI@@
\bibliographystyle{elsarticle-num}\bibliography{references}
\end{document}
'''

COVER=r'''\documentclass[11pt,a4paper]{article}
\usepackage[margin=25mm]{geometry}\usepackage[T1]{fontenc}\usepackage{mathpazo,hyperref,xurl}
\hypersetup{hidelinks}\setlength{\parindent}{0pt}\setlength{\parskip}{7pt}\setlength{\emergencystretch}{2em}
\begin{document}
31 October 2026

Dear SoftwareX Editors,

Please consider \emph{@@TITLE@@} as an Original Software Publication.

WorkCert provides reconstruction-error metadata and reusable queries for tabulated structural responses. Its application is illustrated through a complete public-data exchange: a database producer sends reduced compression tables, a consumer computes variable-stroke energy-absorption indicators, and unresolved design comparisons trigger selective refinement or targeted source queries. A separate full cyclic-bending history demonstrates directed branches and zero-displacement events.

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
