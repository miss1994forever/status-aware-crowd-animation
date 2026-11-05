"""Standalone explanatory figure for the synthetic scalar stress model."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/individual-expression-candidate'
fig,axes=plt.subplots(2,2,figsize=(11,6.8),sharex=True,sharey=True)
for ax,(key,title) in zip(axes.flat,[('high_gain_filter_only','High feedback sensitivity + filtering'),('bounded_gain','Bounded feedback sensitivity + filtering'),('small_gain_steep_observation','Small amplitude, steep observation map'),('bounded_gain_release','Bounded response; encounter ends at 12 s')]):
    rows=list(csv.DictReader((OUT/f'feedback-{key}.csv').open()))
    ax.plot([float(r['t']) for r in rows],[float(r['expression_a']) for r in rows],color='#28776c',lw=1.6,label='Agent A')
    ax.plot([float(r['t']) for r in rows],[float(r['expression_b']) for r in rows],color='#bd7552',lw=1.2,ls='--',label='Agent B')
    ax.set(title=title,xlim=(0,24),ylim=(0,1),xticks=[0,6,12,18,24],yticks=[0,.5,1])
    ax.grid(alpha=.2)
    if 'release' in key:ax.axvline(12,color='#888',lw=1,ls=':')
axes[0,0].legend(loc='lower right',fontsize=8)
for ax in axes[:,0]:ax.set_ylabel('Expression parameter')
for ax in axes[-1,:]:ax.set_xlabel('Time (seconds)')
fig.suptitle('Synthetic mutual-response test',fontsize=16)
fig.text(.5,.02,'Known scalar observation map, 0.25 s delay. Not Unity or status-perception evidence.',ha='center',fontsize=10)
fig.tight_layout(rect=[0,.045,1,.95])
fig.savefig(OUT/'feedback-review.png',dpi=150)
