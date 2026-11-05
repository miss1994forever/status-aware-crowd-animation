const assert=require('assert'),fs=require('fs'),path=require('path');
const {runtime}=require('../scripts/audit_motion_candidate_lab.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../outputs/motion-candidate-lab/lab.json'))),{lab,sample}=runtime();
let checks=0;function check(value,message){checks++;assert.ok(value,message)}
for(const clip of data.clips){
 for(const method of ['baseline','improved']){
  const cycle=clip.methods[method];
  if(!cycle){check(lab.actor(clip,0,{method})===null,'missing stays missing');continue}
  if(!clip.review.methods[method].accepted)check(lab.actor(clip,1,{method})===null,'rejection shown honestly');
  for(const phase of [0,.001,.25,.5,.999,1]){
   const pose=sample(cycle,phase*cycle.stride);check(pose.flat().every(Number.isFinite),'finite');
   for(let j=0;j<pose.length;j++){const p=clip.parents[j];if(p!==null)check(Math.abs(Math.hypot(...pose[j].map((v,k)=>v-pose[p][k]))-cycle.bone_lengths[j])<1e-10,'fixed bone')}
  }
  const a=sample(cycle,-cycle.stride*1e-7),b=sample(cycle,cycle.stride*1e-7);
  check(Math.max(...a.flatMap((p,j)=>p.map((v,k)=>Math.abs(v-b[j][k]))))<1e-5,'cycle continuity');
 }
 const end=lab.rawPose(clip,1000);check(end.frame===clip.raw.length-1&&end.ended,'raw ends honestly');
}
for(const clip of data.clips.slice(0,3))for(const scene of ['straight','turn','slow']){
 const cycle=clip.methods.improved,native=cycle.evidence.native_speed;
 const at9=lab.actor(clip,9,{scene});
 for(const fps of [30,60,120,144]){
  let distance=0;
  for(let i=0;i<9*fps;i++)distance+=lab.progression((i+.5)/fps,native,scene,true).speed/fps;
  check(Math.abs(distance-at9.distance)<1e-7,'partition independent time/distance');
 }
 for(let t=0;t<9;t+=.07){const a=lab.actor(clip,t,{scene});check(a.pose.flat().every(Number.isFinite),'scene finite');check(a.speed>0,'no fake idle')}
 check(Math.abs(lab.progression(9,native,'slow',false).distance-lab.progression(9,native,'slow',true).distance)<1e-12,'same final path progress');
}
for(const clip of data.clips){
 const cycle=clip.methods.improved,a=lab.actor(clip,0,{method:'source'});
 if(!cycle){check(a===null,'source interval absent, no replacement');continue}
 check(a.pose.flat().every(Number.isFinite),'unedited interval view finite');
 check(a.sourceFrame>=cycle.evidence.start&&a.sourceFrame<cycle.evidence.end,'source frame provenance');
}
for(const t of [3,4,6,7]){const a=lab.progression(t-1e-6,.8,'slow'),b=lab.progression(t+1e-6,.8,'slow');check(Math.abs(a.speed-b.speed)<1e-5&&Math.abs(a.acceleration-b.acceleration)<1e-4,'C2 speed envelope')}
for(let d=.01;d<12;d+=.08){const a=lab.trajectory(d-.0001,'turn'),b=lab.trajectory(d+.0001,'turn'),length=Math.hypot(...a.position.map((x,k)=>x-b.position[k]));check(Math.abs(length/.0002-1)<1e-5,'turn arc-length parameter')}
for(const count of [2,10,30]){
 const a=lab.encounterAt(4.4,count),snapshot=JSON.stringify(a),b=lab.encounterAt(4.4,count);
 check(snapshot===JSON.stringify(b),'deterministic encounter seek');check(a.agents.length===count,'count');
 for(let i=0;i<count;i++)check(lab.actor(data.clips[i%3],4.4,{scene:'encounter',count,index:i}).pose.flat().every(Number.isFinite),'mixed body finite');
}
assert.throws(()=>lab.progression(NaN,.8));checks++;
console.log(`${checks} candidate runtime assertions passed`);
