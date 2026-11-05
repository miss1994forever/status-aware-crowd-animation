/* Local reactive passing prototype. No status, relationship model or ORCA claim. */
const mag=v=>Math.hypot(...v),sub=(a,b)=>a.map((x,i)=>x-b[i]),dot2=(a,b)=>a[0]*b[0]+a[1]*b[1];
function normalized(v){const n=mag(v);return n>1e-9?v.map(x=>x/n):[0,0]}
function limitDelta(current,target,maximum){const d=sub(target,current),n=mag(d);return n>maximum?current.map((x,i)=>x+d[i]*maximum/n):target.slice()}
function createEncounter({count=2,scenario='headon',offset=0,speed=.8}={}){
 const agents=[];
 for(let pair=0;pair<count/2;pair++){
  const center=(pair-(count/2-1)/2)*4;
  const setup=scenario==='crossing'?
   [[[center, -3.5],[center,5.5]],[[center-3.5,offset],[center+5.5,offset]]]:
   [[[center-.08,-3.5],[center-.08,5.5]],[[center+.08,3.5+offset],[center+.08,-5.5]]];
  setup.forEach(([position,goal])=>{const dir=normalized(sub(goal,position));agents.push({id:agents.length,pair,position,goal,velocity:dir.map(x=>x*speed),heading:Math.atan2(dir[0],dir[1]),distance:0,passing:[],steer:0,mode:'目标行走',arrived:false})});
 }
 return{agents,time:0,steps:0,trails:agents.map(a=>[a.position.slice()]),speed,scenario,count,minSeparation:Infinity,overlapSamples:0,config:{radius:.24,horizon:2.2,clearance:.74,acceleration:.8,maxTurnRate:1.8}};
}
function stepEncounter(world,dt,reactive=true){
 if(!(dt>0&&dt<=.05))throw Error('Use a positive fixed timestep <= .05 s');
 const {agents,config:c}=world,desired=agents.map(a=>{const r=sub(a.goal,a.position),distance=mag(r),direction=normalized(r);return{direction,distance,velocity:direction.map(x=>x*world.speed*Math.min(1,distance/.9))}});
 const next=agents.map((a,i)=>{
  const pref=desired[i],right=[pref.direction[1],-pref.direction[0]],passing=[];
  if(reactive&&!a.arrived){for(let j=0;j<agents.length;j++){
   if(i===j)continue;const b=agents[j],r=sub(b.position,a.position),rv=sub(desired[j].velocity,pref.velocity),v2=dot2(rv,rv),t=v2>1e-10?-dot2(r,rv)/v2:Infinity;
   const closest=mag(r.map((x,k)=>x+rv[k]*Math.max(0,t))),ahead=dot2(r,pref.direction),near=mag(r)<3.8;
   const retained=a.passing.includes(j)&&ahead>-.45&&near;
   if(retained||(t>0&&t<c.horizon&&closest<c.clearance&&ahead>-.1&&near))passing.push(j);
  }}
  const targetSteer=passing.length?1:0,steer=a.steer+Math.max(-dt*1.8,Math.min(dt*3,targetSteer-a.steer));
  const avoidDirection=normalized(pref.direction.map((v,k)=>v+right[k]*.8*steer));
  let target=avoidDirection.map(v=>v*mag(pref.velocity)*(1-.22*steer));
  // Corridor boundaries apply to head-on lanes; crossing scene is an open floor.
  if(world.scenario==='headon'){
   const center=(a.pair-(world.count/2-1)/2)*4,x=a.position[0]-center;
   if(Math.abs(x)>.85)target[0]+=-(x-Math.sign(x)*.85)*2;
  }
  if(pref.distance<.08)target=[0,0];
  const velocity=limitDelta(a.velocity,target,c.acceleration*dt),position=a.position.map((x,k)=>x+velocity[k]*dt),travel=mag(sub(position,a.position));
  let heading=a.heading;if(mag(velocity)>1e-4){const wanted=Math.atan2(velocity[0],velocity[1]),delta=Math.atan2(Math.sin(wanted-heading),Math.cos(wanted-heading));heading+=Math.max(-c.maxTurnRate*dt,Math.min(c.maxTurnRate*dt,delta))}
  return{...a,position,velocity,heading,distance:a.distance+travel,passing,steer,arrived:pref.distance<.08&&mag(velocity)<.04,mode:pref.distance<.08?'到达（冻结试样）':steer>.05?'右侧绕行 / 减速':'目标行走'};
 });
 world.agents=next;world.time+=dt;world.steps++;if(world.steps%6===0)next.forEach((a,i)=>world.trails[i].push(a.position.slice()));
 for(let i=0;i<next.length;i++)for(let j=0;j<i;j++){const distance=mag(sub(next[i].position,next[j].position));world.minSeparation=Math.min(world.minSeparation,distance);if(distance<2*c.radius)world.overlapSamples++}
 return world;
}
function runEncounter(options={},reactive=true,seconds=18){const world=createEncounter(options);for(let i=0;i<Math.round(seconds*60);i++)stepEncounter(world,1/60,reactive);return world}
if(typeof module!=='undefined')module.exports={createEncounter,stepEncounter,runEncounter};
