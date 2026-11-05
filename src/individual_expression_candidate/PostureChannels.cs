using System;
namespace IndividualExpressionCandidate {
 // IE-05 exploratory geometry channels; independent of status and neighbor inference.
 public static class PostureChannels {
  public static double[] Sub(double[] a,double[] b)=>new[]{a[0]-b[0],a[1]-b[1],a[2]-b[2]};
  public static double Dot(double[] a,double[] b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  public static double[] Mul(double[] a,double s)=>new[]{a[0]*s,a[1]*s,a[2]*s};
  public static double[] Add(double[] a,double[] b)=>new[]{a[0]+b[0],a[1]+b[1],a[2]+b[2]};
  public static double Norm(double[] a)=>Math.Sqrt(Dot(a,a));
  public static double[] Unit(double[] a)=>Mul(a,1/Math.Max(1e-15,Norm(a)));
  public static double[] Cross(double[] a,double[] b)=>new[]{a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
  public static bool Child(int j,int parent,int?[] parents){for(int? p=parents[j];p.HasValue;p=parents[p.Value])if(p.Value==parent)return true;return false;}
  static double[] Rotate(double[] v,double[] axis,double a)=>Add(Add(Mul(v,Math.Cos(a)),Mul(Cross(axis,v),Math.Sin(a))),Mul(axis,Dot(axis,v)*(1-Math.Cos(a))));
  static void Subtree(double[][] p,int pivot,int root,int?[] parents,double[] axis,double radians){
   var origin=(double[])p[pivot].Clone();for(int j=0;j<p.Length;j++)if(j==root||Child(j,root,parents))p[j]=Add(origin,Rotate(Sub(p[j],origin),axis,radians));
  }
  public static double ApplyArms(double[][] p,string[] names,int?[] parents,double weight,bool stronger,double[] right,double[] up,double[] forward){
   double maxAngle=0;
   foreach(string side in new[]{"L","R"}){
    int s=Array.IndexOf(names,"UpperArm_"+side),e=Array.IndexOf(names,"LowerArm_"+side);var outward=Mul(right,side=="L"?-1:1);var v=Unit(Sub(p[e],p[s]));
    double x=Dot(v,outward),y=Dot(v,up),z=Dot(v,forward);var target=ExpressionMath.Solve(x,y,z,weight,side=="L"?1:.75);
    if(stronger&&x>0&&y<0){
     double gate=ExpressionMath.Smooth(.03,.18,-y)*(1-ExpressionMath.Smooth(.25,.65,Math.Abs(z)));
     double amount=.85*ExpressionMath.Clamp(weight,0,1)*(side=="L"?1:.75)*gate;
     double radius=Math.Sqrt(x*x+y*y),theta=Math.Atan2(x,-y),wanted=Math.Asin(ExpressionMath.Clamp(x*(1-amount)/radius,0,1));
     double turn=Math.Min(18*Math.PI/180,Math.Max(0,theta-wanted));
     target.X=radius*Math.Sin(theta-turn);target.Y=-radius*Math.Cos(theta-turn);target.Z=z;target.Changed=turn>1e-12;target.Angle=Math.Acos(ExpressionMath.Clamp(x*target.X+y*target.Y+z*z,-1,1));
    }
    maxAngle=Math.Max(maxAngle,target.Angle*180/Math.PI);
    if(target.Changed){var next=Add(Add(Mul(outward,target.X),Mul(up,target.Y)),Mul(forward,target.Z));var axis=Unit(Cross(v,next));Subtree(p,s,e,parents,axis,target.Angle);}
   }
   return maxAngle;
  }
  public static (double torso,double head) ApplyPosture(double[][] p,string[] names,int?[] parents,double weight,int mode,double[] right,double anteriorSign){
   double torso=mode>=3?12*ExpressionMath.Smooth(.15,.85,weight):0;
   double head=mode>=4?10*ExpressionMath.Smooth(.35,.95,weight):0;
   int I(string n)=>Array.IndexOf(names,n);double angle=torso*Math.PI/180*anteriorSign;
   // Distribute the lean over three spine segments; hips/legs remain unchanged.
   Subtree(p,I("Hips"),I("Spine"),parents,right,angle*.5);
   Subtree(p,I("Spine"),I("Chest"),parents,right,angle/3);
   foreach(int j in new[]{I("Neck"),I("Shoulder_L"),I("Shoulder_R")})Subtree(p,I("Chest"),j,parents,right,angle/6);
   Subtree(p,I("Neck"),I("Head"),parents,right,head*Math.PI/180*anteriorSign);
   return (torso,head);
  }
 }
}
