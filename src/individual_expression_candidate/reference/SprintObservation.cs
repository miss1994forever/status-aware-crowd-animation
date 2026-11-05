using UnityEngine;

// Current-target filter only. No relationship or cross-encounter memory.
public struct SprintObservation {
 public int TargetId { get; private set; }
 public float Value { get; private set; }
 public int Resets { get; private set; }
 bool initialized;

 public void Update(int targetId,float measurement,float dt) {
  if(!initialized||targetId!=TargetId) {
   if(initialized)Resets++;
   initialized=true;TargetId=targetId;
   Value=targetId<0?.5f:Mathf.Clamp01(measurement);
   return;
  }
  if(targetId<0){Value=.5f;return;}
  Value=Mathf.Lerp(Value,Mathf.Clamp01(measurement),1-Mathf.Exp(-Mathf.Max(0,dt)/.4f));
 }
}
