// Offline numerical compatibility layer for the unmodified read-only knee snapshot.
// No Unity engine or editor is started. This is NOT a replacement for Unity validation.
using System;
namespace UnityEngine {
 public static class Mathf {
  public const float Deg2Rad=(float)(Math.PI/180);
  public static float Max(float a,float b)=>Math.Max(a,b);
  public static float Min(float a,float b)=>Math.Min(a,b);
  public static float Abs(float v)=>Math.Abs(v);
  public static float Exp(float v)=>(float)Math.Exp(v);
  public static float Sqrt(float v)=>(float)Math.Sqrt(v);
  public static float Clamp(float v,float a,float b)=>Math.Max(a,Math.Min(b,v));
  public static float InverseLerp(float a,float b,float v)=>a==b?0:Clamp((v-a)/(b-a),0,1);
  public static float SmoothStep(float a,float b,float t){t=Clamp(t,0,1);return a+(b-a)*t*t*(3-2*t);}
 }
 public struct Vector3 {
  public float x,y,z;
  public Vector3(float x,float y,float z){this.x=x;this.y=y;this.z=z;}
  public static Vector3 right=>new Vector3(1,0,0);
  public static Vector3 up=>new Vector3(0,1,0);
  public static Vector3 zero=>new Vector3();
  public float sqrMagnitude=>x*x+y*y+z*z;
  public float magnitude=>(float)Math.Sqrt(sqrMagnitude);
  public Vector3 normalized=>magnitude>1e-12f?this/magnitude:zero;
  public void Normalize(){this=normalized;}
  public static Vector3 operator +(Vector3 a,Vector3 b)=>new Vector3(a.x+b.x,a.y+b.y,a.z+b.z);
  public static Vector3 operator -(Vector3 a,Vector3 b)=>new Vector3(a.x-b.x,a.y-b.y,a.z-b.z);
  public static Vector3 operator *(Vector3 a,float s)=>new Vector3(a.x*s,a.y*s,a.z*s);
  public static Vector3 operator /(Vector3 a,float s)=>a*(1/s);
  public static float Dot(Vector3 a,Vector3 b)=>a.x*b.x+a.y*b.y+a.z*b.z;
  public static Vector3 Cross(Vector3 a,Vector3 b)=>new Vector3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);
  public static Vector3 ProjectOnPlane(Vector3 a,Vector3 n)=>n.sqrMagnitude<1e-16f?a:a-n*(Dot(a,n)/n.sqrMagnitude);
  public static float Distance(Vector3 a,Vector3 b)=>(a-b).magnitude;
  public static Vector3 Slerp(Vector3 a,Vector3 b,float t){
   t=Mathf.Clamp(t,0,1);float al=a.magnitude,bl=b.magnitude;if(al<1e-12f||bl<1e-12f)return a*(1-t)+b*t;
   var ua=a/al;var ub=b/bl;double dot=Mathf.Clamp(Dot(ua,ub),-1,1);var orth=ub-ua*(float)dot;
   if(orth.sqrMagnitude<1e-12f){if(dot>0)return (ua*(1-t)+ub*t).normalized*(al+(bl-al)*t);orth=Cross(ua,Math.Abs(ua.y)<.9?up:right);}
   double angle=Math.Acos(dot)*t;return (ua*(float)Math.Cos(angle)+orth.normalized*(float)Math.Sin(angle))*(al+(bl-al)*t);
  }
  public static Vector3 RotateTowards(Vector3 a,Vector3 b,float maxRadiansDelta,float maxMagnitudeDelta){
   double angle=Math.Acos(Mathf.Clamp(Dot(a.normalized,b.normalized),-1,1));
   float fraction=angle<1e-10?1:(float)Math.Min(1,maxRadiansDelta/angle);
   return Slerp(a,b,fraction);
  }
 }
 public struct Quaternion {
  internal System.Numerics.Quaternion q;
  public Quaternion(System.Numerics.Quaternion q){this.q=q;}
  public static Quaternion Inverse(Quaternion a)=>new Quaternion(System.Numerics.Quaternion.Inverse(a.q));
  public static Quaternion operator *(Quaternion a,Quaternion b)=>new Quaternion(a.q*b.q);
  public static Vector3 operator *(Quaternion a,Vector3 v){var r=System.Numerics.Vector3.Transform(new System.Numerics.Vector3(v.x,v.y,v.z),a.q);return new Vector3(r.X,r.Y,r.Z);}
  public static Quaternion FromToRotation(Vector3 a,Vector3 b){a.Normalize();b.Normalize();var cross=Vector3.Cross(a,b);float dot=Vector3.Dot(a,b);if(dot<-.99999f){cross=Vector3.Cross(a,Math.Abs(a.y)<.9?Vector3.up:Vector3.right).normalized;return new Quaternion(new System.Numerics.Quaternion(cross.x,cross.y,cross.z,0));}return new Quaternion(System.Numerics.Quaternion.Normalize(new System.Numerics.Quaternion(cross.x,cross.y,cross.z,1+dot)));}
 }
 // Required only to compile SprintLegIK.Apply; not exercised by offline knee replay.
 public class Transform { public Vector3 position; public Quaternion rotation; }
}
