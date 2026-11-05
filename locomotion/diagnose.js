/* Fixed full-cycle protocol. Thresholds come from raw motion; never tuned to output metrics. */
const fs=require('node:fs');
const {contactActor,contactState}=require('./contact.js');
const data=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const len=v=>Math.hypot(...v),sub=(a,b)=>a.map((x,i)=>x-b[i]);
function stats(a){const s=a.slice().sort((a,b)=>a-b);return{count:s.length,mean:s.reduce((a,b)=>a+b,0)/Math.max(1,s.length),rms:Math.sqrt(s.reduce((a,b)=>a+b*b,0)/Math.max(s.length,1)),median:s[Math.floor(s.length*.5)]??null,p95:s[Math.min(s.length-1,Math.floor(s.length*.95))]??null,max:s[s.length-1]??null}}
const results=[];
for(const kind of ['straight','curve'])for(const speed of [0,.8,1.2]){
 const record={kind,speed,versions:{}};
 for(const improved of [false,true]){
 const samples={all:[],support:[],core:[],transition:[]},heights={all:[],support:[],core:[],transition:[]},reach=[],kneeDirections=[],perFoot=Object.fromEntries(data.contacts.feet.map(f=>[f.side,{allSpeed:[],supportSpeed:[],transitionSpeed:[],supportGap:[],signedHeight:[],signedReferenceGap:[]} ]));let maxBoneError=0,maxChange=0;
 for(let i=0;i<320;i++){
 const d=data.stride*(3+i/320),dt=1/2000;
 const actor=contactActor(data,d,kind,0,1,improved),a=contactActor(data,d-speed*dt,kind,0,1,improved).pose,b=contactActor(data,d+speed*dt,kind,0,1,improved).pose;
 const original=contactActor(data,d,kind,0,1,false).pose;
 for(let j=0;j<actor.pose.length;j++){const parent=data.parents[j];if(parent!==null)maxBoneError=Math.max(maxBoneError,Math.abs(len(sub(actor.pose[j],actor.pose[parent]))-data.bone_lengths[j]));maxChange=Math.max(maxChange,len(sub(actor.pose[j],original[j])))}
 data.contacts.feet.forEach((foot,k)=>{
 const state=actor.contacts[k],v=len([0,2].map(axis=>(b[foot.toe][axis]-a[foot.toe][axis])/(2*dt))),y=Math.abs(actor.pose[foot.toe][1]-foot.ground_reference);
 const pf=perFoot[foot.side];pf.allSpeed.push(v);pf.signedHeight.push(actor.pose[foot.toe][1]);pf.signedReferenceGap.push(actor.pose[foot.toe][1]-foot.ground_reference);if(state.candidate){pf.supportSpeed.push(v);pf.supportGap.push(y)}if(state.weight>0&&!state.candidate)pf.transitionSpeed.push(v);
 for(const group of ['all',...(state.candidate?['support']:[]),...(state.candidate&&state.weight>.999?['core']:[]),...(state.weight>0&&!state.candidate?['transition']:[])]){samples[group].push(v);heights[group].push(y)}
 if(state.weight>0){reach.push(state.reachError);if(state.poleForward!==undefined)kneeDirections.push(state.poleForward)}
 });
 }
 const edgeJumps=[];
 for(const foot of data.contacts.feet)for(const interval of foot.intervals)for(const edge of [interval.start-interval.ramp,interval.start,interval.start+interval.duration,interval.start+interval.duration+interval.ramp]){
 const d=(3+edge)*data.stride,a=contactActor(data,d-1e-7,kind,0,1,improved).pose,b=contactActor(data,d+1e-7,kind,0,1,improved).pose;edgeJumps.push(Math.max(...a.map((p,j)=>len(sub(p,b[j])))));
 }
 record.versions[improved?'improved':'original']={per_foot:Object.fromEntries(Object.entries(perFoot).map(([side,p])=>[side,{all_speed:stats(p.allSpeed),support_speed:stats(p.supportSpeed),transition_speed:stats(p.transitionSpeed),support_reference_gap:stats(p.supportGap),minimum_toe_world_y:Math.min(...p.signedHeight),minimum_toe_reference_gap:Math.min(...p.signedReferenceGap)}])),horizontal_toe_speed:Object.fromEntries(Object.entries(samples).map(([k,v])=>[k,stats(v)])),absolute_toe_ground_gap:Object.fromEntries(Object.entries(heights).map(([k,v])=>[k,stats(v)])),reach_error:stats(reach),unreachable_samples:reach.filter(v=>v>1e-7).length,min_knee_pole_forward:Math.min(...kneeDirections),max_bone_length_absolute_error:maxBoneError,max_joint_change:maxChange,max_contact_edge_position_difference:Math.max(...edgeJumps)};
 }
 results.push(record);
}
fs.writeFileSync(process.argv[3],JSON.stringify({protocol:{samples_per_cycle:320,cycles_sampled:'full phase [0,1) at cycle 3',velocity_finite_difference_seconds:1/2000,support:'all samples in raw inferred candidate interval; no output-based selection',core:'candidate interval with full anchor weight > .999',transition:'smooth envelope before/after candidate interval, not asserted support',all:'all phases, both feet',units:'fixed source-body-height reference; speed per second; toe gap measured from per-foot raw candidate median toe marker height, not inferred sole',no_ground_truth_contacts:true},raw:data.contacts,results},null,2)+'\n');
