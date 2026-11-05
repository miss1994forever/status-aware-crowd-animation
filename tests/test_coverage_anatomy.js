const assert=require('node:assert/strict');
const fs=require('node:fs');
const {coverageParts,drawCoverageAnatomy}=require('../preview/coverage-anatomy.js');
const html=fs.readFileSync('outputs/motion-coverage/index.html','utf8');
const data=JSON.parse(html.match(/const DATA = ([\s\S]*?);\n/)[1]);
for(const clip of data.clips){
  const parts=coverageParts(clip.names,clip.parents);
  assert.equal(parts.filter(p=>p.kind==='hand').length,2);
  assert.equal(parts.filter(p=>p.kind==='foot').length,2);
  const pose=clip.poses[0],before=JSON.stringify(pose);
  pose.forEach(Object.freeze);Object.freeze(pose);
  let textCount=0;
  const ctx={beginPath(){},moveTo(){},lineTo(){},stroke(){},fill(){},arc(){},closePath(){},fillRect(){},
    measureText(t){return{width:t.length*13}},fillText(){textCount++}};
  for(const shapes of [false,true])for(const labels of [false,true])for(const ends of [false,true]){
    drawCoverageAnatomy(ctx,p=>[p[0]*200,p[1]*200,p[2]],clip,pose,200,1.8,{shapes,labels,ends});
  }
  assert.equal(textCount,56);
  assert.equal(JSON.stringify(pose),before);
}
assert.deepEqual(coverageParts(['Root'],[null]),[]);
console.log('Anatomy renderer: all 4 skeletons, 8 display combinations; input poses unchanged.');
