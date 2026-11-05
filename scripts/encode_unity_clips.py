"""Encode actual Unity camera frames at their simulation cadence; no interpolation."""
import argparse
import csv
import json
import subprocess
from pathlib import Path

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    config = json.loads((args.run / 'config.json').read_text())
    if not (args.run / 'finished.txt').exists() or not config.get('video'):
        parser.error('Requires a completed run with video capture enabled')
    first = next(csv.DictReader((args.run / 'telemetry.csv').open()))
    stride = config.get('clipStride', 4)
    metadata = dict(fps=config['fps']/stride, first_capture_simulated_seconds=float(first['dt'])+(stride-1)/config['fps'], views={})
    for view in ('wide', 'close'):
        source = args.run / ('clip-' + view)
        files = sorted(source.glob('*.jpg'))
        if not files or [int(p.stem) for p in files] != list(range(len(files))):
            raise ValueError(f'Missing or noncontiguous frames: {source}')
        destination = args.run / (view + '.mp4')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                        '-framerate', str(config['fps']/stride), '-start_number', '0',
                        '-i', str(source / '%05d.jpg'), '-c:v', 'libx264', '-threads', '2',
                        '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(destination)], check=True)
        metadata['views'][view] = dict(frames=len(files), seconds=len(files)/(config['fps']/stride), file=str(destination))
    (args.run / 'clip-metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2))
