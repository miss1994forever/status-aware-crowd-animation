/* Synchronized fixed-motion replay. No navigation or status inference in browser. */
function blendPose(a,b,u,parents,lengths){
  const raw=a.map((p,j)=>p.map((v,k)=>v+(b[j][k]-v)*u)),out=raw.map(p=>p.slice());
  parents.forEach((parent,j)=>{if(parent!==null){let d=raw[j].map((v,k)=>v-raw[parent][k]),n=Math.hypot(...d);if(n<1e-12){d=a[j].map((v,k)=>v-a[parent][k]);n=Math.hypot(...d);}out[j]=out[parent].map((v,k)=>v+d[k]*lengths[j]/Math.max(n,1e-12));}});
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
const $=id=>document.getElementById(id),query=new URLSearchParams(location.search),storageKey='animation-expression-review-v1';
let data,runs={},t=0,playing=false,last=null,records=[],ready=false;
try{const stored=JSON.parse(localStorage.getItem(storageKey)||'[]');if(Array.isArray(stored))records=stored;}catch{$('saved').textContent='浏览器记录不可读，仍可导出本次观察。';}
function world(a){const c=Math.cos(a.yaw),s=Math.sin(a.yaw);return a.pose.map(p=>[a.pos[0]+c*p[0]+s*p[2],p[1],a.pos[1]-s*p[0]+c*p[2]]);}
function projection(focus,heading,view,width,height,zoom){return p=>{
  let x=p[0]-focus[0],y=p[1],z=p[2]-focus[1],u,v;
  if(view==='body'){const c=Math.cos(heading),s=Math.sin(heading);[x,z]=[c*x-s*z,s*x+c*z];}
  switch(view){case'top':u=x;v=z;break;case'side':u=z;v=-y+.12*x;break;case'front':case'body':u=x;v=-y+.12*z;break;default:u=.85*x+.5*z;v=.26*z-.3*x-y;}
  return[width/2+zoom*u,(view==='top'?height/2:zoom>100?height-45:height*.65)+zoom*v];
};}
function line(ctx,project,points,color,width=1){ctx.beginPath();points.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function person(ctx,project,a,color,width){const p=world(a);data.parents.forEach((parent,j)=>{if(parent!==null)line(ctx,project,[p[parent],p[j]],color,width);});const h=project(p[4]);ctx.beginPath();ctx.arc(h[0],h[1]-4,width*1.8,0,Math.PI*2);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function drawPanel(id,agents){
  const canvas=$(id),ctx=canvas.getContext('2d'),chosen=agents[Number($('agent').value)],focus=$('focus').checked,view=$('view').value;
  const project=projection(focus?chosen.pos:[0,0],chosen.yaw,view,760,550,focus?425:44);
  ctx.clearRect(0,0,760,550);ctx.fillStyle='#f6f9fb';ctx.fillRect(0,0,760,550);
  for(let q=-9;q<=9;q++){line(ctx,project,[[q,0,-9],[q,0,9]],'#e3ebf1');line(ctx,project,[[-9,0,q],[9,0,q]],'#e3ebf1');}
  if(!focus){for(const goal of runs[0].spec.goals){const p=project([goal[0],0,goal[1]]);ctx.fillStyle='#6d8091';ctx.fillRect(p[0]-2,p[1]-2,4,4);}}
  if($('neighbors').checked)for(const a of agents){if(a.id!==chosen.id)person(ctx,project,a,'#b0bec9',focus?2:3);}
  person(ctx,project,chosen,'#216087',focus?5:4);
  $(id+'-info').textContent=`人物 ${chosen.id} · 当前动作 ${chosen.clip} · ${chosen.arrived?'已到达（冻结姿态）':chosen.hold?'紧急冻结':'移动中'} · 相位 ${chosen.phase.toFixed(2)}`;
}
function drawReference(){
  if(!$('reference-details').open)return;
  const id=Number($('agent').value),ref=data.references[id%3],n=ref.poses.length;
  const phase=(runs[0].frames[0].agents[id].phase+t/ref.period)%1,x=phase*n,i=Math.floor(x),pose=blendPose(ref.poses[i],ref.poses[(i+1)%n],x-i,data.parents,data.lengths);
  const canvas=$('reference'),ctx=canvas.getContext('2d'),project=projection([0,0],0,'oblique',420,400,310);
  ctx.clearRect(0,0,420,400);line(ctx,project,[[-1,0,0],[1,0,0]],'#cedbe4');person(ctx,project,{pos:[0,0],yaw:0,pose},'#216087',4);
  ctx.fillStyle='#6d8091';ctx.font='13px system-ui';ctx.fillText(ref.id+' · 原生节奏参考，不含避障',14,22);
}
function draw(){if(!ready)return;const strength=Number($('strength').value);
  drawPanel('left',frameAt(runs[0],t,data.parents,data.lengths));drawPanel('right',frameAt(runs[strength],t,data.parents,data.lengths));
  $('stamp').textContent=t.toFixed(3)+' s';$('time').value=t;$('right-title').textContent='上身保留 '+strength*100+'%';drawReference();
}
function describe(){const row=data.rows.find(r=>r.strength===Number($('strength').value)),m=row.metrics;
  $('status').className='notice'+(m.max_proxy_penetration>0?' warning':'');
  $('status').textContent=m.max_proxy_penetration>0?`固定路线后的身体代理检查发现穿透（最大 ${m.max_proxy_penetration.toFixed(4)} 参考身高）。本页只看表达，不算通行成功。`:'本段固定路线后的120Hz骨架代理检查未测得穿透；这不是网格安全、自然性或 status 有效性的证明。';
  $('metrics').textContent=JSON.stringify({scene:data.plan.classification,controls:row.contract,proxy_penetration:m.max_proxy_penetration,proxy_collision_time_fraction:m.collision_time_fraction,upper_reference_direction_rms_moving:m.upper_reference_direction_rms_moving,note:'方向接近参考是构造效果，不是感知分数；到达时间不计为新成绩。'},null,2);
}
function stop(){playing=false;$('play').textContent='播放';}
$('play').onclick=()=>{if(!ready)return;if(t>=26)t=0;playing=!playing;last=null;$('play').textContent=playing?'暂停':'播放';draw();};
$('reset').onclick=()=>{stop();t=0;draw();};
$('time').oninput=e=>{stop();t=Number(e.target.value);draw();};
$('strength').onchange=()=>{describe();draw();};
for(const id of ['agent','view','focus','neighbors'])$(id).onchange=draw;
$('reference-details').ontoggle=drawReference;
$('save').onclick=()=>{
  if(!ready)return;const record={created_at:new Date().toISOString(),source_sha256:data.plan.source_sha256,agent:Number($('agent').value),strength:Number($('strength').value),time:t,view:$('view').value,focus:$('focus').checked,neighbors:$('neighbors').checked,rate:Number($('rate').value),identity:$('identity').value,natural:$('natural').value,notes:$('notes').value};
  records.push(record);try{localStorage.setItem(storageKey,JSON.stringify(records));$('saved').textContent=`已保存 ${records.length} 条；未自动发送。`;}catch{$('saved').textContent='本次记录仅在内存，请立即导出。';}
};
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({kind:'informal_user_feedback_not_validation',records},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='expression-observations.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
async function fetchJSON(path){const response=await fetch(path);if(!response.ok)throw new Error(path+' HTTP '+response.status);return response.json();}
(async()=>{try{
  data=await fetchJSON('data.json');for(const row of data.rows)runs[row.strength]=await fetchJSON(row.file);
  $('agent').innerHTML=runs[0].frames[0].agents.map(a=>`<option value="${a.id}">人物 ${a.id}</option>`).join('');
  const agent=Number(query.get('agent')??1);$('agent').value=String(Number.isInteger(agent)&&agent>=0&&agent<10?agent:1);
  const requested=Number(query.get('t')??0);t=Number.isFinite(requested)?Math.max(0,Math.min(26,requested)):0;
  ready=true;for(const id of ['play','reset','time','save'])$(id).disabled=false;
  $('saved').textContent=records.length?`本浏览器已有 ${records.length} 条观察。`:'';describe();draw();
}catch(error){$('status').className='notice warning';$('status').textContent='加载失败：'+error.message+'。请确认本地服务器与生成数据可用，刷新重试。';}})();
function tick(now){if(playing&&ready&&last!==null){const next=advance(t,(now-last)/1000,Number($('rate').value),26,$('loop').checked);t=next.t;if(!next.playing)stop();draw();}last=now;requestAnimationFrame(tick);}requestAnimationFrame(tick);
}
