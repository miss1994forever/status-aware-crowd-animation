using UnityEngine;
using UnityEngine.SceneManagement;
// Submission shell only: scene replay and explicitly labelled configurations.
public class SprintSubmissionControls : MonoBehaviour {
 static int selected=2;SprintDirector director;float started;bool reported;float smokeExit;
 void Awake(){director=GetComponent<SprintDirector>();director.ExpressionVersion=selected==0?0:2;director.PostureExpression=selected==2;director.BodyResponse=selected!=0;director.HeadFilterLevel=selected==0?1:2;started=Time.realtimeSinceStartup;
  foreach(string a in System.Environment.GetCommandLineArgs())if(a.StartsWith("--smoke-exit="))float.TryParse(a.Substring(13),System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out smokeExit);
  Debug.Log("SUBMISSION START variant="+selected);
 }
 void Update(){if(director.DepartedCount==director.Count&&!reported){reported=true;Debug.Log("SUBMISSION COMPLETE exited="+director.DepartedCount+"/"+director.Count);}
  if(smokeExit>0&&Time.realtimeSinceStartup-started>=smokeExit){Debug.Log("SUBMISSION SMOKE EXIT");Application.Quit();}
 }
 void OnGUI(){GUILayout.BeginArea(new Rect(12,12,440,135),GUI.skin.box);GUILayout.Label("Status-aware crowd animation | 10 characters");
  int next=GUILayout.SelectionGrid(selected,new[]{"Frozen baseline","Arms + response","Posture + response"},3);
  if(next!=selected){selected=next;SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);}
  GUILayout.BeginHorizontal();if(GUILayout.Button("Replay"))SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex);if(GUILayout.Button("Wide / close"))director.ToggleSubmissionCamera();if(GUILayout.Button("Next actor"))director.NextSubmissionActor();GUILayout.EndHorizontal();
  GUILayout.Label("Exited "+director.DepartedCount+" / "+director.Count+" | L/M/H labels are diagnostics");GUILayout.EndArea();
 }
}
