const $=id=>document.getElementById(id);
let time=0,playing=false,last=null;
const cards=Array.from({length:3},(_,i)=>{const el=document.createElement('article');el.innerHTML='<h2></h2><canvas></canvas><div class="meta"></div>';$('cards').append(el);return el});
const names={before_knee_fix:'修正前 · 近伸直膝部对照',original:'原版 · 闭环参照',B_050:'新表达 · 50%',B_100:'新表达 · 连续强度',old_upper:'旧上身方向层 · 100%',no_timing:'消融 · 仅轨迹',no_shape:'消融 · 仅时序',first_round:'首轮 · 高幅控制',A_050:'路线 A · 50%',A_100:'路线 A · 100%',raw:'原片区间 · 未闭环'};
const add=(a,b)=>a.map((x,k)=>x+b[k]),sub=(a,b)=>a.map((x,k)=>x-b[k]),mul=(a,s)=>a.map(x=>x*s),dot=(a,b)=>a.reduce((s,x,k)=>s+x*b[k],0),norm=a=>Math.hypot(...a);
function quality(p,c,u,s){
 let o=p.map(x=>x.slice()),dy=s*.016*Math.cos(4*Math.PI*u),legs=['L','R'].map(side=>['UpperLeg','LowerLeg','Foot'].map(n=>c.names.indexOf(n+'_'+side)));
 const slacks=legs.map(([h,k,a])=>Math.max(0,c.lengths[k]+c.lengths[a]-norm(sub(p[a],p[h]))));dy*=slacks.reduce((g,x)=>g*x*x/(x*x+.005**2),1);
 if(dy>0){const limits=legs.map(([h,k,a])=>{const d=sub(p[a],p[h]),horizontal=Math.hypot(d[0],d[2]),slack=Math.max(0,c.lengths[k]+c.lengths[a]-norm(d)),reach=c.lengths[k]+c.lengths[a]-.75*slack,vertical=Math.sqrt(Math.max(0,reach**2-horizontal**2));return Math.max(0,p[a][1]+vertical-p[h][1])});const limit=Math.min(...limits);dy=limit*Math.tanh(dy/Math.max(limit,1e-12))}
 o=o.map(v=>add(v,[0,dy,0]));
 for(const [h,k,a] of legs){const d=sub(p[a],o[h]),dist=norm(d),e=mul(d,1/Math.max(dist,1e-12)),x=(c.lengths[k]**2-c.lengths[a]**2+dist**2)/(2*Math.max(dist,1e-12));let pole=sub(p[k],p[h]);pole=sub(pole,mul(e,dot(pole,e)));pole=mul(pole,1/Math.max(norm(pole),1e-12));o[k]=add(add(o[h],mul(e,x)),mul(pole,Math.sqrt(Math.max(0,c.lengths[k]**2-x*x))));o[a]=p[a].slice();c.parents.forEach((pa,j)=>{while(pa!==null&&pa!==a)pa=c.parents[pa];if(pa===a)o[j]=p[j].slice()})}
 for(const side of ['L','R']){const h=c.names.indexOf('UpperArm_'+side),e=c.names.indexOf('LowerArm_'+side),v=sub(p[e],p[h]),angle=-Math.max(-.65,Math.min(.65,Math.atan2(v[2],-v[1])))*s*.65,co=Math.cos(angle),si=Math.sin(angle);c.parents.forEach((pa,j)=>{while(pa!==null&&pa!==h)pa=c.parents[pa];if(pa===h){const d=sub(o[j],o[h]);o[j]=add(o[h],[d[0],co*d[1]-si*d[2],si*d[1]+co*d[2]])}})}
 return o;
}
function frame(c,key,t){
 let u=t/c.duration,phase=u%1,v=phase;
 if(key==='B_100'||key==='B_050'){
 const s=key==='B_050'?.5:+$('strength').value;v=phase-s*.32*Math.sin(4*Math.PI*phase)/(4*Math.PI);
 const p=sampleCycle(c.cycle,v*c.stride);return {pose:quality(p,c,v,s),distance:(Math.floor(u)+v)*c.stride,sourcePhase:v};
 }
 const a=c.variants[key].poses,n=a.length-1,x=key==='raw'?Math.min(1,u)*n:phase*n,i=Math.min(n-1,Math.floor(x)),f=x-i;
 if(key==='raw'){const held=Math.min(n,Math.floor(x));return {pose:a[held],distance:held/n*c.stride,sourcePhase:held/n}}
 const pose=a[i].map((p,j)=>p.map((z,k)=>z*(1-f)+a[i+1][j][k]*f));
 const times=c.variants[key].source_times;v=(times[i]*(1-f)+times[i+1]*f)/c.duration;
 return {pose,distance:(key==='raw'?Math.min(1,u):Math.floor(u)+v)*c.stride,sourcePhase:v};
}
// Same orthographic projection and depth-sorted bone drawing as existing candidate viewer.
function render(canvas,c,a){
 const w=canvas.clientWidth,h=canvas.clientHeight,dpr=devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 const yaw={front:0,side:Math.PI/2,oblique:.65}[$('view').value],pitch=.10,cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch),scale=Math.min(w/1.7,h/1.35);
 const heading=c.extraction.travel_heading_relative_body,dx=a.distance*Math.sin(heading),dz=a.distance*Math.cos(heading),pose=a.pose.map(p=>add(p,[dx,0,dz]));
 function proj(p){const x=p[0]-dx,y=p[1]-.49,z=p[2]-dz,d=-sy*x+cy*z;return [w/2+scale*(cy*x+sy*z),h/2-scale*(cp*y-sp*d),sp*y+cp*d]}
 function line(a,b,col,width){a=proj(a);b=proj(b);ctx.strokeStyle=col;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke()}
 const cx=Math.floor(dx),cz=Math.floor(dz);for(let n=-4;n<=4;n++){line([cx+n,0,cz-4],[cx+n,0,cz+4],'#e5ebef',1);line([cx-4,0,cz+n],[cx+4,0,cz+n],'#e5ebef',1)}
 ctx.lineCap='round';c.parents.map((p,j)=>({p,j})).filter(b=>b.p!==null).sort((a,b)=>proj(pose[a.j])[2]-proj(pose[b.j])[2]).forEach(({p,j})=>{line(pose[p],pose[j],c.names[j].includes('_L')?'#226e9d':c.names[j].includes('_R')?'#ab613d':'#233746',Math.max(2,scale*.014))});
 const head=proj(pose[c.names.indexOf('Head')]);ctx.strokeStyle='#233746';ctx.lineWidth=2;ctx.beginPath();ctx.arc(head[0],head[1],scale*.027,0,2*Math.PI);ctx.stroke();
}
function draw(){const c=DATA.clips[+$('base').value],keys=['original','B_050',$('mode').value];cards.forEach((card,i)=>{const a=frame(c,keys[i],time);render(card.querySelector('canvas'),c,a);card.querySelector('h2').textContent=$('blind').checked?'样本 '+String.fromCharCode(65+i):names[keys[i]];card.querySelector('.meta').textContent=$('blind').checked?'相同显示条件':`周期 ${c.duration.toFixed(3)} s · 平均 ${(c.stride/c.duration).toFixed(3)} 身高/s\n源相位 ${a.sourcePhase.toFixed(3)} · ${keys[i]==='B_100'?'强度 '+(+$('strength').value).toFixed(2):''}`});$('readout').textContent=time.toFixed(3)+' s';$('time').value=time;$('amount').textContent=(+$('strength').value).toFixed(2);$('play').textContent=playing?'暂停':'播放';$('time').max=$('mode').value==='raw'?c.duration:6*c.duration;
 $('status').textContent=`${c.label}：原生周期 ${c.duration.toFixed(3)} s，步幅 ${c.stride.toFixed(3)} 身高。新表达 100% 的步内源时间速率 0.68–1.32×，周期总时长不变。`;
 $('source').textContent=`Bandai Namco Research / CC BY-NC 4.0；源区间 ${c.extraction.start}–${c.extraction.end} 帧（0起算）；SHA256 ${c.source_sha256}。循环修正最大改动 ${(c.extraction.max_output_change*100).toFixed(2)}% 身高。 donor ${c.donor}，仅检索标签 proud，不作地位标签。`;
 window.expressionState={time,playing,base:c.id,mode:$('mode').value,view:$('view').value,strength:+$('strength').value};}
$('play').onclick=()=>{if(time>=+$('time').max)time=0;playing=!playing;last=null;draw()};$('reset').onclick=()=>{time=0;playing=true;last=null;draw()};$('time').oninput=()=>{time=+$('time').value;playing=false;draw()};
for(const id of ['view','mode','strength','blind'])$(id).oninput=()=>{time=Math.min(time,$('mode').value==='raw'?DATA.clips[+$('base').value].duration:1e9);draw()};$('base').onchange=()=>{time=0;playing=false;draw()};
for(const [key,label] of [['naturalness','自然度'],['confidence','自信'],['intimidation','威慑'],['status','地位感']]){const l=document.createElement('label');l.textContent=label+' ';const el=document.createElement('select');el.id='rating_'+key;el.innerHTML='<option value="">未评价</option>'+Array.from({length:7},(_,i)=>`<option>${i+1}</option>`).join('');l.append(el);$('ratings').append(l)}
let reviews=JSON.parse(localStorage.getItem('expression-space-reviews')||'[]');$('save').onclick=()=>{const row={date:new Date().toISOString(),...window.expressionState,subject:$('subject').value,description:$('description').value,ratings:Object.fromEntries(['naturalness','confidence','intimidation','status'].map(k=>[k,$('rating_'+k).value===''?null:+$('rating_'+k).value]))};reviews.push(row);localStorage.setItem('expression-space-reviews',JSON.stringify(reviews));$('saved').textContent='已存 '+reviews.length+' 条'};$('export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(reviews,null,2)],{type:'application/json'}));a.download='expression-space-reviews.json';a.click();URL.revokeObjectURL(a.href)};
function tick(now){if(playing&&last!==null){time=Math.min(+$('time').max,time+(now-last)/1000);if(time>=+$('time').max)playing=false;draw()}last=now;requestAnimationFrame(tick)}
const params=new URLSearchParams(location.search);for(const id of ['base','mode','view','strength'])if(params.has(id))$(id).value=params.get(id);if(params.has('t'))time=+params.get('t');window.addEventListener('resize',draw);draw();requestAnimationFrame(tick);
