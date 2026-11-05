using UnityEngine;

// Capture after the pose overlay at the configured simulation-frame stride.
[DefaultExecutionOrder(10000)]
public class SprintCaptureLate : MonoBehaviour {
 public SprintDirector Director;
 void LateUpdate(){if(Director){Director.CaptureKneeFrame();Director.CaptureMotionFrame();Director.CaptureClipFrame();}}
}
