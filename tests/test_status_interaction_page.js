const assert=require('assert');
const {blendPose,frameAt,advance}=require('../status-interaction-lab/ui.js');
// Opposite leaning bones have valid endpoints; normalized interpolation dips.
const a=[[0,1,0],[.6,.2,0]],b=[[0,1,0],[-.6,.2,0]],parents=[null,0],lengths=[0,1];
const out=blendPose(a,b,.5,parents,lengths);assert(out.every(p=>p[1]>=0));assert(Math.abs(Math.hypot(...out[1].map((v,k)=>v-out[0][k]))-1)<1e-12);
const run={frames:[{t:0,agents:[{id:0,pos:[0,0],yaw:0,pose:a,arrived:false}]},{t:.05,agents:[{id:0,pos:[1,0],yaw:.1,pose:b,arrived:true}]}]};
assert.strictEqual(frameAt(run,.05,parents,lengths)[0].arrived,true);assert.strictEqual(frameAt(run,-1,parents,lengths)[0].arrived,false);
assert.deepStrictEqual(advance(25.9,1,1,26,false),{t:26,playing:false});assert(advance(25.9,1,1,26,true).t<1);
console.log('Replay interpolation, floor, final state and clock checks passed.');
