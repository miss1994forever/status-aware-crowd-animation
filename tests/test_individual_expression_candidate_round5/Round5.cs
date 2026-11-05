using System;
using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using IndividualExpressionCandidate;
using static IndividualExpressionCandidate.PostureChannels;
class Round5 {
 const double Scale=1.65;
 static readonly string[] Labels={"原动作","当前组合","加强手臂／高度","加强＋躯干","加强＋躯干＋头颈"};
 static int checks;static double maxBone,maxFoot,maxKnee,maxArm;
 static void Check(bool v,string why){checks++;if(!v)throw new Exception(why);}
 public class Clip {
  public string Id;public string[] Names;public int?[] Parents;public double[][][] Raw;public double Dt,Sign;
  public int I(string n)=>Array.IndexOf(Names,n);
  public double[] Right(double[][] p)=>Unit(Sub(p[I("UpperArm_R")],p[I("UpperArm_L")]));
  public double[] Up(double[][] p){var r=Right(p);var u=Sub(p[I("Head")],p[I("Hips")]);return Unit(Sub(u,Mul(r,Dot(u,r))));}
  public double Speed(int f){var v=f==0?Sub(Raw[1][I("Hips")],Raw[0][I("Hips")]):Sub(Raw[f][I("Hips")],Raw[f-1][I("Hips")]);return Math.Sqrt(v[0]*v[0]+v[2]*v[2])/Dt;}
  public double[][] Export(double[][] p)=>p.Select(v=>Mul(v,1/Scale)).ToArray();
  public (double E,double H) Observe(double[][] p){var shoulder=Sub(p[I("UpperArm_R")],p[I("UpperArm_L")]);double e=Dot(Sub(p[I("UpperArm_L")],p[I("LowerArm_L")]),shoulder)/Dot(shoulder,shoulder),leg=0;
   foreach(string side in new[]{"L","R"})leg+=Norm(Sub(p[I("LowerLeg_"+side)],p[I("UpperLeg_"+side)]))+Norm(Sub(p[I("Foot_"+side)],p[I("LowerLeg_"+side)]));
   return(e,(p[I("Hips")][1]-(p[I("Foot_L")][1]+p[I("Foot_R")][1])/2)/(leg/2));}
 }
 class Body {
  public ExpressionPolicy Policy=new();public BodyCombinationSearch Search=new();public SprintLegIK.Hint L,R;
  public Output Step(Clip clip,int frame,double target,int mode,double dt){
   var p=clip.Raw[frame];var right=clip.Right(p);var up=clip.Up(p);var forward=Unit(Cross(right,up));
   var command=Policy.StepCompactness(mode==0?0:target,mode<=1?.0125:.018,Scale,clip.Speed(frame),dt,true);
   Program.Pose Legs(double height)=>Program.Make(p,clip.Names,clip.Parents,height,0,0,right,up,forward,Mul(forward,clip.Sign),dt,L,R);
   double height=0,arm=command.ArmWeight;
   if(mode!=0){var plan=Search.Solve(command.RequestedLowering,arm,dt,Scale,(h,a)=>{
     if(mode==1){var old=Program.Make(p,clip.Names,clip.Parents,h,a,command.ArmWeight,right,up,forward,Mul(forward,clip.Sign),dt,L,R);return new BodyCombinationSearch.Evaluation{Feasible=old.feasible,ElbowResidual=old.elbowResidual,KneeChange=old.kneeDegrees/12,ArmChange=old.armDegrees/9};}
     var candidate=Legs(h);double angle=ApplyArms(candidate.points,clip.Names,clip.Parents,a,mode>=2,right,up,forward);
     var measured=clip.Observe(candidate.points);double wanted=clip.Observe(p).E*(1-(mode>=2?.65:.4)*command.ArmWeight);
     return new BodyCombinationSearch.Evaluation{Feasible=candidate.feasible,ElbowResidual=(measured.E-wanted)/.04,KneeChange=candidate.kneeDegrees/12,ArmChange=angle/(mode>=2?18:9)};
    });Check(plan.Feasible,"no feasible body");height=plan.Lowering;arm=plan.ArmWeight;}
   var pose=Legs(height);L=pose.leftHint;R=pose.rightHint;
   double actualArm=ApplyArms(pose.points,clip.Names,clip.Parents,arm,mode>=2,right,up,forward);
   var posture=ApplyPosture(pose.points,clip.Names,clip.Parents,command.Weight,mode,right,clip.Sign);
   double bone=0,foot=0;
   for(int j=0;j<p.Length;j++){
    Check(pose.points[j].All(ExpressionMath.Finite),"nonfinite pose");
    if(clip.Parents[j].HasValue){int parent=clip.Parents[j].Value;bone=Math.Max(bone,Math.Abs(Norm(Sub(pose.points[j],pose.points[parent]))-Norm(Sub(p[j],p[parent]))));}
    foreach(string side in new[]{"L","R"})if(j==clip.I("Foot_"+side)||Child(j,clip.I("Foot_"+side),clip.Parents))foot=Math.Max(foot,Norm(Sub(pose.points[j],p[j])));
   }
   Check(bone<4e-5&&foot<1e-12&&pose.kneeDegrees<=12,"pose constraints");Check(actualArm<=(mode>=2?18:9)+1e-5,"arm cap");
   if(mode==0)Check(pose.points.Select((v,j)=>Norm(Sub(v,p[j]))).Max()<1e-12,"source identity");
   maxBone=Math.Max(maxBone,bone);maxFoot=Math.Max(maxFoot,foot);maxKnee=Math.Max(maxKnee,pose.kneeDegrees);maxArm=Math.Max(maxArm,actualArm);
   var observed=clip.Observe(pose.points);
   return new Output{pose=clip.Export(pose.points),expansion=observed.E,heightRatio=observed.H,arm=arm,lowering=height/Scale,torso=posture.torso,head=posture.head,target=target};
  }
 }
 public class Output {
  public double[][] pose{get;set;}public double expansion{get;set;}public double heightRatio{get;set;}public double arm{get;set;}public double lowering{get;set;}public double torso{get;set;}public double head{get;set;}public double target{get;set;}public double offset{get;set;}
 }
 class Live {
  readonly Clip clip;readonly VisibleReference reference;readonly Body[] bodies={new(),new()};readonly InteractiveExpression[] responses={new(),new()};
  readonly List<Output[]> history=new();double time;
  public Live(Clip c,VisibleReference r){clip=c;reference=r;}
  public object Step(double[] statuses,int mode,bool interaction,double distance,bool freeze=false,double delay=.25){
   const double dt=1.0/30;int frame=freeze?40:(int)Math.Floor(time/clip.Dt)%clip.Raw.Length;
   var source=clip.Export(clip.Raw[frame]);var result=new Output[2];var targets=new double[2];var offsets=new double[2];
   var profile=mode>=2?new ExpressionProfile(.85,.15,.018):ExpressionProfile.SourceToCompact;
   var observed=history.Count==0?null:history[Math.Max(0,history.Count-1-(int)Math.Round(delay/dt))];
   for(int i=0;i<2;i++){
    var measured=observed==null?clip.Observe(clip.Raw[frame]):(observed[1-i].expansion,observed[1-i].heightRatio);
    var cue=new NeighborCue{ActorId=1-i,Expansion=measured.Item1,HeightRatio=measured.Item2,RelativeX=distance,RelativeVX=-.5,Confidence=1,MeasurementValid=true};
    var response=responses[i].Step(i,statuses[i],profile,reference,new[]{cue},dt,interaction,new ResponseSettings());
    targets[i]=response.CompactnessTarget;offsets[i]=response.EffectiveOffset;
   }
   for(int i=0;i<2;i++){result[i]=bodies[i].Step(clip,frame,targets[i],mode,dt);result[i].offset=offsets[i];}
   history.Add(result);if(history.Count>120)history.RemoveAt(0);time+=dt;
   return new{t=time,names=clip.Names,parents=clip.Parents,source,actors=result,mode,interaction,statuses,distance};
  }
 }
 static Dictionary<string,Clip> Load(string path){
  using var input=JsonDocument.Parse(File.ReadAllText(path));var clips=new Dictionary<string,Clip>();
  foreach(var c in input.RootElement.GetProperty("clips").EnumerateArray()){
   string id=c.GetProperty("id").GetString();if(id!="M01"&&id!="M07")continue;
   var clip=new Clip{Id=id,Names=JsonSerializer.Deserialize<string[]>(c.GetProperty("names").GetRawText()),Parents=JsonSerializer.Deserialize<int?[]>(c.GetProperty("parents").GetRawText()),Raw=JsonSerializer.Deserialize<double[][][]>(c.GetProperty("raw").GetRawText()),Dt=c.GetProperty("dt").GetDouble()};
   foreach(var p in clip.Raw)foreach(var v in p)for(int k=0;k<3;k++)v[k]*=Scale;
   double sign=0;foreach(var p in clip.Raw){var f=Unit(Cross(clip.Right(p),clip.Up(p)));foreach(string side in new[]{"L","R"}){var h=p[clip.I("UpperLeg_"+side)];var bend=Sub(p[clip.I("LowerLeg_"+side)],h);var axis=Unit(Sub(p[clip.I("Foot_"+side)],h));sign+=Dot(Sub(bend,Mul(axis,Dot(bend,axis))),f);}}
   clip.Sign=sign>=0?1:-1;clips[id]=clip;
  }return clips;
 }
 static void Main(string[] args){
  var clips=Load(args[1]);using var calibration=JsonDocument.Parse(File.ReadAllText(args[2]));var j=calibration.RootElement.GetProperty("reference");
  double R(string k)=>j.GetProperty(k).GetDouble();var reference=new VisibleReference(R("expansionCenter"),R("expansionScale"),R("heightCenter"),R("heightScale"));
  if(args[0]=="serve"){
   string html=File.ReadAllText(args[3]);var sessions=new Dictionary<string,Live>();using var listener=new HttpListener();listener.Prefixes.Add("http://127.0.0.1:8790/");listener.Start();Console.WriteLine("IE05 live: http://127.0.0.1:8790/");Console.Out.Flush();
   while(true){var context=listener.GetContext();try{
     if(context.Request.Url.AbsolutePath!="/step"){var bytes=Encoding.UTF8.GetBytes(html);context.Response.ContentType="text/html; charset=utf-8";context.Response.OutputStream.Write(bytes);}
     else{var q=context.Request.QueryString;string id=q["session"]??"default";if(!sessions.ContainsKey(id)||q["reset"]=="1"){if(sessions.Count>12)sessions.Clear();sessions[id]=new Live(clips[q["clip"]=="M07"?"M07":"M01"],reference);}
      double D(string k,double fallback)=>double.TryParse(q[k],System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out double v)&&double.IsFinite(v)?v:fallback;
      var watch=Stopwatch.StartNew();var data=sessions[id].Step(new[]{ExpressionMath.Clamp(D("a",.2),0,1),ExpressionMath.Clamp(D("b",.8),0,1)},(int)ExpressionMath.Clamp(D("mode",4),0,4),q["interaction"]!="0",ExpressionMath.Clamp(D("distance",1),.2,4));watch.Stop();
      context.Response.ContentType="application/json";context.Response.Headers["X-Compute-Ms"]=watch.Elapsed.TotalMilliseconds.ToString("F2",System.Globalization.CultureInfo.InvariantCulture);var bytes=JsonSerializer.SerializeToUtf8Bytes(data);context.Response.OutputStream.Write(bytes);
     }
    }catch(Exception e){context.Response.StatusCode=500;var bytes=Encoding.UTF8.GetBytes(e.Message);context.Response.OutputStream.Write(bytes);}finally{context.Response.Close();}}
  }
  var scenes=new List<object>();
  foreach(var clip in clips.Values){var bodies=Enumerable.Range(0,5).Select(_=>new Body()).ToArray();var frames=new List<object>();
   for(int f=0;f<clip.Raw.Length;f++){var outputs=bodies.Select((b,m)=>b.Step(clip,f,.8,m,clip.Dt)).ToArray();frames.Add(new{source=clip.Export(clip.Raw[f]),actors=outputs});}
   scenes.Add(new{kind="comparison",id=clip.Id,names=clip.Names,parents=clip.Parents,labels=Labels,frames});Console.WriteLine("compared "+clip.Id);Console.Out.Flush();}
  var live=new Live(clips["M01"],reference);var liveFrames=new List<object>();for(int f=0;f<240;f++)liveFrames.Add(live.Step(new[]{.2,.8},4,true,1));
  scenes.Add(new{kind="interactive",id="live",frames=liveFrames});
  var stability=new List<object>();
  foreach(double delay in new[]{0,.25,.5}){var probe=new Live(clips["M01"],reference);var targets=new List<double[]>();for(int f=0;f<720;f++){
    var snapshot=JsonSerializer.SerializeToElement(probe.Step(new[]{.2,.8},4,true,1,true,delay));targets.Add(snapshot.GetProperty("actors").EnumerateArray().Select(a=>a.GetProperty("target").GetDouble()).ToArray());}
   double range=Enumerable.Range(0,2).Max(i=>targets.TakeLast(90).Max(v=>v[i])-targets.TakeLast(90).Min(v=>v[i]));stability.Add(new{delay,lateTargetRange=range,criterionPassed=range<1e-4});}
  File.WriteAllText(args[3],JsonSerializer.Serialize(new{kind="IE05 actual frame-by-frame body+response execution; independent of Unity",checks,maxBone,maxFoot,maxKnee,maxArm,stability,scenes}));Console.WriteLine("checks="+checks+" maxBone="+maxBone+" maxArm="+maxArm+" maxKnee="+maxKnee);
 }
}
