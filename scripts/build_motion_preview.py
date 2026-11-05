"""Build a self-contained, offline BVH inspection page using only Python stdlib."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.bvh import load


def build(manifest_path=ROOT / 'data/pilot_manifest.json', destination=ROOT / 'outputs/preview'):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    clips, evidence = [], []
    for i, entry in enumerate(manifest['entries']):
        path = ROOT / entry['file']
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise ValueError(f'Source hash mismatch: {path}')
        motion = load(path)
        poses = [motion.positions(frame, translation_mode='channels_replace_offset') for frame in range(len(motion.frames))]
        hips = next((j for j, joint in enumerate(motion.joints) if joint.name == 'Hips'), 0)
        # Exclude synthetic root at origin from body bounds and display bones.
        body = [p[j] for p in poses for j in range(len(motion.joints)) if j != 0 or hips == 0]
        bounds = [[min(p[a] for p in body), max(p[a] for p in body)] for a in range(3)]
        hips_bounds = [[min(p[hips][a] for p in poses), max(p[hips][a] for p in poses)] for a in range(3)]
        radius = max(max(abs(p[j][a] - p[hips][a]) for p in poses for j in range(1, len(p))) for a in (0, 2))
        clip = dict(id=f'M{i+1:02}', content=entry['source_content'], style=entry['source_style'],
                    source=path.name, sourceUrl=entry['source_url'], sha256=digest, frameTime=motion.frame_time,
                    duration=motion.duration, translationMode='channels_replace_offset', hips=hips, names=[j.name for j in motion.joints],
                    parents=[j.parent for j in motion.joints], bounds=bounds, hipsBounds=hips_bounds,
                    radius=radius, poses=[[[round(v, 5) for v in joint] for joint in pose] for pose in poses])
        clips.append(clip)
        evidence.append({k: v for k, v in clip.items() if k != 'poses'})
    template = (ROOT / 'preview/index.html').read_text(encoding='utf-8')
    template = template.replace('/*__PLAYER_HELPER__*/', (ROOT / 'preview/player.js').read_text(encoding='utf-8'))
    data = dict(creator=manifest['creator'], license=manifest['license'], revision=manifest['revision'], clips=clips)
    html = template.replace('/*__MOTION_DATA__*/', json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'index.html').write_text(html, encoding='utf-8')
    (destination / 'LICENSE.txt').write_bytes((ROOT / 'data/raw/bandai-pilot/LICENSE').read_bytes())
    (destination / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(clips)} clips → {destination / "index.html"}')
    return clips


if __name__ == '__main__':
    build()
