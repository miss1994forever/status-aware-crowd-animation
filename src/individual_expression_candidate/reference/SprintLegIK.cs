using UnityEngine;

// Knee-plane continuity for the added lowering layer. Source pose, feet and gait
// remain inputs; state belongs to one leg and is expressed in the source pelvis frame.
public static class SprintLegIK {
 public struct Hint {public bool Valid;public Vector3 LocalDirection;}

 public static Vector3 Knee(Vector3 hip,Vector3 foot,float upper,float lower,
  Vector3 sourceHip,Vector3 sourceKnee,Vector3 sourceFoot,Quaternion pelvisFrame,
  Vector3 anatomicalForward,float dt,ref Hint hint){
  Vector3 v=foot-hip;float distance=v.magnitude;
  if(distance<.0001f)return sourceKnee;
  Vector3 axis=v/distance;
  Vector3 sourceAxis=(sourceFoot-sourceHip).normalized;
  Vector3 sourceBend=Vector3.ProjectOnPlane(sourceKnee-sourceHip,sourceAxis);
  float strength=sourceBend.magnitude;
  Vector3 fallback=Vector3.ProjectOnPlane(anatomicalForward,axis);
  if(fallback.sqrMagnitude<1e-8f)fallback=Vector3.Cross(axis,pelvisFrame*Vector3.right);
  if(fallback.sqrMagnitude<1e-8f)fallback=Vector3.Cross(axis,Mathf.Abs(axis.y)<.9f?Vector3.up:Vector3.right);
  Vector3 source=Vector3.ProjectOnPlane(sourceBend,axis);
  Vector3 bend=hint.Valid?Vector3.ProjectOnPlane(pelvisFrame*hint.LocalDirection,axis):source;
  if(bend.sqrMagnitude<1e-8f||(!hint.Valid&&strength<.005f))bend=fallback;
  bend.Normalize();
  if(hint.Valid&&strength>.005f&&source.sqrMagnitude>1e-8f){
   float trust=Mathf.SmoothStep(0,1,Mathf.InverseLerp(.005f,.035f,strength));
   Vector3 goal=Vector3.Slerp(bend,source.normalized,1-Mathf.Exp(-Mathf.Max(0,dt)*trust/.08f));
   bend=Vector3.RotateTowards(bend,goal,360*Mathf.Deg2Rad*Mathf.Max(0,dt),0).normalized;
  }
  hint.Valid=true;hint.LocalDirection=Quaternion.Inverse(pelvisFrame)*bend;
  float reach=Mathf.Clamp(distance,Mathf.Abs(upper-lower)+.00001f,upper+lower-.00001f);
  float along=(upper*upper-lower*lower+reach*reach)/(2*reach);
  float radius=Mathf.Sqrt(Mathf.Max(0,upper*upper-along*along));
  return hip+axis*along+bend*radius;
 }

 public static void Apply(Transform hip,Transform knee,Transform foot,Vector3 target,
  Quaternion footRotation,Vector3 sourceHip,Vector3 sourceKnee,Quaternion pelvisFrame,Vector3 anatomicalForward,float dt,ref Hint hint){
  float upper=Vector3.Distance(hip.position,knee.position),lower=Vector3.Distance(knee.position,foot.position);
  Vector3 desired=Knee(hip.position,target,upper,lower,sourceHip,sourceKnee,target,pelvisFrame,anatomicalForward,dt,ref hint);
  hip.rotation=Quaternion.FromToRotation(knee.position-hip.position,desired-hip.position)*hip.rotation;
  knee.rotation=Quaternion.FromToRotation(foot.position-knee.position,target-knee.position)*knee.rotation;
  foot.rotation=footRotation;
 }
}
