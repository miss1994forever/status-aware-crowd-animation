using UnityEngine;
using MotionMatching;

// Original project code. Engineering expression hypotheses, not calibrated status labels.
public class SprintActor : MonoBehaviour {
 public float OwnStatus; public float Response; public Vector3 LookTarget; public bool HasTarget;
 public int Mode; public float AppliedLowering,AppliedArmAngle,ObservedExpansion,FootError; public int PoseUpdates;
 public int LowerBodyPolicy=1; // 0: no lowering/added leg IK, 1: original, 2: continuous knee plane.
 public Vector3 RawLeftKnee,RawRightKnee,FinalLeftKnee,FinalRightKnee;
 SprintLegIK.Hint leftHint,rightHint;
 Animator rig; MotionMatchingSkinnedMeshRenderer skin;
 Transform hips,head,leftArm,leftForearm,rightArm,leftHip,leftKnee,leftFoot,rightHip,rightKnee,rightFoot;
 float initialHeight;
 void Start(){
  rig=GetComponent<Animator>(); skin=GetComponent<MotionMatchingSkinnedMeshRenderer>();
  if(rig==null||!rig.isHuman||skin==null){Debug.LogError("SPRINT missing humanoid renderer");enabled=false;return;}
  hips=B(HumanBodyBones.Hips);head=B(HumanBodyBones.Head);leftArm=B(HumanBodyBones.LeftUpperArm);leftForearm=B(HumanBodyBones.LeftLowerArm);rightArm=B(HumanBodyBones.RightUpperArm);
  leftHip=B(HumanBodyBones.LeftUpperLeg);leftKnee=B(HumanBodyBones.LeftLowerLeg);leftFoot=B(HumanBodyBones.LeftFoot);rightHip=B(HumanBodyBones.RightUpperLeg);rightKnee=B(HumanBodyBones.RightLowerLeg);rightFoot=B(HumanBodyBones.RightFoot);
  if(!hips||!head||!leftArm||!rightArm||!leftForearm||!leftHip||!rightHip||!leftKnee||!rightKnee||!leftFoot||!rightFoot){Debug.LogError("SPRINT incomplete human bones");enabled=false;return;}
  initialHeight=Mathf.Max(.5f,head.position.y-(leftFoot.position.y+rightFoot.position.y)*.5f);
  skin.OnSkeletonUpdated+=Apply;
 }
 Transform B(HumanBodyBones b){return rig.GetBoneTransform(b);}
 void OnDestroy(){if(skin!=null)skin.OnSkeletonUpdated-=Apply;}
 static void Leg(Transform hip,Transform knee,Transform foot,Vector3 target,Quaternion footRotation,Vector3 oldKnee){
  float a=Vector3.Distance(hip.position,knee.position),b=Vector3.Distance(knee.position,foot.position);Vector3 v=target-hip.position;float d=v.magnitude;
  if(d<.0001f)return;Vector3 axis=v/d;float reach=Mathf.Clamp(d,Mathf.Abs(a-b)+.00001f,a+b-.00001f);
  float along=(a*a-b*b+reach*reach)/(2*reach);float radius=Mathf.Sqrt(Mathf.Max(0,a*a-along*along));
  Vector3 bend=Vector3.ProjectOnPlane(oldKnee-hip.position,axis);if(bend.sqrMagnitude<1e-8f)bend=Vector3.ProjectOnPlane(hip.forward,axis);
  Vector3 desired=hip.position+axis*along+bend.normalized*radius;
  hip.rotation=Quaternion.FromToRotation(knee.position-hip.position,desired-hip.position)*hip.rotation;
  knee.rotation=Quaternion.FromToRotation(foot.position-knee.position,target-knee.position)*knee.rotation;foot.rotation=footRotation;
 }
 void Apply(){
  PoseUpdates++;Vector3 lf=leftFoot.position,rf=rightFoot.position,lk=leftKnee.position,rk=rightKnee.position;Quaternion lr=leftFoot.rotation,rr=rightFoot.rotation;
  Vector3 sourceOrigin=hips.position,lh=leftHip.position,rh=rightHip.position;Quaternion pelvis=hips.rotation,inverse=Quaternion.Inverse(pelvis);
  RawLeftKnee=inverse*(lk-sourceOrigin);RawRightKnee=inverse*(rk-sourceOrigin);
  float contraction=Mode==0?0:Mathf.Clamp01(1-OwnStatus);float response=Mode==2?Response:0;
  AppliedLowering=LowerBodyPolicy==0?0:.0206f*contraction;AppliedArmAngle=12*contraction+8*response;
  if(AppliedLowering>0){hips.position+=Vector3.down*AppliedLowering;
   if(LowerBodyPolicy==2){Vector3 forward=Vector3.Cross(rh-lh,head.position-sourceOrigin).normalized;SprintLegIK.Apply(leftHip,leftKnee,leftFoot,lf,lr,lh,lk,pelvis,forward,Time.deltaTime,ref leftHint);SprintLegIK.Apply(rightHip,rightKnee,rightFoot,rf,rr,rh,rk,pelvis,forward,Time.deltaTime,ref rightHint);}
   else {Leg(leftHip,leftKnee,leftFoot,lf,lr,lk);Leg(rightHip,rightKnee,rightFoot,rf,rr,rk);}
  }
  Vector3 inward=(rightArm.position-leftArm.position).normalized,down=(hips.position-head.position).normalized;
  Vector3 axis=Vector3.Cross(inward,-down).normalized,v=leftForearm.position-leftArm.position;
  Quaternion qa=Quaternion.AngleAxis(AppliedArmAngle,axis),qb=Quaternion.AngleAxis(-AppliedArmAngle,axis);
  leftArm.rotation=(Vector3.Dot(qa*v,inward)>Vector3.Dot(qb*v,inward)?qa:qb)*leftArm.rotation;
  if(response>0&&HasTarget){Vector3 target=Vector3.ProjectOnPlane(LookTarget-head.position,Vector3.up);if(target.sqrMagnitude>.01f){float yaw=Mathf.Clamp(Vector3.SignedAngle(transform.forward,target,Vector3.up),-35,35)*response;head.rotation=Quaternion.AngleAxis(yaw,Vector3.up)*head.rotation;}}
  FootError=Mathf.Max(Vector3.Distance(lf,leftFoot.position),Vector3.Distance(rf,rightFoot.position));
  FinalLeftKnee=inverse*(leftKnee.position-sourceOrigin);FinalRightKnee=inverse*(rightKnee.position-sourceOrigin);
  // Public observation comes only from rendered geometry, never another actor's hidden status.
  float width=Vector3.Distance(leftArm.position,rightArm.position);
  ObservedExpansion=width>.001f?Vector3.Dot(leftArm.position-leftForearm.position,inward)/width:0;
 }
}
