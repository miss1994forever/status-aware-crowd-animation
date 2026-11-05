using System;

namespace IndividualExpressionCandidate {
 // Authoring hypothesis, explicitly separate from the geometry editor.
 // A value is an intended appearance, not an inferred/validated social rank.
 public readonly struct ExpressionProfile {
  public readonly double CompactAtStatusZero,CompactAtStatusOne,MaxLoweringFraction;
  public ExpressionProfile(double compactAtStatusZero,double compactAtStatusOne,double maxLoweringFraction) {
   CompactAtStatusZero=compactAtStatusZero;CompactAtStatusOne=compactAtStatusOne;
   MaxLoweringFraction=maxLoweringFraction;
  }
  public static ExpressionProfile SourceToCompact { get { return new ExpressionProfile(1,0,.0125); } }
  public static ExpressionProfile Neutral { get { return new ExpressionProfile(0,0,0); } }
  public bool Valid { get { return ExpressionMath.Finite(CompactAtStatusZero)&&ExpressionMath.Finite(CompactAtStatusOne)&&
   ExpressionMath.Finite(MaxLoweringFraction)&&CompactAtStatusZero>=0&&CompactAtStatusZero<=1&&
   CompactAtStatusOne>=0&&CompactAtStatusOne<=1&&MaxLoweringFraction>=0&&MaxLoweringFraction<=.02; } }
 }
 public readonly struct ExpressionCommand {
  public readonly bool Valid;
  public readonly double TargetCompactness,ArmWeight,RequestedLowering,Weight;
  internal ExpressionCommand(bool valid,double target,double weight,double lowering) {
   Valid=valid;TargetCompactness=target;Weight=weight;ArmWeight=weight;RequestedLowering=lowering;
  }
  // Host supplies a permitted vertical offset in metres. This does NOT solve legs.
  public double BoundedLowering(double capacity) {
   return Valid&&ExpressionMath.Finite(capacity)?Math.Min(RequestedLowering,Math.Max(0,capacity)):0;
  }
 }
 public sealed class ExpressionPolicy {
  double weight;
  public void Reset() { weight=0; }
  public ExpressionCommand Step(double ownStatus,ExpressionProfile profile,double bodyScale,double rootSpeed,double dt,bool enabled) {
   if(!enabled){Reset();return new ExpressionCommand(true,0,0,0);}
   if(!profile.Valid||!ExpressionMath.Finite(ownStatus)||!ExpressionMath.Finite(bodyScale)||bodyScale<=0||
      !ExpressionMath.Finite(rootSpeed)||rootSpeed<0||!ExpressionMath.Finite(dt)||dt<=0)return default(ExpressionCommand);
   double s=ExpressionMath.Clamp(ownStatus,0,1);
   double target=profile.CompactAtStatusZero+(profile.CompactAtStatusOne-profile.CompactAtStatusZero)*s;
   return StepCompactness(target,profile.MaxLoweringFraction,bodyScale,rootSpeed,dt,true);
  }
  // General expression target: never convert it back into an artificial ownStatus.
  public ExpressionCommand StepCompactness(double compactness,double maxLoweringFraction,double bodyScale,double rootSpeed,double dt,bool enabled){
   if(!enabled){Reset();return new ExpressionCommand(true,0,0,0);}
   if(!ExpressionMath.Finite(compactness)||!ExpressionMath.Finite(maxLoweringFraction)||maxLoweringFraction<0||maxLoweringFraction>.02||
      !ExpressionMath.Finite(bodyScale)||bodyScale<=0||!ExpressionMath.Finite(rootSpeed)||rootSpeed<0||!ExpressionMath.Finite(dt)||dt<=0)return default(ExpressionCommand);
   double target=ExpressionMath.Clamp(compactness,0,1);
   weight=ExpressionMath.Follow(weight,target*ExpressionMath.SpeedGain(rootSpeed,bodyScale),dt);
   return new ExpressionCommand(true,target,weight,bodyScale*maxLoweringFraction*weight);
  }
 }
}
