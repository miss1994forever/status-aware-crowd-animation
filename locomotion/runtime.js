/* Pure movement kernel, shared by browser and Node tests. Source units → fixed body-height display units. */
function hermite(a,b,va,vb,t,step){return a.map((x,k)=>(2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*step*va[k]+(-2*t**3+3*t*t)*b[k]+(t**3-t*t)*step*vb[k])}
function sampleCycle(cycle,distance){
  const phase=((distance/cycle.stride)%1+1)%1,last=cycle.poses.length-1,x=phase*last,i=Math.min(Math.floor(x),last-1);
  const points=cycle.poses[i].map((a,k)=>hermite(a,cycle.poses[i+1][k],cycle.tangents[i][k],cycle.tangents[i+1][k],x-i,1/last));
  const result=[];
  points.forEach((p,j)=>{const parent=cycle.parents[j];if(parent===null){result.push(p)}else{const v=p.map((x,a)=>x-points[parent][a]),n=Math.hypot(...v);result.push(v.map((x,a)=>result[parent][a]+x*cycle.bone_lengths[j]/Math.max(n,1e-10)))}});
  return result;
}
function pathAt(distance,kind,index=0,count=1){
  if(kind==='straight')return{position:[(index-(count-1)/2)*.85,0,distance],heading:0};
  if(kind!=='curve')throw Error('Unknown path');
  const r=3.2,theta=distance/r+2*Math.PI*index/count;
  return{position:[r*Math.sin(theta),0,r*Math.cos(theta)],heading:Math.PI/2+theta};
}
function placePose(pose,position,heading){const c=Math.cos(heading),s=Math.sin(heading);return pose.map(([x,y,z])=>[position[0]+c*x+s*z,position[1]+y,position[2]-s*x+c*z])}
function advanceDistance(distance,speed,dt){return distance+speed*dt}
if(typeof module!=='undefined')module.exports={sampleCycle,pathAt,placePose,advanceDistance};
