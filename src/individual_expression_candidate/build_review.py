"""Render the actual C# check sweep; stdlib only. Synthetic mechanism diagnostic."""
from pathlib import Path
import csv, json, math, hashlib
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/individual-expression-candidate'
rows=list(csv.DictReader((OUT/'synthetic-walk.csv').open()))
data=[{k:float(v) for k,v in r.items()} for r in rows]
colors=['#555e6b','#bb6844','#24796c']
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="610" viewBox="0 0 1050 610"><rect width="1050" height="610" fill="#f7f7f4"/><g font-family="Arial" fill="#222"><text x="30" y="35" font-size="22">Synthetic walking arm: geometry check only</text><text x="30" y="62" font-size="14">Same input / contraction=1 / steady filtered speed weight / not Unity capture</text>']
for j,(title,prefix) in enumerate([('Source','raw'),('Fixed 12 degrees','legacy'),('IE-01 candidate','candidate')]):
    cx=180+j*345
    svg += [f'<text x="{cx}" y="105" text-anchor="middle" font-size="18">{title}</text>',f'<path d="M{cx-40} 150H{cx+40}M{cx} 150V310" fill="none" stroke="#aaa" stroke-width="4"/>']
    for i in [0,90,180,270,360]:
        r=data[i];x=r[prefix+'X'];y=r[prefix+'Y']
        # Front view; these are upper-arm lines, not reconstructed whole bodies.
        svg.append(f'<path d="M{cx-40} 150l{-x*135:.4f} {-y*135:.4f}" stroke="{colors[j]}" opacity=".65" stroke-width="3"/>')
    svg += [f'<text x="{cx}" y="335" text-anchor="middle" font-size="13">Front projection: five sampled phases</text>']
for key,title,oy,scale in [('X','Outward component / upper-arm length',425,160),('Z','Forward component / upper-arm length',535,65)]:
    svg.append(f'<text x="30" y="{oy-38}" font-size="14">{title}</text><path d="M270 {oy}H1000" stroke="#ccc"/>')
    for j,prefix in enumerate(['raw','legacy','candidate']):
        pts=' '.join(f'{270+i/720*730:.2f},{oy-r[prefix+key]*scale:.2f}' for i,r in enumerate(data))
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{colors[j]}" stroke-width="2"/>')
svg.append('<text x="30" y="588" font-size="13">Forward traces coincide by construction. This does not establish naturalness, status perception or wrist/contact safety.</text></g></svg>')
(OUT/'synthetic-review.svg').write_text(''.join(svg))
html='''<!doctype html><meta charset="utf-8"><title>IE-01 mechanism review</title><style>body{max-width:1100px;margin:30px auto;background:#f7f7f4;color:#222;font:16px system-ui}canvas{width:100%;background:white;border:1px solid #ddd}button,input{margin:10px}small{display:block}</style><h1>IE-01 · synthetic mechanism review</h1><p>Source / fixed 12° / candidate. Same synthetic upper-arm input, no EMM capture or humanoid mesh. This is a geometry diagnostic, not a naturalness or status evaluation.</p><button id="toggle">Pause</button><label>Phase <input id="phase" type="range" min="0" max="720" value="0"></label><canvas id="c" width="1080" height="420"></canvas><small>Solid: front projection; dashed: side projection (offset). Upper-arm segments only. Candidate z matches source; hand motion/contact is not tested. Right arm is omitted here; actual adapter uses gain .75 on right.</small><img src="synthetic-review.svg" width="100%"><script>const data=DATA;let playing=true,idx=0;const canvas=document.querySelector('#c'),ctx=canvas.getContext('2d'),phase=document.querySelector('#phase');document.querySelector('#toggle').onclick=()=>playing=!playing;phase.oninput=()=>{playing=false;idx=+phase.value;draw()};function line(x,y,dx,dy,color,dash){ctx.beginPath();ctx.setLineDash(dash?[5,4]:[]);ctx.strokeStyle=color;ctx.lineWidth=4;ctx.moveTo(x,y);ctx.lineTo(x+dx,y+dy);ctx.stroke()}function draw(){ctx.clearRect(0,0,1080,420);let r=data[idx];['raw','legacy','candidate'].forEach((p,j)=>{let x=180+j*360;ctx.fillStyle='#222';ctx.font='18px system-ui';ctx.fillText(['Source','Fixed 12°','IE-01'][j],x-60,40);line(x,95,0,220,'#ccc');line(x-40,105,80,0,'#ccc');line(x-40,105,-r[p+'X']*180,-r[p+'Y']*180,['#555e6b','#bb6844','#24796c'][j]);line(x+90,105,r[p+'Z']*180,-r[p+'Y']*180,['#555e6b','#bb6844','#24796c'][j],true);ctx.fillText('x='+r[p+'X'].toFixed(3),x-65,355);ctx.fillText('z='+r[p+'Z'].toFixed(3),x-65,385)});ctx.setLineDash([])}let last=0;function loop(t){if(playing&&t-last>16){idx=(idx+3)%721;phase.value=idx;last=t}draw();requestAnimationFrame(loop)}requestAnimationFrame(loop)</script>'''.replace('DATA',json.dumps(data,separators=(',',':')))
(OUT/'review.html').write_text(html)
metrics={'type':'synthetic mechanism diagnostic; not Unity runtime', 'samples':len(data),'min_source_x':min(r['rawX'] for r in data),'min_legacy_x':min(r['legacyX'] for r in data),'min_candidate_x':min(r['candidateX'] for r in data),'max_candidate_angle_degrees':max(r['candidateDegrees'] for r in data),'max_observed_delta':max(abs(r['observedRaw']-r['observedCandidate']) for r in data),'assumed_upper_arm_m':.30,'assumed_shoulder_width_m':.40}
(OUT/'synthetic-summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for directory in ['src/individual_expression_candidate','docs/individual-expression-candidate'] for p in (ROOT/directory).rglob('*') if p.is_file()}
(OUT/'source-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps(metrics,indent=2))

# Replay comes from the compiled C# policy/math, not a second Python implementation.
replay_path=OUT/'raw-replay.json'
if replay_path.exists():
    replay=json.loads(replay_path.read_text())
    (OUT/'raw-review.html').write_text((ROOT/'src/individual_expression_candidate/replay_viewer.html').read_text().replace('REPLAY_DATA',json.dumps(replay,separators=(',',':'))))
    source_path=ROOT/'data/expression-space-lab/input-cycles.json'
    audits=[]
    for clip in replay['clips']:
        src=clip['source'];p=ROOT/src['file']
        actual=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
        if actual!=src['sha256']:raise RuntimeError('source missing or changed: '+str(p))
        audits.append({'id':clip['id'],'source_sha256':actual,**clip['audit']})
    (OUT/'replay-audit.json').write_text(json.dumps({'type':replay['type'],'input_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'clips':audits,'not_tested':['Unity runtime','full height+arm expression','mesh/contact','status perception','matched-amplitude causal comparison','user perception']},indent=2)+'\n')
    print(json.dumps(audits,indent=2))
