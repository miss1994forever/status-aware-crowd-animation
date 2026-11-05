using System;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using System.Linq;
using IndividualExpressionCandidate;
using UnityEngine;

// Actual independent response/policy/body search + existing offline pose solver.
// Frozen encounter contexts deliberately hold an approach gate, NOT physical trajectories.
// The managed Unity math shim is not verified equivalent to the engine.
class ClosedLoop {
 const double Scale=1.65,Duration=24,Late=3,Tolerance=1e-4;
 static int checks;
 static void Check(bool b,string why){checks++;if(!b)throw new Exception(why);}
 static double[] Sub(double[] a,double[] b)=>new[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};
 static double Dot(double[] a,double[] b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 static double Norm(double[] a)=>Math.Sqrt(Dot(a,a));
 static double[] Mul(double[] a,double v)=>new[]{a[0]*v,a[1]*v,a[2]*v};
 static double[] Unit(double[] a)=>Mul(a,1/Math.Max(1e-15,Norm(a)));
 static double[] Cross(double[] a,double[] b)=>new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
 record Feature(double E,double H);
 class Clip {
  public string Id;public string[] Names;public int?[] Parents;public double[][][] Raw;public double Dt;public double Sign;
  public int Index(string name)=>Array.IndexOf(Names,name);
  public double[] Right(double[][] p)=>Unit(Sub(p[Index("UpperArm_R")],p[Index("UpperArm_L")]));
  public double[] Up(double[][] p){var r=Right(p);var u=Sub(p[Index("Head")],p[Index("Hips")]);var projected=Mul(r,Dot(u,r));return Unit(Sub(u,projected));}
  public Feature Read(double[][] p){
   var shoulder=Sub(p[Index("UpperArm_R")],p[Index("UpperArm_L")]);
   double e=Dot(Sub(p[Index("UpperArm_L")],p[Index("LowerArm_L")]),shoulder)/Dot(shoulder,shoulder);
   double leg=0;foreach(string side in new[]{"L","R"})leg+=Norm(Sub(p[Index("UpperLeg_"+side)],p[Index("LowerLeg_"+side)]))+Norm(Sub(p[Index("LowerLeg_"+side)],p[Index("Foot_"+side)]));
   return new Feature(e,(p[Index("Hips")][1]-(p[Index("Foot_L")][1]+p[Index("Foot_R")][1])/2)/(leg/2));
  }
  public double Speed(int f){var delta=f==0?Sub(Raw[1][Index("Hips")],Raw[0][Index("Hips")]):Sub(Raw[f][Index("Hips")],Raw[f-1][Index("Hips")]);return Math.Sqrt(delta[0]*delta[0]+delta[2]*delta[2])/Dt;}
 }
 class Actor {
  public readonly InteractiveExpression Response=new();public readonly ExpressionPolicy Policy=new();public readonly BodyCombinationSearch Search=new();
  public SprintLegIK.Hint L,R;public double Status;public Clip Clip;public int Fallbacks;public double MaxBone,MaxKnee;
  public (Feature feature,double arm,double height) Render(ExpressionCommand command,int frame,double dt,bool combination){
   var p=Clip.Raw[frame];var right=Clip.Right(p);var up=Clip.Up(p);var forward=Unit(Cross(right,up));var anterior=Mul(forward,Clip.Sign);
   Program.Pose Make(double h,double a)=>Program.Make(p,Clip.Names,Clip.Parents,h,a,command.ArmWeight,right,up,forward,anterior,dt,L,R);
   double height=0,arm=command.ArmWeight;
   if(combination){
    var plan=Search.Solve(command.RequestedLowering,arm,dt,Scale,(h,a)=>{var q=Make(h,a);return new BodyCombinationSearch.Evaluation{Feasible=q.feasible,ElbowResidual=q.elbowResidual,KneeChange=q.kneeDegrees/12,ArmChange=q.armDegrees/9};});
    Check(plan.Feasible,"no feasible combination");height=plan.Lowering;arm=plan.ArmWeight;if(plan.TemporalFallback)Fallbacks++;
   }
   var pose=Make(height,arm);Check(pose.feasible&&pose.maxBoneError<.00004&&pose.footError<1e-12,"body constraint");
   L=pose.leftHint;R=pose.rightHint;MaxBone=Math.Max(MaxBone,pose.maxBoneError);MaxKnee=Math.Max(MaxKnee,pose.kneeDegrees);
   return (Clip.Read(pose.points),arm,height/Scale);
  }
 }
 record Spec(string Name,string ClipId,bool Combination,int Fps,double Delay,string Context,bool Moving,double[] Statuses);
 record Sample(double T,double[] Targets,double[] Offsets,double[] Arms,double[] Heights,Feature[] Visible,bool[] Saturated);
 class Run {
  public List<Sample> Trace=new();public double MaxBone,MaxKnee;public int Fallbacks;public double SaturationFraction;
 }
 static NeighborCue Cue(int id,Feature f,double x,double vx)=>new(){ActorId=id,Expansion=f.E,HeightRatio=f.H,RelativeX=x,RelativeVX=vx,Confidence=1,MeasurementValid=true};
 static Run Simulate(Spec spec,int seed,bool reverse,Dictionary<string,Clip> clips,VisibleReference reference){
  double dt=1.0/spec.Fps;int frames=(int)(Duration*spec.Fps),delay=(int)Math.Round(spec.Delay/dt);var settings=new ResponseSettings();
  var actors=spec.Statuses.Select(s=>new Actor{Status=s,Clip=clips[spec.ClipId]}).ToArray();
  var initial=new Feature[actors.Length];
  for(int i=0;i<actors.Length;i++){
   var actor=actors[i];ExpressionCommand command=default;
   // Different bounded prehistories, then exactly the same future external inputs.
   double sign=((i+seed)%2==0?1:-1);
   var cue=Cue(1-i,new Feature(reference.ExpansionCenter+sign*3*reference.ExpansionScale,reference.HeightCenter+sign*3*reference.HeightScale),1,-.5);
   for(int f=0;f<3*spec.Fps;f++){
    var r=actor.Response.Step(i,actor.Status,ExpressionProfile.SourceToCompact,reference,new[]{cue},dt,true,settings);
    command=actor.Policy.StepCompactness(r.CompactnessTarget,.0125,Scale,spec.Moving?actor.Clip.Speed(40):0,dt,true);
   }
   initial[i]=actor.Render(command,40,dt,spec.Combination).feature;
  }
  var history=new List<Feature[]>{initial};var result=new Run();int saturated=0;
  for(int f=0;f<frames;f++){
   double t=f*dt;var observed=history[Math.Max(0,history.Count-1-delay)];
   var responses=new InteractiveExpression.Result[actors.Length];
   // All compute from the same immutable snapshot; optional reverse update order.
   for(int n=0;n<actors.Length;n++){
    int i=reverse?actors.Length-1-n:n;var a=actors[i];double x=1,vx=-.5;
    if(spec.Context=="exit"&&t>=12){x=4;vx=0;}
    if(spec.Context=="pass"){x=3-.5*t;vx=-.5;}
    if(i==1){x=-x;vx=-vx;}
    var cue=Cue(1-i,observed[1-i],x,vx);
    responses[i]=a.Response.Step(i,a.Status,ExpressionProfile.SourceToCompact,reference,new[]{cue},dt,true,settings);
    Check(responses[i].Valid&&responses[i].WeightSum<=1+1e-12&&Math.Abs(responses[i].UnclippedOffset)<=.15+1e-12,"response bound");
   }
   var visible=new Feature[actors.Length];var arms=new double[actors.Length];var heights=new double[actors.Length];
   for(int i=0;i<actors.Length;i++){
    var a=actors[i];int frame=spec.Moving?(40+(int)Math.Floor(t/a.Clip.Dt))%a.Clip.Raw.Length:40;
    var command=a.Policy.StepCompactness(responses[i].CompactnessTarget,.0125,Scale,spec.Moving?a.Clip.Speed(frame):0,dt,true);
    var body=a.Render(command,frame,dt,spec.Combination);visible[i]=body.feature;arms[i]=body.arm;heights[i]=body.height;if(responses[i].Saturated)saturated++;
   }
   history.Add(visible);
   result.Trace.Add(new Sample((f+1)*dt,responses.Select(r=>r.CompactnessTarget).ToArray(),responses.Select(r=>r.EffectiveOffset).ToArray(),arms,heights,visible,responses.Select(r=>r.Saturated).ToArray()));
  }
  result.MaxBone=actors.Max(a=>a.MaxBone);result.MaxKnee=actors.Max(a=>a.MaxKnee);result.Fallbacks=actors.Sum(a=>a.Fallbacks);result.SaturationFraction=(double)saturated/(frames*actors.Length);return result;
 }
 static double LateRange(Run r,Func<Sample,double[]> selector)=>Enumerable.Range(0,2).Max(i=>{var values=r.Trace.Where(s=>s.T>Duration-Late).Select(s=>selector(s)[i]).ToArray();return values.Max()-values.Min();});
 static void Main(string[] args){
  using var input=JsonDocument.Parse(File.ReadAllText(args[0]));using var calibration=JsonDocument.Parse(File.ReadAllText(args[1]));
  var j=calibration.RootElement.GetProperty("reference");double Get(string k)=>j.GetProperty(k).GetDouble();
  var reference=new VisibleReference(Get("expansionCenter"),Get("expansionScale"),Get("heightCenter"),Get("heightScale"));var clips=new Dictionary<string,Clip>();
  foreach(var c in input.RootElement.GetProperty("clips").EnumerateArray()){
   string id=c.GetProperty("id").GetString();if(id!="M01"&&id!="M07")continue;
   var clip=new Clip{Id=id,Names=JsonSerializer.Deserialize<string[]>(c.GetProperty("names").GetRawText()),Parents=JsonSerializer.Deserialize<int?[]>(c.GetProperty("parents").GetRawText()),Raw=JsonSerializer.Deserialize<double[][][]>(c.GetProperty("raw").GetRawText()),Dt=c.GetProperty("dt").GetDouble()};
   foreach(var pose in clip.Raw)foreach(var point in pose)for(int k=0;k<3;k++)point[k]*=Scale;
   double sign=0;foreach(var p in clip.Raw){var forward=Unit(Cross(clip.Right(p),clip.Up(p)));foreach(string side in new[]{"L","R"}){var h=p[clip.Index("UpperLeg_"+side)];var bend=Sub(p[clip.Index("LowerLeg_"+side)],h);var axis=Unit(Sub(p[clip.Index("Foot_"+side)],h));sign+=Dot(Sub(bend,Mul(axis,Dot(bend,axis))),forward);}}
   clip.Sign=sign>=0?1:-1;clips[id]=clip;
  }
  var specs=new List<Spec>();
  foreach(string id in new[]{"M01","M07"})foreach(bool combination in new[]{false,true}){
   foreach(double delay in new[]{0,.25,.5})specs.Add(new Spec(id+"-"+(combination?"combo":"arms")+"-delay"+delay,id,combination,60,delay,"frozen-approach",false,new[]{.5,.5}));
  }
  foreach(int fps in new[]{30,120})specs.Add(new Spec("M01-combo-fps"+fps,"M01",true,fps,.25,"frozen-approach",false,new[]{.5,.5}));
  specs.Add(new Spec("M01-combo-exit","M01",true,60,.25,"exit",false,new[]{.2,.8}));
  specs.Add(new Spec("M07-combo-pass-moving","M07",true,60,.25,"pass",true,new[]{.2,.8}));
  specs.Add(new Spec("M01-combo-moving","M01",true,60,.25,"frozen-approach",true,new[]{.5,.5}));
  specs.Add(new Spec("M01-combo-endpoints","M01",true,60,.25,"frozen-approach",false,new[]{0.0,1.0}));
  var audits=new List<object>();var traces=new List<object>();int criterionPass=0;
  foreach(var spec in specs){
   var a=Simulate(spec,0,false,clips,reference);var b=Simulate(spec,1,true,clips,reference);
   double targetDifference=a.Trace.Zip(b.Trace,(x,y)=>Enumerable.Range(0,2).Max(i=>Math.Abs(x.Targets[i]-y.Targets[i]))).TakeLast(spec.Fps*3).Max();
   double armDifference=a.Trace.Zip(b.Trace,(x,y)=>Enumerable.Range(0,2).Max(i=>Math.Abs(x.Arms[i]-y.Arms[i]))).TakeLast(spec.Fps*3).Max();
   double heightDifference=a.Trace.Zip(b.Trace,(x,y)=>Enumerable.Range(0,2).Max(i=>Math.Abs(x.Heights[i]-y.Heights[i]))).TakeLast(spec.Fps*3).Max();
   double range=Math.Max(LateRange(a,s=>s.Targets),LateRange(b,s=>s.Targets));
   double armRange=Math.Max(LateRange(a,s=>s.Arms),LateRange(b,s=>s.Arms));double heightRange=Math.Max(LateRange(a,s=>s.Heights),LateRange(b,s=>s.Heights));
   double residual=spec.Context=="exit"||spec.Context=="pass"?a.Trace.TakeLast(spec.Fps*3).Max(s=>s.Offsets.Max(v=>Math.Abs(v))):0;
   bool passed=targetDifference<Tolerance&&armDifference<Tolerance&&heightDifference<Tolerance&&residual<Tolerance&&(spec.Moving||(range<Tolerance&&armRange<Tolerance&&heightRange<Tolerance));
   if(passed)criterionPass++;
   audits.Add(new{spec.Name,spec.ClipId,spec.Combination,spec.Fps,spec.Delay,spec.Context,spec.Moving,spec.Statuses,lateTargetRange=range,lateArmRange=armRange,lateHeightRange=heightRange,lateInitialHistoryDifference=targetDifference,lateArmHistoryDifference=armDifference,lateHeightHistoryDifference=heightDifference,exitResidual=residual,engineeringCriterionPassed=passed,maxBoneErrorMetres=Math.Max(a.MaxBone,b.MaxBone),maxKneeCorrectionDegrees=Math.Max(a.MaxKnee,b.MaxKnee),temporalFallbacks=a.Fallbacks+b.Fallbacks,saturationFraction=Math.Max(a.SaturationFraction,b.SaturationFraction)});
   for(int seed=0;seed<2;seed++){var run=seed==0?a:b;int stride=Math.Max(1,spec.Fps/30);for(int f=0;f<run.Trace.Count;f+=stride)traces.Add(new{scenario=spec.Name,seed,sample=run.Trace[f]});}
   Console.WriteLine(spec.Name+": criterion="+passed+" lateRange="+range.ToString("G5")+" historyDifference="+targetDifference.ToString("G5"));Console.Out.Flush();
  }
  // Separate identical-history order check: different-history runs cannot isolate update order.
  var orderSpec=specs[3];var forwardRun=Simulate(orderSpec,0,false,clips,reference);var reverseRun=Simulate(orderSpec,0,true,clips,reference);
  double orderDifference=forwardRun.Trace.Zip(reverseRun.Trace,(x,y)=>Enumerable.Range(0,2).Max(i=>Math.Abs(x.Targets[i]-y.Targets[i]))).Max();Check(orderDifference<1e-12,"synchronous update order");
  File.WriteAllText(args[2],JsonSerializer.Serialize(new{kind="offline bidirectional rendered-bone feedback; actual independent C# response/policy/body search and existing knee snapshot via math shim; not Unity",durationSeconds=Duration,lateSeconds=Late,engineeringTolerance=Tolerance,checks,scenarioCount=specs.Count,criterionPass,orderDifference,limits=new[]{"frozen approach gates are external frozen context, not a physical stationary encounter","moving sources use repeated nearest original samples; seams are external forcing, not naturalness evidence","only two clips and two initial prehistories; no global stability guarantee","no navigation, mesh, attention, perception, or engine equivalence validation"},audits,traces}));
  Console.WriteLine("checks="+checks+" scenarios="+specs.Count+" engineeringCriterionPassed="+criterionPass+" orderDifference="+orderDifference);
 }
}
