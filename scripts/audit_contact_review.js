/* Main-review audit: fixed pre-IK contact mask, independent finite differences.
 * Generated output is a diagnostic, not a contact-label or perception validation.
 */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const {sampleCycle} = require('../locomotion/runtime.js');
const {contactActor} = require('../locomotion/contact.js');
const root = require('node:path').resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(root+'/outputs/locomotion/cycle.json'));
const old = JSON.parse(fs.readFileSync(root+'/outputs/contact-review/baseline-cycle.json'));
const distance = (a,b) => Math.hypot(...a.map((v,k)=>v-b[k]));
for(let i=0;i<100;i++) {
  const a=sampleCycle(data,i*.017),b=sampleCycle(old,i*.017);
  assert.ok(a.every((p,j)=>distance(p,b[j])<1e-12),'Baseline pose changed');
}
function summary(values) {
  const s=values.slice().sort((a,b)=>a-b);
  return {n:s.length,mean:s.reduce((a,b)=>a+b,0)/s.length,
    p95:s[Math.floor((s.length-1)*.95)],max:s[s.length-1]};
}
const rows=[];
for(const path of ['straight','curve']) for(const actorIndex of [0,7]) {
  const count=actorIndex?10:1,speed=.8;
  for(const dt of [.001,.00025]) for(const enabled of [false,true]) {
    const feet=data.contacts.feet.map(f=>({side:f.side,all:[],candidate:[],edge:[],core:[],minHeight:Infinity}));
    let maxBoneError=0,maxDisplacement=0,minPole=Infinity;
    for(let n=0;n<960;n++) {
      const d=(4+n/960)*data.stride;
      const here=contactActor(data,d,path,actorIndex,count,enabled);
      const raw=contactActor(data,d,path,actorIndex,count,false);
      const before=contactActor(data,d-speed*dt,path,actorIndex,count,enabled);
      const after=contactActor(data,d+speed*dt,path,actorIndex,count,enabled);
      here.pose.forEach((p,j)=>{
        assert.ok(p.every(Number.isFinite));
        maxDisplacement=Math.max(maxDisplacement,distance(p,raw.pose[j]));
        if(data.parents[j]!==null)maxBoneError=Math.max(maxBoneError,
          Math.abs(distance(p,here.pose[data.parents[j]])-data.bone_lengths[j]));
      });
      data.contacts.feet.forEach((f,k)=>{
        const v=Math.hypot(...[0,2].map(a=>(after.pose[f.toe][a]-before.pose[f.toe][a])/(2*dt)));
        const record=feet[k],w=raw.contacts[k].weight;
        record.all.push(v);record.minHeight=Math.min(record.minHeight,here.pose[f.toe][1]);
        if(raw.contacts[k].candidate)record.candidate.push(v);
        if(w>0)record[raw.contacts[k].candidate&&w>.999?'core':'edge'].push(v);
        if(here.contacts[k].poleForward!==undefined)minPole=Math.min(minPole,here.contacts[k].poleForward);
      });
    }
    assert.ok(maxBoneError<1e-9,'Bone length changed');
    rows.push({path,actorIndex,count,dt,enabled,maxBoneError,maxDisplacement,minPole,
      feet:feet.map(f=>({...f,all:summary(f.all),candidate:summary(f.candidate),
        edge:summary(f.edge),core:summary(f.core)}))});
  }
}
const hash=p=>require('node:crypto').createHash('sha256').update(fs.readFileSync(root+'/'+p)).digest('hex');
const result={sourceHashes:{contact:hash('locomotion/contact.js'),cycle:hash('outputs/locomotion/cycle.json')},protocol:{speed:.8,phaseSamples:960,contactMask:'same pre-IK inferred intervals',
  notes:'Normal cycle and baseline unchanged at 100 samples; no contact truth labels. All/edge/core shown separately. Units reference body heights, seconds.'},rows};
fs.writeFileSync(root+'/outputs/contact-review/main-audit.json',JSON.stringify(result,null,2)+'\n');
console.log('Main audit passed: baseline parity, finite positions, bone lengths; '+rows.length+' paired diagnostic rows.');
