/* Deterministic sampling from absolute seconds; no render-frame integration, IK or status. */
const Lab = (()=>{
const smooth=u=>{u=Math.max(0,Math.min(1,u));return u*u*u*(10-15*u+6*u*u)};
const primitive=u=>{u=Math.max(0,Math.min(1,u));return 2.5*u**4-3*u**5+u**6};
function rampIntegral(t,a,b){return t<=a?0:t>=b?t-b+(b-a)/2:(b-a)*primitive((t-a)/(b-a))}
function progression(t,speed,scene='straight',smoothed=true){
 if(!Number.isFinite(t)||t<0)throw Error('Finite nonnegative time required');
 if(scene!=='slow')return{distance:speed*t,speed,acceleration:0};
 if(!smoothed){const duration=Math.max(0,Math.min(t-3.5,3));return{distance:speed*(t-.65*duration),speed:speed*(t>=3.5&&t<6.5?.35:1),acceleration:0}}
 const r1=smooth(t-3),r2=smooth(t-6),deriv=u=>u<=0||u>=1?0:30*u*u*(1-u)*(1-u);
 return{distance:speed*(t-.65*(rampIntegral(t,3,4)-rampIntegral(t,6,7))),speed:speed*(1-.65*(r1-r2)),acceleration:-.65*speed*(deriv(t-3)-deriv(t-6))};
}
// Midpoint integration at fixed arc-length intervals; exact heading and bounded spatial error.
const step=.005,turnTable=[[0,0]];
function turnHeading(d){return .9*(1-Math.cos(Math.PI*Math.max(0,Math.min(6,d))/6))/2}
function trajectory(d,scene){
 if(scene!=='turn')return{position:[0,0,d],heading:0};
 const n=Math.floor(d/step);
 while(turnTable.length<=n+1){const k=turnTable.length,h=turnHeading((k-.5)*step),p=turnTable[k-1];turnTable.push([p[0]+step*Math.sin(h),p[1]+step*Math.cos(h)])}
 const u=d/step-n,a=turnTable[n],b=turnTable[n+1];return{position:[a[0]+u*(b[0]-a[0]),0,a[1]+u*(b[1]-a[1])],heading:turnHeading(d)};
}
const encounterCache=new Map();
function encounterAt(time,count){
 const tick=Math.round(time*120),key=count;
 if(!encounterCache.has(key))encounterCache.set(key,[createEncounter({count,speed:.8})]);
 const frames=encounterCache.get(key);
 while(frames.length<=tick){const last=structuredClone(frames[frames.length-1]);stepEncounter(last,1/120,true);last.trails=last.trails.map(()=>[]);frames.push(last)}
 return frames[tick];
}
function rawPose(clip,t){
 const i=Math.min(Math.floor(t/clip.dt),clip.raw.length-1);return{pose:clip.raw[i],frame:i,ended:t>=clip.raw.length*clip.dt};
}
function actor(clip,t,{method='improved',scene='straight',condition='native',index=0,count=1,force=false,transition='auto'}={}){
 if(method==='raw'){
  const r=rawPose(clip,t),hip=r.pose[clip.names.indexOf('Hips')];
  return{...r,path:{position:[hip[0],0,hip[2]],heading:0},phase:null,scale:1,speed:null};
 }
 const selected=method==='source'?'improved':method;
 const cycle=clip.methods[selected],accepted=clip.review.methods[selected].accepted;
 if(!cycle||(!accepted&&!force&&method!=='source'))return null;
 const native=cycle.evidence.native_speed;
 let speed=condition==='native'?native:.8,p=progression(t,speed,scene,transition==='auto'?method!=='baseline':transition==='smooth');
 let path=trajectory(p.distance,scene),offset=count>1?(index-(count-1)/2)*.85:0;
 path.position[0]+=offset;
 if(scene==='encounter'){
  const a=encounterAt(t,count===1?2:count).agents[index];
  p={distance:a.distance,speed:Math.hypot(...a.velocity)};path={position:[a.position[0],0,a.position[1]],heading:a.heading};
 }
 const phaseOffset=cycle.evidence.phase_offset||0;
 const sourcePhase=(p.distance/cycle.stride+phaseOffset)%1;
 const localPose=method==='source'?cycle.source_poses[Math.min(Math.floor(sourcePhase*(cycle.source_poses.length-1)),cycle.source_poses.length-2)]:sampleCycle(cycle,p.distance+cycle.stride*phaseOffset);
 const pose=placePose(localPose,path.position,path.heading-(cycle.evidence.travel_heading_relative_body||0));
 return{pose,path,phase:(p.distance/cycle.stride)%1,sourcePhase,sourceFrame:cycle.evidence.start+sourcePhase*cycle.evidence.period_frames,scale:p.speed/native,speed:p.speed,distance:p.distance,accepted};
}
return{smooth,progression,trajectory,rawPose,actor,encounterAt};
})();
if(typeof module!=='undefined')module.exports=Lab;
