using System;
using System.Collections.Generic;
namespace IndividualExpressionCandidate {
 // Visible geometry reference only. No peer status or source-animation internals.
 public readonly struct VisibleReference {
  public readonly double ExpansionCenter,ExpansionScale,HeightCenter,HeightScale;
  public VisibleReference(double expansionCenter,double expansionScale,double heightCenter,double heightScale){
   ExpansionCenter=expansionCenter;ExpansionScale=expansionScale;HeightCenter=heightCenter;HeightScale=heightScale;
  }
  public bool Valid {get{return ExpressionMath.Finite(ExpansionCenter)&&ExpressionMath.Finite(ExpansionScale)&&ExpansionScale>0&&ExpressionMath.Finite(HeightCenter)&&ExpressionMath.Finite(HeightScale)&&HeightScale>0;}}
 }
 public struct NeighborCue {
  public int ActorId;
  public double RelativeX,RelativeZ,RelativeVX,RelativeVZ; // observed horizontal metres and m/s
  public double Expansion,HeightRatio,Confidence; // dimensionless rendered geometry
  public bool MeasurementValid;
 }
 public sealed class ResponseSettings {
  // Initial engineering configuration, not calibrated status/perceptual constants.
  public double NearDistance=.8,FarDistance=3,PredictionSeconds=1.8;
  public double NearMiss=.8,FarMiss=1.6,ClosureStart=.02,ClosureFull=.30;
  public double ObservationTau=.45,WarmupTau=.4,ResponseTau=.35,ReleaseTau=.6;
  public double MaxOffset=.15,OffsetRate=.4,DeadZone=.10;
  public bool Valid {
   get {
    double[] values={NearDistance,FarDistance,PredictionSeconds,NearMiss,FarMiss,ClosureStart,ClosureFull,ObservationTau,WarmupTau,ResponseTau,ReleaseTau,MaxOffset,OffsetRate,DeadZone};
    foreach(double v in values)if(!ExpressionMath.Finite(v))return false;
    return NearDistance>=0&&FarDistance>NearDistance&&PredictionSeconds>0&&NearMiss>=0&&FarMiss>NearMiss&&ClosureStart>=0&&ClosureFull>ClosureStart&&ObservationTau>0&&WarmupTau>0&&ResponseTau>0&&ReleaseTau>0&&MaxOffset>=0&&MaxOffset<=.25&&OffsetRate>0&&DeadZone>=0;
   }
  }
 }
 public sealed class InteractiveExpression {
  sealed class Observation {public double Expansion,Height,Age;}
  readonly Dictionary<int,Observation> observations=new Dictionary<int,Observation>();
  double offset;
  public void Reset(){observations.Clear();offset=0;}
  public struct Result {
   public bool Valid,Saturated;
   public int UsedNeighbors,RejectedCues;
   public double Baseline,CompactnessTarget,DesiredOffset,UnclippedOffset,EffectiveOffset,RawWeightSum,WeightSum;
  }
  static double Dead(double v,double width)=>Math.Sign(v)*Math.Max(0,Math.Abs(v)-width);
  public static double VisibleScore(double expansion,double height,VisibleReference reference,double deadZone){
   if(!reference.Valid||!ExpressionMath.Finite(expansion)||!ExpressionMath.Finite(height)||!ExpressionMath.Finite(deadZone)||deadZone<0)return 0;
   double e=Dead((expansion-reference.ExpansionCenter)/reference.ExpansionScale,deadZone);
   double h=Dead((height-reference.HeightCenter)/reference.HeightScale,deadZone);
   return .6*Math.Tanh(e)+.4*Math.Tanh(h);
  }
  public static double EncounterWeight(NeighborCue c,ResponseSettings settings){
   if(settings==null||!settings.Valid)return 0;
   double[] values={c.RelativeX,c.RelativeZ,c.RelativeVX,c.RelativeVZ,c.Confidence};
   foreach(double v in values)if(!ExpressionMath.Finite(v))return 0;
   double d=Math.Sqrt(c.RelativeX*c.RelativeX+c.RelativeZ*c.RelativeZ);
   if(d<1e-5||d>=settings.FarDistance)return 0;
   double rv=c.RelativeX*c.RelativeVX+c.RelativeZ*c.RelativeVZ;
   double closing=-rv/d;
   double v2=c.RelativeVX*c.RelativeVX+c.RelativeVZ*c.RelativeVZ;
   double time=ExpressionMath.Clamp(-rv/Math.Max(v2,1e-8),0,settings.PredictionSeconds);
   double x=c.RelativeX+c.RelativeVX*time,z=c.RelativeZ+c.RelativeVZ*time;
   double miss=Math.Sqrt(x*x+z*z);
   return (1-ExpressionMath.Smooth(settings.NearDistance,settings.FarDistance,d))*
      ExpressionMath.Smooth(settings.ClosureStart,settings.ClosureFull,closing)*
      (1-ExpressionMath.Smooth(settings.NearMiss,settings.FarMiss,miss))*ExpressionMath.Clamp(c.Confidence,0,1);
  }
  public Result Step(int ownId,double ownStatus,ExpressionProfile profile,VisibleReference reference,
    IReadOnlyList<NeighborCue> cues,double dt,bool enabled,ResponseSettings settings){
   if(settings==null||!settings.Valid||!profile.Valid||!ExpressionMath.Finite(ownStatus)||!ExpressionMath.Finite(dt)||dt<=0){Reset();return default(Result);}
   double s=ExpressionMath.Clamp(ownStatus,0,1);
   double baseline=profile.CompactAtStatusZero+(profile.CompactAtStatusOne-profile.CompactAtStatusZero)*s;
   var result=new Result{Valid=true,Baseline=baseline,CompactnessTarget=baseline};
   // This switch disables interaction only; the personal expression baseline remains.
   if(!enabled){Reset();return result;}
   if(!reference.Valid){Reset();result.Valid=false;return result;}
   var seen=new HashSet<int>();var active=new HashSet<int>();
   double weightedScore=0,rawSum=0;
   if(cues!=null)foreach(var cue in cues){
    if(cue.ActorId==ownId||cue.ActorId<0||!seen.Add(cue.ActorId)||!cue.MeasurementValid||
       !ExpressionMath.Finite(cue.Expansion)||!ExpressionMath.Finite(cue.HeightRatio)) {result.RejectedCues++;continue;}
    double w=EncounterWeight(cue,settings);if(w<=0)continue;
    active.Add(cue.ActorId);
    Observation state;
    if(!observations.TryGetValue(cue.ActorId,out state)){
     state=new Observation{Expansion=cue.Expansion,Height=cue.HeightRatio};observations[cue.ActorId]=state;
    }
    double alpha=1-Math.Exp(-dt/settings.ObservationTau);
    state.Expansion+=(cue.Expansion-state.Expansion)*alpha;state.Height+=(cue.HeightRatio-state.Height)*alpha;state.Age+=dt;
    w*=1-Math.Exp(-state.Age/settings.WarmupTau);
    weightedScore+=w*VisibleScore(state.Expansion,state.Height,reference,settings.DeadZone);
    rawSum+=w;result.UsedNeighbors++;
   }
   // No cross-encounter memory: absent/irrelevant peers lose their filter state.
   var remove=new List<int>();foreach(int id in observations.Keys)if(!active.Contains(id))remove.Add(id);
   foreach(int id in remove)observations.Remove(id);
   double denominator=Math.Max(1,rawSum);
   // Higher own status may also respond: responsiveness never becomes zero.
   double responsiveness=.5+.5*(1-s);
   double desired=settings.MaxOffset*responsiveness*weightedScore/denominator;
   double tau=rawSum>0?settings.ResponseTau:settings.ReleaseTau;
   double step=(desired-offset)*(1-Math.Exp(-dt/tau));
   offset+=ExpressionMath.Clamp(step,-settings.OffsetRate*dt,settings.OffsetRate*dt);
   offset=ExpressionMath.Clamp(offset,-settings.MaxOffset,settings.MaxOffset);
   result.DesiredOffset=desired;result.UnclippedOffset=offset;
   result.CompactnessTarget=ExpressionMath.Clamp(baseline+offset,0,1);
   result.EffectiveOffset=result.CompactnessTarget-baseline;
   result.Saturated=Math.Abs(result.EffectiveOffset-offset)>1e-10;
   result.RawWeightSum=rawSum;result.WeightSum=rawSum/denominator;
   return result;
  }
 }
}
