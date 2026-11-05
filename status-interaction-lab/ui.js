/* Synchronized fixed-motion replay. No navigation or status inference in browser. */
function blendPose(a,b,u,parents,lengths){
  const raw=a.map((p,j)=>p.map((v,k)=>v+(b[j][k]-v)*u)),out=raw.map(p=>p.slice());
  parents.forEach((parent,j)=>{if(parent!==null){let d=raw[j].map((v,k)=>v-raw[parent][k]),n=Math.hypot(...d);if(n<1e-12){d=a[j].map((v,k)=>v-a[parent][k]);n=Math.hypot(...d);}out[j]=out[parent].map((v,k)=>v+d[k]*lengths[j]/Math.max(n,1e-12));}});
  // Same vertical floor projection as discrete execution; horizontal pose unchanged.
  const lift=Math.max(0,-Math.min(...out.map(p=>p[1])));
  if(lift)out.forEach(p=>p[1]+=lift);
  return out;
}
function frameAt(run,t,parents,lengths){
  const end=run.frames.at(-1).t,clamped=Math.min(Math.max(0,t),end);
  if(clamped===end)return run.frames.at(-1).agents;
  const i=Math.min(Math.floor(clamped/.05),run.frames.length-2),a=run.frames[i],b=run.frames[i+1],u=(clamped-a.t)/.05;
  return a.agents.map((p,j)=>({...p,pos:p.pos.map((v,k)=>v+(b.agents[j].pos[k]-v)*u),yaw:p.yaw+(b.agents[j].yaw-p.yaw)*u,pose:blendPose(p.pose,b.agents[j].pose,u,parents,lengths)}));
}
function advance(t,delta,rate,end,loop){const next=t+Math.max(0,delta)*rate;return{t:loop?next%end:Math.min(next,end),playing:loop||next<end};}
if(typeof module!=='undefined')module.exports={blendPose,frameAt,advance};
if(typeof document!=='undefined'){
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search);
let catalog,data,runs=[],t=0,playing=false,last=null,ready=false,swapped=false,loadId=0;
function world(a){const c=Math.cos(a.yaw),s=Math.sin(a.yaw);return a.pose.map(p=>[a.pos[0]+c*p[0]+s*p[2],p[1],a.pos[1]-s*p[0]+c*p[2]]);}
function projection(focus,heading,view,zoom){return p=>{let x=p[0]-focus[0],y=p[1],z=p[2]-focus[1],u,v;
if(view==='body'){const c=Math.cos(heading),s=Math.sin(heading);[x,z]=[c*x-s*z,s*x+c*z];}
switch(view){case'top':u=x;v=z;break;case'side':u=z;v=-y+.12*x;break;case'front':case'body':u=x;v=-y+.12*z;break;default:u=.85*x+.5*z;v=.26*z-.3*x-y;}
return[380+zoom*u,(view==='top'?275:zoom>100?505:358)+zoom*v];};}
function line(ctx,project,points,color,width=1){ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function person(ctx,project,a,color,width){const p=world(a);data.parents.forEach((parent,j)=>{if(parent!==null)line(ctx,project,[p[parent],p[j]],color,width);});const h=project(p[data.names.indexOf('Head')]);ctx.beginPath();ctx.arc(h[0],h[1]-3,width*1.7,0,Math.PI*2);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function drawPanel(id,agents,run,heading){
 const ctx=$(id).getContext('2d'),chosen=agents[Number($('agent').value)]||agents[0],focus=$('focus').checked;
 const zoom=focus?400:(agents.length>10?29:44),project=projection(focus?chosen.pos:[0,0],heading,$('view').value,zoom);
 ctx.fillStyle='#f7f9f9';ctx.fillRect(0,0,760,550);
 for(let q=-10;q<=10;q++){line(ctx,project,[[q,0,-10],[q,0,10]],'#e1e9eb');line(ctx,project,[[-10,0,q],[10,0,q]],'#e1e9eb');}
 for(const w of run.spec.walls){const points=[[w[0],0,w[1]],[w[2],0,w[1]],[w[2],0,w[3]],[w[0],0,w[3]],[w[0],0,w[1]]];line(ctx,project,points,'#87999f',4);}
 for(const a of agents)if(a.id!==chosen.id)person(ctx,project,a,'#98adb4',focus?2:3);
 person(ctx,project,chosen,'#236f7b',focus?5:4);
 $(id+'-info').textContent=`人物 ${chosen.id+1} · ${chosen.arrived?'到达后保持':chosen.hold?'停滞保持':'移动中'} · 全场到达 ${agents.filter(a=>a.arrived).length}/${agents.length}`;
}
function stop(){playing=false;$('play').textContent='播放';}
function draw(){if(!ready)return;const left=runs[swapped?1:0],right=runs[swapped?0:1],a=frameAt(left,t,data.parents,data.lengths),b=frameAt(right,t,data.parents,data.lengths);const heading=a[Number($('agent').value)]?.yaw||0;
 drawPanel('left',a,left,heading);drawPanel('right',b,right,heading);$('time').value=t;$('stamp').textContent=t.toFixed(2)+' s';
 const debug=$('technical').open;$('left-title').textContent=debug?'左 · '+left.mode:'片段 A';$('right-title').textContent=debug?'右 · '+right.mode:'片段 B';
 if(debug){const id=Number($('agent').value),pair=catalog.pairs[Number($('scene').value)];$('logs').textContent=JSON.stringify({time:t,selected:id+1,panels:[left,right].map(r=>{const d=r.decisions.filter(d=>d.id===id&&d.t<=t).at(-1),m=pair.metrics.find(m=>m.mode===r.mode);return{condition:r.mode,decision_time:d?.t,safe_candidates:d?.safe_count,executed:d?.executed,response:d?.response,arrival_fraction:m?.arrived_fraction,proxy_penetration:m?.max_proxy_penetration,hold_agent_seconds:m?.emergency_hold_agent_seconds};})},null,2);}
}
async function json(path){const r=await fetch(path);if(!r.ok)throw new Error(path+' HTTP '+r.status);return r.json();}
async function loadScene(){const token=++loadId;stop();ready=false;for(const id of ['play','reset','end','time','agent','swap'])$(id).disabled=true;$('status').textContent='加载实际骨架回放…';try{
 const pair=catalog.pairs[Number($('scene').value)];const loaded=await Promise.all(pair.files.map(json));if(token!==loadId)return;runs=loaded;
 if(!runs.every(r=>r.frames.length>1&&r.frames[0].agents.length))throw new Error('回放为空');
 $('agent').innerHTML=runs[0].frames[0].agents.map(a=>`<option value="${a.id}">人物 ${a.id+1}</option>`).join('');
 const requestedAgent=Number(query.get('agent')||0);$('agent').value=String(Number.isInteger(requestedAgent)&&requestedAgent>=0&&requestedAgent<runs[0].frames[0].agents.length?requestedAgent:0);
 const end=Math.min(...runs.map(r=>r.frames.at(-1).t));$('time').max=end;const requested=Number(query.get('t')||pair.start||0);t=Number.isFinite(requested)?Math.max(0,Math.min(requested,end)):0;swapped=!!pair.swapped;ready=true;
 for(const id of ['play','reset','end','time','agent','swap'])$(id).disabled=false;
 $('status').textContent=`已加载 ${end.toFixed(1)} 秒完整回放。两侧时间同步；可选人物、切镜头或查看终点。`;draw();
 }catch(e){if(token!==loadId)return;$('status').textContent='加载失败：'+e.message+'。检查本地数据后刷新重试。';}}
$('scene').onchange=loadScene;$('play').onclick=()=>{if(!ready)return;if(t>=Number($('time').max))t=0;playing=!playing;last=null;$('play').textContent=playing?'暂停':'播放';draw();};
$('reset').onclick=()=>{stop();t=0;draw();};$('end').onclick=()=>{stop();t=Number($('time').max);draw();};$('time').oninput=e=>{stop();t=Number(e.target.value);draw();};
$('swap').onclick=()=>{swapped=!swapped;draw();};for(const id of ['agent','focus','view'])$(id).onchange=draw;$('technical').ontoggle=draw;
(async()=>{try{catalog=await json(query.get('catalog')||'catalog.json');data=await json('skeleton.json');$('scene').innerHTML=catalog.pairs.map((p,i)=>`<option value="${i}">${p.title}</option>`).join('');const requestedScene=Number(query.get('scene')||0);$('scene').value=String(Number.isInteger(requestedScene)&&requestedScene>=0&&requestedScene<catalog.pairs.length?requestedScene:0);if(['oblique','front','side','body','top'].includes(query.get('view')))$('view').value=query.get('view');$('focus').checked=query.get('focus')==='1';$('scene').disabled=false;await loadScene();}catch(e){$('status').textContent='加载失败：'+e.message+'。检查本地数据后刷新重试。';}})();
function tick(now){if(playing&&ready&&last!==null){const next=advance(t,(now-last)/1000,Number($('rate').value),Number($('time').max),$('loop').checked);t=next.t;if(!next.playing)stop();draw();}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);
}
