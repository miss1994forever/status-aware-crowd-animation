using UnityEngine;

namespace IndividualExpressionCandidate {
 // Plain helper, not a MonoBehaviour: host explicitly chooses update order and fallback.
 public sealed class ExpressionOverlay {
  public struct Result {
   public bool ValidFrame;
   public float LeftDegrees,RightDegrees,Weight;
  }
  public Result Apply(Transform hips,Transform head,Transform leftUpper,Transform leftLower,
    Transform rightUpper,Transform rightLower,ExpressionCommand command,bool enabled) {
   var result=new Result();
   // Hard disable is exact identity. Do not crossfade baseline diagnostic mode.
   if(!enabled)return result;
   if(!command.Valid||!hips||!head||!leftUpper||!leftLower||!rightUpper||!rightLower)return result;
   if(!Finite(hips.position)||!Finite(head.position)||!Finite(leftUpper.position)||!Finite(leftLower.position)||
      !Finite(rightUpper.position)||!Finite(rightLower.position))return result;
   if((leftLower.position-leftUpper.position).sqrMagnitude<1e-10f||
      (rightLower.position-rightUpper.position).sqrMagnitude<1e-10f)return result;
   Vector3 right=rightUpper.position-leftUpper.position;
   if(right.sqrMagnitude<1e-8f)return result;right.Normalize();
   Vector3 up=Vector3.ProjectOnPlane(head.position-hips.position,right);
   if(up.sqrMagnitude<1e-8f)return result;up.Normalize();
   Vector3 forward=Vector3.Cross(right,up).normalized;
   result.ValidFrame=true;result.Weight=(float)command.ArmWeight;
   result.LeftDegrees=Arm(leftUpper,leftLower,-right,up,forward,command.ArmWeight,1);
   result.RightDegrees=Arm(rightUpper,rightLower,right,up,forward,command.ArmWeight,.75);
   return result;
  }
  static bool Finite(Vector3 v) {
   return ExpressionMath.Finite(v.x)&&ExpressionMath.Finite(v.y)&&ExpressionMath.Finite(v.z);
  }
  float Arm(Transform upper,Transform lower,Vector3 outward,Vector3 up,Vector3 forward,double weight,double sideGain) {
   Vector3 v=lower.position-upper.position;float length=v.magnitude;
   if(length<1e-5f)return 0;Vector3 unit=v/length;
   var t=ExpressionMath.Solve(Vector3.Dot(unit,outward),Vector3.Dot(unit,up),Vector3.Dot(unit,forward),weight,sideGain);
   if(!t.Changed)return 0;
   Vector3 target=outward*(float)t.X+up*(float)t.Y+forward*(float)t.Z;
   upper.rotation=Quaternion.FromToRotation(unit,target)*upper.rotation;
   return (float)(t.Angle*Mathf.Rad2Deg);
  }
 }
}
