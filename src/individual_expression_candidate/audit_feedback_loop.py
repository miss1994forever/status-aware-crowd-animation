"""Bounded scalar feedback stress model, NOT an animation/status validation.

No Unity, no real body observation, no hidden-neighbour-status access in update.
The known synthetic observation slope is varied to expose gain assumptions.
"""
from pathlib import Path
import math,json,csv
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/individual-expression-candidate'

def clamp(v,a,b):return max(a,min(b,v))
def simulate(*,gain=.15,slope=2,body_slope=1,delay=.25,noise=0,release=False,fps=60,anchor=True,baselines=(.5,.5),initial=(.2,.2)):
    dt=1/fps;n=round(24*fps);lag=round(delay*fps)
    c=list(initial);filtered=[.5,.5];history=[];rows=[]
    alpha=1-math.exp(-dt/.3);obs_alpha=1-math.exp(-dt/.4)
    baseline=list(baselines)
    for k in range(n):
        t=k*dt;history.append(c[:]);previous=history[max(0,k-lag)]
        gate=1 if not release or t<12 else 0
        targets=[]
        for i in range(2):
            # Only the other's synthetic visible signal enters. No other baseline/status read.
            q=clamp(.5-body_slope*(previous[1-i]-.5)+noise*math.sin(2*math.pi*1.8*t),0,1)
            filtered[i]+=(q-filtered[i])*obs_alpha
            response=gain*gate*math.tanh(slope*(filtered[i]-.5))
            center=baseline[i] if anchor else c[i]
            targets.append(clamp(center+response,0,1))
        c=[c[i]+(targets[i]-c[i])*alpha for i in range(2)]
        rows.append([t,*c,*filtered,gate])
    tail=[r[1] for r in rows[-6*fps:]]
    crossings=sum((a-.5)*(b-.5)<0 for a,b in zip(tail,tail[1:]))
    bound=gain*slope*body_slope
    return rows,{'gain':gain,'response_slope':slope,'synthetic_body_observation_slope':body_slope,
                 'bound_L':bound,'delay_seconds':delay,'fps':fps,'late_peak_to_peak':max(tail)-min(tail),
                 'late_midpoint_crossings':crossings,'end_distance_to_baseline':max(abs(c[i]-baseline[i]) for i in range(2)),
                 'is_perceptual_or_Unity_evidence':False}

def crowd_test(n=10):
    fps=60;dt=1/fps;steps=24*fps;delay=15
    baselines=[.35+.30*i/(n-1) for i in range(n)]
    def run(reverse=False):
        state=[.1+.8*i/(n-1) for i in range(n)]
        if reverse:state.reverse()
        history=[];obs=[.5]*n;max_row=0
        for frame in range(steps):
            history.append(state[:]);snapshot=history[max(0,frame-delay)]
            for j in range(n):obs[j]+=(clamp(1-snapshot[j],0,1)-obs[j])*(1-math.exp(-dt/.4))
            next_state=[]
            for i in range(n):
                raw=[0 if i==j else math.exp(-((.2+abs(i-j)*.1)/1.5)**2) for j in range(n)]
                denominator=max(1,sum(raw));weights=[v/denominator for v in raw]
                max_row=max(max_row,sum(weights))
                response=.15*sum(weights[j]*math.tanh(2*(obs[j]-.5)) for j in range(n))
                target=clamp(baselines[i]+response,0,1)
                next_state.append(state[i]+(target-state[i])*(1-math.exp(-dt/.3)))
            state=next_state
        return state,max_row
    a,row=run();b,_=run(True);difference=max(abs(x-y) for x,y in zip(a,b))
    assert difference<1e-6 and row<=1+1e-12
    return {'agents':n,'delay_seconds':delay*dt,'max_weight_row_sum':row,
            'instantaneous_synthetic_lipschitz_bound':.15*2*row,
            'final_difference_between_two_initial_states':difference,
            'scope':'synthetic normalized-visible-response model; no navigation/pose feedback'}

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    cases={
      'high_gain_filter_only':dict(gain=.45,slope=10),
      'bounded_gain':dict(),
      'high_gain_polarization':dict(gain=.45,slope=10,initial=(.2,.8)),
      'bounded_gain_asymmetric_start':dict(initial=(.2,.8)),
      'bounded_gain_noise':dict(noise=.03),
      'bounded_gain_release':dict(release=True,baselines=(.35,.65)),
      'small_gain_steep_observation':dict(gain=.15,slope=10,body_slope=4),
      'bounded_gain_30fps':dict(fps=30),
      'bounded_gain_120fps':dict(fps=120),
    }
    summaries={};records={}
    for name,kwargs in cases.items():
        rows,metrics=simulate(**kwargs);summaries[name]=metrics;records[name]=rows
        with (OUT/f'feedback-{name}.csv').open('w') as f:
            w=csv.writer(f);w.writerow(['t','expression_a','expression_b','filtered_visible_b','filtered_visible_a','encounter_weight']);w.writerows(rows)
    assert summaries['high_gain_filter_only']['late_peak_to_peak']>.1
    assert summaries['small_gain_steep_observation']['late_peak_to_peak']>.05
    assert summaries['high_gain_polarization']['end_distance_to_baseline']>.3
    assert summaries['bounded_gain_asymmetric_start']['end_distance_to_baseline']<1e-6
    assert summaries['bounded_gain']['late_peak_to_peak']<1e-6
    assert summaries['bounded_gain_release']['end_distance_to_baseline']<1e-6
    assert summaries['bounded_gain_noise']['late_peak_to_peak']<.02
    for name in ['bounded_gain_30fps','bounded_gain_120fps']:
        assert summaries[name]['late_peak_to_peak']<1e-6
    report={'model':'two synchronized scalar agents, known synthetic observation map; illustration only',
            'guarantee_scope':'For fixed external input and synchronous memoryless F with sup-norm Lipschitz L<1, relaxed map has bound 1-beta+beta*L<1. Delayed/filter stress runs are numerical examples, not a proof of engine stability.',
            'cases':summaries,'crowd_test':crowd_test()}
    (OUT/'feedback-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    # Static standalone plot: preserves actual data scales, labels the theoretical toy model.
    width,height=1100,700
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="1100" height="700" fill="#fafaf7"/><g font-family="Arial" fill="#222"><text x="35" y="35" font-size="22">Synthetic mutual-response stress test</text><text x="35" y="60" font-size="14">Known scalar observation model; not Unity animation or status perception evidence.</text>']
    titles=[('high_gain_filter_only','Strong feedback + filtering (delay 0.25 s)'),('bounded_gain','Bounded loop sensitivity + filtering'),('small_gain_steep_observation','Small amplitude, steep observation mapping'),('bounded_gain_release','Bounded response; encounter ends at t=12 s')]
    for index,(name,title) in enumerate(titles):
        x=60+(index%2)*550;y=120+(index//2)*290;w=450;h=190
        svg.append(f'<text x="{x}" y="{y-20}" font-size="16">{title}</text>')
        svg.append(f'<path d="M{x} {y}V{y+h}H{x+w}" stroke="#999" fill="none"/>')
        for v in [0,.5,1]:
            yy=y+h*(1-v);svg.append(f'<path d="M{x} {yy}H{x+w}" stroke="#ddd"/><text x="{x-25}" y="{yy+4}" font-size="12">{v}</text>')
        pts=' '.join(f'{x+r[0]/24*w:.2f},{y+(1-r[1])*h:.2f}' for r in records[name])
        svg.append(f'<polyline points="{pts}" stroke="#28776c" fill="none" stroke-width="2"/>')
        for v in [0,12,24]:svg.append(f'<text x="{x+v/24*w}" y="{y+h+20}" font-size="12">{v}s</text>')
        L=summaries[name]['bound_L'];svg.append(f'<text x="{x}" y="{y+h+42}" font-size="13">Synthetic instantaneous sensitivity bound L = {L:.2f}</text>')
    svg.append('</g></svg>');(OUT/'feedback-review.svg').write_text(''.join(svg))
    print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
