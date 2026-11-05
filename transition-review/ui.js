/* Local replay only. No production controller or source motion changes. */
let data, current, time=0, playing=false, last;
const $=id=>document.getElementById(id);
const canvases=[...document.querySelectorAll('canvas')];
const query=new URLSearchParams(location.search);
function sample(run,t){
  const i=Math.min(Math.floor(t/data.dt),run.frames.length-2);
  const a=run.frames[i].agents[0],b=run.frames[i+1].agents[0];
  const u=Math.max(0,Math.min(1,(t-run.frames[i].t)/data.dt));
  return {...a,pos:a.pos.map((v,j)=>v+(b.pos[j]-v)*u),yaw:a.yaw+(b.yaw-a.yaw)*u,
    pose:a.pose.map((p,j)=>p.map((v,k)=>v+(b.pose[j][k]-v)*u))};
}
function project(p){
  const [x,y,z]=p,view=$('view').value;
  if(view==='side')return [320+z*300,435-y*300+x*35];
  if(view==='front')return [320+x*300,435-y*300+z*35];
  return [320+(x*.85+z*.5)*300,435+(-y+z*.26-x*.3)*300];
}
function stroke(ctx,pts,color,width){ctx.beginPath();pts.forEach((p,i)=>{const q=project(p);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
function draw(){
  if(!current)return;
  $('time').value=time;$('stamp').textContent=time.toFixed(3)+' s';
  $('stage').textContent=time<data.switch_time?' · 切换前':' · 切换后';
  current.variants.forEach((run,index)=>{
    const ctx=canvases[index].getContext('2d'),a=sample(run,time);ctx.clearRect(0,0,640,510);
    // Camera follows each root, while the floor translates to retain motion cues.
    for(let v=-8;v<=8;v++){
      stroke(ctx,[[v*.5-a.pos[0],0,-3],[v*.5-a.pos[0],0,3]],'#d9dfe2',1);
      stroke(ctx,[[-3,0,v*.5-a.pos[1]],[3,0,v*.5-a.pos[1]]],'#d9dfe2',1);
    }
    const c=Math.cos(a.yaw),s=Math.sin(a.yaw);
    const world=a.pose.map(p=>[c*p[0]+s*p[2],p[1],-s*p[0]+c*p[2]]);
    world.forEach((p,j)=>{if(data.parents[j]!==null)stroke(ctx,[world[data.parents[j]],p],'#225f8c',4)});
    const head=project(world[data.names.indexOf('Head')]);ctx.beginPath();ctx.arc(head[0],head[1]-5,8,0,Math.PI*2);ctx.strokeStyle='#225f8c';ctx.lineWidth=3;ctx.stroke();
    ctx.fillStyle='#333';ctx.font='15px system-ui';ctx.fillText(time<data.switch_time||index===0?'M02':current.target,20,28);
  });
  $('metrics').textContent=JSON.stringify({case:current.id,AB根运动完全相同:current.root_pair_identical,
    variants:current.variants.map(v=>({method:v.method,切入相位偏移:v.entry_offset,diagnostics:v.metrics}))},null,2);
}
function selectCase(){
  current=data.cases.find(c=>c.target===$('pair').value&&c.initial_phase===Number($('phase').value));
  playing=false;$('play').textContent='播放';draw();
}
function tick(now){if(last!==undefined&&playing&&current){time=Math.min(data.duration,time+Math.min((now-last)/1000,.1)*Number($('rate').value));if(time>=data.duration){playing=false;$('play').textContent='播放'}draw()}last=now;requestAnimationFrame(tick)}
$('play').onclick=()=>{if(time>=data.duration)time=0;playing=!playing;$('play').textContent=playing?'暂停':'播放';draw()};
$('reset').onclick=()=>{time=0;playing=false;$('play').textContent='播放';draw()};
$('switch').onclick=()=>{time=.95;playing=false;$('play').textContent='播放';draw()};
$('time').oninput=e=>{time=Number(e.target.value);playing=false;$('play').textContent='播放';draw()};
$('pair').onchange=selectCase;$('phase').onchange=selectCase;$('view').onchange=draw;
fetch('data.json').then(r=>{if(!r.ok)throw Error('数据 HTTP '+r.status);return r.json()}).then(d=>{
  data=d;$('phase').innerHTML=Array.from({length:8},(_,i)=>`<option value="${i/8}">${i/8}</option>`).join('');
  if(['M11','M01','M03'].includes(query.get('target')))$('pair').value=query.get('target');
  if(Array.from($('phase').options).some(o=>o.value===query.get('phase')))$('phase').value=query.get('phase');
  if(['side','front','oblique'].includes(query.get('view')))$('view').value=query.get('view');
  time=Math.max(0,Math.min(d.duration,Number(query.get('t'))||0));selectCase();$('play').disabled=false;
}).catch(e=>{$('stage').textContent='加载失败：'+e.message;$('play').disabled=true});
requestAnimationFrame(tick);
window.transitionReview={get loaded(){return !!current},get time(){return time},get current(){return current}};
