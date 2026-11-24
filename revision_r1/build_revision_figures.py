"""Build revision architecture and measured exchange-performance figures.

Run: python -B revision_r1/build_revision_figures.py
Requires NumPy and Matplotlib. All plotted measurements come from archived JSON
or CSV records; no image-generation system is used. Outputs are PDF, SVG, PNG and
TIFF. The manifest records exact source-file identities and figure captions.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.path import Path as MplPath
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'revision_r1/figures'
BLUE='#0072B2'
ORANGE='#D55E00'
GREEN='#009E73'
GREY='#687580'
INK='#172A3A'
LIGHT='#DFE5E9'

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.,
 'axes.titlesize':10.,'axes.labelsize':9.,'xtick.labelsize':8.5,
 'ytick.labelsize':8.5,'legend.fontsize':8.,'axes.edgecolor':'#59656F',
 'axes.linewidth':.7,'text.color':INK,'axes.labelcolor':INK,'xtick.color':INK,
 'ytick.color':INK,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'workcert-r1-20261123',
 'savefig.facecolor':'white','axes.spines.top':False,'axes.spines.right':False})


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, name):
    files=[]
    for ext,opts in [('pdf',{'metadata':{'CreationDate':None,'ModDate':None,'Creator':'Matplotlib'}}),
                     ('svg',{'metadata':{'Date':None,'Creator':'Matplotlib'}}),
                     ('png',{'dpi':250}),('tiff',{'dpi':300,'pil_kwargs':{'compression':'tiff_lzw'}})]:
        p=OUT/(name+'.'+ext)
        fig.savefig(p,**opts)
        files.append({'file':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    plt.close(fig)
    return files


def arrow(ax,points,color=GREY,style='-',width=1.15,scale=10):
    path=MplPath(points,[MplPath.MOVETO]+[MplPath.LINETO]*(len(points)-1))
    ax.add_patch(FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=scale,
                               linewidth=width,color=color,linestyle=style,zorder=3))


def box(ax,x,y,w,h,title,detail,color,fill):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.014',
                               linewidth=1.,edgecolor=color,facecolor=fill,zorder=4))
    ax.text(x+w/2,y+h*.72,title,ha='center',va='center',fontsize=9.5,fontweight='bold',color=INK,zorder=5)
    ax.text(x+w/2,y+h*.31,detail,ha='center',va='center',fontsize=8.4,linespacing=1.15,color=INK,zorder=5)


def architecture():
    fig,ax=plt.subplots(figsize=(7.4,3.65))
    fig.subplots_adjust(left=.02,right=.98,bottom=.03,top=.98)
    ax.set_xlim(-.025,1.035);ax.set_ylim(0,1);ax.axis('off')
    ax.add_patch(FancyBboxPatch((.025,.17),.285,.76,boxstyle='round,pad=.012,rounding_size=.025',
                               fc='#F5F9FC',ec='#D5E4EF',lw=.9,zorder=0))
    ax.add_patch(FancyBboxPatch((.69,.17),.285,.76,boxstyle='round,pad=.012,rounding_size=.025',
                               fc='#F3FAF7',ec='#CDE7DC',lw=.9,zorder=0))
    ax.text(.1675,.968,'PRODUCER',ha='center',va='center',fontsize=10.2,fontweight='bold',color=BLUE)
    ax.text(.1675,.918,'Full numerical reference',ha='center',va='center',fontsize=8.4)
    ax.text(.8325,.968,'CONSUMER',ha='center',va='center',fontsize=10.2,fontweight='bold',color=GREEN)
    ax.text(.8325,.918,'No dense reference required',ha='center',va='center',fontsize=8.4)
    w,h=.25,.15
    for y,title,detail in [(.72,'Reference record','Coordinates, force and units'),
                           (.47,'Node selection','Selector, anchors and budget'),
                           (.22,'Error evaluation','Force and work errors\nsource fingerprint')]:
        box(ax,.0425,y,w,h,title,detail,BLUE,'white')
    box(ax,.375,.47,.25,.19,'JSON exchange','Nodes, units and errors\nmetadata and checksum',ORANGE,'#FFF6EE')
    for y,title,detail in [(.72,'Validation and policy','Schema and checksum\nrequested tolerance'),
                           (.47,'Reusable queries','Prefixes, windows and peaks'),
                           (.22,'Decision','Accept or request refinement')]:
        box(ax,.7075,y,w,h,title,detail,GREEN,'white')
    arrow(ax,[(.1675,.711),(.1675,.628)])
    arrow(ax,[(.1675,.461),(.1675,.378)])
    arrow(ax,[(.301,.295),(.5,.295),(.5,.462)])
    arrow(ax,[(.633,.565),(.666,.565),(.666,.795),(.699,.795)])
    arrow(ax,[(.8325,.711),(.8325,.628)])
    ax.text(.847,.673,'pass',va='center',ha='left',fontsize=7.8,color=GREEN)
    arrow(ax,[(.8325,.461),(.8325,.378)])
    # Both a failed gate and an unresolved comparison may request new source
    # tables. A failed gate has no arrow leading through query operations.
    arrow(ax,[(.966,.795),(1.014,.795),(1.014,.09),(.995,.09)],color=ORANGE,style='--',scale=8)
    ax.text(1.015,.44,'unmet',rotation=90,ha='center',va='center',fontsize=7.7,color=ORANGE,
            bbox={'boxstyle':'square,pad=.15','fc':'white','ec':'none'})
    arrow(ax,[(.8325,.211),(.8325,.09),(-.005,.09),(-.005,.545),(.034,.545)],color=ORANGE,style='--')
    ax.plot([.8325,.995],[.09,.09],color=ORANGE,ls='--',lw=1.15)
    ax.text(.51,.035,'Refine only unresolved records or failed branches',ha='center',va='center',fontsize=8.5,color=ORANGE)
    return save(fig,'fig01_architecture')


def style_ax(ax,title):
    ax.set_title(title,loc='left',fontweight='bold',pad=9)
    ax.grid(axis='y',color=LIGHT,linewidth=.6,zorder=0)
    ax.set_axisbelow(True)


def performance():
    records=list(csv.DictReader((ROOT/'revision_r1/results/exchange_per_curve.csv').open(encoding='utf8')))
    summary=json.loads((ROOT/'revision_r1/results/exchange_summary.json').read_text())
    scaling=json.loads((ROOT/'validation/results/scaling/headline_repeats.json').read_text())
    assert len(records)==70
    fig,axes=plt.subplots(2,2,figsize=(7.4,5.8))
    fig.subplots_adjust(left=.095,right=.98,bottom=.10,top=.95,wspace=.34,hspace=.55)
    ax=axes[0,0]
    style_ax(ax,'(a) Complete serialized files')
    keys=['reduced_json_bytes','dense_minimal_json_bytes','dense_schema_json_bytes']
    colors=[BLUE,GREY,ORANGE]
    values=[np.array([float(r[k])/1000 for r in records]) for k in keys]
    rng=np.random.default_rng(20261123)
    for j,(v,c) in enumerate(zip(values,colors),1):
        ax.scatter(j+rng.uniform(-.11,.11,len(v)),v,s=9,alpha=.24,color=c,edgecolor='none',zorder=2)
        p=ax.boxplot([v],positions=[j],widths=.40,showfliers=False,patch_artist=True,
                     boxprops={'facecolor':c+'25','edgecolor':c,'linewidth':1.1},
                     medianprops={'color':c,'linewidth':1.7},
                     whiskerprops={'color':c,'linewidth':1.},capprops={'color':c,'linewidth':1.})
        med=np.median(v)
        ax.text(j,med*1.30,f'{med:.2f}',ha='center',va='bottom',fontsize=8.2,fontweight='bold',color=c)
    ax.set_yscale('log')
    ax.set_ylim(1.1,380);ax.set_yticks([2,10,50,200],labels=['2','10','50','200'])
    ax.set_ylabel('Uncompressed JSON (kB)')
    ax.set_xticks([1,2,3],['Reduced\nWorkCert','Dense\nminimal','Full-node\nWorkCert'])
    ax.text(.02,.98,'70 references; 33 retained nodes',transform=ax.transAxes,ha='left',va='top',fontsize=7.7)

    ax=axes[0,1]
    style_ax(ax,'(b) Loading and repeated queries')
    x=np.arange(3);width=.33
    for delta,name,c,label in [(-width/2,'reduced',BLUE,'Reduced'),(width/2,'full_schema',ORANGE,'Full-node')]:
        keys=[name+'_load_median_ms',name+'_prefix_10000_median_ms',name+'_window_10000_median_ms']
        groups=[np.array([float(r[k]) for r in records]) for k in keys]
        meds=np.array([np.median(v) for v in groups]);q=np.array([np.quantile(v,[.25,.75]) for v in groups])
        ax.bar(x+delta,meds,width,label=label,color=c,alpha=.85,zorder=2)
        ax.errorbar(x+delta,meds,yerr=np.array([meds-q[:,0],q[:,1]-meds]),fmt='none',ecolor=INK,elinewidth=.8,capsize=2.5,zorder=3)
    ax.set_ylabel('Elapsed time (ms)')
    ax.set_xticks(x,['Load\nfile + cache','Prefix\n10,000 queries','Window\n10,000 queries'])
    ax.set_ylim(0,9.4);ax.legend(loc='upper left',frameon=False,ncol=1)
    ax.text(.98,.97,'Median and IQR\nacross 70 references',transform=ax.transAxes,ha='right',va='top',fontsize=7.3)
    ax.set_yticks([0,2,4,6,8])

    ax=axes[1,0]
    style_ax(ax,'(c) Direct-summation fallback')
    stress=summary['fallback_stress'];n=np.array([r['retained_points'] for r in stress])
    for name,c,label,ls,marker in [('enabled_median_ms',BLUE,'Normal runtime','-','o'),
                                  ('diagnostic_bypassed_median_ms',GREY,'Bypassed (incorrect)','--','s')]:
        med=np.array([r[name]['median'] for r in stress]);lo=np.array([r[name]['minimum'] for r in stress]);hi=np.array([r[name]['maximum'] for r in stress])
        ax.errorbar(n,med,yerr=[med-lo,hi-med],color=c,label=label,linestyle=ls,marker=marker,
                    markersize=4,capsize=2.5,linewidth=1.3,elinewidth=.8)
    ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(20,160000);ax.set_ylim(.18,14000)
    ax.set_xticks(n,labels=['33','1,001','100,001'])
    ax.set_yticks([1,10,100,1000],labels=['1','10','100','1,000'])
    ax.set_xlabel('Retained nodes in signed stress fixture')
    ax.set_ylabel('256 window queries (ms)')
    ax.legend(loc='upper left',frameon=False,fontsize=7.6)

    ax=axes[1,1]
    style_ax(ax,'(d) Million-node construction')
    keys=['v0_1_full_scan','v0_3_stable_incremental']
    vals=[np.array([r['seconds'] for r in scaling['measurements'] if r['implementation']==k]) for k in keys]
    for j,(v,c) in enumerate(zip(vals,[GREY,BLUE])):
        med=np.median(v)
        ax.bar(j,med,.52,color=c,alpha=.85,zorder=2)
        ax.errorbar(j,med,yerr=[[med-v.min()],[v.max()-med]],fmt='none',capsize=4,color=INK,elinewidth=1.,zorder=4)
        ax.scatter(j+np.array([-.1,0,.1]),v,s=15,color='white',edgecolor=INK,linewidth=.6,zorder=5)
        ax.text(j,max(v)+.42,f'{med:.2f} s',ha='center',va='bottom',fontsize=8.5,fontweight='bold')
    ax.set_ylim(0,15.7);ax.set_yticks([0,5,10,15]);ax.set_ylabel('Construction time (s)')
    ax.set_xticks([0,1],['Full scan\nv0.1','Incremental\nv0.3'])
    ax.text(.98,.96,'Same 0.1% window target\n107 retained nodes',transform=ax.transAxes,ha='right',va='top',fontsize=7.7)
    return save(fig,'fig05_exchange_scale')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inputs=['revision_r1/results/exchange_per_curve.csv','revision_r1/results/exchange_summary.json',
            'validation/results/scaling/headline_repeats.json']
    files=architecture()+performance()
    captions={
      'fig01_architecture': 'WorkCert exchange workflow. The producer selects nodes and evaluates reconstruction errors against the full numerical reference. The consumer validates the exchanged file, applies an explicit application-level tolerance policy and evaluates reusable queries without that reference. Unmet branch budgets or unresolved comparisons request source-side refinement. OpenAI Codex assisted with the archived figure code.',
      'fig05_exchange_scale': 'Exchange measurements and numerical cost. (a) Actual uncompressed JSON sizes for 70 references; reduced and full-node WorkCert files include their error, identity and checksum metadata, whereas minimal dense JSON contains coordinates, units and source identity only. Points show individual references; boxes show medians and interquartile ranges with 1.5-IQR whiskers. (b) Median and interquartile range across reference-specific timings; loads include file validation and cache construction, and each query batch contains 10,000 locations. Loading and ordinary queries use three independent processes with five measurements after warm-up per process. No fallback occurred at the 1.4 million tested query locations per representation. (c) A synthetic signed stress fixture uses three measurements after warm-up per process and triggers fallback for every query; the diagnostic bypass is faster but loses the small integral. Bars show minimum and maximum process medians. (d) Previously archived three-process construction timings for one million synthetic samples under the same interval-error target; symbols show individual processes. OpenAI Codex assisted with the archived plotting code.'}
    manifest={'status':'GENERATED','generator':Path(__file__).relative_to(ROOT).as_posix(),
              'generator_sha256':sha(Path(__file__)),'matplotlib':matplotlib.__version__,'numpy':np.__version__,
              'source_files':{p:sha(ROOT/p) for p in inputs},'outputs':files,'captions':captions,
              'architecture_semantics':'Source-free consumer validates file consistency and local acceptance policy; producer computes reference errors.'}
    (OUT/'figure_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    (OUT/'captions.txt').write_text('\n\n'.join(k+'\n'+v for k,v in captions.items())+'\n',encoding='utf8')
    print(json.dumps({'figures':2,'files':len(files),'output':str(OUT)},ensure_ascii=False))


if __name__=='__main__':main()



