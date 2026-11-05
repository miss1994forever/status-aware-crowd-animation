using UnityEngine;
using Unity.Mathematics;
using MotionMatching;
using System.IO;
using System.Text;
using System.Globalization;

[DefaultExecutionOrder(-200)]
public class SprintDirector : MonoBehaviour {
 public GameObject Template; public int Count=10; public int Mode=2; public float Radius=5;
 public bool CaptureRun; public string CaptureRoot; public float Duration=35;
 public int Seed=806; public string Scenario="crowd"; public bool EnableResponsePose=true;
 public int CaptureFps=60; public int CaptureWidth=1280,CaptureHeight=720;
 public string RunLabel="manual";
 public bool CaptureVideo; public int ClipActor=9;RenderTexture clipTarget;Texture2D clipImage;
 public int LowerBodyPolicy=1;public bool KneeDiagnostics;
 StreamWriter kneeWriter;int lastKneeFrame=-1;
 public int SpatialPolicy; // 0: legacy, 1: soft side, 2: committed, 3: reserved clearance.
 public bool UseOwnedSearch=true; MotionMatchingSearch runtimeSearch;
 int[] heldSides,safeCandidates;float[] sideRelease,predictedGaps;
 int[] sideFlips,rapidSideFlips,safetyOverrides;float[] lastSideChange;float minimumFrameGap=100;
 int[] guardFrames;float[] guardResidual;
 SprintObservation[] observations; int frame; float oldCaptureDeltaTime,oldFixedDeltaTime;
 Vector3[] inputs; int[] partners; float[] risks; double lastRealtime; float realFrameDelta;
 CrowdCharacterController[] controllers; SprintActor[] actors; Vector3[] goals,previous,positions,velocities;float[] observed,belief,response; int[] encounters,arrivals;
 float elapsed,lastLog;int shot;public bool Finished;
 [System.Serializable] class RuntimeSettings {public string build="knee-ik-v3";public bool ownedSearch;public int spatial,lowerBody;}
 void Start(){
  Application.runInBackground=true;lastRealtime=Time.realtimeSinceStartupAsDouble;
  oldCaptureDeltaTime=Time.captureDeltaTime;oldFixedDeltaTime=Time.fixedDeltaTime;
  if(CaptureRun&&CaptureFps>0){Time.captureDeltaTime=1f/CaptureFps;Time.fixedDeltaTime=1f/CaptureFps;}
  if(Scenario=="headon"||Scenario=="crossing")Count=2;
  if(ObstacleManager.Instance==null)new GameObject("EMMObstacleManager").AddComponent<ObstacleManager>();
  UnityEngine.Random.InitState(Seed);controllers=new CrowdCharacterController[Count];actors=new SprintActor[Count];goals=new Vector3[Count];previous=new Vector3[Count];positions=new Vector3[Count];velocities=new Vector3[Count];observed=new float[Count];belief=new float[Count];response=new float[Count];encounters=new int[Count];arrivals=new int[Count];observations=new SprintObservation[Count];inputs=new Vector3[Count];partners=new int[Count];risks=new float[Count];
  heldSides=new int[Count];safeCandidates=new int[Count];sideRelease=new float[Count];predictedGaps=new float[Count];
  sideFlips=new int[Count];rapidSideFlips=new int[Count];safetyOverrides=new int[Count];lastSideChange=new float[Count];for(int i=0;i<Count;i++)lastSideChange[i]=-100;
  guardFrames=new int[Count];guardResidual=new float[Count];
  if(UseOwnedSearch){
   var original=Template.GetComponentInChildren<MotionMatchingController>(true).Search;
   if(!(original is EnvironmentMotionMatchingSearch))throw new System.InvalidOperationException("Owned search expects original EMM environment search settings");
   runtimeSearch=ScriptableObject.CreateInstance<SprintOwnedEnvironmentSearch>();JsonUtility.FromJsonOverwrite(JsonUtility.ToJson(original),runtimeSearch);
  }
  for(int i=0;i<Count;i++){float a=2*Mathf.PI*i/Count;Vector3 start=new Vector3(Mathf.Cos(a),0,Mathf.Sin(a))*Radius;
   if(Scenario=="headon")start=i==0?new Vector3(-4,0,0):new Vector3(4,0,.4f);
   if(Scenario=="crossing")start=i==0?new Vector3(-4,0,0):new Vector3(0,0,-4);
   GameObject go=Instantiate(Template,start,Quaternion.LookRotation(-start),transform);go.name="Character_"+i;if(runtimeSearch)go.GetComponentInChildren<MotionMatchingController>(true).Search=runtimeSearch;controllers[i]=go.GetComponentInChildren<CrowdCharacterController>(true);var mesh=go.GetComponentInChildren<MotionMatchingSkinnedMeshRenderer>(true);actors[i]=mesh.gameObject.AddComponent<SprintActor>();actors[i].OwnStatus=(i%3)*.5f;actors[i].Mode=Mode;go.SetActive(true);controllers[i].MaxSpeed=1;goals[i]=-start;previous[i]=start;
   actors[i].LowerBodyPolicy=LowerBodyPolicy;
   foreach(var trail in go.GetComponentsInChildren<TrailRenderer>(true)){trail.emitting=false;trail.Clear();trail.enabled=false;}
  }
  if(CaptureRun){Directory.CreateDirectory(CaptureRoot);File.WriteAllText(Path.Combine(CaptureRoot,"telemetry.csv"),"time,mode,id,x,z,status,observed,belief,response,lowering,arm_deg,foot_error,pose_updates,arrivals,frame,dt,real_dt,target_id,belief_target_id,belief_resets,risk,input_x,input_z,response_pose,spatial_policy,held_side,predicted_gap,safe_candidates,side_flips,rapid_side_flips,safety_overrides,min_frame_gap,guard_frames,guard_residual\n");}
  if(CaptureRun)File.WriteAllText(Path.Combine(CaptureRoot,"runtime-config.json"),JsonUtility.ToJson(new RuntimeSettings{ownedSearch=runtimeSearch!=null,spatial=SpatialPolicy,lowerBody=LowerBodyPolicy},true));
  if(CaptureRun&&CaptureVideo){Directory.CreateDirectory(Path.Combine(CaptureRoot,"clip-wide"));Directory.CreateDirectory(Path.Combine(CaptureRoot,"clip-close"));}
  if(CaptureRun&&KneeDiagnostics){kneeWriter=new StreamWriter(Path.Combine(CaptureRoot,"knees.csv"));kneeWriter.WriteLine("frame,time,dt,id,status,lower_policy,pose_updates,raw_lx,raw_ly,raw_lz,out_lx,out_ly,out_lz,raw_rx,raw_ry,raw_rz,out_rx,out_ry,out_rz,foot_error");}
  if(CaptureRun&&(CaptureVideo||KneeDiagnostics))gameObject.AddComponent<SprintCaptureLate>().Director=this;
 }
 void Update(){if(controllers==null||Finished)return;elapsed+=Time.deltaTime;frame++;double now=Time.realtimeSinceStartupAsDouble;realFrameDelta=(float)(now-lastRealtime);lastRealtime=now;
  // Snapshot first; all social decisions use the same previous-render observations.
  for(int i=0;i<Count;i++){positions[i]=controllers[i].transform.position;velocities[i]=(positions[i]-previous[i])/Mathf.Max(Time.deltaTime,.001f);previous[i]=positions[i];observed[i]=actors[i].ObservedExpansion;}
  for(int i=0;i<Count;i++)for(int j=i+1;j<Count;j++)minimumFrameGap=Mathf.Min(minimumFrameGap,Vector3.Distance(positions[i],positions[j]));
  for(int i=0;i<Count;i++){
   Vector3 desired=goals[i]-positions[i];desired.y=0;if(desired.magnitude<.65f){arrivals[i]++;goals[i]=-goals[i];desired=goals[i]-positions[i];if(SpatialPolicy>=2){heldSides[i]=0;sideRelease[i]=0;lastSideChange[i]=-100;}}
   Vector3 forward=desired.normalized;float best=0;int partner=-1;Vector3 steer=Vector3.zero;
   for(int j=0;j<Count;j++){if(i==j)continue;Vector3 rel=positions[j]-positions[i];rel.y=0;float distance=rel.magnitude;if(distance>3||distance<.001f)continue;
    Vector3 dv=velocities[j]-velocities[i];dv.y=0;float tau=Mathf.Clamp(-Vector3.Dot(rel,dv)/Mathf.Max(.01f,dv.sqrMagnitude),0,1.8f);float miss=(rel+dv*tau).magnitude;
    float threat=Mathf.Clamp01((1.3f-miss)/1.3f)*Mathf.Clamp01((3-distance)/2.5f);
    if(threat>best){best=threat;partner=j;}
    // Geometric support common to all modes; EMM still generates final movement.
    if(distance<1.5f)steer-=rel.normalized*Mathf.Clamp01((1.5f-distance)/.8f)*.55f;
   }
   if(partner>=0&&actors[partner].PoseUpdates==0)partner=-1;
   float measurement=partner>=0?Mathf.Clamp01((observed[partner]-.05f)/.7f):.5f;
   observations[i].Update(partner,measurement,Time.deltaTime);belief[i]=observations[i].Value;partners[i]=partner;risks[i]=best;
   if(partner>=0)actors[i].LookTarget=positions[partner]+Vector3.up*1.4f;
   float target=Mode==2?best:0;response[i]=Mathf.Lerp(response[i],target,1-Mathf.Exp(-Time.deltaTime/.25f));actors[i].Response=EnableResponsePose?response[i]:0;actors[i].HasTarget=EnableResponsePose&&partner>=0;actors[i].Mode=Mode;
   float cooperation=Mode==2?response[i]*Mathf.Clamp01(.45f+.35f*(belief[i]-actors[i].OwnStatus)):0;
   Vector3 velocity=(forward+steer).normalized*(1-.45f*cooperation);
   if(SpatialPolicy>=1){
    var plan=SprintSpacePlanner.Solve(i,forward,inputs[i],heldSides[i],positions,velocities,SpatialPolicy>=2,SpatialPolicy==3?.15f:0);
    velocity=plan.Input;risks[i]=plan.Risk;predictedGaps[i]=plan.PredictedGap;safeCandidates[i]=plan.SafeCandidates;
    if(plan.SafetyOverride)safetyOverrides[i]++;
    if(plan.Risk>.05f){sideRelease[i]=.5f;if(plan.Side!=0){
     if(heldSides[i]!=plan.Side){if(heldSides[i]!=0){sideFlips[i]++;if(elapsed-lastSideChange[i]<.6f)rapidSideFlips[i]++;}lastSideChange[i]=elapsed;}
     heldSides[i]=plan.Side;
    }}
    else {sideRelease[i]-=Time.deltaTime;if(sideRelease[i]<=0){heldSides[i]=0;lastSideChange[i]=-100;}}
   }
   if(SpatialPolicy==4){Vector3 guarded=SprintSpacePlanner.Guard(i,velocity,positions,velocities,out guardResidual[i]);if((guarded-velocity).sqrMagnitude>1e-6f)guardFrames[i]++;velocity=guarded;}
   inputs[i]=velocity;controllers[i].SetMovementDirection(new float2(velocity.x,velocity.z));
  }
  if(CaptureRun&&(frame==1||elapsed-lastLog>=.25f||elapsed>=Duration)){lastLog=elapsed;var b=new StringBuilder();for(int i=0;i<Count;i++){
   object[] values={elapsed,Mode,i,positions[i].x,positions[i].z,actors[i].OwnStatus,observed[i],belief[i],response[i],actors[i].AppliedLowering,actors[i].AppliedArmAngle,actors[i].FootError,actors[i].PoseUpdates,arrivals[i],frame,Time.deltaTime,realFrameDelta,partners[i],observations[i].TargetId,observations[i].Resets,risks[i],inputs[i].x,inputs[i].z,EnableResponsePose?1:0,SpatialPolicy,heldSides[i],predictedGaps[i],safeCandidates[i],sideFlips[i],rapidSideFlips[i],safetyOverrides[i],minimumFrameGap,guardFrames[i],guardResidual[i]};
   for(int k=0;k<values.Length;k++){if(k>0)b.Append(',');b.Append(System.Convert.ToString(values[k],CultureInfo.InvariantCulture));}b.AppendLine();
  }File.AppendAllText(Path.Combine(CaptureRoot,"telemetry.csv"),b.ToString());}
  if(CaptureRun&&shot<3&&elapsed>new float[]{5,12,25}[shot]){CaptureViews(shot);shot++;}
  if(CaptureRun&&elapsed>=Duration){Finished=true;File.WriteAllText(Path.Combine(CaptureRoot,"finished.txt"),"Completed "+elapsed+" seconds; not perceptual validation.");}
 }
 void OnDestroy(){if(kneeWriter!=null)kneeWriter.Dispose();if(runtimeSearch)Destroy(runtimeSearch);if(clipTarget){clipTarget.Release();Destroy(clipTarget);}if(clipImage)Destroy(clipImage);if(CaptureRun){Time.captureDeltaTime=oldCaptureDeltaTime;Time.fixedDeltaTime=oldFixedDeltaTime;}}
 public void CaptureKneeFrame(){
  if(kneeWriter==null||frame==lastKneeFrame)return;lastKneeFrame=frame;
  for(int i=0;i<Count;i++){var a=actors[i];if(a.PoseUpdates==0)continue;
   object[] values={frame,elapsed,Time.deltaTime,i,a.OwnStatus,LowerBodyPolicy,a.PoseUpdates,a.RawLeftKnee.x,a.RawLeftKnee.y,a.RawLeftKnee.z,a.FinalLeftKnee.x,a.FinalLeftKnee.y,a.FinalLeftKnee.z,a.RawRightKnee.x,a.RawRightKnee.y,a.RawRightKnee.z,a.FinalRightKnee.x,a.FinalRightKnee.y,a.FinalRightKnee.z,a.FootError};
   for(int k=0;k<values.Length;k++){if(k>0)kneeWriter.Write(',');kneeWriter.Write(System.Convert.ToString(values[k],CultureInfo.InvariantCulture));}kneeWriter.WriteLine();
  }
  if(frame%60==0||Finished)kneeWriter.Flush();
 }
 public void CaptureClipFrame(){
  if(!CaptureRun||!CaptureVideo||frame<=0||frame%4!=0||!Camera.main)return;
  if(!clipTarget){clipTarget=new RenderTexture(960,540,24);clipImage=new Texture2D(960,540,TextureFormat.RGB24,false);}
  var camera=Camera.main;Vector3 p=camera.transform.position;Quaternion r=camera.transform.rotation;var oldTarget=camera.targetTexture;var oldActive=RenderTexture.active;
  try{camera.targetTexture=clipTarget;for(int view=0;view<2;view++){
   SetCamera(view==1,Mathf.Clamp(ClipActor,0,Count-1));camera.Render();RenderTexture.active=clipTarget;clipImage.ReadPixels(new Rect(0,0,960,540),0,0);clipImage.Apply();
   string directory=view==0?"clip-wide":"clip-close";
   File.WriteAllBytes(Path.Combine(CaptureRoot,directory,((frame/4)-1).ToString("D5")+".jpg"),clipImage.EncodeToJPG(85));
  }}finally{camera.targetTexture=oldTarget;RenderTexture.active=oldActive;camera.transform.SetPositionAndRotation(p,r);}
 }
 void CaptureViews(int index){
  var camera=Camera.main;if(!camera)return;Vector3 p=camera.transform.position;Quaternion r=camera.transform.rotation;
  var oldTarget=camera.targetTexture;var oldActive=RenderTexture.active;
  var rt=new RenderTexture(CaptureWidth,CaptureHeight,24);var image=new Texture2D(CaptureWidth,CaptureHeight,TextureFormat.RGB24,false);
  try{camera.targetTexture=rt;for(int view=0;view<2;view++){
   bool close=view==1;SetCamera(close,0);camera.Render();RenderTexture.active=rt;image.ReadPixels(new Rect(0,0,CaptureWidth,CaptureHeight),0,0);image.Apply();
   File.WriteAllBytes(Path.Combine(CaptureRoot,$"frame-{index}-{(close?"close":"wide")}.png"),image.EncodeToPNG());
  }}finally{camera.targetTexture=oldTarget;RenderTexture.active=oldActive;camera.transform.SetPositionAndRotation(p,r);rt.Release();Destroy(rt);Destroy(image);}
 }
 void SetCamera(bool close,int actor){if(!Camera.main||controllers==null)return;Vector3 target=close?controllers[actor].transform.position+Vector3.up*.9f:Vector3.zero;Camera.main.transform.position=close?target+new Vector3(2,1.1f,-3):new Vector3(0,9,-11);Camera.main.transform.LookAt(target);}
 int focusActor; bool closeView;
 void LateUpdate(){SetCamera(closeView,focusActor);}
 void OnGUI(){
  GUILayout.BeginArea(new Rect(15,15,390,200),GUI.skin.box);
  GUILayout.Label("Expression / space pilot — "+Count+" actors");
  GUILayout.Label("EMM locomotion + original experimental layers");
  GUI.enabled=!CaptureRun;Mode=GUILayout.SelectionGrid(Mode,new[]{"Baseline","Expression","Response"},3);
  SpatialPolicy=GUILayout.SelectionGrid(SpatialPolicy,new[]{"Legacy","Soft side","Committed","Reserved","Guarded"},3);GUI.enabled=true;
  GUILayout.BeginHorizontal();closeView=GUILayout.Toggle(closeView,"Close view");if(GUILayout.Button("Next actor"))focusActor=(focusActor+1)%Count;GUILayout.Label("Actor "+focusActor);GUILayout.EndHorizontal();
  GUILayout.Label(RunLabel+" / "+Scenario+" / "+elapsed.ToString("F1")+"s");
  GUILayout.Label("Hidden status is not a validated perceptual label.");GUILayout.EndArea();
 }
}
