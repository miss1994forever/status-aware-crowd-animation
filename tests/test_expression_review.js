const assert=require('node:assert/strict');
const {blendPose,frameAt,advance}=require('../expression-review/ui.js');
const parents=[null,0],lengths=[0,1];
const a=[[0,0,0],[0,1,0]],b=[[0,0,0],[1,0,0]];
for(let i=0;i<=100;i++){const p=blendPose(a,b,i/100,parents,lengths);assert.ok(Math.abs(Math.hypot(...p[1])-1)<1e-12);}
const run={frames:[{t:0,agents:[{pos:[0,0],yaw:0,pose:a,arrived:false}]},{t:.05,agents:[{pos:[1,0],yaw:1,pose:b,arrived:true}]}]};
assert.deepEqual(frameAt(run,10,parents,lengths),run.frames[1].agents);
assert.equal(frameAt(run,.025,parents,lengths)[0].pos[0],.5);
assert.equal(frameAt(run,-1,parents,lengths)[0].pos[0],0);
assert.deepEqual(advance(25,2,1,26,false),{t:26,playing:false});
assert.deepEqual(advance(25,2,1,26,true),{t:1,playing:true});
assert.deepEqual(advance(1,2,.5,26,false),{t:2,playing:true});
assert.deepEqual(advance(1,-2,1,26,false),{t:1,playing:true});
console.log('Fixed expression viewer: bone interpolation, clamping, terminal flags, timing and looping passed.');
