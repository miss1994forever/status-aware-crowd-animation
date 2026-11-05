using System;
namespace IndividualExpressionCandidate {
 // Bounded feature-target search. The host evaluates actual pose geometry/constraints.
 // Costs and tolerances are engineering authoring choices, not perceptual status calibration.
 public sealed class BodyCombinationSearch {
  public struct Evaluation { public bool Feasible; public double ElbowResidual,KneeChange,ArmChange; }
  public struct Plan { public double Lowering,ArmWeight,Cost; public bool Feasible,TemporalFallback; }
  double previousHeight,previousArm;
  public void Reset(){previousHeight=0;previousArm=0;}
  public Plan Solve(double requestedHeight,double requestedArm,double dt,double bodyScale,Func<double,double,Evaluation> evaluate) {
   if(!ExpressionMath.Finite(requestedHeight)||requestedHeight<0||!ExpressionMath.Finite(requestedArm)||
      !ExpressionMath.Finite(dt)||dt<=0||!ExpressionMath.Finite(bodyScale)||bodyScale<=0||evaluate==null)return default(Plan);
   requestedArm=ExpressionMath.Clamp(requestedArm,0,1);
   if(requestedHeight==0&&requestedArm==0){Reset();return new Plan{Feasible=true};}
   double tolerance=.003*bodyScale;
   double Cost(double height,double arm,Evaluation e) {
    double dh=(height-requestedHeight)/tolerance;
    double temporalH=(height-previousHeight)/tolerance,temporalA=arm-previousArm;
    return dh*dh+e.ElbowResidual*e.ElbowResidual+.20*e.KneeChange*e.KneeChange+
      .10*e.ArmChange*e.ArmChange+.10*(temporalH*temporalH+temporalA*temporalA);
   }
   var best=new Plan{Cost=double.PositiveInfinity};
   // Include exact no-change and intended endpoints. 25 evaluations, no general optimizer.
   for(int h=0;h<=4;h++)for(int a=0;a<=4;a++){
    double height=requestedHeight*h/4,arm=requestedArm*a/4;
    var e=evaluate(height,arm);if(!e.Feasible)continue;
    double cost=Cost(height,arm,e);if(!ExpressionMath.Finite(cost))continue;
    if(cost<best.Cost)best=new Plan{Feasible=true,Lowering=height,ArmWeight=arm,Cost=cost};
   }
   if(!best.Feasible){Reset();return best;}
   // Smooth parameters, then evaluate again: never blend joint positions/bone lengths.
   double blend=1-Math.Exp(-dt/.10);
   double sh=previousHeight+(best.Lowering-previousHeight)*blend;
   double sa=previousArm+(best.ArmWeight-previousArm)*blend;
   var check=evaluate(sh,sa);
   if(check.Feasible&&ExpressionMath.Finite(Cost(sh,sa,check))){best.Lowering=sh;best.ArmWeight=sa;best.Cost=Cost(sh,sa,check);}
   else best.TemporalFallback=true;
   previousHeight=best.Lowering;previousArm=best.ArmWeight;return best;
  }
 }
}
