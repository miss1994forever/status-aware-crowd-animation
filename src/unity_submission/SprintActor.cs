using UnityEngine;
using MotionMatching;

// Original project code. Engineering expression hypotheses, not calibrated status labels.
public class SprintActor : MonoBehaviour {
 public int ExpressionVersion; public float ExpressionTarget,RootSpeed,ObservedHeight,RawExpansion,RawHeight;
 public bool PostureExpression;public float AppliedTorsoAngle,AppliedHeadAngle;
 float postureWeight;Transform spine,midChest,upperChest,neck;
 public SprintExpressionBody ExpressionBody;
 public float OwnStatus; public float Response;
 public float ExpressionStatusOverride=-1; // Diagnostic control: freeze pose expression while changing own status.
 public int Mode; public float AppliedLowering,AppliedArmAngle,ObservedExpansion,FootError; public int PoseUpdates;
 public int LowerBodyPolicy=2; // 0: no lowering/added leg IK, 1: original, 2: continuous knee plane.
 public int HeadFilterLevel=1;
 public bool HeadStability;Quaternion smoothHead;bool headReady;
 public Quaternion RawHeadLocal,RawNeckLocal,RawHeadChest,FinalHeadChest;
 public Vector3 RawLeftKnee,RawRightKnee,FinalLeftKnee,FinalRightKnee;
 SprintLegIK.Hint leftHint,rightHint;
 Animator rig; MotionMatchingSkinnedMeshRenderer skin;
 Transform chest;Transform hips,head,leftArm,leftForearm,rightArm,leftHip,leftKnee,leftFoot,rightHip,rightKnee,rightFoot;
 float initialHeight;
 void Start(){
  rig=GetComponent<Animator>(); skin=GetComponent<MotionMatchingSkinnedMeshRenderer>();
  if(rig==null||!rig.isHuman||skin==null){Debug.LogError("SPRINT missing humanoid renderer");enabled=false;return;}
  hips=B(HumanBodyBones.Hips);head=B(HumanBodyBones.Head);leftArm=B(HumanBodyBones.LeftUpperArm);leftForearm=B(HumanBodyBones.LeftLowerArm);rightArm=B(HumanBodyBones.RightUpperArm);
  leftHip=B(HumanBodyBones.LeftUpperLeg);leftKnee=B(HumanBodyBones.LeftLowerLeg);leftFoot=B(HumanBodyBones.LeftFoot);rightHip=B(HumanBodyBones.RightUpperLeg);rightKnee=B(HumanBodyBones.RightLowerLeg);rightFoot=B(HumanBodyBones.RightFoot);
  if(!hips||!head||!leftArm||!rightArm||!leftForearm||!leftHip||!rightHip||!leftKnee||!rightKnee||!leftFoot||!rightFoot){Debug.LogError("SPRINT incomplete human bones");enabled=false;return;}
  chest=B(HumanBodyBones.UpperChest);if(!chest)chest=B(HumanBodyBones.Chest);
  initialHeight=Mathf.Max(.5f,head.position.y-(leftFoot.position.y+rightFoot.position.y)*.5f);
  spine=B(HumanBodyBones.Spine);midChest=B(HumanBodyBones.Chest);upperChest=B(HumanBodyBones.UpperChest);neck=B(HumanBodyBones.Neck);
  ExpressionBody=new SprintExpressionBody(rig);
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
  RawHeadLocal=head.localRotation;RawNeckLocal=head.parent.localRotation;RawHeadChest=Quaternion.Inverse(chest?chest.rotation:hips.rotation)*head.rotation;
  PoseUpdates++;Vector3 lf=leftFoot.position,rf=rightFoot.position,lk=leftKnee.position,rk=rightKnee.position;Quaternion lr=leftFoot.rotation,rr=rightFoot.rotation;
  Vector3 sourceOrigin=hips.position,lh=leftHip.position,rh=rightHip.position;Quaternion pelvis=hips.rotation,inverse=Quaternion.Inverse(pelvis);
  RawLeftKnee=inverse*(lk-sourceOrigin);RawRightKnee=inverse*(rk-sourceOrigin);
  if(ExpressionBody.Valid){RawExpansion=ExpressionBody.Expansion();RawHeight=ExpressionBody.HeightRatio();}
  if(ExpressionVersion==1&&ExpressionBody.Valid){
   ExpressionBody.Apply(ExpressionTarget,initialHeight,RootSpeed,Time.deltaTime,LowerBodyPolicy!=0);
   AppliedLowering=ExpressionBody.Lowering;AppliedArmAngle=ExpressionBody.ArmAngle;
  }else{
  float expressionStatus=ExpressionStatusOverride>=0?ExpressionStatusOverride:OwnStatus;
  float contraction=Mode==0?0:Mathf.Clamp01(1-expressionStatus);float response=Mode==2?Response:0;
  AppliedLowering=LowerBodyPolicy==0?0:.0206f*contraction;AppliedArmAngle=12*contraction+8*response;
  if(AppliedLowering>0){hips.position+=Vector3.down*AppliedLowering;
   if(LowerBodyPolicy==2){Vector3 forward=Vector3.Cross(rh-lh,head.position-sourceOrigin).normalized;SprintLegIK.Apply(leftHip,leftKnee,leftFoot,lf,lr,lh,lk,pelvis,forward,Time.deltaTime,ref leftHint);SprintLegIK.Apply(rightHip,rightKnee,rightFoot,rf,rr,rh,rk,pelvis,forward,Time.deltaTime,ref rightHint);}
   else {Leg(leftHip,leftKnee,leftFoot,lf,lr,lk);Leg(rightHip,rightKnee,rightFoot,rf,rr,rk);}
  }
  if(ExpressionVersion==2&&ExpressionBody.Valid){
   ExpressionBody.Apply(ExpressionTarget,initialHeight,RootSpeed,Time.deltaTime,false,true);
   AppliedArmAngle=ExpressionBody.ArmAngle;
  }else{
  Vector3 inward=(rightArm.position-leftArm.position).normalized,down=(hips.position-head.position).normalized;
  Vector3 axis=Vector3.Cross(inward,-down).normalized,v=leftForearm.position-leftArm.position;
  Quaternion qa=Quaternion.AngleAxis(AppliedArmAngle,axis),qb=Quaternion.AngleAxis(-AppliedArmAngle,axis);
  leftArm.rotation=(Vector3.Dot(qa*v,inward)>Vector3.Dot(qb*v,inward)?qa:qb)*leftArm.rotation;
  }
  }
  // Pitch only above the pelvis. The legs, root and foot targets are untouched.
  Vector3 postureAxis=(rightArm.position-leftArm.position).normalized;
  AppliedTorsoAngle=AppliedHeadAngle=0;
  if(PostureExpression&&ExpressionVersion==2&&spine&&midChest&&neck){
   float desired=Mathf.SmoothStep(0,1,Mathf.InverseLerp(.15f,.85f,ExpressionTarget));
   postureWeight=Mathf.Lerp(postureWeight,desired,1-Mathf.Exp(-Time.deltaTime/.25f));
   AppliedTorsoAngle=10*postureWeight;AppliedHeadAngle=8*postureWeight;
   spine.rotation=Quaternion.AngleAxis(AppliedTorsoAngle*.5f,postureAxis)*spine.rotation;
   midChest.rotation=Quaternion.AngleAxis(AppliedTorsoAngle*(upperChest?1f/3:.5f),postureAxis)*midChest.rotation;
   if(upperChest)upperChest.rotation=Quaternion.AngleAxis(AppliedTorsoAngle/6,postureAxis)*upperChest.rotation;
  }else postureWeight=0;
  // No gaze target. Filter local head orientation only; position/neck/body stay native.
  if(HeadStability){
   if(!headReady||Time.deltaTime>.1f){smoothHead=RawHeadChest;headReady=true;}
   Quaternion headGoal=Quaternion.Slerp(smoothHead,RawHeadChest,1-Mathf.Exp(-Mathf.Log(2)*Time.deltaTime/(HeadFilterLevel>=2?.12f:.08f)));
   if(HeadFilterLevel>=2){
    Quaternion delta=headGoal*Quaternion.Inverse(smoothHead);delta.ToAngleAxis(out float degrees,out Vector3 axis);
    if(degrees>180)degrees-=360;
    Vector3 angular=degrees==0?Vector3.zero:axis*degrees;
    Vector3 lateral=Quaternion.Inverse(chest?chest.rotation:hips.rotation)*postureAxis;
    float pitch=Vector3.Dot(angular,lateral);
    Vector3 remaining=angular-lateral*pitch;
    angular=Vector3.ClampMagnitude(remaining,90*Time.deltaTime)+lateral*Mathf.Clamp(pitch,-45*Time.deltaTime,45*Time.deltaTime);
    angular=Vector3.ClampMagnitude(angular,90*Time.deltaTime);
    if(angular.sqrMagnitude>1e-10f)smoothHead=Quaternion.AngleAxis(angular.magnitude,angular.normalized)*smoothHead;
   }else smoothHead=headGoal;
   head.rotation=(chest?chest.rotation:hips.rotation)*smoothHead;
  }else headReady=false;
  // Add expression after source-head stabilization, so filtering cannot erase it.
  if(AppliedHeadAngle>0){
   neck.rotation=Quaternion.AngleAxis(AppliedHeadAngle*.6f,postureAxis)*neck.rotation;
   head.rotation=Quaternion.AngleAxis(AppliedHeadAngle*.4f,postureAxis)*head.rotation;
  }
  FinalHeadChest=Quaternion.Inverse(chest?chest.rotation:hips.rotation)*head.rotation;
  FootError=Mathf.Max(Vector3.Distance(lf,leftFoot.position),Vector3.Distance(rf,rightFoot.position));
  FinalLeftKnee=inverse*(leftKnee.position-sourceOrigin);FinalRightKnee=inverse*(rightKnee.position-sourceOrigin);
  // Public observation comes only from rendered geometry, never another actor's hidden status.
  float width=Vector3.Distance(leftArm.position,rightArm.position);
  if(ExpressionBody.Valid)ObservedHeight=ExpressionBody.HeightRatio();
  ObservedExpansion=width>.001f?Vector3.Dot(leftArm.position-leftForearm.position,(rightArm.position-leftArm.position).normalized)/width:0;
 }
}
