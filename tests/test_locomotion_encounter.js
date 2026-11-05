const assert=require('node:assert/strict'),fs=require('node:fs');
const{createEncounter,stepEncounter,runEncounter}=require('../src/locomotion_encounter.js');
const distance=(a,b)=>Math.hypot(...a.map((x,i)=>x-b[i]));let assertions=0;function check(v){assert.ok(v);assertions++}
const records=[];
for(const count of [2,10])for(const scenario of ['headon','crossing'])for(const speed of [.6,.8,1])for(const offset of [-.4,0,.4]){
 const options={count,scenario,speed,offset},a=runEncounter(options,false,22),b=runEncounter(options,true,22);
 check(a.minSeparation<.48);check(b.minSeparation>.48);check(b.overlapSamples===0);check(b.agents.every(a=>distance(a.position,a.goal)<.1));
 records.push({options,seconds:22,no_response_min_center_distance:a.minSeparation,response_min_center_distance:b.minSeparation,no_response_overlap_samples:a.overlapSamples,response_overlap_samples:b.overlapSamples,max_remaining_goal_distance:Math.max(...b.agents.map(a=>distance(a.position,a.goal)))});
}
const w=createEncounter();let peakSteer=0,slowestPassing=Infinity;
for(let i=0;i<1200;i++){
 const before=w.agents.map(a=>structuredClone(a));stepEncounter(w,1/60,true);
 w.agents.forEach((a,j)=>{check(a.position.every(Number.isFinite));check(distance(a.velocity,before[j].velocity)<=w.config.acceleration/60+1e-12);check(Math.abs(a.heading-before[j].heading)<=w.config.maxTurnRate/60+1e-12);check(Math.abs(a.distance-before[j].distance-distance(a.position,before[j].position))<1e-12);peakSteer=Math.max(peakSteer,a.steer);if(a.steer>.95)slowestPassing=Math.min(slowestPassing,Math.hypot(...a.velocity))});
}
check(peakSteer>.9);check(slowestPassing<.72);
function onset(offset){const w=createEncounter({offset});for(let i=0;i<600;i++){stepEncounter(w,1/60,true);if(w.agents[0].passing.length)return w.time}return Infinity}
const early=onset(0),late=onset(2);check(late-early>.8);
const alone=createEncounter();alone.agents=alone.agents.slice(0,1);for(let i=0;i<600;i++)stepEncounter(alone,1/60,true);check(alone.agents[0].steer===0);check(alone.agents[0].position[0]===-.08);
check(JSON.stringify(runEncounter({},true,10))===JSON.stringify(runEncounter({},true,10)));
const frozen=createEncounter({speed:0}),initial=frozen.agents.map(a=>a.position.slice());for(let i=0;i<30;i++)stepEncounter(frozen,1/60,true);check(frozen.agents.every((a,i)=>distance(a.position,initial[i])===0&&a.distance===0));
fs.mkdirSync('outputs/locomotion-encounter',{recursive:true});fs.writeFileSync('outputs/locomotion-encounter/controller-checks.json',JSON.stringify({protocol:{radius:.24,dt:1/60,scenarios:'36 deterministic synthetic conditions, not independent human/motion samples',geometry:'center discs only; not mesh collision'},records,neighbor_dependence:{normal_onset:early,delayed_neighbor_onset:late,isolated_agent_steering:alone.agents[0].steer},assertions},null,2)+'\n');
console.log(`${assertions} encounter assertions passed; ${records.length} conditions`);
