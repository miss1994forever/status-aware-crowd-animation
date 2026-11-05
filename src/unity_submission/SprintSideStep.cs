using UnityEngine;

// Bounded use of the existing controller's native fixed-orientation mode.
// It changes the facing query, never the accepted movement vector or bones.
public static class SprintSideStep {
 public struct State {
  public bool Locked;
  public float Remaining,Cooldown;
  public bool Release(){bool changed=Locked;Locked=false;Remaining=0;Cooldown=.7f;return changed;}
  public bool Update(float goalAngle,float facingAngle,float speed,bool near,float dt){
   Cooldown=Mathf.Max(0,Cooldown-dt);
   if(Locked){
    Remaining-=dt;
    if(Remaining<=0||speed<.25f||facingAngle>85||!near)return Release();
    return false;
   }
   if(Cooldown<=0&&near&&speed>=.34f&&goalAngle>=20&&goalAngle<=85&&facingAngle<=70){
    Locked=true;Remaining=.85f;return true;
   }
   return false;
  }
 }
}
