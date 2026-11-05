const assert=require('node:assert/strict'),fs=require('node:fs');
const {sampleCycle,pathAt,placePose,advanceDistance}=require('../locomotion/runtime.js');
const data=JSON.parse(fs.readFileSync('outputs/locomotion/cycle.json','utf8'));
function diff(a,b){return Math.hypot(...a.map((x,i)=>x-b[i]))}
let checks=0;function check(ok){assert.ok(ok);checks++}
for(const d of [0,.03,.7,1.7]){
 const a=sampleCycle(data,d),b=sampleCycle(data,d+data.stride);
 check(a.every((p,i)=>diff(p,b[i])<1e-11));
 a.forEach((p,j)=>{const parent=data.parents[j];if(parent!==null)check(Math.abs(diff(p,a[parent])-data.bone_lengths[j])<1e-10)});
}
check(advanceDistance(.3,0,99)===.3);
check(Math.abs(advanceDistance(0,.2,3)-advanceDistance(0,1,.6))<1e-12);
for(const kind of ['straight','curve']){
 for(const d of [0,1,20.106192982974676]){
 const a=pathAt(d,kind),b=pathAt(d+1e-6,kind);
 check(Math.abs(diff(a.position,b.position)/1e-6-1)<1e-6);
 check(diff([(b.position[0]-a.position[0])/1e-6,(b.position[2]-a.position[2])/1e-6],[Math.sin(a.heading),Math.cos(a.heading)])<1e-6);
 }
 const d=data.stride,eps=1e-6,a=pathAt(d-eps,kind),b=pathAt(d+eps,kind);
 const pa=placePose(sampleCycle(data,d-eps),a.position,a.heading),pb=placePose(sampleCycle(data,d+eps),b.position,b.heading);
 check(pa.every((p,i)=>diff(p,pb[i])<1e-4));
}
console.log(`${checks} locomotion runtime assertions passed`);
