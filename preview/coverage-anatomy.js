/* Display-only anatomy hints. Never mutates motion, joints, or bone lengths. */
function coverageParts(names,parents){
  const parts=[];
  for(const side of ['Left','Right']){
    const wrist=names.indexOf(side+'Wrist');
    const end=parents.findIndex((p,j)=>p===wrist&&names[j].includes('EndSite'));
    if(wrist>=0&&end>=0)parts.push({kind:'hand',side,indices:[wrist,end]});
    const ankle=names.indexOf(side+'Ankle'),toe=names.indexOf(side+'Toe');
    const tip=parents.findIndex((p,j)=>p===toe&&names[j].includes('EndSite'));
    if(ankle>=0&&toe>=0&&tip>=0)parts.push({kind:'foot',side,indices:[ankle,toe,tip]});
  }
  return parts;
}
function drawCoverageAnatomy(ctx,project,c,pose,scale,height,options){
  const color=name=>name.includes('Left')?'#176eaf':name.includes('Right')?'#bf593b':'#19334e';
  const parts=coverageParts(c.names,c.parents),hidden=new Set();
  if(options.shapes)for(const p of parts)for(const j of p.indices.slice(1))hidden.add(j);
  const line=(a,b,stroke,width)=>{ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke()};
  const bones=c.parents.map((p,j)=>({p,j,z:project(pose[j])[2]}))
    .filter(b=>b.p!==null&&!(b.p===0&&c.hips!==0)&&!(c.names[b.p]==='Head'&&c.names[b.j].includes('EndSite')))
    .sort((a,b)=>a.z-b.z);
  ctx.lineCap='round';ctx.lineJoin='round';
  for(const {p,j} of bones){
    if(hidden.has(j))continue;
    const a=project(pose[p]),b=project(pose[j]),end=c.names[j].includes('EndSite');
    line(a,b,color(c.names[j]),end?1.5:4);
    // Actual articulated joints are dots; terminal offsets are not joints.
    if(!end){ctx.fillStyle=color(c.names[j]);ctx.beginPath();ctx.arc(b[0],b[1],3,0,Math.PI*2);ctx.fill()}
  }
  if(options.shapes){
    for(const part of parts){
      const points=part.indices.map(j=>project(pose[j]));
      // A screen-space schematic only, not a fitted hand/foot mesh or collision shape.
      const a=points[0],b=points.at(-1),dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
      if(length<1){ctx.fillStyle=color(part.side);ctx.beginPath();ctx.arc(a[0],a[1],4,0,Math.PI*2);ctx.fill();continue}
      const nx=-dy/length,ny=dx/length,w=scale*height*(part.kind==='hand'?.019:.023);
      const sections=part.kind==='hand'
        ?[[a[0],a[1],w*.35],[a[0]+dx*.35,a[1]+dy*.35,w],[a[0]+dx*.8,a[1]+dy*.8,w*.85],[b[0],b[1],w*.3]]
        :[[a[0],a[1],w*.65],[points[1][0],points[1][1],w],[b[0],b[1],w*.55]];
      const outline=[...sections.map(([x,y,r])=>[x+nx*r,y+ny*r]),...sections.toReversed().map(([x,y,r])=>[x-nx*r,y-ny*r])];
      ctx.beginPath();outline.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.closePath();
      ctx.fillStyle=part.side==='Left'?'#d7eaf6':'#f3ded3';ctx.fill();ctx.strokeStyle=color(part.side);ctx.lineWidth=2;ctx.stroke();
      // Wrist/ankle remain at their unmodified coordinates; toe is a smaller joint dot.
      for(const j of part.indices.filter(j=>!c.names[j].includes('EndSite'))){const p=project(pose[j]);ctx.fillStyle=color(part.side);ctx.beginPath();ctx.arc(p[0],p[1],j===part.indices[0]?3:2,0,Math.PI*2);ctx.fill()}
    }
  }
  if(options.ends){
    c.names.forEach((name,j)=>{if(!name.includes('EndSite')||c.names[c.parents[j]]==='Head')return;
      const p=project(pose[j]);ctx.strokeStyle=color(name);ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(p[0],p[1]-4);ctx.lineTo(p[0]+4,p[1]);ctx.lineTo(p[0],p[1]+4);ctx.lineTo(p[0]-4,p[1]);ctx.closePath();ctx.stroke();});
  }
  const head=c.names.indexOf('Head');
  if(head>=0){const end=c.parents.findIndex((p,j)=>p===head&&c.names[j].includes('EndSite'));
    const center=end>=0?pose[head].map((v,k)=>(v+pose[end][k])/2):pose[head],p=project(center);
    ctx.strokeStyle='#19334e';ctx.lineWidth=3;ctx.beginPath();ctx.arc(p[0],p[1],Math.max(5,scale*height*.035),0,Math.PI*2);ctx.stroke();}
  if(options.labels){
    const labels={Shoulder:'肩',Elbow:'肘',Wrist:'腕',Hip:'髋',Knee:'膝',Ankle:'踝',Toe:'脚趾关节'};
    ctx.font='13px -apple-system, sans-serif';ctx.textBaseline='middle';
    for(const side of ['Left','Right']){
      const left=side==='Left';
      const tags=Object.entries(labels).flatMap(([suffix,label])=>{
        const j=c.names.indexOf(side+suffix);if(j<0)return [];
        const p=project(pose[j]);
        return [{p,x:p[0]+(left?-82:30),y:p[1]+(suffix==='Toe'?18:0),text:(left?'左':'右')+label}];
      }).sort((a,b)=>a.y-b.y);
      // Separate nearby labels only; leader lines keep the true joint location explicit.
      for(let i=1;i<tags.length;i++)tags[i].y=Math.max(tags[i].y,tags[i-1].y+22);
      for(const {p,x,y,text} of tags){
      const tw=ctx.measureText(text).width;
      line(p,[left?x+tw+3:x-3,y],'#8b9ba8',1);
      ctx.fillStyle='#f9fcff';ctx.fillRect(x-3,y-9,tw+6,18);ctx.fillStyle=color(side);ctx.fillText(text,x,y);
      }
    }
  }
}
if(typeof module!=='undefined')module.exports={coverageParts,drawCoverageAnatomy};
