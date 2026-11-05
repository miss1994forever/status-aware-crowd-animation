"""Plot actual offline C# bone-feedback traces; never presented as Unity/perception evidence."""
from pathlib import Path
from collections import defaultdict
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/individual-expression-candidate'

def main():
    data=json.loads((OUT/'body-feedback-audit.json').read_text())
    groups=defaultdict(list)
    for row in data['traces']:
        groups[row['scenario'],row['seed']].append(row['sample'])
    frozen=[a for a in data['audits'] if not a['Moving'] and a['Context']=='frozen-approach']
    worst=max(frozen,key=lambda a:a['lateTargetRange'])
    fig,axes=plt.subplots(2,2,figsize=(12,7.8))
    fig.suptitle('Bone feedback: offline engineering checks',fontsize=16,x=.07,ha='left',y=.98)
    colors=['#177f8c','#b4653a']
    choices=[(worst['Name'],'Targets','Largest late target variation among frozen cases'),
             ('M01-combo-exit','Offsets','Interaction removed at 12 s; own baselines retained'),
             ('M01-combo-moving','Targets','Repeating source motion: periodic response remains'),
             ('M01-combo-endpoints','Targets','Endpoint clipping: both histories settle at bounds')]
    for ax,(name,key,title) in zip(axes.flat,choices):
        for seed in [0,1]:
            rows=groups[name,seed]
            for actor,color in enumerate(colors):
                ax.plot([s['T'] for s in rows],[s[key][actor] for s in rows],
                        color=color,linestyle='-' if seed==0 else '--',linewidth=1.3,
                        alpha=1 if seed==0 else .7,label=f'actor {actor+1}, history {seed+1}')
        if 'exit' in name:
            ax.axvline(12,color='#555',linewidth=.9,linestyle=':')
            ax.axhline(0,color='#555',linewidth=.7)
        if 'endpoints' in name:
            ax.set_ylim(-.08,1.08)
            ax.text(.04,.48,'History 1: saturated throughout\nHistory 2: also reaches the bounds',
                    transform=ax.transAxes,fontsize=9,color='#8b4230')
        ax.set_title(title,loc='left',fontsize=10,pad=9)
        ax.text(0,1.015,name,transform=ax.transAxes,fontsize=8,color='#666')
        ax.set_xlabel('Time (s)');ax.set_ylabel(key+' (unitless)')
        ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
    axes[0,0].legend(fontsize=8,ncol=2,loc='best')
    fig.text(.07,.025,
             f"{data['criterionPass']}/{data['scenarioCount']} specified cases pass the stated numerical criterion. "
             'Frozen approach gates are test context, not stationary physical encounters.\n'
             'Actual C# response + policy + offline body solver; managed math shim. '
             'No Unity, navigation, naturalness, perception, or global stability claim.',fontsize=9,color='#444')
    fig.tight_layout(rect=(.025,.085,.995,.93),h_pad=2.5,w_pad=2)
    fig.savefig(OUT/'body-feedback-review.png',dpi=160,facecolor='white')
    paths=['data/expression-space-lab/input-cycles.json',
           'src/individual_expression_candidate/ExpressionMath.cs',
           'src/individual_expression_candidate/ExpressionPolicy.cs',
           'src/individual_expression_candidate/InteractiveExpression.cs',
           'src/individual_expression_candidate/BodyCombinationSearch.cs',
           'src/individual_expression_candidate/reference/SprintLegIK.cs',
           'tests/test_individual_expression_candidate_combination/Program.cs',
           'tests/test_individual_expression_candidate_combination/UnityMathShim.cs',
           'tests/test_individual_expression_candidate_closedloop/ClosedLoop.cs',
           'tests/test_individual_expression_candidate_closedloop/ClosedLoop.csproj',
           'outputs/individual-expression-candidate/visible-reference.json',
           'outputs/individual-expression-candidate/body-feedback-audit.json']
    manifest={'kind':'offline body-feedback source and input hashes; not engine or perception acceptance',
              'sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
    (OUT/'body-feedback-provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(OUT/'body-feedback-review.png')

if __name__=='__main__':main()
