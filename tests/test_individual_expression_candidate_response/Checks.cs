using System;
using System.IO;
using System.Text.Json;
using System.Collections.Generic;
using IndividualExpressionCandidate;
class Checks {
 static int checks;
 static void Check(bool v,string message){checks++;if(!v)throw new Exception(message);}
 static NeighborCue Cue(int id,double e,double h,double distance=1,double vx=-.5){return new NeighborCue{ActorId=id,Expansion=e,HeightRatio=h,Confidence=1,MeasurementValid=true,RelativeX=distance,RelativeVX=vx};}
 static void Basic(VisibleReference reference){
  var settings=new ResponseSettings();var profile=ExpressionProfile.SourceToCompact;
  Check(InteractiveExpression.EncounterWeight(Cue(1,0,1,4),settings)==0,"far");
  Check(InteractiveExpression.EncounterWeight(Cue(1,0,1,1,.5),settings)==0,"separating");
  var parallel=Cue(1,0,1);parallel.RelativeVX=0;parallel.RelativeVZ=0;
  Check(InteractiveExpression.EncounterWeight(parallel,settings)==0,"parallel");
  Check(InteractiveExpression.EncounterWeight(Cue(1,0,1),settings)>0,"approaching");
  var same=Cue(1,0,1,0);Check(InteractiveExpression.EncounterWeight(same,settings)==0,"coincident degeneracy");
  Check(InteractiveExpression.VisibleScore(reference.ExpansionCenter,reference.HeightCenter,reference,settings.DeadZone)==0,"reference neutral signal");
  var high=Cue(1,reference.ExpansionCenter+3*reference.ExpansionScale,reference.HeightCenter+3*reference.HeightScale);
  var controller=new InteractiveExpression();InteractiveExpression.Result r=default;
  for(int f=0;f<360;f++)r=controller.Step(0,.5,profile,reference,new[]{high},1.0/60,true,settings);
  Check(r.Valid&&r.EffectiveOffset>0&&r.EffectiveOffset<=settings.MaxOffset,"open observed to compact response hypothesis");
  Check(r.Baseline==.5&&r.CompactnessTarget==r.Baseline+r.EffectiveOffset,"anchor");
  double before=r.EffectiveOffset;
  for(int f=0;f<600;f++)r=controller.Step(0,.5,profile,reference,Array.Empty<NeighborCue>(),1.0/60,true,settings);
  Check(Math.Abs(r.EffectiveOffset)<1e-7&&before>.001,"release to own baseline");
  var highStatus=new InteractiveExpression();for(int f=0;f<300;f++)r=highStatus.Step(0,1,profile,reference,new[]{high},1.0/60,true,settings);
  Check(r.EffectiveOffset>0,"high own status allowed to respond");
  var endpoint=new InteractiveExpression();for(int f=0;f<300;f++)r=endpoint.Step(0,0,profile,reference,new[]{high},1.0/60,true,settings);
  Check(r.Saturated&&r.UnclippedOffset>0&&r.EffectiveOffset==0&&r.Baseline==1,"endpoint saturation is reported, baseline not changed");
  var a=new InteractiveExpression();var b=new InteractiveExpression();
  for(int f=0;f<120;f++){
   var ra=a.Step(0,.5,profile,reference,new[]{high},1.0/60,true,settings);
   var rb=b.Step(0,.5,profile,reference,new[]{high,high},1.0/60,true,settings);
   Check(ra.CompactnessTarget==rb.CompactnessTarget,"duplicate id not double counted");
  }
  var crowd=new List<NeighborCue>();for(int i=1;i<=9;i++){var c=high;c.ActorId=i;crowd.Add(c);}
  var many=new InteractiveExpression();for(int f=0;f<300;f++)r=many.Step(0,.5,profile,reference,crowd,1.0/60,true,settings);
  Check(r.RawWeightSum>1&&r.WeightSum<=1&&Math.Abs(r.EffectiveOffset)<=settings.MaxOffset,"crowd budget");
  r=many.Step(0,.5,profile,reference,crowd,1.0/60,false,settings);
  Check(r.CompactnessTarget==.5&&r.EffectiveOffset==0,"interaction off preserves personal baseline");
  var invalid=high;invalid.Expansion=double.NaN;
  r=many.Step(0,.5,profile,reference,new[]{invalid},1.0/60,true,settings);
  Check(r.UsedNeighbors==0&&r.EffectiveOffset==0,"missing signal neutral");
  Check(!many.Step(0,double.NaN,profile,reference,crowd,.016,true,settings).Valid,"invalid own input");
  foreach(int fps in new[]{30,60,120}){
   var rate=new InteractiveExpression();double old=0;
   for(int f=0;f<fps*6;f++){
    r=rate.Step(0,.5,profile,reference,new[]{high},1.0/fps,true,settings);
    Check(Math.Abs(r.UnclippedOffset-old)<=settings.OffsetRate/fps+1e-12,"time-based rate bound");old=r.UnclippedOffset;
   }
   Check(r.EffectiveOffset>0&&r.EffectiveOffset<settings.MaxOffset,"frame-rate response bounds");
   for(int f=0;f<fps*10;f++)r=rate.Step(0,.5,profile,reference,null,1.0/fps,true,settings);
   Check(Math.Abs(r.EffectiveOffset)<1e-7,"frame-rate release");
  }
  // Target switch: observation resets, output remains rate limited.
  var switcher=new InteractiveExpression();double previous=0;
  for(int f=0;f<600;f++){
   var c=high;if(f>=300){c.ActorId=2;c.Expansion=reference.ExpansionCenter-3*reference.ExpansionScale;c.HeightRatio=reference.HeightCenter-3*reference.HeightScale;}
   r=switcher.Step(0,.5,profile,reference,new[]{c},1.0/60,true,settings);
   Check(Math.Abs(r.UnclippedOffset-previous)<=settings.OffsetRate/60+1e-12,"rate on switch");previous=r.UnclippedOffset;
  }
  // Existing independent baseline path is numerically unchanged by the generic intent API.
  var original=new ExpressionPolicy();var intent=new ExpressionPolicy();
  for(int f=0;f<120;f++){
   var p=original.Step(.3,profile,1.65,1.2,1.0/60,true);var q=intent.StepCompactness(.7,.0125,1.65,1.2,1.0/60,true);
   Check(Math.Abs(p.Weight-q.Weight)<1e-14&&Math.Abs(p.RequestedLowering-q.RequestedLowering)<1e-14,"policy refactor parity");
  }
 }
 static double Field(JsonElement e,string k)=>e.GetProperty(k).GetDouble();
 static void Main(string[] args){
  using var doc=JsonDocument.Parse(File.ReadAllText(args[0]));var j=doc.RootElement.GetProperty("reference");
  var reference=new VisibleReference(Field(j,"expansionCenter"),Field(j,"expansionScale"),Field(j,"heightCenter"),Field(j,"heightScale"));
  Basic(reference);var settings=new ResponseSettings();var summaries=new List<object>();var traces=new List<object>();
  foreach(var clip in doc.RootElement.GetProperty("clips").EnumerateArray()){
   string id=clip.GetProperty("id").GetString();double dt=Field(clip,"dt");var means=new Dictionary<string,double>();var scores=new Dictionary<string,List<double>>();
   foreach(string variant in new[]{"source","half","full","combination"}){
    var controller=new InteractiveExpression();var observations=clip.GetProperty("variants").GetProperty(variant);var qvalues=new List<double>();double sum=0;int count=0;
    for(int f=0;f<observations.GetArrayLength();f++){
     var values=observations[f];var cue=Cue(1,values[0].GetDouble(),values[1].GetDouble());
     var r=controller.Step(0,.5,ExpressionProfile.SourceToCompact,reference,new[]{cue},dt,true,settings);
     double q=InteractiveExpression.VisibleScore(cue.Expansion,cue.HeightRatio,reference,settings.DeadZone);qvalues.Add(q);
     Check(r.Valid&&r.WeightSum<=1+1e-12&&Math.Abs(r.UnclippedOffset)<=settings.MaxOffset+1e-12,"real-cue replay bounds");
     if(f*dt>=1){sum+=r.EffectiveOffset;count++;}
     traces.Add(new{clip=id,variant,frame=f,t=f*dt,qRaw=q,r.EffectiveOffset,r.CompactnessTarget,r.WeightSum});
    }
    means[variant]=sum/Math.Max(1,count);scores[variant]=qvalues;
   }
   double maxSampledSlope=0;
   var src=scores["source"];var full=scores["full"];var half=scores["half"];
   // Sampled secants across the actual recorded controller settings, NOT a global gain bound.
   for(int i=30;i<src.Count;i++)maxSampledSlope=Math.Max(maxSampledSlope,Math.Max(Math.Abs(full[i]-half[i])/.5,Math.Abs(half[i]-src[i])/.5));
   summaries.Add(new{clip=id,meanEffectiveOffset=means,sampledRawSignalSecant=maxSampledSlope,heldOut=false});
  }
  File.WriteAllText(Path.Combine(Path.GetDirectoryName(args[1]),"response-settings.json"),JsonSerializer.Serialize(settings,new JsonSerializerOptions{IncludeFields=true,WriteIndented=true}));
  File.WriteAllText(args[1],JsonSerializer.Serialize(new{checks,kind="actual C# response module replaying recorded visible geometry; one-way replay, not perceptual or full-body closed-loop validation",reference=new{reference.ExpansionCenter,reference.ExpansionScale,reference.HeightCenter,reference.HeightScale},summaries,traces}));
  Console.WriteLine("checks="+checks+"; one-way recorded-cue replay passed; perception and full-body feedback unverified");
 }
}
