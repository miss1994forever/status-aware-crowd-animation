using System;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using IndividualExpressionCandidate;

// Read-only source replay. Only upper-arm subtrees are rotated; no leg/lowering solve.
static class Replay {
 static double[] Add(double[] a,double[] b)=>new[]{a[0]+b[0],a[1]+b[1],a[2]+b[2]};
 static double[] Sub(double[] a,double[] b)=>new[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};
 static double[] Mul(double[] a,double s)=>new[]{a[0]*s,a[1]*s,a[2]*s};
 static double Dot(double[] a,double[] b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 static double Norm(double[] a)=>Math.Sqrt(Dot(a,a));
 static double[] Unit(double[] a)=>Mul(a,1/Norm(a));
 static double[] Cross(double[] a,double[] b)=>new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
 static double[] Rotate(double[] v,double[] from,double[] to) {
  var k=Cross(from,to);return Add(Add(v,Cross(k,v)),Mul(Cross(k,Cross(k,v)),1/(1+Dot(from,to))));
 }
 static double[] AxisRotate(double[] v,double[] axis,double angle)=>Add(Add(Mul(v,Math.Cos(angle)),Mul(Cross(axis,v),Math.Sin(angle))),Mul(axis,Dot(axis,v)*(1-Math.Cos(angle))));
 static double[][] Clone(double[][] p){var q=new double[p.Length][];for(int i=0;i<p.Length;i++)q[i]=(double[])p[i].Clone();return q;}
 static bool Child(int joint,int parent,int?[] parents){for(int? p=parents[joint];p.HasValue;p=parents[p.Value])if(p.Value==parent)return true;return false;}
 static double Expansion(double[][] p,int l,int r,int elbow)=>Dot(Sub(p[l],p[elbow]),Unit(Sub(p[r],p[l])))/Norm(Sub(p[r],p[l]));
 public static void Run(string input,string output) {
  using var doc=JsonDocument.Parse(File.ReadAllText(input));
  var clips=new List<object>();
  foreach(var c in doc.RootElement.GetProperty("clips").EnumerateArray()) {
   string id=c.GetProperty("id").GetString();if(id!="M01"&&id!="M07")continue;
   var names=JsonSerializer.Deserialize<string[]>(c.GetProperty("names").GetRawText());
   var parents=JsonSerializer.Deserialize<int?[]>(c.GetProperty("parents").GetRawText());
   var raw=JsonSerializer.Deserialize<double[][][]>(c.GetProperty("raw").GetRawText());
   double dt=c.GetProperty("dt").GetDouble();
   int h=Array.IndexOf(names,"Hips"),head=Array.IndexOf(names,"Head"),l=Array.IndexOf(names,"UpperArm_L"),r=Array.IndexOf(names,"UpperArm_R");
   int le=Array.IndexOf(names,"LowerArm_L"),re=Array.IndexOf(names,"LowerArm_R");
   var variants=new Dictionary<string,List<double[][]>>();
   foreach(var key in new[]{"source","fixed","half","full"})variants[key]=new List<double[][]>();
   var halfPolicy=new ExpressionPolicy();var fullPolicy=new ExpressionPolicy();
   double maxBoneError=0,maxSagittal=0,maxAngle=0,maxNonArmChange=0,maxObservationDelta=0,maxWristChange=0,maxRequested=0;
   var requested=new List<double>();
   for(int f=0;f<raw.Length;f++) {
    var p=raw[f];var right=Unit(Sub(p[r],p[l]));var up=Sub(p[head],p[h]);up=Unit(Sub(up,Mul(right,Dot(up,right))));var forward=Unit(Cross(right,up));
    // Frozen input is already normalized by reference height. speed/scale is dimensionless.
    var d=Sub(p[h],raw[Math.Max(0,f-1)][h]);
    if(f==0&&raw.Length>1)d=Sub(raw[1][h],p[h]);
    double speed=Math.Sqrt(d[0]*d[0]+d[2]*d[2])/dt;
    var full=fullPolicy.Step(0,ExpressionProfile.SourceToCompact,1,speed,dt,true);
    var half=halfPolicy.Step(.5,ExpressionProfile.SourceToCompact,1,speed,dt,true);
    requested.Add(full.RequestedLowering);maxRequested=Math.Max(maxRequested,full.RequestedLowering);
    foreach(var key in new[]{"source","fixed","half","full"}) {
     var q=Clone(p);
     if(key=="fixed") {
      var v=Sub(p[le],p[l]);double a=12*Math.PI/180;
      var va=AxisRotate(v,forward,a);var vb=AxisRotate(v,forward,-a);
      if(Dot(va,right)<Dot(vb,right))a=-a;
      for(int j=0;j<p.Length;j++)if(Child(j,l,parents))q[j]=Add(p[l],AxisRotate(Sub(p[j],p[l]),forward,a));
     } else if(key!="source") {
      double weight=key=="full"?full.ArmWeight:half.ArmWeight;
      foreach(var arm in new[]{new[]{l,le},new[]{r,re}}) {
       bool left=arm[0]==l;var outward=Mul(right,left?-1:1);var v=Unit(Sub(p[arm[1]],p[arm[0]]));
       var t=ExpressionMath.Solve(Dot(v,outward),Dot(v,up),Dot(v,forward),weight,left?1:.75);
       maxSagittal=Math.Max(maxSagittal,Math.Abs(t.Z-Dot(v,forward)));maxAngle=Math.Max(maxAngle,t.Angle*180/Math.PI);
       if(t.Changed){var target=Add(Add(Mul(outward,t.X),Mul(up,t.Y)),Mul(forward,t.Z));
        for(int j=0;j<p.Length;j++)if(Child(j,arm[0],parents))q[j]=Add(p[arm[0]],Rotate(Sub(p[j],p[arm[0]]),v,target));
       }
      }
      maxObservationDelta=Math.Max(maxObservationDelta,Math.Abs(Expansion(q,l,r,le)-Expansion(p,l,r,le)));
      foreach(string hand in new[]{"Hand_L","Hand_R"})maxWristChange=Math.Max(maxWristChange,Norm(Sub(q[Array.IndexOf(names,hand)],p[Array.IndexOf(names,hand)])));
      for(int j=0;j<p.Length;j++){
       if(parents[j].HasValue)maxBoneError=Math.Max(maxBoneError,Math.Abs(Norm(Sub(q[j],q[parents[j].Value]))-Norm(Sub(p[j],p[parents[j].Value]))));
       if(!Child(j,l,parents)&&!Child(j,r,parents))maxNonArmChange=Math.Max(maxNonArmChange,Norm(Sub(q[j],p[j])));
      }
     }
     variants[key].Add(q);
    }
   }
   if(maxBoneError>1e-10||maxNonArmChange!=0||maxSagittal>1e-12||maxAngle>9.000001)throw new Exception("replay constraint violation "+id);
   clips.Add(new{id,names,parents,dt,variants,requestedLowering=requested,
    audit=new{frames=raw.Length,maxBoneLengthAbsoluteError=maxBoneError,maxNonArmChange,maxSagittalChange=maxSagittal,maxAngleDegrees=maxAngle,maxObservationDelta,maxWristDisplacement=maxWristChange,maxRequestedLowering=maxRequested,loweringApplied=false},
    source=c.GetProperty("review").GetProperty("source").Clone()});
  }
  File.WriteAllText(output,JsonSerializer.Serialize(new{type="offline arm-only replay; not Unity",coordinateUnits="frozen reference body heights; not verified metres",clips}));
  Console.WriteLine("replayed two frozen raw clips; output="+output);
 }
}
