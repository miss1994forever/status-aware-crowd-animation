using UnityEngine;
using IndividualExpressionCandidate;

// IE05 height/arms host adapter. Navigation and source EMM poses remain host-owned.
// All trial poses and leg hints are restored before the selected pose is committed.
public sealed class SprintExpressionBody {
 readonly ExpressionPolicy policy=new ExpressionPolicy();
 readonly BodyCombinationSearch search=new BodyCombinationSearch();
 Transform hips,head,la,ll,ra,rl,lh,lk,lf,rh,rk,rf;
 Transform[] bones;Quaternion[] rotations;Vector3 origin,lht,lkt,lft,rht,rkt,rft,right,up,forward;Quaternion pelvis,lfr,rfr;
 SprintLegIK.Hint leftHint,rightHint,trialLeft,trialRight;
 bool armsOnly;
 float dt,requestedArm,rawExpansion;
 public float Lowering,ArmAngle,KneeAngle;public bool Feasible,TemporalFallback;
 public SprintExpressionBody(Animator rig){
  Transform B(HumanBodyBones b)=>rig.GetBoneTransform(b);
  hips=B(HumanBodyBones.Hips);head=B(HumanBodyBones.Head);
  la=B(HumanBodyBones.LeftUpperArm);ll=B(HumanBodyBones.LeftLowerArm);ra=B(HumanBodyBones.RightUpperArm);rl=B(HumanBodyBones.RightLowerArm);
  lh=B(HumanBodyBones.LeftUpperLeg);lk=B(HumanBodyBones.LeftLowerLeg);lf=B(HumanBodyBones.LeftFoot);rh=B(HumanBodyBones.RightUpperLeg);rk=B(HumanBodyBones.RightLowerLeg);rf=B(HumanBodyBones.RightFoot);
  bones=new[]{hips,lh,lk,lf,rh,rk,rf,la,ra};rotations=new Quaternion[bones.Length];
 }
 public bool Valid=>hips&&head&&la&&ll&&ra&&rl&&lh&&lk&&lf&&rh&&rk&&rf;
 public float Expansion(){var v=ra.position-la.position;return Vector3.Dot(la.position-ll.position,v)/Mathf.Max(v.sqrMagnitude,1e-8f);}
 public float HeightRatio(){float leg=(Vector3.Distance(lh.position,lk.position)+Vector3.Distance(lk.position,lf.position)+Vector3.Distance(rh.position,rk.position)+Vector3.Distance(rk.position,rf.position))*.5f;return (hips.position.y-(lf.position.y+rf.position.y)*.5f)/Mathf.Max(leg,1e-5f);}
 void Restore(){hips.position=origin;for(int i=0;i<bones.Length;i++)bones[i].localRotation=rotations[i];}
 float Arm(Transform upper,Transform lower,Vector3 outward,double weight,double gain){
  var unit=(lower.position-upper.position).normalized;double x=Vector3.Dot(unit,outward),y=Vector3.Dot(unit,up),z=Vector3.Dot(unit,forward);
  if(x<=0||y>=0)return 0;
  double gate=ExpressionMath.Smooth(.03,.18,-y)*(1-ExpressionMath.Smooth(.25,.65,System.Math.Abs(z)));
  double amount=.85*ExpressionMath.Clamp(weight,0,1)*gain*gate,radius=System.Math.Sqrt(x*x+y*y);
  double theta=System.Math.Atan2(x,-y),wanted=System.Math.Asin(ExpressionMath.Clamp(x*(1-amount)/radius,0,1));
  double turn=System.Math.Min(18*System.Math.PI/180,System.Math.Max(0,theta-wanted));
  var target=outward*(float)(radius*System.Math.Sin(theta-turn))-up*(float)(radius*System.Math.Cos(theta-turn))+forward*(float)z;
  upper.rotation=Quaternion.FromToRotation(unit,target)*upper.rotation;return Vector3.Angle(unit,target);
 }
 BodyCombinationSearch.Evaluation Evaluate(double height,double arm){
  Restore();trialLeft=leftHint;trialRight=rightHint;
  if(!armsOnly){hips.position=origin+Vector3.down*(float)height;
   SprintLegIK.Apply(lh,lk,lf,lft,lfr,lht,lkt,pelvis,forward,dt,ref trialLeft);
   SprintLegIK.Apply(rh,rk,rf,rft,rfr,rht,rkt,pelvis,forward,dt,ref trialRight);
  }
  KneeAngle=Mathf.Max(Vector3.Angle(lkt-lht,lk.position-lh.position),Vector3.Angle(rkt-rht,rk.position-rh.position));
  ArmAngle=Mathf.Max(Arm(la,ll,-right,arm,1),Arm(ra,rl,right,arm,.75));
  float foot=Mathf.Max(Vector3.Distance(lf.position,lft),Vector3.Distance(rf.position,rft));
  float measured=Expansion(),wanted=rawExpansion*(1-.65f*requestedArm);
  return new BodyCombinationSearch.Evaluation{Feasible=ExpressionMath.Finite(measured)&&foot<.002f&&KneeAngle<=12.001f,ElbowResidual=(measured-wanted)/.04,KneeChange=KneeAngle/12,ArmChange=ArmAngle/18};
 }
 public void Apply(float target,float scale,float speed,float delta,bool lower,bool onlyArms=false){
  armsOnly=onlyArms;
  if(!Valid){Feasible=false;return;}dt=delta;origin=hips.position;pelvis=hips.rotation;
  for(int i=0;i<bones.Length;i++)rotations[i]=bones[i].localRotation;
  lht=lh.position;lkt=lk.position;lft=lf.position;rht=rh.position;rkt=rk.position;rft=rf.position;lfr=lf.rotation;rfr=rf.rotation;
  right=(ra.position-la.position).normalized;up=Vector3.ProjectOnPlane(head.position-hips.position,right).normalized;forward=Vector3.Cross(right,up).normalized;rawExpansion=Expansion();
  var cmd=policy.StepCompactness(target,lower&&!armsOnly?.018:0,scale,speed,dt,true);requestedArm=(float)cmd.ArmWeight;
  var plan=search.Solve(cmd.RequestedLowering,cmd.ArmWeight,dt,scale,Evaluate);Feasible=plan.Feasible;TemporalFallback=plan.TemporalFallback;
  if(!Feasible){Restore();Lowering=ArmAngle=KneeAngle=0;return;}
  Evaluate(plan.Lowering,plan.ArmWeight);leftHint=trialLeft;rightHint=trialRight;Lowering=(float)plan.Lowering;
 }
}
