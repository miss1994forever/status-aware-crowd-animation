/* Deterministic world-space contacts: a contact event is keyed by unwrapped gait distance. */
if(typeof module!=='undefined'){var {sampleCycle,pathAt,placePose}=require('./runtime.js')}
const vadd=(a,b)=>a.map((x,i)=>x+b[i]),vsub=(a,b)=>a.map((x,i)=>x-b[i]),vmul=(a,s)=>a.map(x=>x*s),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),length=a=>Math.hypot(...a);
function unit(a,fallback=[0,0,1]){const n=length(a);return n>1e-10?vmul(a,1/n):fallback.slice()}
function smooth5(x){x=Math.max(0,Math.min(1,x));return x*x*x*(10+x*(-15+6*x))}
function twoBoneIK(hip,knee,ankle,target,forward,l1,l2){
 if(!(l1>0&&l2>0))throw Error('IK requires positive segment lengths');
 const requested=length(vsub(target,hip)),axis=unit(vsub(target,hip),[0,-1,0]);
 const min=Math.abs(l1-l2)+1e-6,max=l1+l2-1e-6,d=Math.max(min,Math.min(max,requested));
 const reached=vadd(hip,vmul(axis,d)),along=(l1*l1-l2*l2+d*d)/(2*d),bend=Math.sqrt(Math.max(0,l1*l1-along*along));
 let pole=vsub(vsub(knee,hip),vmul(axis,dot(vsub(knee,hip),axis)));
 let projectedGuide=vsub(forward,vmul(axis,dot(forward,axis)));
 if(length(projectedGuide)<1e-8){const basis=Math.abs(axis[0])<.8?[1,0,0]:[0,1,0];projectedGuide=vsub(basis,vmul(axis,dot(basis,axis)))}
 const guide=unit(projectedGuide);
 if(length(pole)<1e-7)pole=guide;
 const direction=unit(pole,guide),joint=vadd(vadd(hip,vmul(axis,along)),vmul(direction,bend));
 return{knee:joint,ankle:reached,unreachable:Math.abs(requested-d)>1e-7,reachError:Math.abs(requested-d),poleForward:dot(direction,guide)};
}
function contactState(cycle,distance,index,foot){
 const offset=index*.137,q=distance/cycle.stride+offset;
 for(const interval of foot.intervals){
  const event=Math.floor(q-interval.start+interval.ramp),age=q-interval.start-event;
  if(age>=-interval.ramp&&age<interval.duration+interval.ramp){const w=smooth5((age+interval.ramp)/interval.ramp)*smooth5((interval.duration+interval.ramp-age)/interval.ramp);return{weight:w,candidate:age>=0&&age<interval.duration,onsetDistance:(event+interval.start-offset)*cycle.stride,age,interval}}
 }
 return{weight:0,candidate:false,onsetDistance:null};
}
function baseActor(cycle,distance,kind,index=0,count=1){const path=pathAt(distance,kind,index,count);return{pose:placePose(sampleCycle(cycle,distance+cycle.stride*index*.137),path.position,path.heading),path}}
function contactActor(cycle,distance,kind,index=0,count=1,enabled=true){
 const base=baseActor(cycle,distance,kind,index,count),pose=base.pose.map(p=>p.slice()),contacts=[];
 for(const foot of cycle.contacts.feet){
  const state=contactState(cycle,distance,index,foot),w=state.weight;
  let marker={side:foot.side,weight:w,candidate:state.candidate,anchor:null,unreachable:false,reachError:0};
  if(w>0){
   const probes=[.15,.325,.5,.675,.85].map(u=>baseActor(cycle,state.onsetDistance+u*state.interval.duration*cycle.stride,kind,index,count).pose);
   const mean=k=>[0,1,2].map(a=>probes.reduce((s,p)=>s+p[k][a],0)/probes.length);
   const anchor=mean(foot.toe);anchor[1]=foot.ground_reference;
   // One forefoot marker constraint: retain source ankle-to-toe orientation (allows roll).
   const footVector=vsub(base.pose[foot.toe],base.pose[foot.ankle]);
   const targetToe=vadd(vmul(base.pose[foot.toe],1-w),vmul(anchor,w)),target=vsub(targetToe,footVector);
   const forward=[Math.sin(base.path.heading),0,Math.cos(base.path.heading)];
   const ik=twoBoneIK(base.pose[foot.hip],base.pose[foot.knee],base.pose[foot.ankle],target,forward,cycle.bone_lengths[foot.knee],cycle.bone_lengths[foot.ankle]);
   marker={...marker,anchor,unreachable:enabled&&ik.unreachable,reachError:enabled?ik.reachError:0,poleForward:ik.poleForward};
   if(enabled){pose[foot.knee]=ik.knee;pose[foot.ankle]=ik.ankle;pose[foot.toe]=vadd(ik.ankle,footVector);for(const j of foot.descendants)pose[j]=pose[foot.toe].slice()}
  }
  contacts.push(marker);
 }
 return{...base,pose,contacts};
}
if(typeof module!=='undefined')Object.assign(module.exports,{twoBoneIK,contactState,baseActor,contactActor,smooth5});
