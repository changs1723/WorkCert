"""Data-linked v0.2 figures; no generated experimental imagery."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'software/src'))
from workcert import ReducedResponse
OUT=ROOT/'figures';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.labelsize':9,'legend.fontsize':8,
                     'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
COL={'work':'#0072b2','vertical':'#009e73','rdp':'#cc79a7','vw':'#d55e00','uniform_peak':'#777777','uniform':'#b3b3b3'}
LABEL={'work':'Work','vertical':'Vertical','rdp':'RDP','vw':'VW','uniform_peak':'Uniform + peak','uniform':'Uniform'}
manifest=[]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf8'))
def export(fig,name):
    for suffix in ('pdf','png','tiff'):
        path=OUT/(name+'.'+suffix)
        opts={'bbox_inches':'tight','pad_inches':.08}
        if suffix=='png':opts['dpi']=180
        if suffix=='tiff':opts.update(dpi=600,pil_kwargs={'compression':'tiff_lzw'})
        fig.savefig(path,**opts)
        manifest.append({'file':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,
                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    plt.close(fig)

def architecture():
    fig,ax=plt.subplots(figsize=(7,3.4));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    for x,text in [(.245,'DATABASE PRODUCER'),(.755,'TABLE CONSUMER')]:ax.text(x,.98,text,ha='center',va='top',fontweight='bold',color='#234a64')
    boxes=[(.03,.68,'Source and preparation\nReference, units and measured mass\nChronological branches if cyclic'),
           (.03,.37,'Construct or import nodes\nExplicit selector / external indices\nReconstruction errors and source hash'),
           (.03,.06,'Save exchange JSON\nForce table, cached work primitives\nUnit labels and error metadata'),
           (.54,.06,'Load received response\nJSON plus reported specimen mass\nClient queries use the table only'),
           (.54,.37,'Evaluate requested strokes\nEA / SEA / MCF / CFE intervals\nArbitrary work-window requests'),
           (.54,.68,'Audit indicators and comparisons\nReconstruction versus repeat scatter\nPublished-workbook cross-check')]
    for x,y,text in boxes:
        ax.add_patch(FancyBboxPatch((x,y),.43,.23,boxstyle='round,pad=.008',facecolor='#eef4f8' if x<.5 else '#fff4e6',edgecolor='#7090a4',lw=.8))
        ax.text(x+.215,y+.115,text,ha='center',va='center',fontsize=8.6,linespacing=1.3)
    for a,b in [((.245,.67),(.245,.61)),((.245,.36),(.245,.30)),((.47,.175),(.53,.175)),((.755,.30),(.755,.36)),((.755,.61),(.755,.67))]:
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'->','lw':1.1,'color':'#34586d'})
    ax.annotate('',xy=(.47,.795),xytext=(.53,.795),arrowprops={'arrowstyle':'->','linestyle':'--','lw':1,'color':'#8f5c25'})
    export(fig,'fig01_architecture')

def workflow():
    folder=ROOT/'validation/workflow_results_round2'
    raw=pd.read_csv(ROOT/'data/prepared/PLA_STWC-1.csv',float_precision='round_trip')
    tab=ReducedResponse.load(folder/'tables/STWC-1.json')
    q=pd.read_csv(folder/'queries.csv');q=q[q.specimen=='STWC-1'].sort_values('stroke_mm')
    summary=read('validation/workflow_results_round2/summary.json')
    fig,axes=plt.subplots(2,2,figsize=(7,4.9),constrained_layout=True)
    a=axes[0,0];a.plot(raw.x_mm,raw.force_kN,color='#333333',lw=1.45,label='Reference')
    a.plot(tab.x,tab.force,color='#d55e00',ls='--',marker='o',ms=3,mfc='white',mew=.8,lw=1,label='Exchanged table')
    a.set(xlabel='Travel (mm)',ylabel='Force (kN)',title='(a) STWC-1 response');a.legend(frameon=False,loc='upper right')
    a=axes[0,1];a.axhspan(0,tab.certificate.prefix,color='#d7e9f5',label='Stored prefix-error bound')
    a.plot(q.stroke_mm,q.EA_error_J,'o-',color='#0072b2',label='Actual EA error')
    a.set(xlabel='Requested stroke (mm)',ylabel='Absolute EA error (J)',title='(b) Client work queries',xticks=[10,20,30,40],ylim=(0,tab.certificate.prefix*1.25))
    a.legend(frameon=False,fontsize=7.5,loc='upper right')
    scatter=pd.read_csv(folder/'repeat_scatter.csv').sort_values(['configuration','stroke_mm'])
    a=axes[1,0];pos=np.arange(len(scatter))
    a.bar(pos-.16,scatter.EA_sample_SD_J,width=.32,color='#88b9d6',label='Observed SD (n=3)')
    a.bar(pos+.16,scatter.maximum_prefix_bound_J,width=.32,color='#d55e00',label='Largest prefix bound')
    labs=[('N' if r.configuration=='N-SCMC' else 'S')+str(int(r.stroke_mm)) for r in scatter.itertuples()]
    a.set(ylabel='Energy (J)',title='(c) Repeat scatter and table error',xticks=pos,xticklabels=labs,xlabel='N: nominal; S: STWC; stroke in mm')
    a.legend(frameon=False,fontsize=7,loc='upper left')
    pub=pd.read_csv(folder/'published_indicator_comparison.csv')
    a=axes[1,1];pos=np.arange(len(pub));center=pub.reduced_EA_J-pub.published_EA_J
    a.axhline(0,color='#555555',lw=.8)
    a.errorbar(pos,center,yerr=pub.prefix_bound_J,fmt='.',ms=3,capsize=0,lw=.6,color='#0072b2')
    bad=~pub.EA_J_published_in_interval.astype(bool)
    a.plot(pos[bad],center[bad],'o',mfc='white',ms=6,color='#d55e00',label='Specimen 05 (outside)')
    a.set(xlabel='Source workbook specimen order',ylabel='Table EA minus workbook EA (J)',title='(d) Published values: 45/46 covered')
    a.legend(frameon=False,fontsize=7,loc='lower right')
    export(fig,'fig02_workflow')

def selectors():
    summary=read('validation/results_v02/comparative_summary.json')
    keys=['work','vertical','rdp','vw','uniform_peak','uniform'];cohorts=['CX_steel','EDAH','PLA_plus']
    matrix=np.asarray([[summary[c]['at33'][m]['window_error_percent'] for m in keys] for c in cohorts])
    gaps=pd.read_csv(ROOT/'validation/results_v02/optimality_gaps.csv')
    fig,axes=plt.subplots(1,2,figsize=(7,3.35),constrained_layout=True,
                          gridspec_kw={'width_ratios':[1.18,1]})
    ax=axes[0];im=ax.imshow(matrix,cmap='Blues',norm=LogNorm(vmin=matrix.min()*.85,vmax=matrix.max()*1.2),aspect='auto')
    for i in range(3):
        for j in range(6):ax.text(j,i,'%.3f'%matrix[i,j],ha='center',va='center',fontsize=8,color='white' if matrix[i,j]>np.sqrt(matrix.min()*matrix.max()) else '#102a3a')
    tick_labels={**LABEL,'uniform_peak':'Uniform\n+ peak'}
    ax.set(xticks=range(6),xticklabels=[tick_labels[k] for k in keys],yticks=range(3),yticklabels=['CX steel (23)','EDAH (1)','PLA+ (46)'],title='(a) Median interval-work error (%)')
    ax.tick_params(axis='x',rotation=0,labelsize=8)
    for label in ax.get_xticklabels():
        label.set_ha('center')
    bar=fig.colorbar(im,ax=ax,fraction=.045,pad=.03,label='Error (%)')
    bar.set_ticks([.15,.3,.6,1.2]);bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:'%g'%v))
    bar.ax.minorticks_off()
    ax=axes[1]
    # Field names are recorded in the comparator's data schema.
    methodcol='method' if 'method' in gaps else 'greedy_method'
    objcol='objective';ratiocol='cost_ratio' if 'cost_ratio' in gaps else 'ratio'
    subset=gaps[(gaps.budget==33)&(gaps[objcol]=='eta')]
    keys=keys[:-1]
    data=[subset[subset[methodcol]==k][ratiocol].to_numpy() for k in keys]
    bp=ax.boxplot(data,positions=np.arange(1,6),widths=.55,patch_artist=True,showfliers=True)
    for patch,k in zip(bp['boxes'],keys):patch.set(facecolor=COL[k],alpha=.6)
    ax.axhline(1,color='#555555',lw=.9,ls='--')
    ax.set(xticks=range(1,6),xticklabels=[tick_labels[k] for k in keys],ylabel=r'Area cost / exact optimum $\eta^*$',title='(b) Matched area objective (58 records)',ylim=(.8,max(max(d) for d in data)*1.08))
    ax.tick_params(axis='x',rotation=0,labelsize=8)
    for label in ax.get_xticklabels():
        label.set_ha('center')
    export(fig,'fig03_selectors')

def stopping_scaling():
    stop=pd.read_csv(ROOT/'validation/results_v02/stopping_metrics.csv')
    scale=read('validation/results/scaling/measurements.json')
    rows=scale if isinstance(scale,list) else scale.get('measurements',scale.get('rows'))
    df=pd.DataFrame(rows);head=read('validation/results/scaling/headline_repeats.json')['summary']
    fig,axes=plt.subplots(1,2,figsize=(7,3.3),constrained_layout=True)
    ax=axes[0];boundcol='certificate' if 'certificate' in stop else 'measure'
    countcol='points' if 'points' in stop else 'retained_points'
    choices=[('work','eta'),('work','window'),('vertical','eta'),('vertical','window')]
    vals=[stop[(stop.method==m)&(stop[boundcol]==c)][countcol].to_numpy() for m,c in choices]
    bp=ax.boxplot(vals,widths=.55,patch_artist=True,showfliers=True)
    for patch,c in zip(bp['boxes'],['#a6cce2','#0072b2','#a5d9c3','#009e73']):patch.set_facecolor(c)
    ax.set(xticks=[1,2,3,4],xticklabels=['Work\narea','Work\ninterval','Vertical\narea','Vertical\ninterval'],ylabel='Nodes at a 1% interval-work requirement',title='(a) Same query requirement')
    ax=axes[1]
    for impl,label,col in [('v0_1_full_scan','Full scan (0.1)','#555555'),('v0_2_incremental','Incremental (0.2)','#0072b2')]:
        d=df[(df.implementation==impl)&np.isclose(df.tolerance_fraction,.001)].sort_values('n')
        ax.plot(d.n,d.seconds,'o-',color=col,label=label,ms=4)
        h=head[impl];mid=h['median_seconds'];ax.errorbar(1e6,mid,yerr=[[mid-h['minimum_seconds']],[h['maximum_seconds']-mid]],fmt='s',color=col,capsize=3,ms=4)
    ax.set(xscale='log',yscale='log',xlabel='Reference samples',ylabel='Construction time (s)',title='(b) 0.1% interval-work tolerance',xticks=[1e3,1e4,1e5,1e6],ylim=(.002,60))
    ax.set_yticks([.01,.1,1,10]);ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:'%g'%v))
    ax.legend(frameon=False,loc='upper left')
    export(fig,'fig04_stopping_scaling')

def cyclic():
    folder=ROOT/'validation/workflow_results/cyclic_path'
    trace=np.load(folder/'chronological_path.npz')
    info=read('validation/cyclic_round2_results/summary.json')
    branches=pd.read_csv(ROOT/'validation/cyclic_round2_results/branch_diagnostics.csv')
    dead=pd.read_csv(ROOT/'validation/cyclic_round2_results/deadband_sensitivity.csv')
    fig,axes=plt.subplots(2,2,figsize=(7,4.7),constrained_layout=True)
    axes[0,0].plot(trace['displacement_mm'],trace['reference_force_kN'],color='#406780',lw=.5)
    axes[0,0].set(xlabel='Displacement (mm)',ylabel='Force (kN)',title='(a) Complete cyclic path')
    vals=np.sort(branches.source_points.to_numpy());pct=100*np.arange(1,len(vals)+1)/len(vals)
    a=axes[0,1];a.step(vals,pct,color='#0072b2',where='post');a.axvline(9,color='#d55e00',ls='--',lw=.8,label='Median: 9 source nodes')
    a.set(xscale='log',xlabel='Source nodes per branch',ylabel='Cumulative branches (%)',title='(b) Exact branch-size distribution',ylim=(0,102));a.legend(frameon=False,fontsize=7)
    a=axes[1,0];a.plot(dead.deadband_mm,dead.confirmed_reversals,'o-',ms=3,color='#0072b2')
    a.axhline(94,color='#d55e00',ls='--',lw=.8,label='94 extrema at 0.1–5 mm')
    a.set(xscale='log',xlabel='Diagnostic deadband (mm)',ylabel='Detected reversals',title='(c) Reversal-scale sensitivity');a.legend(frameon=False,fontsize=7)
    e=trace['cumulative_error_J'];a=axes[1,1];bound=info['sum_branch_window_errors_J']
    a.axhspan(-bound,bound,color='#e4eff6');a.plot(np.arange(len(e))/1000,e,color='#0072b2',lw=.8)
    a.axhline(0,color='#777777',lw=.5)
    a.set(xlabel=r'Chronological sample ($\times10^3$)',ylabel='Signed work error (J)',title='(d) Chronological integral')
    export(fig,'fig05_cyclic')

def main():
    architecture();workflow();selectors();stopping_scaling();cyclic()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('Exported five vector/PNG/600dpi TIFF figures.')

if __name__=='__main__':main()
