"""IE05 comparisons and direct per-step interaction export; no trace reconstruction."""
from pathlib import Path
import json,math,subprocess,hashlib
from PIL import Image,ImageDraw,ImageFont
import render_example_video as base

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'outputs/individual-expression-candidate'
W,H,FPS=1440,900,30
def sub(a,b):return [x-y for x,y in zip(a,b)]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def unit(a):
    n=math.sqrt(dot(a,a));return [v/max(n,1e-15) for v in a]
def render(scene,frame,index,total):
    im=Image.new('RGB',(W,H),base.BG);d=ImageDraw.Draw(im);live=scene['kind']=='interactive'
    source=frame['source'];names=scene['names'];parents=scene['parents'];b=base.basis(source,names);yaw=scene['yaw']
    centers=[420,1020] if live else [144+288*i for i in range(5)]
    labels=['A · status 0.2','B · status 0.8'] if live else scene['labels']
    base.text(d,(38,28),scene['title'],28);base.text(d,(1400,35),scene['chapter'],20,fill='#64736b',anchor='ra')
    base.text(d,(38,78),'现场函数逐帧执行；双方读取对方上一轮可见骨点。新版本个人基底保留15%互动余量。' if live else '相同源帧、速度与表达目标 c=0.8；逐项加入身体通道，原动作列保留 c=0。',18)
    base.text(d,(38,112),'浅灰：同帧原骨架；头部短线表示朝向；下方头颈／胸部放大2倍。',18,fill='#63716a')
    hip=names.index('Hips');head=names.index('Head');tip=names.index('Head:EndSite')
    r,f=b
    def project(v,c):
        delta=[v[0]-source[hip][0],v[1],v[2]-source[hip][2]]
        return c+(dot(delta,r)*math.cos(yaw)+dot(delta,f)*math.sin(yaw))*360,620-v[1]*360
    for i,(c,label,a) in enumerate(zip(centers,labels,frame['actors'])):
        base.text(d,(c,164),label,18,anchor='ma')
        d.line((c-(245 if live else 132),620,c+(245 if live else 132),620),fill='#cfd7d1',width=1)
        base.draw_pose(d,source,source,names,parents,c,b,yaw,True)
        base.draw_pose(d,a['pose'],source,names,parents,c,b,yaw)
        # Orientation marker derived from the displayed head segment, same rule in every column.
        up=unit(sub(a['pose'][tip],a['pose'][head]));right=b[0]
        forward=[right[1]*up[2]-right[2]*up[1],right[2]*up[0]-right[0]*up[2],right[0]*up[1]-right[1]*up[0]]
        forward=unit(forward);nose=[a['pose'][head][k]+forward[k]*.037*scene['sign'] for k in range(3)]
        d.line((project(a['pose'][head],c),project(nose,c)),fill='#556167',width=2)
        base.text(d,(c,645),f"躯干 {a['torso']:.1f}°  头颈 {a['head']:.1f}°",18,anchor='ma')
        if live:base.text(d,(c,673),f"紧缩 {a['target']:.3f}  互动 {a['offset']:+.3f}",18,anchor='ma')
        else:base.text(d,(c,673),f"下降 {100*a['lowering']:.2f}% 身高",16,anchor='ma',fill='#64716b')
    cy=(project(source[head],0)[1]+project(source[names.index('Chest')],0)[1])/2
    crops=[im.crop((int(c-68),int(cy-40),int(c+68),int(cy+40))).resize((272,160),Image.Resampling.LANCZOS) for c in centers]
    for c,crop in zip(centers,crops):im.paste(crop,(int(c-136),706));d.rectangle((c-137,705,c+136,866),outline='#d3dbd5')
    base.text(d,(38,878),'独立C#离线骨架 · 未接入Unity  |  动作：Bandai Namco Research · CC BY-NC 4.0',16,fill='#64716b')
    base.text(d,(1400,878),f'{index/FPS:.1f}s',16,anchor='ra',fill='#64716b');d.rectangle((0,896,W*(index+1)/total,900),fill=base.BLUE)
    return im

def sign_for(scene):
    n=scene['names'];score=0
    for row in scene['frames']:
        p=row['source'];r,f=base.basis(p,n)
        for side in ('L','R'):
            h,k,a=[p[n.index(s+'_'+side)] for s in ('UpperLeg','LowerLeg','Foot')]
            axis=unit(sub(a,h));v=sub(k,h);bend=[v[j]-axis[j]*dot(v,axis) for j in range(3)]
            score+=dot(bend,f)
    return 1 if score>=0 else -1

def main():
    data=json.loads((OUT/'round5-poses.json').read_text());comparison={s['id']:s for s in data['scenes'] if s['kind']=='comparison'};scenes=[]
    for id,yaw,title in [('M01',0,'行走 · 正面身体通道对照'),('M01',math.pi/2,'行走 · 侧面观察躯干与头颈'),('M07',.9,'侧移 · 身体组合对照')]:
        scene=dict(comparison[id]);scene.update(yaw=yaw,title=title);scene['sign']=sign_for(scene);scenes.append(scene)
    live=next(s for s in data['scenes'] if s['kind']=='interactive');rows=live['frames'];scene={'kind':'interactive','names':rows[0]['names'],'parents':rows[0]['parents'],'frames':rows,'yaw':math.pi/2,'title':'双向互动 · 加强组合逐帧运行'};scene['sign']=sign_for(scene);scenes.append(scene)
    total=sum(len(s['frames']) for s in scenes);index=0;stills=[];chapters=[]
    with (OUT/'round5-encode.log').open('wb') as log:
        p=subprocess.Popen(['/opt/homebrew/bin/ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'round5-animation.mp4')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
        for k,scene in enumerate(scenes):
            scene['chapter']=f'{k+1:02d} / 04';chapters.append({'title':scene['title'],'start':index/FPS,'duration':len(scene['frames'])/FPS})
            for f,row in enumerate(scene['frames']):
                im=render(scene,row,index,total)
                if f==min(90,len(scene['frames'])-1):stills.append(im.copy())
                p.stdin.write(im.tobytes());index+=1
            print(scene['title'],flush=True)
        p.stdin.close()
        if p.wait()!=0:raise RuntimeError('video encoding failed')
    stills[1].save(OUT/'round5-poster.jpg',quality=93);sheet=Image.new('RGB',(1440,900))
    for i,im in enumerate(stills):sheet.paste(im.resize((720,450),Image.Resampling.LANCZOS),((i%2)*720,(i//2)*450))
    sheet.save(OUT/'round5-contact-sheet.jpg',quality=94)
    (OUT/'round5-video-manifest.json').write_text(json.dumps({'fps':FPS,'duration':total/FPS,'chapters':chapters,'input_sha256':hashlib.sha256((OUT/'round5-poses.json').read_bytes()).hexdigest(),'kind':'actual per-step C# output rendered directly; no feedback trace reconstruction; independent of Unity'},ensure_ascii=False,indent=2))
    (OUT/'round5-review.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>下一轮身体组合</title><style>body{max-width:1200px;margin:30px auto;padding:0 20px;font:17px/1.7 system-ui;color:#253237;background:#f5f5f1}video{width:100%;background:#fff}a{color:#33758c}</style><h1>身体组合 · 下一轮</h1><p>比较现有组合、加强手臂／高度、加入躯干、加入头颈。正面之后有同一动作的侧面对照。</p><video controls playsinline preload="metadata" poster="round5-poster.jpg" src="round5-animation.mp4"></video><p><a href="http://127.0.0.1:8790/">打开实时预览：调status、距离和互动开关</a> · <a href="round5-animation.mp4" download>下载MP4</a></p><p>视频与实时预览使用同一套C#身体及响应函数。独立骨架版，尚未接入Unity；新增姿态的自然度和人物印象仍需评价。</p></html>''')
    print('saved round5-animation.mp4',flush=True)

if __name__=='__main__':main()
