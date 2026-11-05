"""Check fixed-condition runs and report measured repeatability, without perceptual claims."""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path


def read_run(path):
    config = json.loads((path / 'config.json').read_text())
    rows = list(csv.DictReader((path / 'telemetry.csv').open()))
    samples = {(int(r['frame']), int(r['id'])): r for r in rows}
    if len(samples) != len(rows):
        raise ValueError('Duplicate frame/actor samples')
    errors = []
    if (path / 'INVALID.txt').exists():
        errors.append('Run explicitly invalidated: ' + (path / 'INVALID.txt').read_text().strip())
    if config.get('ownedSearch'):
        runtime_path = path / 'runtime-config.json'
        if not runtime_path.exists():
            errors.append('Missing actual runtime settings for owned search')
        else:
            runtime = json.loads(runtime_path.read_text())
            if not runtime.get('ownedSearch') or runtime.get('spatial') != config['spatial']:
                errors.append('Actual search/spatial settings differ from request')
            for flag in ('waitFacing','softWait'):
                if flag in config and runtime.get(flag, False) != config[flag]:
                    errors.append('Actual '+flag+' differs from request')
            if 'headStability' in config and runtime.get('headStability', False) != config['headStability']:
                errors.append('Actual head stabilization differs from request')
            if 'routeRecovery' in config and runtime.get('routeRecovery', False) != config['routeRecovery']:
                errors.append('Actual route recovery differs from request')
            if 'statusYield' in config and runtime.get('statusYield', False) != config['statusYield']:
                errors.append('Actual status yielding differs from request')
            if 'lateralSteps' in config and runtime.get('lateralSteps') != config['lateralSteps']:
                errors.append('Actual facing mode differs from request')
            if 'singlePass' in config and runtime.get('singlePass') != config['singlePass']:
                errors.append('Actual journey lifecycle differs from request')
            if 'lowerBody' in config and runtime.get('lowerBody') != config['lowerBody']:
                errors.append('Actual lower-body policy differs from request')
            if runtime.get('build') not in ('s1b-owned-reserve-v1', 's1b-nearfield-v2', 'knee-ik-v3', 'social-space-v4', 'social-space-v5', 'social-space-v6','social-space-v7','social-space-v8','social-space-v9','social-space-v10','social-space-v11','social-space-v12', 'social-space-v13','social-space-v14','social-space-v15','social-space-v16','social-space-v17','social-space-v18','social-space-v19','social-space-v20','social-space-v21','social-space-v22','social-space-v23'):
                errors.append('Unexpected runtime build marker')
        if not (path / 'compiled-sha256.txt').exists():
            errors.append('Missing compiled assembly hashes')
    expected_count = config['count'] if config['scenario'] == 'crowd' else 2
    if not (path / 'finished.txt').exists():
        errors.append('Run did not finish')
    if len({r['id'] for r in rows}) != expected_count:
        errors.append('Unexpected actor count')
    # Start changes captureDeltaTime after Unity has already determined frame 1's dt.
    # Keep this startup step visible rather than pretending the whole run is fixed.
    if any(abs(float(r['dt']) - 1 / config['fps']) > 1e-6 for r in rows if int(r['frame']) > 1):
        errors.append('Simulation step differs from configuration')
    if any(r['target_id'] != r['belief_target_id'] for r in rows):
        errors.append('Belief is bound to the wrong target')
    if any(int(r['target_id']) < 0 and abs(float(r['belief']) - .5) > 1e-6 for r in rows):
        errors.append('Released target retained a non-neutral belief')
    if config.get('expressionVersion', 0) >= 1:
        from audit_unity_expression import audit as audit_expression
        try:
            audit_expression(path)
        except (AssertionError, ValueError) as exc:
            errors.append('Expression checks: ' + str(exc))
        for key in ('expressionVersion', 'bodyResponse', 'expressionECenter', 'expressionEScale', 'expressionHCenter', 'expressionHScale'):
            actual, requested = runtime.get(key), config.get(key)
            if actual is None or requested is None or abs(float(actual)-float(requested)) > 1e-6:
                errors.append('Expression runtime mismatch: ' + key)
    elif not config['responsePose']:
        if any(abs(float(r['arm_deg']) - 12 * (1 - (config['fixedExpression'] if config.get('fixedExpression', -1) >= 0 else float(r['status'])))) > 1e-4
               for r in rows if int(r['pose_updates']) > 0):
            errors.append('Own expression did not remain fixed')
        if any(int(r['response_pose']) != 0 for r in rows):
            errors.append('Response pose was enabled')
    if max(float(r['time']) for r in rows) + 1e-4 < config['duration']:
        errors.append('Final telemetry does not cover configured duration')
    for index in range(3):
        if config['duration'] > [5, 12, 25][index]:
            for view in ('wide', 'close'):
                if not (path / f'frame-{index}-{view}.png').exists():
                    errors.append(f'Missing frame {index} {view}')
    return config, samples, dict(
        run=path.name, checks_passed=not errors, errors=errors,
        actor_count=expected_count, sample_count=len(rows),
        simulated_seconds=max(float(r['time']) for r in rows),
        startup_dt_seconds=float(rows[0]['dt']),
        step_qualification='Frame 1 uses Unity startup dt; frames 2 onward use configured capture delta.',
        target_resets=max(int(r['belief_resets']) for r in rows),
        max_foot_target_error_m=max(float(r['foot_error']) for r in rows),
        source_manifest_sha256=hashlib.sha256((path / 'source-sha256.txt').read_bytes()).hexdigest())


if __name__ == '__main__':
    paths = [Path(arg) for arg in sys.argv[1:]]
    runs = [read_run(path) for path in paths]
    result = dict(runs=[r[2] for r in runs], qualification='Engineering checks only; images require visual review.')
    if len(runs) == 2:
        a, b = runs
        config_a, config_b = ({k: v for k, v in r[0].items() if k != 'run'} for r in runs)
        same_keys = a[1].keys() == b[1].keys()
        distances = [math.hypot(float(a[1][k]['x']) - float(b[1][k]['x']),
                                float(a[1][k]['z']) - float(b[1][k]['z']))
                     for k in a[1].keys() & b[1].keys()]
        result['repeatability'] = dict(
            same_config=config_a == config_b,
            same_sources=a[2]['source_manifest_sha256'] == b[2]['source_manifest_sha256'],
            same_frame_actor_keys=same_keys,
            max_sample_position_difference_m=max(distances, default=None),
            rms_sample_position_difference_m=math.sqrt(sum(d*d for d in distances)/len(distances)) if distances else None,
            identical_logged_samples=same_keys and all(
                {k:v for k,v in a[1][key].items() if k != 'real_dt'} ==
                {k:v for k,v in b[1][key].items() if k != 'real_dt'} for key in a[1]))
    output = paths[0].parent / ('s0-repeatability.json' if len(runs) == 2 else paths[0].name + '-s0-audit.json')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if any(not r[2]['checks_passed'] for r in runs):
        raise SystemExit(1)
