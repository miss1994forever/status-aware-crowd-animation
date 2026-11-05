const assert=require('node:assert/strict'),fs=require('node:fs');
const {sampleCycle,pathAt,placePose}=require('../locomotion/runtime.js');
const {contactActor,contactState,twoBoneIK}=require('../locomotion/contact.js');
const data=JSON.parse(fs.readFileSync('outputs/locomotion/cycle.json','utf8')),metrics=JSON.parse(fs.readFileSync('outputs/locomotion/contact-diagnostics.json','utf8'));
const backup=JSON.parse(fs.readFileSync('outputs/locomotion-before-contact-fix/cycle.json','utf8'));for(const key of ['poses','tangents','stride','parents','bone_lengths'])assert.deepEqual(data[key],backup[key]);
const len=a=>Math.hypot(...a),sub=(a,b)=>a.map((x,i)=>x-b[i]);let count=0;function check(v){assert.ok(v);count++}
for(const target of [[0,.2,0],[0,-8,0],[0,1,0],[0,1.00000001,0],[7,1,0]]){
 const r=twoBoneIK([0,1,0],[0,.6,.2],[0,0,0],target,[0,0,1],.5,.5);
 check([...r.knee,...r.ankle].every(Number.isFinite));check(Math.abs(len(sub(r.knee,[0,1,0]))-.5)<1e-8);check(Math.abs(len(sub(r.ankle,r.knee))-.5)<1e-8);
 if(len(sub(target,[0,1,0]))>1)check(r.unreachable&&r.reachError>0);if(len(sub(target,[0,1,0]))>.1&&len(sub(target,[0,1,0]))<.99)check(!r.unreachable);check(r.poleForward>0);
}
const parallel=twoBoneIK([0,0,0],[.5,0,0],[1,0,0],[9,0,0],[1,0,0],.5,.5);check(Math.abs(len(parallel.knee)-.5)<1e-8);
for(const kind of ['straight','curve'])for(const actor of [0,7])for(let i=0;i<160;i++){
 const d=data.stride*(2+i/160),a=contactActor(data,d,kind,actor,actor?10:1,false),b=contactActor(data,d,kind,actor,actor?10:1,true);
 const p=pathAt(d,kind,actor,actor?10:1),old=placePose(sampleCycle(data,d+data.stride*actor*.137),p.position,p.heading);
 check(a.pose.every((p,j)=>len(sub(p,old[j]))<1e-12));check(b.pose.flat().every(Number.isFinite));for(let j=0;j<data.names.length;j++)if(!/^(UpperLeg|LowerLeg|Foot|Toes)_[LR]/.test(data.names[j]))check(len(sub(a.pose[j],b.pose[j]))<1e-12);
 check(JSON.stringify(b.pose)===JSON.stringify(contactActor(data,d,kind,actor,actor?10:1,true).pose)); // zero speed / paused same input
 for(let j=0;j<b.pose.length;j++){const parent=data.parents[j];if(parent!==null)check(Math.abs(len(sub(b.pose[j],b.pose[parent]))-data.bone_lengths[j])<1e-8)}
 for(const contact of b.contacts)if(contact.weight>0)check(contact.poleForward>.5);
}
for(const foot of data.contacts.feet)for(const interval of foot.intervals)for(const edge of [interval.start-interval.ramp,interval.start,interval.start+interval.duration,interval.start+interval.duration+interval.ramp,1])for(const kind of ['straight','curve']){
 const d=data.stride*(3+edge),h=1e-6,a=contactActor(data,d-h,kind).pose,b=contactActor(data,d+h,kind).pose;
 check(Math.max(...a.map((p,j)=>len(sub(p,b[j]))))<.0001);const center=contactActor(data,d,kind).pose;check(Math.max(...a.map((p,j)=>len(p.map((x,k)=>(center[j][k]-x)/h-(b[j][k]-center[j][k])/h))))<.03);
}
for(const row of metrics.results){const a=row.versions.original,b=row.versions.improved;
 check(b.max_bone_length_absolute_error<1e-8);check(b.max_contact_edge_position_difference<1e-4);
 for(const foot of Object.values(b.per_foot))check(foot.minimum_toe_world_y>-.005);
 if(row.speed>0){check(b.horizontal_toe_speed.support.mean<a.horizontal_toe_speed.support.mean*.15);check(b.absolute_toe_ground_gap.support.mean<a.absolute_toe_ground_gap.support.mean*.2);check(b.horizontal_toe_speed.all.mean<a.horizontal_toe_speed.all.mean*1.05);check(b.horizontal_toe_speed.transition.mean>a.horizontal_toe_speed.transition.mean)}else{check(b.horizontal_toe_speed.all.max===0)}
}
console.log(`${count} contact/IK assertions passed`);
