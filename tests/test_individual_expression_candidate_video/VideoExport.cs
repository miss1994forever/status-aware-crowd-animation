using System;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using IndividualExpressionCandidate;

// Reconstruct sampled feedback parameters using the existing offline pose function.
// Exact arms/hips targets; knees re-evaluated at the retained 30Hz samples.
class VideoExport {
 static double[] Sub(double[] a,double[] b)=>new[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};
 static double Dot(double[] a,double[] b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 static double[] Mul(double[] a,double v)=>new[]{a[0]*v,a[1]*v,a[2]*v};
 static double[] Unit(double[] a)=>Mul(a,1/Math.Max(1e-15,Math.Sqrt(Dot(a,a))));
 static double[] Cross(double[] a,double[] b)=>new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
 static void Main(string[] args){
  using var input=JsonDocument.Parse(File.ReadAllText(args[0]));using var feedback=JsonDocument.Parse(File.ReadAllText(args[1]));
  JsonElement clip=default;foreach(var c in input.RootElement.GetProperty("clips").EnumerateArray())if(c.GetProperty("id").GetString()=="M01")clip=c;
  var names=JsonSerializer.Deserialize<string[]>(clip.GetProperty("names").GetRawText());var parents=JsonSerializer.Deserialize<int?[]>(clip.GetProperty("parents").GetRawText());var raw=JsonSerializer.Deserialize<double[][][]>(clip.GetProperty("raw").GetRawText());double sourceDt=clip.GetProperty("dt").GetDouble();
  const double scale=1.65;foreach(var pose in raw)foreach(var point in pose)for(int k=0;k<3;k++)point[k]*=scale;
  int Index(string name)=>Array.IndexOf(names,name);
  double[] Right(double[][] p)=>Unit(Sub(p[Index("UpperArm_R")],p[Index("UpperArm_L")]));
  double[] Up(double[][] p){var r=Right(p);var u=Sub(p[Index("Head")],p[Index("Hips")]);return Unit(Sub(u,Mul(r,Dot(u,r))));}
  double sign=0;foreach(var p in raw){var forward=Unit(Cross(Right(p),Up(p)));foreach(string side in new[]{"L","R"}){var h=p[Index("UpperLeg_"+side)];var bend=Sub(p[Index("LowerLeg_"+side)],h);var axis=Unit(Sub(p[Index("Foot_"+side)],h));sign+=Dot(Sub(bend,Mul(axis,Dot(bend,axis))),forward);}}
  var scenes=new List<object>();double maxBone=0,maxKnee=0,maxFoot=0;int checks=0;
  foreach(string scenario in new[]{"M01-combo-moving","M01-combo-endpoints"}){
   bool moving=scenario.EndsWith("moving");var hints=new SprintLegIK.Hint[2,2];var frames=new List<object>();double previous=0;
   foreach(var entry in feedback.RootElement.GetProperty("traces").EnumerateArray()){
    if(entry.GetProperty("scenario").GetString()!=scenario||entry.GetProperty("seed").GetInt32()!=0)continue;
    var sample=entry.GetProperty("sample");double t=sample.GetProperty("T").GetDouble();if(t>(moving?8:4))continue;
    int frame=moving?(40+(int)Math.Floor((t-1.0/60)/sourceDt+1e-6))%raw.Length:40;var p=raw[frame];var right=Right(p);var up=Up(p);var forward=Unit(Cross(right,up));var anterior=Mul(forward,sign>=0?1:-1);var poses=new List<double[][]>();
    for(int actor=0;actor<2;actor++){
     double arm=sample.GetProperty("Arms")[actor].GetDouble(),height=sample.GetProperty("Heights")[actor].GetDouble()*scale;
     var pose=Program.Make(p,names,parents,height,arm,arm,right,up,forward,anterior,t-previous,hints[actor,0],hints[actor,1]);
     hints[actor,0]=pose.leftHint;hints[actor,1]=pose.rightHint;
     if(!pose.feasible)throw new Exception("sample reconstruction infeasible: "+scenario+" "+t);
     maxBone=Math.Max(maxBone,pose.maxBoneError);maxFoot=Math.Max(maxFoot,pose.footError);maxKnee=Math.Max(maxKnee,pose.kneeDegrees);checks++;
     foreach(var point in pose.points)for(int k=0;k<3;k++)point[k]/=scale;poses.Add(pose.points);
    }
    var source=new double[p.Length][];for(int i=0;i<p.Length;i++)source[i]=Mul(p[i],1/scale);
    frames.Add(new{t,source,poses,targets=sample.GetProperty("Targets").Clone(),offsets=sample.GetProperty("Offsets").Clone()});previous=t;
   }
   scenes.Add(new{scenario,names,parents,frames});
  }
  File.WriteAllText(args[2],JsonSerializer.Serialize(new{kind="offline preview reconstructed from recorded 30Hz feedback parameters; knees recomputed at retained sample interval; not lossless original run or Unity capture",checks,maxBoneErrorMetres=maxBone,maxFootErrorMetres=maxFoot,maxKneeCorrectionDegrees=maxKnee,scenes}));
  Console.WriteLine("video reconstruction checks="+checks+" maxBone="+maxBone+" maxKnee="+maxKnee);
 }
}
