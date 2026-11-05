"""Invariant and implementation-parity checks; no perceptual validation."""
import json,subprocess,unittest
from pathlib import Path
import numpy as np
from src.expression_space_lab.model import phase_map,quality
from src.locomotion import Cycle
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'outputs/expression-space-lab/experiment.json').read_text())

def cycle(c):
 z=c['cycle'];return Cycle(z['poses'],z['tangents'],z['stride'],z['evidence'],z['parents'],z['bone_lengths'])
def pose(c,u,s):
 cy=cycle(c);v=phase_map(u,s);p=np.array(cy.sample(v*cy.stride))
 return quality(p,c['names'],c['parents'],np.array(c['lengths']),v,s)

class Experiment(unittest.TestCase):
 def test_identity_and_contacts_all_strengths(self):
  for c in DATA['clips']:
   cy=cycle(c); feet=[i for i,n in enumerate(c['names']) if 'Foot' in n or 'Toes' in n]
   for s in np.linspace(0,1,11):
    for u in np.linspace(0,1,101):
     v=phase_map(u,s);source=np.array(cy.sample(v*cy.stride));p=pose(c,u,s)
     self.assertTrue(np.isfinite(p).all())
     np.testing.assert_allclose(p[feet],source[feet],atol=1e-10)
     if s==0:np.testing.assert_allclose(p,source,atol=0)
     for j,k in enumerate(c['parents']):
      if k is not None:self.assertAlmostEqual(np.linalg.norm(p[j]-p[k]),c['lengths'][j],places=8)
 def test_monotonic_timing_duration_and_periodic_seam(self):
  u=np.linspace(0,1,10001)
  for s in [0,.17,.5,1]:
   v=phase_map(u,s);self.assertEqual(v[0],0);self.assertEqual(v[-1],1);self.assertGreater(np.diff(v).min(),0)
   for c in DATA['clips']:
    e=1e-5;np.testing.assert_allclose(pose(c,0,s),pose(c,1,s),atol=1e-8)
    left=(pose(c,1,s)-pose(c,1-e,s))/e;right=(pose(c,e,s)-pose(c,0,s))/e
    self.assertLess(np.linalg.norm(left-right,axis=1).max(),.025)
 def test_python_browser_model_parity(self):
  # Extract the same pure functions used by the page; exercise independent JS port.
  ui=(ROOT/'src/expression_space_lab/ui.js').read_text();pure=ui[ui.index('const add='):ui.index('function frame(')]
  probes=[];expected=[]
  for c in DATA['clips']:
   for u,s in [(.07,.23),(.31,.5),(.76,1),(.99,.8)]:
    cy=cycle(c);v=float(phase_map(u,s));p=np.array(cy.sample(v*cy.stride));probes.append(dict(p=p.tolist(),c=c,u=v,s=s));expected.append(quality(p,c['names'],c['parents'],np.array(c['lengths']),v,s).tolist())
  script=pure+'\nconst fs=require("fs");const x=JSON.parse(fs.readFileSync(0,"utf8"));console.log(JSON.stringify(x.map(a=>quality(a.p,a.c,a.u,a.s))));'
  result=subprocess.run(['node','-e',script],input=json.dumps(probes),text=True,capture_output=True,check=True)
  np.testing.assert_allclose(json.loads(result.stdout),expected,atol=1e-10)
 def test_near_extension_tracks_source_bend(self):
  # Preserve the source extension rather than either locking the IK chain or
  # adding a persistent crouch. Compare at identical source phase, not time.
  def bend(p,h,k,a):
   v=p[h]-p[k];w=p[a]-p[k]
   return 180-np.degrees(np.arccos(np.clip(np.dot(v,w)/np.linalg.norm(v)/np.linalg.norm(w),-1,1)))
  for c in DATA['clips']:
   cy=cycle(c)
   for u in np.linspace(0,1,1201):
    source=np.array(cy.sample(u*cy.stride))
    out=quality(source,c['names'],c['parents'],np.array(c['lengths']),u,1)
    for side in ['L','R']:
     h,k,a=[c['names'].index(n+'_'+side) for n in ['UpperLeg','LowerLeg','Foot']]
     before,after=bend(source,h,k,a),bend(out,h,k,a)
     if before<8:
      self.assertLess(abs(after-before),3.5)
      self.assertGreaterEqual(after,before*.85)
 def test_small_strength_limit(self):
  for c in DATA['clips']:
   for u in [.1,.4,.75]:self.assertLess(np.max(abs(pose(c,u,1e-7)-pose(c,u,0))),1e-6)
if __name__=='__main__':unittest.main()
