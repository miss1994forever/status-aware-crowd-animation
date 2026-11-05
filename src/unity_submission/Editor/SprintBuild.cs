using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;
using System.IO;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

[InitializeOnLoad]
public static class SprintBuild {
 const string ScenePath="Assets/SubmissionSprint/SubmissionDemo.unity";
 const string Root="/Users/haojun/Documents/documents/大四上/动画/期末大作业/outputs/unity-submission";
 static bool refreshedRequest;
 static SprintBuild(){EditorApplication.update+=Tick;}
 public static void Create(){
  var old=EditorSceneManager.OpenScene("Assets/EnvironmentMotionMatching/Scenes/EMM_NoDependencies/10_Crowds_Corridor.unity");
  var source=Object.FindFirstObjectByType<CrowdDemoCorridorController>();if(source==null)throw new System.Exception("No source controller");
  var template=Object.Instantiate(source.Prefab[0]);template.name="OriginalEMMTemplate";template.transform.SetParent(null);template.SetActive(false);
  var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Additive);SceneManager.MoveGameObjectToScene(template,scene);SceneManager.SetActiveScene(scene);EditorSceneManager.CloseScene(old,true);
  var director=new GameObject("AutonomousExpressionAndResponse").AddComponent<SprintDirector>();director.Template=template;
  var plane=GameObject.CreatePrimitive(PrimitiveType.Plane);plane.name="Ground";plane.transform.localScale=Vector3.one*2;
  var light=new GameObject("KeyLight").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1.3f;light.transform.rotation=Quaternion.Euler(45,-30,0);
  var camera=new GameObject("Main Camera").AddComponent<Camera>();camera.tag="MainCamera";camera.transform.position=new Vector3(0,9,-11);camera.transform.LookAt(Vector3.zero);camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.76f,.82f,.87f);camera.fieldOfView=48;
  RenderSettings.ambientLight=new Color(.65f,.65f,.65f);Directory.CreateDirectory("Assets/SubmissionSprint");EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();Directory.CreateDirectory(Root);File.WriteAllText(Path.Combine(Root,"scene-created.txt"),ScenePath);
 }
 [System.Serializable] public class RunCommand {
  public string run="s0-new-run";public int mode=1;public string scenario="crowd";
  public int seed=806,fps=60,count=10;public float duration=35;
  public bool responsePose=false,ownedSearch=true,video=false;public int width=1280,height=720;public int spatial=0;
  public int lowerBody=2,clipStride=4,clipActor=9;public bool kneeDiagnostics=false;
  public string statusPattern="cycle";public float fixedExpression=-1;public bool singlePass=true,lateralSteps=false,statusYield=false,routeRecovery=false;
 }
 [System.Serializable] class SocialFixture {public string test;public float own,estimate,weight,separation,gap,inputX,inputZ;}
 [System.Serializable] class SocialFixtures {public SocialFixture[] fixtures;}
 static SocialFixture[] socialFixtures,gapFixtures;
 static SocialFixture Fixture(string name,float own,float estimate,float weight,float separation,bool statusGap=false){
  var pref=statusGap?SprintSocialSpace.ForStatusGap(own,estimate,weight):SprintSocialSpace.ForEstimate(own,estimate,weight);
  var positions=new[]{Vector3.zero,new Vector3(0,0,separation)};var velocities=new[]{Vector3.forward,Vector3.back};
  var plan=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,positions,velocities,true,0,new[]{pref,pref},SprintSocialSpace.ProgressWeight(own));
  return new SocialFixture{test=name,own=own,estimate=estimate,weight=weight,separation=separation,gap=pref.Distance,inputX=plan.Input.x,inputZ=plan.Input.z};
 }
 static void CheckObservation(){
  var observation=new SprintObservation();observation.Update(3,1,.016f);observation.Update(3,0,.016f);
  if(observation.TargetId!=3||observation.Value<=0||observation.Value>=1)throw new System.Exception("Observation smoothing failed");
  observation.Update(7,0,.016f);
  if(observation.TargetId!=7||observation.Value!=0)throw new System.Exception("Observation leaked across targets");
  observation.Update(-1,1,.016f);
  if(observation.TargetId!=-1||observation.Value!=.5f)throw new System.Exception("Observation release failed");
  if(Mathf.Abs(SprintSpacePlanner.Closest(new Vector3(2,0,0),new Vector3(-2,0,0),0,1.8f))>.0001f)throw new System.Exception("Closest approach missed pass-through");
  var positions=new[]{Vector3.zero,new Vector3(0,0,2)};var velocities=new[]{Vector3.forward,Vector3.back};
  var meeting=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,positions,velocities);
  if((meeting.Input-Vector3.forward).sqrMagnitude<.001f)throw new System.Exception("Head-on conflict did not change input");
  positions[1]=new Vector3(4,0,0);velocities[1]=Vector3.forward;
  var parallel=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,positions,velocities);
  if((parallel.Input-Vector3.forward).sqrMagnitude>.0001f)throw new System.Exception("Unrelated parallel neighbour changed input");
  positions[1]=new Vector3(0,0,2);velocities[1]=Vector3.back;
  var committed=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,-1,positions,velocities,true);
  if(committed.Side>0||committed.SafetyOverride)throw new System.Exception("Safe committed side was discarded");
  positions[1]=new Vector3(0,0,1.2f);float residual;
  Vector3 guarded=SprintSpacePlanner.Guard(0,Vector3.forward,positions,velocities,out residual);
  if(guarded.z>=.5f||guarded.magnitude>1.0001f||residual>.0001f)throw new System.Exception("Near-field guard failed head-on bound");
  var hint=new SprintLegIK.Hint();Vector3 last=Vector3.zero;
  for(int k=0;k<100;k++){
   Vector3 knee=SprintLegIK.Knee(new Vector3(0,.98f,0),Vector3.zero,.5f,.5f,Vector3.up,new Vector3((k%2==0?1:-1)*.00001f,.5f,0),Vector3.zero,Quaternion.identity,Vector3.forward,1f/60,ref hint);
   if(Mathf.Abs(Vector3.Distance(knee,new Vector3(0,.98f,0))-.5f)>.0001f||Mathf.Abs(knee.magnitude-.5f)>.0001f)throw new System.Exception("Stable knee changed segment lengths");
   if(k>0&&Vector3.Distance(knee,last)>.001f)throw new System.Exception("Weak source bend caused knee flip");last=knee;
  }
  socialFixtures=new[]{Fixture("own-low",0,.5f,0,2),Fixture("own-high",1,.5f,0,2),Fixture("cue-low",.5f,0,.5f,2.3f),Fixture("cue-high",.5f,1,.5f,2.3f)};
  if(Mathf.Abs(socialFixtures[0].inputX-socialFixtures[1].inputX)<.01f)throw new System.Exception("Own status did not affect fixed-geometry decision");
  if(Mathf.Abs(socialFixtures[2].inputX-socialFixtures[3].inputX)<.01f)throw new System.Exception("Visible estimate did not affect fixed-geometry decision");
  // Public cluster ahead, no hidden status: low self should select a less dense route.
  var cluster=new[]{Vector3.zero,new Vector3(-.7f,0,3),new Vector3(.7f,0,3),new Vector3(0,0,3.8f)};
  var still=new Vector3[4];
  var direct=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,cluster,still);
  var avoiding=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,cluster,still,true,0,null,.4875f,SprintSocialSpace.CrowdAversion(0));
  if(SprintSpacePlanner.CrowdExposure(0,avoiding.Input,cluster,still)>=SprintSpacePlanner.CrowdExposure(0,direct.Input,cluster,still)-.01f)throw new System.Exception("Low-status cluster preference did not reduce prospective exposure");
  if(SprintSocialSpace.CrowdAversion(.5f)!=0||SprintSocialSpace.CrowdAversion(1)!=0)throw new System.Exception("Crowd preference escaped low-status range");
  var one=new[]{Vector3.zero,Vector3.forward};
  if(SprintSpacePlanner.CrowdExposure(0,Vector3.forward,one,new Vector3[2])!=0)throw new System.Exception("Single neighbour incorrectly treated as crowd");
  var flowing=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.zero,0,cluster,still,true,0,null,.4875f,3,true);
  if(flowing.Input.magnitude<.69f||flowing.PredictedGap<.6f||flowing.Side==0)throw new System.Exception("Open cluster flanks should permit a moving bypass from rest");
  var continuing=SprintSpacePlanner.Solve(0,Vector3.forward,flowing.Input,flowing.Side,cluster,still,true,0,null,.4875f,3,true);
  if(continuing.Side!=flowing.Side||continuing.Input.magnitude<.69f)throw new System.Exception("Open bypass did not continue its safe side");
  var enclosed=new Vector3[9];for(int k=1;k<9;k++)enclosed[k]=Quaternion.AngleAxis((k-1)*45,Vector3.up)*Vector3.forward*.7f;
  var waiting=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.zero,0,enclosed,new Vector3[9],true,0,null,.4875f,3,true);
  if(waiting.Input.magnitude>.001f||waiting.PredictedGap<.6f)throw new System.Exception("Enclosed actor must retain safe waiting");
  var similar=SprintSocialSpace.ForStatusGap(1,1,.5f);
  var lower=SprintSocialSpace.ForStatusGap(1,0,.5f);
  var higher=SprintSocialSpace.ForStatusGap(0,1,.5f);
  if(Mathf.Abs(similar.Distance-1.1f)>.0001f||lower.Distance<=similar.Distance||higher.Distance<=similar.Distance)throw new System.Exception("Status-gap distance directions failed");
  if(SprintSocialSpace.ForStatusGap(1,0,0).Distance!=1.1f)throw new System.Exception("Unknown status must not create a gap preference");
  gapFixtures=new SocialFixture[9];int fixtureIndex=0;
  foreach(float own in new[]{0f,.5f,1f})foreach(float estimate in new[]{0f,.5f,1f})
   gapFixtures[fixtureIndex++]=Fixture("gap",own,estimate,.5f,2.1f,true);
  bool changed=false;for(int step=0;step<=20;step++){
   var peer=Fixture("peer",1,1,.5f,1.5f+step*.1f,true);var other=Fixture("lower",1,0,.5f,1.5f+step*.1f,true);
   if(Mathf.Abs(peer.inputX-other.inputX)+Mathf.Abs(peer.inputZ-other.inputZ)>.01f)changed=true;
  }
  if(!changed)throw new System.Exception("Gap preference did not affect controlled planner commands");
  var masked=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,positions,velocities,true,0,null,.65f,0,false,1f/60,new[]{true,false});
  if((masked.Input-Vector3.forward).sqrMagnitude>.0001f||SprintSpacePlanner.CrowdExposure(0,Vector3.forward,cluster,still,new[]{true,false,false,false})!=0)throw new System.Exception("Departed actor still affected planning");
  var coflow=new[]{new Vector3(.5f,0,1.5f),Vector3.zero};var coVel=new[]{Vector3.forward,Vector3.forward};
  var deferPref=SprintSocialSpace.ForStatusGap(0,1,.5f);var pair=new[]{deferPref,deferPref};
  float ahead=SprintSpacePlanner.PassageExposure(0,Vector3.forward,coflow,coVel,pair);
  coflow[0]=new Vector3(.5f,0,-1.5f);float behind=SprintSpacePlanner.PassageExposure(0,Vector3.forward,coflow,coVel,pair);
  if(ahead<=behind+.01f)throw new System.Exception("Passage field did not distinguish front from rear");
  coflow[0]=new Vector3(.5f,0,1.5f);
  var ordinary=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,coflow,coVel,true,0,pair,.4875f,3,true);
  var yielding=SprintSpacePlanner.Solve(0,Vector3.forward,Vector3.forward,0,coflow,coVel,true,0,pair,.4875f,3,true,1f/60,null,true);
  if((ordinary.Input-yielding.Input).sqrMagnitude<.0001f)throw new System.Exception("Passage field did not affect actual co-travel command");
  var neutral=SprintSocialSpace.ForStatusGap(0,1,0);
  if(SprintSpacePlanner.PassageExposure(0,Vector3.forward,coflow,coVel,new[]{neutral,neutral})!=0)throw new System.Exception("Unknown cue retained passage preference");
  if(Mathf.Abs(SprintSocialSpace.DetourWeight(0,10,10)-1)>.0001f||SprintSocialSpace.DetourWeight(12,10,10)>=.3f||SprintSocialSpace.DetourWeight(12,10,10)<.15f)throw new System.Exception("Own route budget did not preserve direct paths and soften large detours");
  var sideStep=new SprintSideStep.State();
  if(!sideStep.Update(30,10,1,true,.016f)||!sideStep.Locked)throw new System.Exception("Side-step did not enter bounded facing hold");
  for(int k=0;k<60;k++)sideStep.Update(30,10,1,true,.016f);
  if(sideStep.Locked||sideStep.Cooldown<=0)throw new System.Exception("Side-step failed to time out with cooldown");
  var unsafeSide=new SprintSideStep.State();unsafeSide.Update(30,10,1,true,.016f);
  if(!unsafeSide.Update(30,90,1,true,.016f)||unsafeSide.Locked)throw new System.Exception("Side-step did not release excessive facing difference");
  var crossPos=new[]{new Vector3(0,0,1.2f),Vector3.zero};var crossVel=new[]{Vector3.left,Vector3.forward};
  float crossOld=SprintSpacePlanner.PassageExposure(0,Vector3.left,crossPos,crossVel,pair);
  float crossNew=SprintSpacePlanner.PassageExposure(0,Vector3.left,crossPos,crossVel,pair,null,true);
  if(crossNew<=crossOld+.01f)throw new System.Exception("Crossing yield did not cover non-aligned traffic");
  if(SprintSpacePlanner.PassageExposure(0,Vector3.left,crossPos,crossVel,new[]{neutral,neutral},null,true)!=0)throw new System.Exception("Crossing yield read unavailable status");
  if(SprintSpacePlanner.RecoveryCost(Vector3.forward,Vector3.forward,.3f)!=0||SprintSpacePlanner.RecoveryCost(Vector3.left,Vector3.forward,1)!=0||SprintSpacePlanner.RecoveryCost(Vector3.back,Vector3.forward,.3f)<=SprintSpacePlanner.RecoveryCost(Vector3.left,Vector3.forward,.3f))throw new System.Exception("Detour recovery did not distinguish useful progress from retreat");
  var cue=new SprintSocialSpace.Cue();cue.Update(true,.17f,.6f);cue.Update(false,0,.016f);
  if(cue.Weight!=0||SprintSocialSpace.ForEstimate(.5f,cue.Estimate,cue.Weight).Estimate!=.5f)throw new System.Exception("Lost observation did not return to neutral");
 }
 static string Hash(string path){using(var sha=SHA256.Create())return System.BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant();}
 static void Tick(){
  if(EditorApplication.isCompiling||EditorApplication.isUpdating)return;
  string command=Path.Combine(Root,"run.request");
  if(!File.Exists(command))refreshedRequest=false;
  if(!EditorApplication.isPlaying&&!EditorApplication.isPlayingOrWillChangePlaymode&&File.Exists(command)){
   // A background editor may not notice source changes before a request arrives.
   // Keep the request until refresh/compilation/domain reload have completed.
   if(!refreshedRequest){refreshedRequest=true;AssetDatabase.Refresh();return;}
   string payload=File.ReadAllText(command);var config=JsonUtility.FromJson<RunCommand>(payload);File.Delete(command);
   refreshedRequest=false;
   if(config==null||!Regex.IsMatch(config.run??"","^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")||config.mode<0||config.mode>2||config.fps<1||config.fps>120||config.duration<1||config.duration>120||config.count<2||config.count>30||config.width<320||config.width>1920||config.height<240||config.height>1080||(config.scenario!="crowd"&&config.scenario!="headon"&&config.scenario!="crossing"))throw new System.Exception("Invalid sprint run configuration");
   if(config.spatial<0||config.spatial>10||(config.spatial>=1&&(config.mode!=1||config.responsePose)))throw new System.Exception("Space tests require expression mode with response pose off");
   if((config.statusPattern!="cycle"&&config.statusPattern!="low-high"&&config.statusPattern!="high-low")||config.fixedExpression< -1||config.fixedExpression>1)throw new System.Exception("Invalid status/expression diagnostic configuration");
   if(config.lowerBody<0||config.lowerBody>2)throw new System.Exception("Invalid lower-body diagnostic policy");
   if(config.clipStride<1||config.clipStride>120||config.clipActor<0||config.clipActor>29)throw new System.Exception("Invalid clip capture configuration");
   string captureRoot=Path.Combine(Root,config.run);if(Directory.Exists(captureRoot))throw new System.Exception("Refusing to overwrite existing run "+config.run);
   CheckObservation();EditorSceneManager.OpenScene(ScenePath);var d=Object.FindFirstObjectByType<SprintDirector>();
   d.Mode=config.mode;d.Scenario=config.scenario;d.Seed=config.seed;d.CaptureFps=config.fps;d.Count=config.count;d.Duration=config.duration;d.EnableResponsePose=config.responsePose;d.CaptureWidth=config.width;d.CaptureHeight=config.height;d.RunLabel=config.run;
   d.SpatialPolicy=config.spatial;
   d.UseOwnedSearch=config.ownedSearch;
   d.CaptureVideo=config.video;
   d.LowerBodyPolicy=config.lowerBody;d.KneeDiagnostics=config.kneeDiagnostics;
   d.ClipStride=config.clipStride;d.ClipActor=config.clipActor;
   d.StatusPattern=config.statusPattern;d.FixedExpressionStatus=config.fixedExpression;d.SinglePass=config.singlePass;d.LateralSteps=config.lateralSteps;d.StatusYield=config.statusYield;d.RouteRecovery=config.routeRecovery;
   d.CaptureRun=true;d.CaptureRoot=captureRoot;Directory.CreateDirectory(captureRoot);File.WriteAllText(Path.Combine(captureRoot,"config.json"),JsonUtility.ToJson(config,true));
   var sources=new System.Text.StringBuilder();foreach(string path in Directory.GetFiles("Assets/SubmissionSprint","*.cs",SearchOption.AllDirectories))sources.AppendLine(Hash(path)+"  "+path);
   File.WriteAllText(Path.Combine(captureRoot,"source-sha256.txt"),sources.ToString());File.WriteAllText(Path.Combine(captureRoot,"checks.txt"),"Observation filter: smoothing, target switch, release passed.\nPlanner: analytic pass-through, head-on adjustment, unrelated parallel neighbour passed.\nCapture delta time is controlled after frame 1; runtime determinism must be measured, not assumed.\n");
   File.WriteAllText(Path.Combine(captureRoot,"compiled-sha256.txt"),Hash("Library/ScriptAssemblies/Assembly-CSharp.dll")+"  Assembly-CSharp.dll\n"+Hash("Library/ScriptAssemblies/Assembly-CSharp-Editor.dll")+"  Assembly-CSharp-Editor.dll\n");
   File.WriteAllText(Path.Combine(captureRoot,"social-fixtures.json"),JsonUtility.ToJson(new SocialFixtures{fixtures=socialFixtures},true));
   File.WriteAllText(Path.Combine(captureRoot,"gap-fixtures.json"),JsonUtility.ToJson(new SocialFixtures{fixtures=gapFixtures},true));
   File.WriteAllText(Path.Combine(captureRoot,"flow-checks.txt"),"Open cluster: moving safe bypass from rest.\nSafe chosen side continues.\nEnclosed ring: safe waiting retained.\n");
   Debug.Log("SPRINT START "+config.run);EditorApplication.ExecuteMenuItem("Window/General/Game");EditorApplication.isPlaying=true;return;
  }
  if(EditorApplication.isPlaying){var d=Object.FindFirstObjectByType<SprintDirector>();if(d&&d.Finished){Debug.Log("SPRINT FINISHED "+d.RunLabel);EditorApplication.isPlaying=false;}}
 }
}
