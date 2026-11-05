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
 public bool CaptureVideo; public int ClipActor=9,ClipStride=4;RenderTexture clipTarget;Texture2D clipImage;
 public int LowerBodyPolicy=2;public bool KneeDiagnostics;
 public bool HeadStability;public bool RouteRecovery;public bool StatusYield;public bool LateralSteps;SprintSideStep.State[] sideSteps;StreamWriter motionWriter;int lastMotionFrame=-1;
 public bool SinglePass=true;
 GameObject[] actorRoots;bool[] active;int[] journeyPhase;Vector3[] destinations;float[] arrivedAt,departedAt;
 public string StatusPattern="cycle";public float FixedExpressionStatus=-1;
 SprintSocialSpace.Cue[] pairCues;SprintSocialSpace.Preference[] socialPreferences;
 SprintSocialSpace.Preference[] focusPreferences;float[] socialProgress,crowdExposure,crowdAversion;
 struct PoseSnapshot {public float Status,Lowering,Arm,FootError;public int Updates;}
 PoseSnapshot[] poseSnapshots;
 TextMesh[] actorLabels,goalLabels;TextMesh journeyLabel;
 StreamWriter kneeWriter;int lastKneeFrame=-1;
 public int SpatialPolicy; // 0: legacy, 1: soft side, 2: committed, 3: reserved clearance.
 public bool UseOwnedSearch=true; MotionMatchingSearch runtimeSearch;
 int[] heldSides,safeCandidates;float[] sideRelease,predictedGaps;
 int[] sideFlips,rapidSideFlips,safetyOverrides;float[] lastSideChange;float minimumFrameGap=100;
 int[] passageReleases;float[] passageExposure;float[] journeyPath,journeyDirect,primaryPath,discretionaryWeight,detourExtra;
 int[] guardFrames;float[] guardResidual;
 SprintObservation[] observations; int frame; float oldCaptureDeltaTime,oldFixedDeltaTime;
 Vector3[] inputs; int[] partners; float[] risks; double lastRealtime; float realFrameDelta;
 CrowdCharacterController[] controllers; SprintActor[] actors; Vector3[] goals,previous,positions,velocities;float[] observed,belief,response; int[] encounters,arrivals;
 float elapsed,lastLog;int shot;public bool Finished;
 [System.Serializable] class RuntimeSettings {public string build="social-space-v23";public bool ownedSearch;public int spatial,lowerBody,clipStride,clipActor;public string statusPattern,cueCalibration;public float fixedExpression;public bool singlePass,lateralSteps,statusYield,routeRecovery,headStability;public string preferenceModel;}
 void Start(){
  Application.runInBackground=true;lastRealtime=Time.realtimeSinceStartupAsDouble;
  oldCaptureDeltaTime=Time.captureDeltaTime;oldFixedDeltaTime=Time.fixedDeltaTime;
  if(CaptureRun&&CaptureFps>0){Time.captureDeltaTime=1f/CaptureFps;Time.fixedDeltaTime=1f/CaptureFps;}
  if(Scenario=="headon"||Scenario=="crossing")Count=2;
  if(ObstacleManager.Instance==null)new GameObject("EMMObstacleManager").AddComponent<ObstacleManager>();
  UnityEngine.Random.InitState(Seed);controllers=new CrowdCharacterController[Count];actors=new SprintActor[Count];goals=new Vector3[Count];previous=new Vector3[Count];positions=new Vector3[Count];velocities=new Vector3[Count];observed=new float[Count];belief=new float[Count];response=new float[Count];encounters=new int[Count];arrivals=new int[Count];observations=new SprintObservation[Count];inputs=new Vector3[Count];partners=new int[Count];risks=new float[Count];
  heldSides=new int[Count];safeCandidates=new int[Count];sideRelease=new float[Count];predictedGaps=new float[Count];
  sideFlips=new int[Count];rapidSideFlips=new int[Count];safetyOverrides=new int[Count];lastSideChange=new float[Count];for(int i=0;i<Count;i++)lastSideChange[i]=-100;
  journeyPath=new float[Count];journeyDirect=new float[Count];primaryPath=new float[Count];discretionaryWeight=new float[Count];detourExtra=new float[Count];for(int i=0;i<Count;i++)discretionaryWeight[i]=1;
  passageReleases=new int[Count];passageExposure=new float[Count];guardFrames=new int[Count];guardResidual=new float[Count];
  pairCues=new SprintSocialSpace.Cue[Count*Count];socialPreferences=new SprintSocialSpace.Preference[Count];focusPreferences=new SprintSocialSpace.Preference[Count];socialProgress=new float[Count];crowdExposure=new float[Count];crowdAversion=new float[Count];
  sideSteps=new SprintSideStep.State[Count];
  poseSnapshots=new PoseSnapshot[Count];
  actorRoots=new GameObject[Count];active=new bool[Count];journeyPhase=new int[Count];destinations=new Vector3[Count];arrivedAt=new float[Count];departedAt=new float[Count];
  for(int i=0;i<Count;i++){active[i]=true;arrivedAt[i]=departedAt[i]=-1;}
  if(UseOwnedSearch){
   var original=Template.GetComponentInChildren<MotionMatchingController>(true).Search;
   if(!(original is EnvironmentMotionMatchingSearch))throw new System.InvalidOperationException("Owned search expects original EMM environment search settings");
   runtimeSearch=ScriptableObject.CreateInstance<SprintOwnedEnvironmentSearch>();JsonUtility.FromJsonOverwrite(JsonUtility.ToJson(original),runtimeSearch);
  }
  for(int i=0;i<Count;i++){float a=2*Mathf.PI*i/Count;Vector3 start=new Vector3(Mathf.Cos(a),0,Mathf.Sin(a))*Radius;
   if(Scenario=="headon")start=i==0?new Vector3(-4,0,0):new Vector3(4,0,.4f);
   if(Scenario=="crossing")start=i==0?new Vector3(-4,0,0):new Vector3(0,0,-4);
   GameObject go=Instantiate(Template,start,Quaternion.LookRotation(-start),transform);go.name="Character_"+i;if(runtimeSearch)go.GetComponentInChildren<MotionMatchingController>(true).Search=runtimeSearch;controllers[i]=go.GetComponentInChildren<CrowdCharacterController>(true);var mesh=go.GetComponentInChildren<MotionMatchingSkinnedMeshRenderer>(true);actors[i]=mesh.gameObject.AddComponent<SprintActor>();actors[i].OwnStatus=(i%3)*.5f;actors[i].Mode=Mode;go.SetActive(true);controllers[i].MaxSpeed=1;goals[i]=-start;previous[i]=start;
   actorRoots[i]=go;destinations[i]=goals[i];journeyDirect[i]=Vector3.Distance(start,goals[i]);
   actors[i].LowerBodyPolicy=LowerBodyPolicy;actors[i].HeadStability=HeadStability;
   if(StatusPattern=="low-high")actors[i].OwnStatus=i%2;
   if(StatusPattern=="high-low")actors[i].OwnStatus=1-i%2;
   actors[i].ExpressionStatusOverride=FixedExpressionStatus;poseSnapshots[i].Status=actors[i].OwnStatus;
   foreach(var trail in go.GetComponentsInChildren<TrailRenderer>(true)){trail.emitting=false;trail.Clear();trail.enabled=false;}
  }
  if(SinglePass)CreateJourneyLabels();
  if(CaptureRun){Directory.CreateDirectory(CaptureRoot);File.WriteAllText(Path.Combine(CaptureRoot,"telemetry.csv"),"time,mode,id,x,z,status,observed,belief,response,lowering,arm_deg,foot_error,pose_updates,arrivals,frame,dt,real_dt,target_id,belief_target_id,belief_resets,risk,input_x,input_z,response_pose,spatial_policy,held_side,predicted_gap,safe_candidates,side_flips,rapid_side_flips,safety_overrides,min_frame_gap,guard_frames,guard_residual,social_estimate,social_weight,social_gap,social_cooperation,social_progress_weight,crowd_aversion,crowd_exposure,social_raw_estimate,journey_phase,arrival_time,departure_time,goal_x,goal_z,destination_x,destination_z,passage_exposure,passage_releases,focus_deference,detour_extra,discretion_weight,journey_path,first_trip_path\n");}
  if(CaptureRun)File.WriteAllText(Path.Combine(CaptureRoot,"runtime-config.json"),JsonUtility.ToJson(new RuntimeSettings{ownedSearch=runtimeSearch!=null,spatial=SpatialPolicy,lowerBody=LowerBodyPolicy,clipStride=ClipStride,clipActor=Mathf.Clamp(ClipActor,0,Count-1),statusPattern=StatusPattern,fixedExpression=FixedExpressionStatus,cueCalibration=SprintSocialSpace.Calibration,singlePass=SinglePass,lateralSteps=LateralSteps,statusYield=StatusYield,routeRecovery=RouteRecovery,headStability=HeadStability,preferenceModel=SpatialPolicy>=8?(SpatialPolicy==10?"status-gap-budget-v1":SpatialPolicy==9?"status-gap-passage-v1":"status-gap-quadratic-v1"):"relative-linear-v1"},true));
  if(CaptureRun&&CaptureVideo){Directory.CreateDirectory(Path.Combine(CaptureRoot,"clip-wide"));Directory.CreateDirectory(Path.Combine(CaptureRoot,"clip-close"));}
  if(CaptureRun&&KneeDiagnostics){kneeWriter=new StreamWriter(Path.Combine(CaptureRoot,"knees.csv"));kneeWriter.WriteLine("frame,time,dt,id,status,lower_policy,pose_updates,raw_lx,raw_ly,raw_lz,out_lx,out_ly,out_lz,raw_rx,raw_ry,raw_rz,out_rx,out_ry,out_rz,foot_error");}
  if(CaptureRun&&KneeDiagnostics){motionWriter=new StreamWriter(Path.Combine(CaptureRoot,"motion.csv"));motionWriter.WriteLine("frame,time,dt,id,journey_phase,x,z,input_x,input_z,controller_yaw,sim_yaw,facing_hold,clip_index,clip_name,source_frame,arrivals,head_x,head_y,head_z,head_w,neck_x,neck_y,neck_z,neck_w,headchest_x,headchest_y,headchest_z,headchest_w,overlay_head_angle,headout_x,headout_y,headout_z,headout_w");}
  if(CaptureRun&&KneeDiagnostics)ExportSourceMotion();
  if(CaptureRun&&(CaptureVideo||KneeDiagnostics))gameObject.AddComponent<SprintCaptureLate>().Director=this;
 }
 void Update(){if(controllers==null||Finished)return;elapsed+=Time.deltaTime;frame++;double now=Time.realtimeSinceStartupAsDouble;realFrameDelta=(float)(now-lastRealtime);lastRealtime=now;
  // Snapshot first; all social decisions use the same previous-render observations.
  for(int i=0;i<Count;i++){if(!active[i])continue;positions[i]=controllers[i].transform.position;velocities[i]=(positions[i]-previous[i])/Mathf.Max(Time.deltaTime,.001f);journeyPath[i]+=Vector3.Distance(positions[i],previous[i]);previous[i]=positions[i];observed[i]=actors[i].ObservedExpansion;poseSnapshots[i]=new PoseSnapshot{Status=actors[i].OwnStatus,Lowering=actors[i].AppliedLowering,Arm=actors[i].AppliedArmAngle,FootError=actors[i].FootError,Updates=actors[i].PoseUpdates};}
  if(SinglePass)UpdateJourneys();
  for(int i=0;i<Count;i++)for(int j=i+1;j<Count;j++)if(active[i]&&active[j])minimumFrameGap=Mathf.Min(minimumFrameGap,Vector3.Distance(positions[i],positions[j]));
  for(int i=0;i<Count;i++){
   if(!active[i])continue;
   Vector3 desired=goals[i]-positions[i];desired.y=0;
   if(!SinglePass&&desired.magnitude<.65f){arrivals[i]++;goals[i]=-goals[i];desired=goals[i]-positions[i];if(SpatialPolicy==10){journeyPath[i]=0;journeyDirect[i]=desired.magnitude;}if(SpatialPolicy>=2){heldSides[i]=0;sideRelease[i]=0;lastSideChange[i]=-100;}}
   Vector3 forward=desired.normalized;float best=0,nearest=10;int partner=-1;Vector3 steer=Vector3.zero;
   for(int j=0;j<Count;j++){if(i==j||!active[j])continue;Vector3 rel=positions[j]-positions[i];rel.y=0;float distance=rel.magnitude;if(distance>3||distance<.001f)continue;nearest=Mathf.Min(nearest,distance);
    Vector3 dv=velocities[j]-velocities[i];dv.y=0;float tau=Mathf.Clamp(-Vector3.Dot(rel,dv)/Mathf.Max(.01f,dv.sqrMagnitude),0,1.8f);float miss=(rel+dv*tau).magnitude;
    float threat=Mathf.Clamp01((1.3f-miss)/1.3f)*Mathf.Clamp01((3-distance)/2.5f);
    if(threat>best){best=threat;partner=j;}
    // Geometric support common to all modes; EMM still generates final movement.
    if(distance<1.5f)steer-=rel.normalized*Mathf.Clamp01((1.5f-distance)/.8f)*.55f;
   }
   if(partner>=0&&actors[partner].PoseUpdates==0)partner=-1;
   float measurement=partner>=0?Mathf.Clamp01((observed[partner]-.05f)/.7f):.5f;
   observations[i].Update(partner,measurement,Time.deltaTime);belief[i]=observations[i].Value;partners[i]=partner;risks[i]=best;
   float target=Mode==2?best:0;response[i]=Mathf.Lerp(response[i],target,1-Mathf.Exp(-Time.deltaTime/.25f));actors[i].Response=EnableResponsePose?response[i]:0;actors[i].Mode=Mode;
   float cooperation=Mode==2?response[i]*Mathf.Clamp01(.45f+.35f*(belief[i]-actors[i].OwnStatus)):0;
   Vector3 velocity=(forward+steer).normalized*(1-.45f*cooperation);
   if(SpatialPolicy>=1){
    focusPreferences[i]=new SprintSocialSpace.Preference{Distance=1.1f,Cooperation=.5f,Estimate=.5f};socialProgress[i]=.65f;
    if(SpatialPolicy>=5){
     discretionaryWeight[i]=SpatialPolicy==10?SprintSocialSpace.DetourWeight(journeyPath[i],desired.magnitude,journeyDirect[i]):1;
     detourExtra[i]=Mathf.Max(0,journeyPath[i]+desired.magnitude-journeyDirect[i]);
     socialProgress[i]=Mathf.Lerp(SprintSocialSpace.ProgressWeight(actors[i].OwnStatus),.85f,1-discretionaryWeight[i]);
     for(int j=0;j<Count;j++){
      bool visible=j!=i&&active[j]&&actors[j].PoseUpdates>0&&(positions[j]-positions[i]).sqrMagnitude<=9;
      int key=i*Count+j;pairCues[key].Update(visible,observed[j],Time.deltaTime);
      socialPreferences[j]=SpatialPolicy>=8?SprintSocialSpace.ForStatusGap(actors[i].OwnStatus,pairCues[key].Estimate,pairCues[key].Weight):SprintSocialSpace.ForEstimate(actors[i].OwnStatus,pairCues[key].Estimate,pairCues[key].Weight);
     }
     if(SpatialPolicy==10)for(int j=0;j<Count;j++){socialPreferences[j].Distance=1.1f+(socialPreferences[j].Distance-1.1f)*discretionaryWeight[i];socialPreferences[j].Deference*=discretionaryWeight[i];}
     focusPreferences[i]=partner>=0?socialPreferences[partner]:(SpatialPolicy>=8?SprintSocialSpace.ForStatusGap(actors[i].OwnStatus,.5f,0):SprintSocialSpace.ForEstimate(actors[i].OwnStatus,.5f,0));
    }
    var plan=SprintSpacePlanner.Solve(i,forward,inputs[i],heldSides[i],positions,velocities,SpatialPolicy>=2,SpatialPolicy==3?.15f:0,SpatialPolicy>=5?socialPreferences:null,socialProgress[i],SpatialPolicy>=6?SprintSocialSpace.CrowdAversion(actors[i].OwnStatus)*discretionaryWeight[i]:0,SpatialPolicy>=7,Time.deltaTime,SinglePass?active:null,SpatialPolicy>=9,discretionaryWeight[i],StatusYield?1+1.5f*actors[i].OwnStatus*actors[i].OwnStatus:1,StatusYield,RouteRecovery);
    passageExposure[i]=SpatialPolicy>=9?SprintSpacePlanner.PassageExposure(i,plan.Input,positions,velocities,socialPreferences,SinglePass?active:null,StatusYield):0;
    if(plan.PassageRelease)passageReleases[i]++;
    crowdAversion[i]=SpatialPolicy>=6?SprintSocialSpace.CrowdAversion(actors[i].OwnStatus)*discretionaryWeight[i]:0;crowdExposure[i]=SprintSpacePlanner.CrowdExposure(i,plan.Input,positions,velocities,SinglePass?active:null);
    velocity=plan.Input;risks[i]=plan.Risk;predictedGaps[i]=plan.PredictedGap;safeCandidates[i]=plan.SafeCandidates;
    if(plan.SafetyOverride)safetyOverrides[i]++;
    bool crowdBypass=SpatialPolicy>=7&&crowdAversion[i]>0&&SprintSpacePlanner.CrowdExposure(i,forward,positions,velocities,SinglePass?active:null)>.06f;
    if(plan.Risk>.05f||crowdBypass){sideRelease[i]=crowdBypass?.8f:.5f;if(plan.Side!=0){
     if(heldSides[i]!=plan.Side){if(heldSides[i]!=0){sideFlips[i]++;if(elapsed-lastSideChange[i]<.6f)rapidSideFlips[i]++;}lastSideChange[i]=elapsed;}
     heldSides[i]=plan.Side;
    }}
    else {sideRelease[i]-=Time.deltaTime;if(sideRelease[i]<=0){heldSides[i]=0;lastSideChange[i]=-100;}}
   }
   if(SpatialPolicy==4){Vector3 guarded=SprintSpacePlanner.Guard(i,velocity,positions,velocities,out guardResidual[i],SinglePass?active:null);if((guarded-velocity).sqrMagnitude>1e-6f)guardFrames[i]++;velocity=guarded;}
   if(LateralSteps&&elapsed>1){
    float goalAngle=Vector3.Angle(forward,velocity),facingAngle=Vector3.Angle(controllers[i].transform.forward,velocity);
    if(sideSteps[i].Update(goalAngle,facingAngle,velocity.magnitude,nearest<2.2f,Time.deltaTime))controllers[i].SwapFixOrientation();
   }
   if(!LateralSteps&&sideSteps[i].Locked&&sideSteps[i].Release())controllers[i].SwapFixOrientation();
   inputs[i]=velocity;controllers[i].SetMovementDirection(new float2(velocity.x,velocity.z));

  }
  if(CaptureRun&&(frame==1||elapsed-lastLog>=.25f||elapsed>=Duration)){lastLog=elapsed;var b=new StringBuilder();for(int i=0;i<Count;i++){
   var preference=focusPreferences[i];var pose=poseSnapshots[i];object[] values={elapsed,Mode,i,positions[i].x,positions[i].z,pose.Status,observed[i],belief[i],response[i],pose.Lowering,pose.Arm,pose.FootError,pose.Updates,arrivals[i],frame,Time.deltaTime,realFrameDelta,partners[i],observations[i].TargetId,observations[i].Resets,risks[i],inputs[i].x,inputs[i].z,EnableResponsePose?1:0,SpatialPolicy,heldSides[i],predictedGaps[i],safeCandidates[i],sideFlips[i],rapidSideFlips[i],safetyOverrides[i],minimumFrameGap,guardFrames[i],guardResidual[i],preference.Estimate,preference.ObservationWeight,preference.Distance,preference.Cooperation,socialProgress[i],crowdAversion[i],crowdExposure[i],preference.RawEstimate,journeyPhase[i],arrivedAt[i],departedAt[i],goals[i].x,goals[i].z,destinations[i].x,destinations[i].z,passageExposure[i],passageReleases[i],preference.Deference,detourExtra[i],discretionaryWeight[i],journeyPath[i],primaryPath[i]};
   for(int k=0;k<values.Length;k++){if(k>0)b.Append(',');b.Append(System.Convert.ToString(values[k],CultureInfo.InvariantCulture));}b.AppendLine();
  }File.AppendAllText(Path.Combine(CaptureRoot,"telemetry.csv"),b.ToString());}
  if(CaptureRun&&shot<3&&elapsed>new float[]{5,12,25}[shot]){CaptureViews(shot);shot++;}
  if(CaptureRun&&elapsed>=Duration){Finished=true;File.WriteAllText(Path.Combine(CaptureRoot,"finished.txt"),"Completed "+elapsed+" seconds; not perceptual validation.");}
 }
 void UpdateJourneys(){
  // Update all lifecycle states before any actor plans against the shared snapshot.
  for(int i=0;i<Count;i++){
   if(!active[i]||(goals[i]-positions[i]).sqrMagnitude>=.65f*.65f)continue;
   if(journeyPhase[i]==0){
    if(sideSteps[i].Release())controllers[i].SwapFixOrientation();
    primaryPath[i]=journeyPath[i];arrivals[i]=1;journeyPhase[i]=1;arrivedAt[i]=elapsed;goals[i]=destinations[i].normalized*(Radius+3);journeyPath[i]=0;journeyDirect[i]=Vector3.Distance(positions[i],goals[i]);
    heldSides[i]=0;sideRelease[i]=0;lastSideChange[i]=-100;
   }else{
    journeyPhase[i]=2;departedAt[i]=elapsed;active[i]=false;inputs[i]=velocities[i]=Vector3.zero;
    observations[i].Update(-1,.5f,Time.deltaTime);partners[i]=-1;belief[i]=.5f;response[i]=0;
    controllers[i].SetMovementDirection(float2.zero);actorRoots[i].SetActive(false);Destroy(actorRoots[i]);
   }
  }
 }
 TextMesh Label(string name,Transform parent,Vector3 position,float size,Color color){
  var go=new GameObject(name);go.transform.SetParent(parent);go.transform.position=position;
  var label=go.AddComponent<TextMesh>();label.fontSize=48;label.characterSize=size;label.anchor=TextAnchor.MiddleCenter;label.color=color;
  return label;
 }
 void CreateJourneyLabels(){
  actorLabels=new TextMesh[Count];goalLabels=new TextMesh[Count];
  for(int i=0;i<Count;i++){
   Color color=actors[i].OwnStatus<.25f?new Color(.15f,.9f,.55f):actors[i].OwnStatus>.75f?new Color(1,.75f,.15f):new Color(.3f,.7f,1);
   string status=actors[i].OwnStatus<.25f?"L":actors[i].OwnStatus>.75f?"H":"M";
   actorLabels[i]=Label("ViewerStatusLabel",actorRoots[i].transform,controllers[i].transform.position+Vector3.up*2.1f,.045f,color);
   actorLabels[i].text=i+" "+status;
   goalLabels[i]=Label("GoalLabel_"+i,transform,destinations[i]+Vector3.up*.08f,.035f,color);
   goalLabels[i].text="Goal "+i;
  }
  journeyLabel=Label("JourneySummary",transform,new Vector3(0,2.8f,5.7f),.075f,Color.white);
 }
 void UpdateJourneyLabels(){
  if(!SinglePass||actorLabels==null||!Camera.main)return;int reached=0,left=0;
  for(int i=0;i<Count;i++){
   if(arrivals[i]>0)reached++;if(journeyPhase[i]==2)left++;
   if(active[i]){actorLabels[i].transform.position=positions[i]+Vector3.up*2.1f;actorLabels[i].transform.rotation=Camera.main.transform.rotation;}
   goalLabels[i].transform.rotation=Camera.main.transform.rotation;
   goalLabels[i].text=arrivals[i]>0?"Goal "+i+" OK":"Goal "+i;
  }
  int lows=0,mids=0,highs=0;for(int i=0;i<Count;i++){if(poseSnapshots[i].Status<.25f)lows++;else if(poseSnapshots[i].Status>.75f)highs++;else mids++;}
  journeyLabel.text="One way | Arrived "+reached+"/"+Count+" | Exited "+left+"/"+Count+"\nL:"+lows+"  M:"+mids+"  H:"+highs;
  journeyLabel.transform.rotation=Camera.main.transform.rotation;
 }
 void OnDestroy(){if(motionWriter!=null)motionWriter.Dispose();if(kneeWriter!=null)kneeWriter.Dispose();if(runtimeSearch)Destroy(runtimeSearch);if(clipTarget){clipTarget.Release();Destroy(clipTarget);}if(clipImage)Destroy(clipImage);if(CaptureRun){Time.captureDeltaTime=oldCaptureDeltaTime;Time.fixedDeltaTime=oldFixedDeltaTime;}}
 public void CaptureKneeFrame(){
  if(kneeWriter==null||frame==lastKneeFrame)return;lastKneeFrame=frame;
  for(int i=0;i<Count;i++){var a=actors[i];if(!active[i]||a.PoseUpdates==0)continue;
   object[] values={frame,elapsed,Time.deltaTime,i,a.OwnStatus,LowerBodyPolicy,a.PoseUpdates,a.RawLeftKnee.x,a.RawLeftKnee.y,a.RawLeftKnee.z,a.FinalLeftKnee.x,a.FinalLeftKnee.y,a.FinalLeftKnee.z,a.RawRightKnee.x,a.RawRightKnee.y,a.RawRightKnee.z,a.FinalRightKnee.x,a.FinalRightKnee.y,a.FinalRightKnee.z,a.FootError};
   for(int k=0;k<values.Length;k++){if(k>0)kneeWriter.Write(',');kneeWriter.Write(System.Convert.ToString(values[k],CultureInfo.InvariantCulture));}kneeWriter.WriteLine();
  }
  if(frame%60==0||Finished)kneeWriter.Flush();
 }
 public void ExportSourceMotion(){
  var mm=controllers[0].MotionMatching;
  using(var writer=new StreamWriter(Path.Combine(CaptureRoot,"source-motion.csv"))){
   writer.WriteLine("source_frame,clip_index,clip_name,local_x,local_z");
   for(int f=0;f<mm.PoseSet.NumberPoses;f++){
    mm.PoseSet.GetPose(f,out var pose,out int clip);
    float3 v=math.mul(math.inverse(pose.JointLocalRotations[0]),pose.JointLocalVelocities[0]);
    writer.WriteLine(string.Join(",",f,clip,mm.MMData.AnimationDatas[clip].name.Replace(",","_"),v.x.ToString(CultureInfo.InvariantCulture),v.z.ToString(CultureInfo.InvariantCulture)));
   }
  }
 }
 public void CaptureMotionFrame(){
  if(motionWriter==null||frame==lastMotionFrame)return;lastMotionFrame=frame;
  for(int i=0;i<Count;i++){
   if(!active[i]||actors[i].PoseUpdates==0)continue;
   var mm=controllers[i].MotionMatching;mm.PoseSet.GetPose(mm.CurrentFrame,out var pose,out int clip);
   string name=clip>=0&&clip<mm.MMData.AnimationDatas.Count?mm.MMData.AnimationDatas[clip].name.Replace(",","_"):"unknown";
   Vector3 position=mm.transform.position;
   object[] values={frame,elapsed,Time.deltaTime,i,journeyPhase[i],position.x,position.z,inputs[i].x,inputs[i].z,
    Vector3.SignedAngle(Vector3.forward,controllers[i].transform.forward,Vector3.up),Vector3.SignedAngle(Vector3.forward,mm.transform.forward,Vector3.up),sideSteps[i].Locked?1:0,clip,name,mm.CurrentFrame,arrivals[i],actors[i].RawHeadLocal.x,actors[i].RawHeadLocal.y,actors[i].RawHeadLocal.z,actors[i].RawHeadLocal.w,actors[i].RawNeckLocal.x,actors[i].RawNeckLocal.y,actors[i].RawNeckLocal.z,actors[i].RawNeckLocal.w,actors[i].RawHeadChest.x,actors[i].RawHeadChest.y,actors[i].RawHeadChest.z,actors[i].RawHeadChest.w,Quaternion.Angle(actors[i].RawHeadChest,actors[i].FinalHeadChest),actors[i].FinalHeadChest.x,actors[i].FinalHeadChest.y,actors[i].FinalHeadChest.z,actors[i].FinalHeadChest.w};
   for(int k=0;k<values.Length;k++){if(k>0)motionWriter.Write(',');motionWriter.Write(System.Convert.ToString(values[k],CultureInfo.InvariantCulture));}motionWriter.WriteLine();
  }
  if(frame%60==0||Finished)motionWriter.Flush();
 }
 public void CaptureClipFrame(){
  if(!CaptureRun||!CaptureVideo||frame<=0||frame%Mathf.Max(1,ClipStride)!=0||!Camera.main)return;
  if(!clipTarget){clipTarget=new RenderTexture(960,540,24);clipImage=new Texture2D(960,540,TextureFormat.RGB24,false);}
  var camera=Camera.main;Vector3 p=camera.transform.position;Quaternion r=camera.transform.rotation;var oldTarget=camera.targetTexture;var oldActive=RenderTexture.active;
  try{camera.targetTexture=clipTarget;for(int view=0;view<2;view++){
   SetCamera(view==1,Mathf.Clamp(ClipActor,0,Count-1));camera.Render();RenderTexture.active=clipTarget;clipImage.ReadPixels(new Rect(0,0,960,540),0,0);clipImage.Apply();
   string directory=view==0?"clip-wide":"clip-close";
   File.WriteAllBytes(Path.Combine(CaptureRoot,directory,((frame/Mathf.Max(1,ClipStride))-1).ToString("D5")+".jpg"),clipImage.EncodeToJPG(85));
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
 void SetCamera(bool close,int actor){if(!Camera.main||controllers==null)return;Vector3 target=close?(active[actor]?controllers[actor].transform.position:positions[actor])+Vector3.up*.9f:Vector3.zero;Camera.main.transform.position=close?target+new Vector3(2,1.1f,-3):new Vector3(0,9,-11);Camera.main.transform.LookAt(target);UpdateJourneyLabels();}
 int focusActor; bool closeView;
 void LateUpdate(){SetCamera(closeView,focusActor);}
 void OnGUI(){
  GUILayout.BeginArea(new Rect(15,15,390,200),GUI.skin.box);
  GUILayout.Label("Expression / space pilot — "+Count+" actors");
  GUILayout.Label("EMM locomotion + original experimental layers");
  GUI.enabled=!CaptureRun;Mode=GUILayout.SelectionGrid(Mode,new[]{"Baseline","Expression","Response"},3);
  SpatialPolicy=GUILayout.SelectionGrid(SpatialPolicy,new[]{"Legacy","Soft side","Committed","Reserved","Guarded","Social space","Crowd aware","Crowd flow","Status gap","Passage","Route budget"},3);GUI.enabled=true;
  GUILayout.BeginHorizontal();closeView=GUILayout.Toggle(closeView,"Close view");if(GUILayout.Button("Next actor"))focusActor=(focusActor+1)%Count;GUILayout.Label("Actor "+focusActor);GUILayout.EndHorizontal();
  int reached=0,left=0;for(int i=0;i<Count;i++){if(arrivals[i]>0)reached++;if(journeyPhase[i]==2)left++;}
  GUILayout.Label((SinglePass?"One way":"Repeat")+" / arrived "+reached+" / exited "+left+" of "+Count);
  GUILayout.Label(RunLabel+" / "+Scenario+" / "+elapsed.ToString("F1")+"s");
  GUI.enabled=!CaptureRun;RouteRecovery=GUILayout.Toggle(RouteRecovery,"Detour recovery");StatusYield=GUILayout.Toggle(StatusYield,"Status passage priority");LateralSteps=GUILayout.Toggle(LateralSteps,"Short lateral steps");GUI.enabled=true;
  GUILayout.Label("Hidden status is not a validated perceptual label.");GUILayout.EndArea();
 }
}
