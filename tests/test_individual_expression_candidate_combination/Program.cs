using System;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using IndividualExpressionCandidate;
using UnityEngine;
class Program {
 const double Scale=1.65; // Virtual-avatar scale for solver thresholds, not original BVH metres.
 static double[] Add(double[] a,double[] b)=>new[]{a[0]+b[0],a[1]+b[1],a[2]+b[2]};
 static double[] Sub(double[] a,double[] b)=>new[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};
 static double[] Mul(double[] a,double s)=>new[]{a[0]*s,a[1]*s,a[2]*s};
 static double Dot(double[] a,double[] b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
 static double Norm(double[] a)=>Math.Sqrt(Dot(a,a));
 static double[] Unit(double[] a)=>Mul(a,1/Math.Max(1e-15,Norm(a)));
 static double[] Cross(double[] a,double[] b)=>new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
 static Vector3 V(double[] p)=>new Vector3((float)p[0],(float)p[1],(float)p[2]);
 static double[] D(Vector3 p)=>new[]{(double)p.x,(double)p.y,(double)p.z};
 static double[] Rotate(double[] v,double[] from,double[] to){var k=Cross(from,to);return Add(Add(v,Cross(k,v)),Mul(Cross(k,Cross(k,v)),1/(1+Dot(from,to))));}
 static double[][] Clone(double[][] p){var q=new double[p.Length][];for(int i=0;i<p.Length;i++)q[i]=(double[])p[i].Clone();return q;}
 static bool Child(int joint,int parent,int?[] parents){for(int? p=parents[joint];p.HasValue;p=parents[p.Value])if(p.Value==parent)return true;return false;}
 static double Angle(double[] a,double[] b)=>Math.Acos(ExpressionMath.Clamp(Dot(Unit(a),Unit(b)),-1,1))*180/Math.PI;
 static Quaternion Frame(double[] r,double[] u,double[] f)=>new Quaternion(System.Numerics.Quaternion.CreateFromRotationMatrix(new System.Numerics.Matrix4x4((float)r[0],(float)r[1],(float)r[2],0,(float)u[0],(float)u[1],(float)u[2],0,(float)f[0],(float)f[1],(float)f[2],0,0,0,0,1)));
 internal class Pose {
  public double[][] points;public double maxBoneError,footError,kneeDegrees,armDegrees,elbowResidual;public bool feasible;
  public SprintLegIK.Hint leftHint,rightHint;
 }
 internal static Pose Make(double[][] p,string[] names,int?[] parents,double height,double armWeight,double desiredArm,
  double[] right,double[] up,double[] forward,double[] anterior,double dt,SprintLegIK.Hint lh,SprintLegIK.Hint rh){
  var q=Clone(p);int li=0;double maxKnee=0;
  var frame=Frame(right,up,forward);
  for(int j=0;j<q.Length;j++)q[j][1]-=height;
  foreach(string side in new[]{"L","R"}){
   int hip=Array.IndexOf(names,"UpperLeg_"+side),k=Array.IndexOf(names,"LowerLeg_"+side),foot=Array.IndexOf(names,"Foot_"+side);
   if(height>1e-12){
    float a=(float)Norm(Sub(p[k],p[hip])),b=(float)Norm(Sub(p[foot],p[k]));
    if(li==0)q[k]=D(SprintLegIK.Knee(V(q[hip]),V(p[foot]),a,b,V(p[hip]),V(p[k]),V(p[foot]),frame,V(anterior),(float)dt,ref lh));
    else q[k]=D(SprintLegIK.Knee(V(q[hip]),V(p[foot]),a,b,V(p[hip]),V(p[k]),V(p[foot]),frame,V(anterior),(float)dt,ref rh));
    maxKnee=Math.Max(maxKnee,Angle(Sub(q[k],q[hip]),Sub(p[k],p[hip])));
   } else q[k]=(double[])p[k].Clone();
   for(int j=0;j<q.Length;j++)if(j==foot||Child(j,foot,parents))q[j]=(double[])p[j].Clone();li++;
  }
  double residual=0,maxArm=0;
  foreach(string side in new[]{"L","R"}){
   int shoulder=Array.IndexOf(names,"UpperArm_"+side),elbow=Array.IndexOf(names,"LowerArm_"+side);
   var outwards=Mul(right,side=="L"?-1:1);var v=Unit(Sub(p[elbow],p[shoulder]));
   double x=Dot(v,outwards),y=Dot(v,up),z=Dot(v,forward);
   var target=ExpressionMath.Solve(x,y,z,armWeight,side=="L"?1:.75);
   maxArm=Math.Max(maxArm,target.Angle*180/Math.PI);
   if(target.Changed){var next=Add(Add(Mul(outwards,target.X),Mul(up,target.Y)),Mul(forward,target.Z));
    for(int j=0;j<q.Length;j++)if(Child(j,shoulder,parents))q[j]=Add(q[shoulder],Rotate(Sub(p[j],p[shoulder]),v,next));
   }
   // Observable target is shoulder-relative elbow occupancy, not commanded angle.
   double desiredX=x>0&&y<0?x*(1-.40*desiredArm):x;
   residual+=Math.Pow((target.X-desiredX)/.04,2)/2;
  }
  double bone=0,footError=0;
  for(int j=0;j<q.Length;j++)if(parents[j].HasValue)bone=Math.Max(bone,Math.Abs(Norm(Sub(q[j],q[parents[j].Value]))-Norm(Sub(p[j],p[parents[j].Value]))));
  foreach(string side in new[]{"L","R"}){int foot=Array.IndexOf(names,"Foot_"+side);for(int j=0;j<q.Length;j++)if(j==foot||Child(j,foot,parents))footError=Math.Max(footError,Norm(Sub(q[j],p[j])));}
  return new Pose{points=q,maxBoneError=bone,footError=footError,kneeDegrees=maxKnee,armDegrees=maxArm,elbowResidual=Math.Sqrt(residual),leftHint=lh,rightHint=rh,feasible=bone<.00004&&footError<1e-12&&maxKnee<=12};
 }
 static void SearchChecks(){
  var search=new BodyCombinationSearch();
  var zero=search.Solve(0,0,.016,Scale,(h,a)=>new BodyCombinationSearch.Evaluation{Feasible=true});
  if(!zero.Feasible||zero.Lowering!=0||zero.ArmWeight!=0)throw new Exception("identity");
  var clipped=search.Solve(.02,1,.016,Scale,(h,a)=>new BodyCombinationSearch.Evaluation{Feasible=h<=.01,ElbowResidual=1-a});
  if(!clipped.Feasible||clipped.Lowering>.01||clipped.ArmWeight<0||clipped.ArmWeight>1)throw new Exception("constraint projection");
  if(search.Solve(double.NaN,1,.016,Scale,(h,a)=>new BodyCombinationSearch.Evaluation()).Feasible)throw new Exception("NaN");

  var s1=new BodyCombinationSearch();var s2=new BodyCombinationSearch();
  for(int i=0;i<60;i++){
   var a=s1.Solve(.02,1,.016,Scale,(h,w)=>new BodyCombinationSearch.Evaluation{Feasible=h<=.015,ElbowResidual=1-w});
   var b=s2.Solve(.04,1,.016,2*Scale,(h,w)=>new BodyCombinationSearch.Evaluation{Feasible=h<=.030,ElbowResidual=1-w});
   if(Math.Abs(a.Lowering*2-b.Lowering)>1e-12||Math.Abs(a.ArmWeight-b.ArmWeight)>1e-12)throw new Exception("scale normalization");
  }
  var q=new Quaternion(System.Numerics.Quaternion.CreateFromAxisAngle(System.Numerics.Vector3.UnitY,.7f));
  var original=new Vector3(.2f,-.7f,.3f);var restored=Quaternion.Inverse(q)*(q*original);
  if(Vector3.Distance(restored,original)>1e-6)throw new Exception("shim frame roundtrip");

 }
 static void Main(string[] args){
  SearchChecks();using var doc=JsonDocument.Parse(File.ReadAllText(args[0]));var result=new List<object>();
  foreach(var clip in doc.RootElement.GetProperty("clips").EnumerateArray()){
   string id=clip.GetProperty("id").GetString();if(id!="M01"&&id!="M07")continue;
   var names=JsonSerializer.Deserialize<string[]>(clip.GetProperty("names").GetRawText());var parents=JsonSerializer.Deserialize<int?[]>(clip.GetProperty("parents").GetRawText());var raw=JsonSerializer.Deserialize<double[][][]>(clip.GetProperty("raw").GetRawText());double dt=clip.GetProperty("dt").GetDouble();
   // Convert normalized coordinates to a declared virtual avatar scale solely for snapshot thresholds.
   foreach(var pose in raw)foreach(var point in pose)for(int j=0;j<3;j++)point[j]*=Scale;
   int hip=Array.IndexOf(names,"Hips"),head=Array.IndexOf(names,"Head"),ls=Array.IndexOf(names,"UpperArm_L"),rs=Array.IndexOf(names,"UpperArm_R");
   // Infer anterior sign from well-defined source knee bends, not the hidden status.
   double sign=0;foreach(var p in raw){var rr=Unit(Sub(p[rs],p[ls]));var uu=Unit(Sub(p[head],p[hip]));var ff=Unit(Cross(rr,uu));foreach(string side in new[]{"L","R"}){var h=p[Array.IndexOf(names,"UpperLeg_"+side)];var k=p[Array.IndexOf(names,"LowerLeg_"+side)];var foot=p[Array.IndexOf(names,"Foot_"+side)];var axis=Unit(Sub(foot,h));var bend=Sub(Sub(k,h),Mul(axis,Dot(Sub(k,h),axis)));sign+=Dot(bend,ff);}}
   var variants=new Dictionary<string,List<double[][]>>();foreach(string key in new[]{"source","arms","combination","target"})variants[key]=new List<double[][]>();
   var hints=new Dictionary<string,SprintLegIK.Hint[]>();foreach(string key in variants.Keys)hints[key]=new SprintLegIK.Hint[2];
   var policy=new ExpressionPolicy();var search=new BodyCombinationSearch();var telemetry=new List<object>();
   double maxBone=0,maxFoot=0,maxKnee=0,maxHeight=0,maxOverlayStep=0;int rejected=0,fallback=0;double[][] previousOverlay=null;
   for(int f=0;f<raw.Length;f++){
    var p=raw[f];var right=Unit(Sub(p[rs],p[ls]));var up=Sub(p[head],p[hip]);up=Unit(Sub(up,Mul(right,Dot(up,right))));var forward=Unit(Cross(right,up));var anterior=Mul(forward,sign>=0?1:-1);
    var delta=f==0?Sub(raw[1][hip],p[hip]):Sub(p[hip],raw[f-1][hip]);double speed=Math.Sqrt(delta[0]*delta[0]+delta[2]*delta[2])/dt;
    var command=policy.Step(0,ExpressionProfile.SourceToCompact,Scale,speed,dt,true);
    var hs=hints["target"];
    var plan=search.Solve(command.RequestedLowering,command.ArmWeight,dt,Scale,(h,a)=>{var test=Make(p,names,parents,h,a,command.ArmWeight,right,up,forward,anterior,dt,hs[0],hs[1]);return new BodyCombinationSearch.Evaluation{Feasible=test.feasible,ElbowResidual=test.elbowResidual,KneeChange=test.kneeDegrees/12,ArmChange=test.armDegrees/9};});
    if(!plan.Feasible)throw new Exception("no source fallback");if(plan.TemporalFallback)fallback++;
    double appliedTargetHeight=plan.Lowering;
    foreach(string key in new[]{"source","arms","combination","target"}){
     double height=key=="combination"?command.RequestedLowering:key=="target"?plan.Lowering:0;
     double arm=key=="source"?0:key=="target"?plan.ArmWeight:command.ArmWeight;
     var hh=hints[key];var pose=Make(p,names,parents,height,arm,command.ArmWeight,right,up,forward,anterior,dt,hh[0],hh[1]);
     if(key=="combination"&&!pose.feasible)rejected++;
     if(key=="target"&&!pose.feasible)throw new Exception("target invalid");
     hints[key]=new[]{pose.leftHint,pose.rightHint};
     if(key=="target"){
      maxBone=Math.Max(maxBone,pose.maxBoneError);maxFoot=Math.Max(maxFoot,pose.footError);maxKnee=Math.Max(maxKnee,pose.kneeDegrees);maxHeight=Math.Max(maxHeight,height);
      var overlay=new double[p.Length][];for(int j=0;j<p.Length;j++){overlay[j]=Sub(pose.points[j],p[j]);if(previousOverlay!=null)maxOverlayStep=Math.Max(maxOverlayStep,Norm(Sub(overlay[j],previousOverlay[j]))/Scale);}previousOverlay=overlay;
     }
     // Export in the original frozen reference-height coordinates for equal-scale display.
     var export=Clone(pose.points);foreach(var point in export)for(int j=0;j<3;j++)point[j]/=Scale;variants[key].Add(export);
    }
    telemetry.Add(new{frame=f,requestedHeight=command.RequestedLowering/Scale,targetHeight=appliedTargetHeight/Scale,requestedArm=command.ArmWeight,targetArm=plan.ArmWeight,plan.Cost,plan.TemporalFallback});
   }
   if(maxOverlayStep>.035)throw new Exception("large overlay step "+id+" "+maxOverlayStep);
   result.Add(new{id,names,parents,dt,variants,telemetry,source=clip.GetProperty("review").GetProperty("source").Clone(),audit=new{frames=raw.Length,virtualScaleMetres=Scale,maxBoneErrorMetres=maxBone,maxFootErrorMetres=maxFoot,maxKneeCorrectionDegrees=maxKnee,maxAppliedLoweringBodyHeights=maxHeight/Scale,maxOverlayStepBodyHeights=maxOverlayStep,targetTemporalFallbacks=fallback,unconstrainedCombinationRejectedFrames=rejected}});
  }
  File.WriteAllText(args[1],JsonSerializer.Serialize(new{type="offline body-combination exploration; unmodified reference knee source via managed math shim; not Unity",clips=result}));Console.WriteLine("Combination replay written; target constraints checked; not a perception result.");
 }
}
