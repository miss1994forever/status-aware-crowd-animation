using System;
using System.IO;
using System.Globalization;
using IndividualExpressionCandidate;
class Checks {
 static int checks;
 static void Assert(bool ok,string name){checks++;if(!ok)throw new Exception(name);}
 static void PolicyChecks() {
  var p=new ExpressionPolicy();var profile=ExpressionProfile.SourceToCompact;
  var off=p.Step(0,profile,1.65,1.2,1.0/60,false);
  Assert(off.Valid&&off.ArmWeight==0&&off.RequestedLowering==0,"disable identity");
  double previous=0;
  for(int i=0;i<300;i++){
   var c=p.Step(0,profile,1.65,1.2,1.0/60,true);
   Assert(c.Valid&&c.Weight>=previous&&c.Weight<=1,"weight monotone");previous=c.Weight;
   Assert(c.RequestedLowering<=1.65*.0125,"lowering request bounded");
   Assert(c.BoundedLowering(0)==0&&c.BoundedLowering(-1)==0,"zero capacity");
   Assert(c.BoundedLowering(.001)<=.001,"host budget");
  }
  p.Reset();Assert(p.Step(1,profile,1.65,1.2,.1,true).Weight==0,"high endpoint source");
  p.Reset();Assert(p.Step(0,ExpressionProfile.Neutral,1.65,1.2,.1,true).Weight==0,"neutral ablation");
  Assert(!p.Step(0,new ExpressionProfile(1,0,1),1.65,1,.1,true).Valid,"invalid profile");
  Assert(!p.Step(double.NaN,profile,1.65,1,.1,true).Valid,"invalid status");
  var a=new ExpressionPolicy();var b=new ExpressionPolicy();
  for(int i=0;i<120;i++){
   var ca=a.Step(.25,profile,1.65,1.2,.016,true);var cb=b.Step(.25,profile,3.3,2.4,.016,true);
   Assert(Math.Abs(ca.Weight-cb.Weight)<1e-14&&Math.Abs(cb.RequestedLowering-2*ca.RequestedLowering)<1e-14,"scaled command");
  }
 }
 static void Main(string[] args) {
  if(args.Length>0&&args[0]=="--replay"){Replay.Run(args[1],args[2]);return;}
  PolicyChecks();
  var rng=new Random(20261105);double maxNorm=0,maxAngle=0,maxZ=0;
  for(int i=0;i<100000;i++){
   double x=rng.NextDouble()*2-1,y=rng.NextDouble()*2-1,z=rng.NextDouble()*2-1;
   double n=Math.Sqrt(x*x+y*y+z*z);x/=n;y/=n;z/=n;
   var t=ExpressionMath.Solve(x,y,z,rng.NextDouble(),rng.NextDouble());
   double err=Math.Abs(t.X*t.X+t.Y*t.Y+t.Z*t.Z-1);
   maxNorm=Math.Max(maxNorm,err);maxAngle=Math.Max(maxAngle,t.Angle);maxZ=Math.Max(maxZ,Math.Abs(t.Z-z));
   Assert(err<1e-12,"length");Assert(t.Z==z,"sagittal preservation");
   Assert(t.Angle<=ExpressionMath.MaxAngleRadians+1e-12,"rotation cap");
   if(t.Changed){Assert(t.X>=0&&t.X<=x+1e-12,"no crossing / only contraction");Assert(t.Y<=0,"downward");}
   if(x<=0||y>=0)Assert(!t.Changed,"gesture / already inward guard");
   var zero=ExpressionMath.Solve(x,y,z,0,1);Assert(zero.X==x&&zero.Y==y&&zero.Z==z&&!zero.Changed,"zero identity");
  }
  double w=0;for(int i=0;i<60;i++)w=ExpressionMath.Follow(w,1,1.0/60);
  Assert(Math.Abs(w-(1-Math.Exp(-5)))<1e-14,"filter timestep");
  foreach(double s in new[]{0,.1,.5,1.0,3.0})
   Assert(Math.Abs(ExpressionMath.SpeedGain(s,1.7)-ExpressionMath.SpeedGain(s*3,5.1))<1e-14,"uniform scale");
  Assert(!ExpressionMath.Solve(.1,-.99,0,1,1).Changed,"nonunit guard");
  Assert(!ExpressionMath.Solve(double.NaN,-1,0,1,1).Changed,"NaN guard");
  // Phase sweep tests continuity of the mapping, not real animation continuity.
  double previous=0,maxStep=0;
  using(var csv=new StreamWriter(args[0])) {
   csv.WriteLine("phase,rawX,rawY,rawZ,candidateX,candidateY,candidateZ,legacyX,legacyY,legacyZ,candidateDegrees,observedRaw,observedCandidate");
   for(int i=0;i<=720;i++){
    double phase=i*Math.PI*2/720,z=.45*Math.Sin(phase),x=.20+.025*Math.Cos(phase*2),y=-Math.Sqrt(1-x*x-z*z);
    var t=ExpressionMath.Solve(x,y,z,ExpressionMath.SpeedGain(1.3,1.7),1);
    // Legacy coronal rotation of 12 degrees (fixed input, contraction=1).
    double a=12*Math.PI/180,lx=x*Math.Cos(a)+y*Math.Sin(a),ly=-x*Math.Sin(a)+y*Math.Cos(a);
    if(i>0)maxStep=Math.Max(maxStep,Math.Abs(t.Angle-previous));previous=t.Angle;
    csv.WriteLine(FormattableString.Invariant($"{phase},{x},{y},{z},{t.X},{t.Y},{t.Z},{lx},{ly},{z},{t.Angle*180/Math.PI},{x*.30/.40},{t.X*.30/.40}"));
   }
  }
  Assert(maxStep<.005,"phase mapping continuity");
  Console.WriteLine(FormattableString.Invariant($"checks={checks}; samples=100000; maxUnitLengthSquaredError={maxNorm}; maxAngleDegrees={maxAngle*180/Math.PI}; maxZChange={maxZ}; phaseMaxAngleStepDegrees={maxStep*180/Math.PI}"));
 }
}
