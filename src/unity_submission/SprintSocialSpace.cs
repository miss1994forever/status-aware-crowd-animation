using UnityEngine;

// Experimental mapping for this avatar/overlay only. Public geometry is not a
// validated status label. No neighbour hidden status enters this interface.
public static class SprintSocialSpace {
 public const string Calibration="prototype-elbow-v1";
 public struct Cue {
  public float Mean,Age;
  public void Update(bool visible,float expansion,float dt){
   if(!visible){Mean=Age=0;return;}
   Mean=Age==0?expansion:Mathf.Lerp(Mean,expansion,1-Mathf.Exp(-dt/.35f));
   Age+=Mathf.Max(0,dt);
  }
  // Calibrated from rendered expansion medians in the existing fixed-avatar run.
  public float Estimate=>Mathf.Clamp01((Mean-.01f)/.16f);
  // Exposure weighting, capped deliberately; not a measured recognition confidence.
  public float Weight=>.5f*Mathf.Clamp01(Age/.6f);
 }
 public struct Preference {
  public float Distance,ComfortWeight,Cooperation,Estimate,ObservationWeight,RawEstimate,Deference;
 }
 public static Preference ForEstimate(float ownStatus,float visibleEstimate,float observationWeight){
  float weight=Mathf.Clamp01(observationWeight);
  float estimate=Mathf.Lerp(.5f,Mathf.Clamp01(visibleEstimate),weight);
  float cooperation=Mathf.Clamp01(.5f+.3f*(estimate-Mathf.Clamp01(ownStatus)));
  return new Preference{Distance=1.1f+.8f*(cooperation-.5f),ComfortWeight=.75f+.5f*cooperation,
   Cooperation=cooperation,Estimate=estimate,ObservationWeight=weight,RawEstimate=Mathf.Clamp01(visibleEstimate)};
 }
 public const float LowerGap=.4f,HigherGap=.6f;
 public static Preference ForStatusGap(float ownStatus,float visibleEstimate,float observationWeight){
  var preference=ForEstimate(ownStatus,visibleEstimate,observationWeight);
  float difference=Mathf.Clamp01(ownStatus)-preference.RawEstimate;
  float lower=Mathf.Max(0,difference),higher=Mathf.Max(0,-difference);
  preference.Distance=1.1f+preference.ObservationWeight*(LowerGap*lower*lower+HigherGap*higher*higher);
  preference.Deference=preference.ObservationWeight*higher;
  return preference;
 }
 public static float ProgressWeight(float ownStatus)=>.65f*(.75f+.5f*Mathf.Clamp01(ownStatus));
 // Own-task route inefficiency, not a random choice or another actor's status.
 // Allow 2m of extra travel before fading discretionary social preferences.
 public static float DetourWeight(float travelled,float remaining,float initialDistance){
  float excess=Mathf.Max(0,travelled+remaining-initialDistance-2)/3;
  return .15f+.85f/(1+excess*excess);
 }
 // Character-design hypothesis: only the lowest range actively avoids clusters.
 public static float CrowdAversion(float ownStatus){float low=Mathf.Clamp01((.35f-ownStatus)/.35f);return 3*low*low;}
}
