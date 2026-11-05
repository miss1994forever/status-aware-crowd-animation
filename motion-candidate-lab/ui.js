const $=id=>document.getElementById(id);
let time=0,playing=false,last=null,costs=[],intervals=[],lastRAF=null;
const cards=Array.from({length:3},(_,i)=>{const el=document.createElement('article');el.className='card';el.innerHTML=`<div class="cardhead"><h2 id="title${i}"></h2><span id="decision${i}"></span></div><canvas aria-label="候选${i+1}身体动作"></canvas><div class="phase"><span></span></div><div class="stats"></div>`;$('cards').append(el);return el});
function options(){return{method:$('method').value,scene:$('scene').value,condition:$('condition').value,count:+$('count').value,force:$('force').checked}}
function clips(){return DATA.clips.slice(+$('content').value,+$('content').value+3)}
function render(canvas,actors,multi=false){
 const w=canvas.clientWidth,h=canvas.clientHeight,dpr=devicePixelRatio||1;
 if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
 const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 if(!actors.length){ctx.fillStyle='#a53640';ctx.font='15px system-ui';ctx.fillText('处理被拒绝 · 可切原始片段或故障诊断',18,h/2);return}
 const poses=actors.map(a=>a.actor.pose),roots=actors.map(a=>a.actor.path.position);
 const center=roots[0].map((_,k)=>roots.reduce((s,p)=>s+p[k],0)/roots.length);center[1]=.48;
 const [yaw,pitch]=({oblique:[.65,.28],front:[0,.07],side:[Math.PI/2,.07],top:[0,Math.PI/2]})[$('view').value];
 const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
 let scale=Math.min(w/2.3,h/1.65);
 if(multi){const span=Math.max(4,...roots.map(p=>Math.hypot(p[0]-center[0],p[2]-center[2])*2+2));scale=Math.min(w/(span+1),h/(span*Math.abs(sp)+2.5))}
 function project(p){const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2],d=-sy*x+cy*z;return[w/2+scale*(cy*x+sy*z),h/2-scale*(cp*y-sp*d),sp*y+cp*d]}
 function line(a,b,color,width=1){a=project(a);b=project(b);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke()}
 const extent=multi?Math.ceil(w/scale):4,cx=Math.floor(center[0]),cz=Math.floor(center[2]);
 for(let n=-extent;n<=extent;n++){line([cx+n,0,cz-extent],[cx+n,0,cz+extent],'#e0e8ef');line([cx-extent,0,cz+n],[cx+extent,0,cz+n],'#e0e8ef')}
 ctx.lineCap='round';actors.sort((a,b)=>project(a.actor.path.position)[2]-project(b.actor.path.position)[2]);
 for(const {actor:a,clip,index} of actors){
  const pose=a.pose,bones=clip.parents.map((p,j)=>({p,j})).filter(b=>b.p!==null).sort((a,b)=>project(pose[a.j])[2]-project(pose[b.j])[2]);
  for(const {p,j} of bones){const name=clip.names[j];line(pose[p],pose[j],name.includes('_L')?'#226e9d':name.includes('_R')?'#ab613d':'#233746',Math.max(1.6,scale*.014))}
  const head=project(pose[clip.names.indexOf('Head')]);ctx.strokeStyle='#233746';ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(head[0],head[1],Math.max(2,scale*.027),0,2*Math.PI);ctx.stroke();
  if(multi){const label=project([a.path.position[0],1.18,a.path.position[2]]);ctx.fillStyle='#233746';ctx.font='11px ui-monospace,monospace';ctx.textAlign='center';ctx.fillText(`${index+1}·${clip.id}`,label[0],label[1])}
 }
}
function draw(){
 const began=performance.now(),o=options(),selected=clips();
 $('cards').style.display=o.count===1?'grid':'none';$('crowd').style.display=o.count===1?'none':'block';
 if(o.count===1){
  selected.forEach((clip,i)=>{const card=cards[i],a=Lab.actor(clip,time,o),key=o.method==='source'?'improved':o.method,review=clip.review.methods[key],e=clip.methods[key]?.evidence;
   $('title'+i).textContent=clip.id;$('decision'+i).textContent=o.method==='raw'?'原始参照':o.method==='source'?'未修正源区间':review.accepted?'工程门槛通过':'处理拒绝';
   render(card.querySelector('canvas'),a?[{actor:a,clip,index:i}]:[]);
   card.querySelector('.phase span').style.width=(a?.phase??0)*100+'%';
   card.querySelector('.stats').textContent=o.method==='raw'?`源帧 ${(a?.frame??0)+1} / ${clip.raw.length} · ${clip.dt.toFixed(6)} s/帧\n源采样保持 / 不循环 / ${a?.ended?'已到片尾':'源节奏'}\n原始关节姿态未作循环修正`:`周期 ${e?.period_frames??'—'} 帧 · ${(e?.period_seconds??0).toFixed(3)} s · 步幅 ${(e?.stride??0).toFixed(3)} 身高\n当前相位 ${a?.phase?.toFixed(3)??'—'} · 调速 ${a?.scale?.toFixed(3)??'—'}×\n源帧段 ${e?e.start+1:'—'}–${e?e.end+1:'—'} · 当前源帧 ${a?.sourceFrame!==undefined?(a.sourceFrame+1).toFixed(2):'—'}\n${o.method==='source'?'未修正、逐源帧保持；循环接缝可能跳变':`最大节点改动 ${((e?.max_output_change??0)*100).toFixed(2)}% 身高`}\n${review.reasons.join('；')}`;
  });
 }else{
  const actors=[];for(let i=0;i<o.count;i++){const clip=selected[i%3],a=Lab.actor(clip,time,{...o,index:i});if(a)actors.push({actor:a,clip,index:i})}
  render($('crowdCanvas'),actors,true);
  $('crowdStats').textContent=`显示 ${actors.length}/${o.count} 人 · M${+$('content').value+1}–M${+$('content').value+3} 交替 · 调速 ${actors.length?Math.min(...actors.map(a=>a.actor.scale)).toFixed(2):'—'}–${actors.length?Math.max(...actors.map(a=>a.actor.scale)).toFixed(2):'—'}× · ${o.scene==='encounter'?'稀疏相遇，统一0.8名义速度':'原生节奏条件允许各自不同路径进度'}`;
 }
 $('readout').textContent=time.toFixed(3)+' s';$('time').value=time;
 $('play').textContent=playing?'暂停':'播放';$('play').setAttribute('aria-pressed',String(playing));
 $('notice').textContent=o.method==='raw'?'原始片段保留源采样与完整位移；场景和速度控件不改变原始素材。到片尾只显示末帧，不声称自然停止。':o.method==='source'?'此版本取改进方法选中的原始帧段，只移除线性移动并按同一路径放置；无闭环修正、无骨长重建，逐源帧保持。重复区间会暴露原始接缝。':o.scene==='encounter'?'相遇使用现有统一控制器，忽略原生速度选择：以实际路径路程推进各自步态，显示真实调速倍数；10/30人为稀疏成对布置。':o.method==='baseline'?'固定窗口故障对照：M02 等可能不满足工程门槛。被拒绝处理需主动勾选故障诊断才能查看。':'改进只涉及周期提取、相位和速度连续性；无脚部IK、无肩臂姿态美化、无status映射。';
 costs.push(performance.now()-began);if(costs.length>600)costs.shift();
 const stats=values=>{const sorted=values.slice().sort((a,b)=>a-b);return{samples:values.length,mean:values.reduce((a,b)=>a+b,0)/Math.max(1,values.length),p95:sorted[Math.floor(sorted.length*.95)]??null,max:sorted.at(-1)??null}};
 const raf=stats(intervals);
 $('perf').textContent=JSON.stringify({time,playing,...o,effective_condition:o.scene==='encounter'?'matched_encounter_nominal_0.8':o.condition,draw_ms:stats(costs),raf_interval_ms:raf,observed_raf_hz:raf.samples?1000/raf.mean:null,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio},null,2);
 window.labState={time,playing,...o,renderCost:costs.at(-1),visibleActors:o.count===1?selected.filter(c=>o.method==='raw'||o.method==='source'||o.force||c.review.methods[o.method].accepted).length:o.count};
}
function maxTime(){return $('method').value==='raw'?Math.max(...clips().map(c=>c.raw.length*c.dt)):9}
function update(){time=Math.min(time,maxTime());$('time').max=maxTime();draw()}
$('play').onclick=()=>{if(time>=maxTime())time=0;playing=!playing;last=null;draw()};
$('reset').onclick=()=>{playing=false;time=0;last=null;draw()};
$('time').oninput=()=>{time=+$('time').value;last=null;draw()};
for(const id of ['method','condition','scene','view','force'])$(id).onchange=()=>{costs=[];intervals=[];lastRAF=null;update()};
for(const id of ['content','count'])$(id).onchange=()=>{playing=false;time=0;last=null;costs=[];intervals=[];lastRAF=null;update()};
window.addEventListener('resize',draw);document.addEventListener('visibilitychange',()=>{last=null;lastRAF=null});
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['SELECT','INPUT','BUTTON'].includes(document.activeElement.tagName)){e.preventDefault();$('play').click()}});
for(const clip of DATA.clips){const e=clip.review.methods.improved.evidence;const tr=document.createElement('tr');for(const value of [clip.id,clip.review.source.source_style+' / '+clip.review.source.source_content,(clip.raw.length*clip.dt).toFixed(3)+' s',e?e.period_frames+'帧 / '+e.period_seconds.toFixed(3)+'s':'不足',e?(e.max_output_change*100).toFixed(2)+'%':'—',clip.review.decision]){const td=document.createElement('td');td.textContent=value;tr.append(td)}$('audit').append(tr)}
window.labEvidence=()=>({state:window.labState,renderMilliseconds:costs.slice(),rafIntervalsMilliseconds:intervals.slice(),userAgent:navigator.userAgent,dpr:devicePixelRatio,viewport:[innerWidth,innerHeight]});
window.labClearPerformance=()=>{costs=[];intervals=[];lastRAF=null};
function tick(now){if(playing){if(last!==null)time=Math.min(maxTime(),time+(now-last)/1000);if(lastRAF!==null)intervals.push(now-lastRAF);if(intervals.length>600)intervals.shift();lastRAF=now;if(time>=maxTime())playing=false;draw()}else lastRAF=null;last=now;requestAnimationFrame(tick)}
update();requestAnimationFrame(tick);
