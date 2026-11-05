import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.build_locomotion_preview import build,ROOT
from src.bvh import load
from src.locomotion import build_cycle,place_pose,path_at,norm


class LocomotionBuildTests(unittest.TestCase):
    def test_offline_bundle_and_python_js_movement_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            data=build(destination=target)
            html=(target/'index.html').read_text()
            self.assertNotIn('/*__',html)
            self.assertNotRegex(html,r'<(?:script|link)[^>]+(?:src|href)=')
            self.assertNotRegex(html,r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(')
            self.assertEqual(data['translation_mode'],'channels_replace_offset')
            self.assertEqual(len(data['poses']),data['evidence']['period_frames']+1)
            self.assertTrue((target/'LICENSE.txt').exists())
            source=ROOT/data['source']['file']
            cycle=build_cycle(load(source))
            runtime=str(ROOT/'locomotion/runtime.js')
            js='''const fs=require('node:fs');const{sampleCycle,pathAt,placePose}=require(process.argv[1]);
const c=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const results=[];
for(const kind of ['straight','curve'])for(const d of [-.01,0,.37,1.0325076434896736,20.106192982974676]){
const p=pathAt(d,kind,3,10);results.push(placePose(sampleCycle(c,d),p.position,p.heading));}
console.log(JSON.stringify(results));'''
            try:
                result=subprocess.run(['node','-e',js,runtime,str(target/'cycle.json')],capture_output=True,text=True,check=True)
            except FileNotFoundError:
                self.skipTest('Node unavailable: Python/JS parity requires Node; viewer itself does not')
            actual=json.loads(result.stdout)
            expected=[]
            for kind in ['straight','curve']:
                for d in [-.01,0,.37,1.0325076434896736,20.106192982974676]:
                    p,h=path_at(d,kind,3,10);expected.append(place_pose(cycle.sample(d),p,h))
            for a,b in zip(actual,expected):
                self.assertLess(max(norm([x-y for x,y in zip(p,q)]) for p,q in zip(a,b)),1e-11)
