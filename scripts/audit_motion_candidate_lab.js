/* Offline numerical matrix: operation time is explicitly not browser FPS. */
const fs=require('fs'),vm=require('vm'),path=require('path'),{performance}=require('perf_hooks');
const ROOT=path.resolve(__dirname,'..');
function runtime(){const box={structuredClone,performance,console};vm.createContext(box);for(const p of ['locomotion/runtime.js','src/locomotion_encounter.js','src/motion_candidate_lab/runtime.js'])vm.runInContext(fs.readFileSync(path.join(ROOT,p),'utf8'),box);return{lab:vm.runInContext('Lab',box),sample:vm.runInContext('sampleCycle',box)}}
function quantile(a,p){a=a.slice().sort((x,y)=>x-y);return a.length?a[Math.floor((a.length-1)*p)]:null}
function summary(a){return{samples:a.length,median:quantile(a,.5),p95:quantile(a,.95),max:a.length?Math.max(...a):null}}
function matrix(data){
 const {lab,sample}=runtime(),rows=[],dt=1/120;
 for(const clip of data.clips.slice(0,3))for(const method of ['baseline','improved'])for(const condition of ['native','matched'])for(const scene of ['straight','turn','slow'])for(const transition of (scene==='slow'?['step','smooth']:['smooth'])){
  const foot=clip.names.map((n,i)=>n.startsWith('Toes_')?i:-1).filter(i=>i>=0),cycle=clip.methods[method];
  const floor=Math.min(...cycle.poses.flatMap(p=>foot.map(k=>p[k][1]))),speeds=[],speedJumps=[],accelJumps=[],footSpeeds=[],jointAccelJumps=[];
  let previous=null,prevVel=null,prevAcc=null,prevSpeed=null,prevJointVel=null,prevJointAcc=null;const scales=[],began=performance.now();
  for(let frame=0;frame<=9/dt;frame++){
   const a=lab.actor(clip,frame*dt,{method,condition,scene,transition,force:true});scales.push(a.scale);speeds.push(a.speed);
   if(prevSpeed!==null)speedJumps.push(Math.abs(a.speed-prevSpeed));prevSpeed=a.speed;
   if(previous){
    const v=a.path.position.map((x,k)=>(x-previous.path.position[k])/dt);
    const jv=a.pose.map((p,j)=>p.map((x,k)=>(x-previous.pose[j][k])/dt));
    for(const k of foot)if(a.pose[k][1]<floor+.025)footSpeeds.push(Math.hypot(jv[k][0],jv[k][2]));
    if(prevVel){const acc=v.map((x,k)=>(x-prevVel[k])/dt),ja=jv.map((p,j)=>p.map((x,k)=>(x-prevJointVel[j][k])/dt));
     if(prevAcc){
      accelJumps.push(Math.hypot(...acc.map((x,k)=>x-prevAcc[k])));
      const deltas=ja.map((p,j)=>Math.hypot(...p.map((x,k)=>x-prevJointAcc[j][k])));
      jointAccelJumps.push(Math.max(...deltas));
     }
     prevAcc=acc;prevJointAcc=ja;
    }
    prevVel=v;prevJointVel=jv;
   }previous=a;
  }
  const duration=cycle.evidence.period_seconds,stride=cycle.stride,eps=1e-5;
  const a=sample(cycle,stride*(1-eps)),b=sample(cycle,0),c=sample(cycle,stride*eps);
  const seamVelocity=Math.sqrt(a.flatMap((p,j)=>p.map((x,k)=>(((c[j][k]-b[j][k])-(b[j][k]-x))/(duration*eps))**2)).reduce((x,y)=>x+y,0)/(a.length*3));
  rows.push({id:clip.id,method,condition,scene,transition,accepted:clip.review.methods[method].accepted,seconds:9,dt,
   speed:summary(speeds),max_speed_step:Math.max(...speedJumps),path_acceleration_step:summary(accelJumps),joint_acceleration_step:summary(jointAccelJumps),
   low_toe_height_horizontal_speed_proxy:summary(footSpeeds),speed_scale_range:[Math.min(...scales),Math.max(...scales)],
   final_cycle_seam_velocity_rms:seamVelocity,offline_milliseconds:performance.now()-began});
 }
 const encounters=[];
 for(const count of [2,10,30]){
  const began=performance.now();let finite=true,minSpeed=Infinity,actors=0;
  for(let frame=0;frame<=1080;frame++)for(let i=0;i<count;i++){
   const a=lab.actor(data.clips[i%3],frame/120,{scene:'encounter',condition:'matched',count,index:i});
   finite&&=a.pose.flat().every(Number.isFinite);minSpeed=Math.min(minSpeed,a.speed);actors++;
  }
  const world=lab.encounterAt(9,count);encounters.push({count,seconds:9,dt:1/120,finite,min_speed:minSpeed,min_center_separation:world.minSeparation,center_circle_overlap_samples:world.overlapSamples,actor_samples:actors,offline_milliseconds:performance.now()-began,layout:'count/2 sparse pairs; not dense crowd'});
 }
 return{schema:1,units:'M01 fixed reference height; seconds',foot_proxy_definition:'Toes Y < sampled cycle minimum +0.025; includes low swinging toes; not ground truth contact',acceleration_step_definition:'difference of adjacent finite-difference accelerations at dt=1/120; not jerk per second',matrix:rows,encounters};
}
if(require.main===module){const data=JSON.parse(fs.readFileSync(path.join(ROOT,'outputs/motion-candidate-lab/lab.json')));const began=performance.now(),result=matrix(data);result.total_offline_seconds=(performance.now()-began)/1000;fs.writeFileSync(path.join(ROOT,'data/motion-candidate-lab/scenario-metrics.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({rows:result.matrix.length,encounters:result.encounters,offline_seconds:result.total_offline_seconds},null,2))}
module.exports={runtime,matrix,summary};
