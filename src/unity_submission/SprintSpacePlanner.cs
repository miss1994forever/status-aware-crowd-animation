using UnityEngine;

// Finite-candidate planner. Geometry is public; optional preferences belong to self.
// Safety is a centre-distance prediction proxy, not a final-body collision guarantee.
public static class SprintSpacePlanner {
 public const float SafetyDistance=.60f,ComfortDistance=1.10f,Horizon=1.8f;
 static readonly float[] Angles={0,25,-25,50,-50,70,-70};
 static readonly float[] CrowdAngles={0,25,-25,50,-50,70,-70,90,-90,110,-110};
 static readonly float[] FlowAngles={0,15,-15,30,-30,45,-45,60,-60,75,-75,90,-90};
 static readonly float[] Speeds={1,.7f,.35f,0};
 public struct Result {
  public Vector3 Input;
  public float PredictedGap,Risk;
  public int Side,SafeCandidates;
  public bool SafetyOverride,PassageRelease;
 }
 public static float Closest(Vector3 relative,Vector3 relativeVelocity,float start,float end){
  relative.y=relativeVelocity.y=0;
  float t=relativeVelocity.sqrMagnitude>.0001f?Mathf.Clamp(-Vector3.Dot(relative,relativeVelocity)/relativeVelocity.sqrMagnitude,start,end):start;
  return (relative+relativeVelocity*t).magnitude;
 }
 // A local input constraint, separate from comfort planning. Each participant
 // takes half the correction around measured pair velocity. EMM still executes it.
 // Projection can leave residual violations in a crowded/infeasible configuration.
 public static Vector3 Guard(int self,Vector3 input,Vector3[] positions,Vector3[] velocities,out float residual,bool[] active=null){
  Vector3 result=input;const float guard=.75f,horizon=.45f,delay=.25f;
  for(int pass=0;pass<3;pass++)for(int j=0;j<positions.Length;j++){
   if(j==self||(active!=null&&!active[j]))continue;Vector3 away=positions[self]-positions[j];away.y=0;float d=away.magnitude;
   if(d>2.5f||d<.001f)continue;Vector3 n=away/d;
   float projectedDistance=d+Vector3.Dot(velocities[self]-velocities[j],n)*delay;
   float bound=.5f*Vector3.Dot(velocities[self]+velocities[j],n)+(guard-projectedDistance)/(2*horizon);
   float shortfall=bound-Vector3.Dot(result,n);
   if(shortfall>0)result=Vector3.ClampMagnitude(result+n*shortfall,1);
  }
  residual=0;
  for(int j=0;j<positions.Length;j++){
   if(j==self||(active!=null&&!active[j]))continue;Vector3 away=positions[self]-positions[j];away.y=0;float d=away.magnitude;
   if(d>2.5f||d<.001f)continue;Vector3 n=away/d;
   float projectedDistance=d+Vector3.Dot(velocities[self]-velocities[j],n)*delay;
   float bound=.5f*Vector3.Dot(velocities[self]+velocities[j],n)+(guard-projectedDistance)/(2*horizon);
   residual=Mathf.Max(residual,bound-Vector3.Dot(result,n));
  }
  return result;
 }
 // Broad density over a prospective path; remove the strongest neighbour so a
 // single passer-by is handled by pair spacing, not labelled a crowd.
 public static float CrowdExposure(int self,Vector3 candidate,Vector3[] positions,Vector3[] velocities,bool[] active=null){
  float cost=0;
  for(int sample=1;sample<=4;sample++){
   float time=sample*.7f;Vector3 point=positions[self]+velocities[self]*.25f+candidate*(time-.25f);
   float sum=0,strongest=0;
   for(int j=0;j<positions.Length;j++){
    if(j==self||(active!=null&&!active[j])||(positions[j]-positions[self]).sqrMagnitude>36)continue;
    Vector3 delta=positions[j]+velocities[j]*Mathf.Min(time,1.4f)-point;delta.y=0;
    float density=Mathf.Exp(-delta.sqrMagnitude/(2*1.6f*1.6f));sum+=density;strongest=Mathf.Max(strongest,density);
   }
   float excess=Mathf.Max(0,sum-strongest-.35f);cost+=excess*excess/4;
  }
  return cost;
 }
 // A directional personal-space field around a perceived higher-status moving
 // neighbour. Penalises sustained co-travel especially ahead; it never attracts
 // the actor to a prescribed following position or reads a neighbour's goal.
 public static float PassageExposure(int self,Vector3 candidate,Vector3[] positions,Vector3[] velocities,SprintSocialSpace.Preference[] preferences,bool[] active=null,bool crossingYield=false){
  if(preferences==null)return 0;float cost=0;
  for(int j=0;j<positions.Length;j++){
   if(j==self||(active!=null&&!active[j])||preferences[j].Deference<=0)continue;
   Vector3 other=velocities[j];other.y=0;float speed=other.magnitude;if(speed<.25f)continue;
   Vector3 heading=other/speed;
   float aligned=candidate.sqrMagnitude<.01f?1:Mathf.Clamp01((Vector3.Dot(candidate.normalized,heading)+.2f)/1.2f);
   // Extend the existing directional field to crossing/oncoming traffic.
   // Only observed higher-status cues contribute; safety ranking is unchanged.
   if(crossingYield)aligned=.65f+.35f*aligned;
   for(int sample=1;sample<=3;sample++){
    float time=sample*.6f;
    Vector3 relative=positions[self]+velocities[self]*.25f+candidate*(time-.25f)-(positions[j]+other*time);relative.y=0;
    float along=Vector3.Dot(relative,heading),lateralSquared=Mathf.Max(0,relative.sqrMagnitude-along*along);
    float forwardWeight=.15f+.85f/(1+Mathf.Exp(-along/.35f));
    float field=Mathf.Exp(-along*along/8-lateralSquared/(2*1.1f*1.1f));
    cost+=preferences[j].Deference*aligned*forwardWeight*field/3;
   }
  }
  return cost;
 }
 // An exhausted detour budget makes sideways/backward travel less attractive
 // than a brief safe wait. Zero at full budget; no safety or velocity alteration.
 public static float RecoveryCost(Vector3 candidate,Vector3 forward,float budget){
  return 2*Mathf.Clamp01(1-budget)*Mathf.Max(0,candidate.magnitude-Vector3.Dot(candidate,forward));
 }
 public static Result Solve(int self,Vector3 forward,Vector3 previousInput,int heldSide,Vector3[] positions,Vector3[] velocities,bool commitSide=false,float clearanceReserve=0,SprintSocialSpace.Preference[] preferences=null,float progressWeight=.65f,float crowdAversion=0,bool flow=false,float dt=1f/60,bool[] active=null,bool passage=false,float sidePersistence=1,float routePersistence=1,bool crossingYield=false,bool routeRecovery=false){
  forward.y=0;forward.Normalize();float planningDistance=SafetyDistance+Mathf.Max(0,clearanceReserve);
  float bestScore=float.PositiveInfinity;bool haveSafe=false;int safeCount=0;
  var result=new Result{Input=forward,PredictedGap=10};
  Result kept=result;float keptScore=float.PositiveInfinity,bestFuture=0,keptFuture=0;
  bool haveKept=false,keptSafe=false;
  bool flowing=flow&&crowdAversion>0;int bestRank=-1,keptRank=-1;
  float turnStep=180*Mathf.Clamp(dt,.001f,.05f);
  var angles=flowing?FlowAngles:crowdAversion>0?CrowdAngles:Angles;
  bool previousHeading=flowing&&previousInput.sqrMagnitude>.04f;
  float previousAngle=previousHeading?Vector3.SignedAngle(forward,previousInput,Vector3.up):0;
  float baseGap=10;
  for(int j=0;j<positions.Length;j++)if(j!=self&&(active==null||active[j])&&(positions[j]-positions[self]).sqrMagnitude<25)
   baseGap=Mathf.Min(baseGap,Closest(positions[j]-positions[self],velocities[j]-forward,0,Horizon));
  result.Risk=Mathf.Clamp01((ComfortDistance-baseGap)/ComfortDistance);
  foreach(float speed in Speeds)for(int angleIndex=0;angleIndex<angles.Length+(previousHeading?3:0);angleIndex++){
   float angle=angleIndex<angles.Length?angles[angleIndex]:previousAngle+(angleIndex-angles.Length-1)*turnStep;
   if(speed==0&&angleIndex!=0)continue;
   Vector3 candidate=Quaternion.AngleAxis(angle,Vector3.up)*forward*speed;
   float gap=10,futureMinimum=10,comfortCost=0,dangerCost=0;
   for(int j=0;j<positions.Length;j++){
    if(j==self||(active!=null&&!active[j]))continue;Vector3 rel=positions[j]-positions[self];rel.y=0;if(rel.sqrMagnitude>25)continue;
    // Approximate EMM's response delay: measured velocity for .25 s, then candidate.
    // Check both segments analytically; a late endpoint alone would miss pass-throughs.
    Vector3 firstVelocity=velocities[j]-velocities[self];
    float earlyGap=Closest(rel,firstVelocity,0,.25f);
    Vector3 delayed=rel+firstVelocity*.25f;
    float futureGap=Closest(delayed,velocities[j]-candidate,0,Horizon-.25f);
    futureMinimum=Mathf.Min(futureMinimum,futureGap);
    gap=Mathf.Min(gap,Mathf.Min(earlyGap,futureGap));
    float desiredDistance=preferences==null?ComfortDistance:preferences[j].Distance;
    float comfortWeight=preferences==null?1:preferences[j].ComfortWeight;
    float shortfall=Mathf.Max(0,desiredDistance-futureGap);
    comfortCost+=comfortWeight*shortfall*shortfall;
    // The early interval is unavoidable for every candidate; future clearance
    // determines emergency recovery rather than treating all candidates as tied.
    float danger=Mathf.Max(0,SafetyDistance-futureGap);dangerCost+=danger*danger;
   }
   bool safe=gap>=planningDistance;if(safe)safeCount++;
   bool continuous=!previousHeading||speed==0||Vector3.Angle(candidate,previousInput)<=turnStep+.01f;
   // Safety first, then bounded steering when a safe bounded choice exists.
   // All alternatives remain available for emergency recovery.
   int rank=safe?(continuous?2:1):0;
   int side=speed>.01f?(angle>1?1:angle< -1?-1:0):0;
   // For crowd bypasses, separate goal progress from stopping cost: sideways
   // travel must not cost more than standing still simply for having velocity.
   float goalCost=flow&&crowdAversion>0?progressWeight*(1-Vector3.Dot(candidate,forward))+.8f*(1-speed)*(1-speed):progressWeight*(candidate-forward).sqrMagnitude;
   goalCost*=Mathf.Clamp(routePersistence,1,2.5f);
   if(routeRecovery&&flow&&crowdAversion>0)goalCost-=.5f*Mathf.Clamp01(1-sidePersistence)*(1-speed)*(1-speed);
   float score=goalCost+.15f*(candidate-previousInput).sqrMagnitude+5*comfortCost+100*dangerCost;
   if(routeRecovery)score+=RecoveryCost(candidate,forward,sidePersistence);
   // Compare safe candidates with heading continuity included. No unsafe
   // post-planning interpolation of an already checked command is applied.
   if(flow&&crowdAversion>0&&speed>0&&previousInput.sqrMagnitude>.04f)
    score+=.35f*(1-Vector3.Dot(candidate.normalized,previousInput.normalized));
   if(crowdAversion>0)score+=crowdAversion*CrowdExposure(self,candidate,positions,velocities,active);
   if(passage)score+=4*PassageExposure(self,candidate,positions,velocities,preferences,active,crossingYield);
   if(heldSide!=0&&side!=0&&side!=heldSide)score+=.22f;
   // Common right-side convention breaks exact geometric ties without status priority.
   if(side<0)score+=.001f;
   if(rank>bestRank||(rank==bestRank&&score<bestScore)){
    bestRank=rank;haveSafe=safe;bestScore=score;result.Input=candidate;result.Side=side;result.PredictedGap=gap;bestFuture=futureMinimum;
   }
   if(side==0||side==heldSide){
    if(rank>keptRank||(rank==keptRank&&score<keptScore)){
     keptRank=rank;haveKept=true;keptSafe=safe;keptScore=score;kept.Input=candidate;kept.Side=side;kept.PredictedGap=gap;keptFuture=futureMinimum;
    }
   }
  }
  if(commitSide&&heldSide!=0&&haveKept){
   float risk=result.Risk;
   // A safe continuing-side candidate wins over comfort/efficiency improvements
   // on the opposite side. Safety can still override this current-encounter state.
   bool keep=keptSafe||(!haveSafe&&(bestFuture<keptFuture+.10f||(clearanceReserve>0&&keptFuture>=planningDistance)));
   bool release=passage&&keptSafe&&haveSafe&&bestRank>=keptRank&&bestScore+.3f*sidePersistence<keptScore;
   if(keep&&!release)result=kept;
   else if(release)result.PassageRelease=true;
   else result.SafetyOverride=result.Side!=0&&result.Side!=heldSide;
   result.Risk=risk;
  }
  result.SafeCandidates=safeCount;return result;
 }
}
