using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.Build.Reporting;
using UnityEngine;
using System.IO;
[InitializeOnLoad] public static class SprintPackageBuild {
 static readonly string Root=System.Environment.GetEnvironmentVariable("UNITY_SUBMISSION_PACKAGE") ?? Path.GetFullPath(Path.Combine(Application.dataPath,"../SubmissionPackage"));
 static SprintPackageBuild(){EditorApplication.update+=Tick;}
 static bool refreshed;
 static void Tick(){string request=Path.Combine(Root,"build.request");if(!File.Exists(request)||EditorApplication.isPlayingOrWillChangePlaymode||EditorApplication.isCompiling||EditorApplication.isUpdating||EditorUtility.scriptCompilationFailed)return;if(!refreshed){refreshed=true;AssetDatabase.Refresh();return;}refreshed=false;File.Delete(request);Build();}
 [MenuItem("Submission/Build macOS package")] public static void Build(){
  EditorSceneManager.OpenScene("Assets/SubmissionSprint/SubmissionDemo.unity");var d=Object.FindFirstObjectByType<SprintDirector>();
  d.Count=10;d.Mode=1;d.Seed=806;d.Scenario="crowd";d.CaptureRun=false;d.CaptureVideo=false;d.KneeDiagnostics=false;d.CaptureRoot="";
  d.SpatialPolicy=10;d.LowerBodyPolicy=2;d.LateralSteps=true;d.StatusYield=true;d.RouteRecovery=true;d.HeadStability=true;d.HeadFilterLevel=2;
  d.ExpressionVersion=2;d.PostureExpression=true;d.BodyResponse=true;d.ExpressionECenter=.1653792f;d.ExpressionEScale=.1f;d.ExpressionHCenter=.9366972f;d.ExpressionHScale=.04f;
  d.SinglePass=true;d.EnableResponsePose=false;d.StatusPattern="cycle";d.FixedExpressionStatus=-1;d.RunLabel="Final submission";
  if(!d.GetComponent<SprintSubmissionControls>())d.gameObject.AddComponent<SprintSubmissionControls>();
  const string scene="Assets/SubmissionSprint/FinalSubmission.unity";EditorSceneManager.SaveScene(d.gameObject.scene,scene);
  PlayerSettings.productName="Status Crowd Animation";PlayerSettings.companyName="AnimationCourse";PlayerSettings.defaultScreenWidth=1280;PlayerSettings.defaultScreenHeight=720;PlayerSettings.fullScreenMode=FullScreenMode.Windowed;
  Directory.CreateDirectory(Path.Combine(Root,"运行程序"));
  var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{scene},locationPathName=Path.Combine(Root,"运行程序/StatusCrowd.app"),target=BuildTarget.StandaloneOSX,options=BuildOptions.None});
  File.WriteAllText(Path.Combine(Root,"build-result.json"),JsonUtility.ToJson(new Result{status=result.summary.result.ToString(),errors=(int)result.summary.totalErrors,size=result.summary.totalSize.ToString()},true));
 }
 [System.Serializable] class Result{public string status,size;public int errors;}
}
