using System;

namespace IndividualExpressionCandidate {
 // Engineering hypotheses only; no learned/perceptually calibrated status function.
 public static class ExpressionMath {
  public const double MaxAngleRadians = 9 * Math.PI / 180;
  public static bool Finite(double v) { return !double.IsNaN(v) && !double.IsInfinity(v); }
  public static double Clamp(double v,double lo,double hi) { return Math.Max(lo,Math.Min(hi,v)); }
  public static double Smooth(double a,double b,double v) {
   double t=Clamp((v-a)/(b-a),0,1);return t*t*(3-2*t);
  }
  // dt is seconds; filter once per source-pose callback, never per arm.
  public static double Follow(double current,double target,double dt) {
   if(!Finite(current)||!Finite(target)||!Finite(dt)||dt<=0)return current;
   return current+(Clamp(target,0,1)-current)*(1-Math.Exp(-dt/.20));
  }
  public static double SpeedGain(double speed,double bodyScale) {
   if(!Finite(speed)||!Finite(bodyScale)||speed<0||bodyScale<=0)return 0;
   double s=speed/bodyScale; // body lengths per second, uniform-scale invariant
   return (.65+.35*Smooth(.05,.35,s))*(1-.35*Smooth(.8,1.6,s));
  }
  public struct Target {
   public double X,Y,Z,Angle;
   public bool Changed;
   public Target(double x,double y,double z) { X=x;Y=y;Z=z;Angle=0;Changed=false; }
  }
  // Unit upper-arm vector in body basis: X=outward, Y=up, Z=forward.
  // Both arms use outward-positive X. Input must be the fresh EMM pose.
  public static Target Solve(double x,double y,double z,double weight,double sideGain) {
   var result=new Target(x,y,z);
   if(!Finite(x)||!Finite(y)||!Finite(z)||!Finite(weight)||!Finite(sideGain))return result;
   if(Math.Abs(x*x+y*y+z*z-1)>1e-4||x<=0||y>=0)return result;
   double gate=Smooth(.03,.18,-y)*(1-Smooth(.25,.65,Math.Abs(z)));
   double amount=.60*Clamp(weight,0,1)*Clamp(sideGain,0,1)*gate;
   if(amount<=0)return result;
   double radius=Math.Sqrt(x*x+y*y),theta=Math.Atan2(x,-y);
   double wanted=Math.Asin(Clamp(x*(1-amount)/radius,0,1));
   double turn=Math.Min(MaxAngleRadians,Math.Max(0,theta-wanted));
   result.X=radius*Math.Sin(theta-turn);result.Y=-radius*Math.Cos(theta-turn);
   // Z is untouched, length stays one, elbow never crosses medial to shoulder.
   result.Angle=Math.Acos(Clamp(x*result.X+y*result.Y+z*z,-1,1));
   result.Changed=turn>1e-12;return result;
  }
 }
}
