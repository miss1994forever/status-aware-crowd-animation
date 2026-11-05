"""Render measured offline bone poses to an H.264 preview, without Unity or pose exaggeration."""
from pathlib import Path
import json,math,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/individual-expression-candidate'
W,H,FPS=1440,900,30
FONT='/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
FONTS={s:ImageFont.truetype(FONT,s) for s in (16,18,20,22,28,34)}
BG='#f5f5f1';INK='#253237';BLUE='#33758c';ORANGE='#b87347'

def text(draw,xy,label,size=20,fill=INK,anchor=None):
    draw.text(xy,label,font=FONTS[size],fill=fill,anchor=anchor)

def basis(p,names):
    a,b=(p[names.index(s)] for s in ('UpperArm_L','UpperArm_R'))
    r=[b[0]-a[0],0,b[2]-a[2]];n=math.hypot(r[0],r[2]);r=[x/n for x in r]
    return r,[-r[2],0,r[0]]

def draw_pose(draw,pose,source,names,parents,center,b,yaw,ghost=False):
    scale,floor=360,620;r,f=b;root=source[names.index('Hips')]
    def project(v):
        d=[v[0]-root[0],v[1],v[2]-root[2]]
        x=sum(d[k]*r[k] for k in range(3))*math.cos(yaw)+sum(d[k]*f[k] for k in range(3))*math.sin(yaw)
        return center+x*scale,floor-v[1]*scale
    points=[project(p) for p in pose]
    for j,parent in enumerate(parents):
        if parent is None:continue
        name=names[j];color='#ccd1cf' if ghost else BLUE if '_L' in name else ORANGE if '_R' in name else '#556167'
        width=2 if ghost else 2 if 'EndSite' in name else 5
        draw.line([points[parent],points[j]],fill=color,width=width)
    if not ghost:
        for j,(x,y) in enumerate(points):
            radius=9 if names[j]=='Head' else 3
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=BG,outline='#4d5b61',width=2)

def frame_image(scene,index,total_index,total_frames):
    im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
    feedback=scene['kind']=='feedback';row=scene['frames'][index]
    title=scene['title'];text(d,(48,30),title,34)
    text(d,(W-48,42),scene['chapter'],22,fill='#6c7776',anchor='ra')
    text(d,(48,84),scene['subtitle'],20,fill='#52625f')
    text(d,(48,117),'浅灰为同帧原骨架；主画面保持真实幅度，下方局部放大 2×。',18,fill='#6a7471')
    centers=[420,1020] if feedback else [240,720,1200]
    names,parents=scene['names'],scene['parents'];source=row['source'];b=scene['basis']
    poses=row['poses'];yaw=scene.get('yaw',0)
    for actor,(center,pose,label) in enumerate(zip(centers,poses,scene['labels'])):
        text(d,(center,164),label,22,anchor='ma')
        x0=center-(250 if feedback else 215);x1=center+(250 if feedback else 215)
        d.line((x0,620,x1,620),fill='#cfd7d1',width=2)
        draw_pose(d,source,source,names,parents,center,b,yaw,True)
        draw_pose(d,pose,source,names,parents,center,b,yaw)
        if feedback:
            text(d,(center,645),f"紧缩目标 {row['targets'][actor]:.3f}   互动偏移 {row['offsets'][actor]:+.3f}",20,anchor='ma')
        else:
            hip=names.index('Hips');lower=source[hip][1]-pose[hip][1]
            text(d,(center,645),f'胯部下降 {lower*100:.2f}% 参考身高',18,anchor='ma',fill='#5d6c67')
    # Crop already drawn geometry; this changes only display scale, never body parameters.
    # Track the source reference only, so lowering is not cancelled by inset alignment.
    reference_y=sum(source[names.index(k)][1]*weight for k,weight in
                    [('LowerArm_L',1),('LowerArm_R',1),('Hips',2)])/4
    crop_center=620-360*reference_y
    crops=[im.crop((int(c-73),int(crop_center-39),int(c+73),int(crop_center+39))).resize((292,156),Image.Resampling.LANCZOS) for c in centers]
    for center,crop in zip(centers,crops):
        text(d,(center,681),'肘部／胯部局部 · 2×',18,anchor='ma',fill='#5a6964')
        im.paste(crop,(int(center-146),709));d.rectangle((center-147,708,center+146,865),outline='#d3dbd5',width=1)
    text(d,(48,876),'离线骨架预览 · 非 Unity 录屏  |  动作：Bandai Namco Research · CC BY-NC 4.0',16,fill='#67726b')
    text(d,(W-48,876),f'{total_index/FPS:04.1f}s',16,anchor='ra',fill='#67726b')
    d.rectangle((0,H-4,W*(total_index+1)/total_frames,H),fill=BLUE)
    return im

def main():
    combined=json.loads((OUT/'combination-replay.json').read_text())
    reconstructed=json.loads((OUT/'video-feedback-poses.json').read_text())
    scenes=[]
    for chapter,c in enumerate(combined['clips']):
        variants=c['variants'];frames=[]
        for f in range(len(variants['source'])):
            frames.append({'source':variants['source'][f],'poses':[variants[k][f] for k in ('source','arms','target')]})
        scenes.append({'kind':'channels','title':'身体通道对照 · '+('向前行走' if c['id']=='M01' else '侧移'),
                       'subtitle':'同一源动作、同一时间与尺度；右两栏使用相同的最大表达目标。',
                       'chapter':f'0{chapter+1} / 04','labels':['原动作','仅修改手臂','手臂＋胯部高度'],
                       'names':c['names'],'parents':c['parents'],'frames':frames,
                       'basis':basis(variants['source'][0],c['names']),'yaw':0 if c['id']=='M01' else .35})
    for c in reconstructed['scenes']:
        moving=c['scenario'].endswith('moving')
        scenes.append({'kind':'feedback','title':'双向互动 · 不同初始偏移' if moving else '端点诊断 · 互动被裁剪',
                       'subtitle':'双方通过修改后的可见骨点回应彼此；相遇上下文固定，源动作循环。' if moving else '固定同一源姿态；这组初始状态中，有效互动偏移始终为零。',
                       'chapter':'03 / 04' if moving else '04 / 04',
                       'labels':['A · 自身 status = 0.5','B · 自身 status = 0.5'] if moving else ['A · 自身 status = 0','B · 自身 status = 1'],
                       'names':c['names'],'parents':c['parents'],'frames':c['frames'],
                       'basis':basis(c['frames'][0]['source'],c['names']),'yaw':0})
    total_frames=sum(len(s['frames']) for s in scenes);video=OUT/'example-animation.mp4'
    args=['/opt/homebrew/bin/ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
          '-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19',
          '-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
    index=0;stills=[];chapters=[]
    with (OUT/'video-encode.log').open('wb') as log:
        process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
        for scene in scenes:
            chapters.append({'title':scene['title'],'start':index/FPS,'duration':len(scene['frames'])/FPS})
            selected=min(len(scene['frames'])-1,90)
            for f in range(len(scene['frames'])):
                im=frame_image(scene,f,index,total_frames)
                if f==selected:stills.append(im.copy())
                if not stills and index==0:im.save(OUT/'video-first-frame.png')
                process.stdin.write(im.tobytes());index+=1
            print('Rendered '+scene['title'],flush=True)
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('ffmpeg failed; inspect video-encode.log')
    stills[0].save(OUT/'example-animation-poster.jpg',quality=92)
    sheet=Image.new('RGB',(1440,900),'white')
    for i,im in enumerate(stills):sheet.paste(im.resize((720,450),Image.Resampling.LANCZOS),((i%2)*720,(i//2)*450))
    sheet.save(OUT/'example-animation-contact-sheet.jpg',quality=93)
    paths=['combination-replay.json','body-feedback-audit.json','video-feedback-poses.json']
    report={'kind':'offline skeleton example video; original-scale channel comparison plus feedback-parameter reconstruction',
            'video':video.name,'frames':total_frames,'fps':FPS,'duration':total_frames/FPS,'width':W,'height':H,'chapters':chapters,
            'input_sha256':{p:hashlib.sha256((OUT/p).read_bytes()).hexdigest() for p in paths},
            'limits':['not Unity recording or perception validation','feedback knees reconstructed from retained 30Hz parameters, not lossless original frames',
                      'source loop seams retained','main skeleton unexaggerated; explicitly labelled 2x inset',
                      'frozen approach context not physical navigation or actual passing'],
            'source':'Bandai Namco Research Inc.; revision 74ead3ba1ae4696404e6086233779f60de8bf9ef; CC BY-NC 4.0; modified FK poses'}
    (OUT/'example-animation-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (OUT/'video-review.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>身体表达示例视频</title><style>body{max-width:1100px;margin:32px auto;padding:0 20px;background:#f5f5f1;color:#253237;font:17px/1.7 system-ui}h1{font-size:26px}video{width:100%;border-radius:8px;background:#fff}a{color:#33758c}</style><h1>身体表达 · 示例动画</h1><p>先比较同一动作的原骨架、手臂修改与高度组合，再看双向互动和端点裁剪。主画面保持真实修改幅度，下方为标明的2倍局部放大。</p><video controls preload="metadata" playsinline poster="example-animation-poster.jpg" src="example-animation.mp4"></video><p>离线骨架预览，非Unity录屏。互动部分按记录参数重建；不代表导航、自然度或地位感知已验收。</p><p><a href="example-animation.mp4" download>下载 MP4</a> · <a href="example-animation-manifest.json">来源与片段说明</a></p></html>''')
    print(video,flush=True)

if __name__=='__main__':main()
