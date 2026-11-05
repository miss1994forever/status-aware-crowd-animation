"""Atomically queue one bounded run for the already-open Unity editor."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'outputs/unity-submission'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    parser.add_argument('--scenario', choices=['crowd', 'headon', 'crossing'], default='crowd')
    parser.add_argument('--spatial', choices=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], type=int, default=0)
    parser.add_argument('--status-pattern', choices=['cycle', 'low-high', 'high-low'], default='cycle')
    parser.add_argument('--fixed-expression', type=float, choices=[-1, 0, .5, 1], default=-1)
    parser.add_argument('--expression-version', type=int, choices=[0,1,2], default=0)
    parser.add_argument('--posture-expression', action='store_true', help='10-degree torso and 8-degree head pitch, stable legs only')
    parser.add_argument('--body-response', action='store_true')
    parser.add_argument('--expression-reference', type=Path, help='JSON with measured Unity E/H center and scale')
    parser.add_argument('--head-filter-level', type=int, choices=[1,2], default=1)
    parser.add_argument('--head-stability', action='store_true', help='Damp head orientation relative to upper chest, without a gaze target')
    parser.add_argument('--route-recovery', action='store_true', help='Use consumed detour budget to discourage retreat and allow brief waiting')
    parser.add_argument('--status-yield', action='store_true', help='Extend passage yielding to crossing traffic and strengthen own route persistence')
    parser.add_argument('--lateral-steps', action='store_true', help='Experimental bounded native facing hold for diagonal/side steps')
    parser.add_argument('--repeat', action='store_true', help='Diagnostic: retain the historical return journeys')
    parser.add_argument('--video', action='store_true', help='Capture two 15-Hz views for subsequent MP4 encoding')
    parser.add_argument('--lower-body', type=int, choices=[0, 1, 2], default=2)
    parser.add_argument('--clip-fps', type=int, choices=[15, 30, 60], default=15)
    parser.add_argument('--clip-actor', type=int, choices=range(30), default=9)
    parser.add_argument('--knee-diagnostics', action='store_true')
    parser.add_argument('--legacy-search', action='store_true', help='Diagnostic only: reproduce upstream ownership leak')
    parser.add_argument('--duration', type=float, default=35)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', args.run):
        parser.error('Invalid run name')
    if not 1 <= args.duration <= 120:
        parser.error('Duration must be 1–120 seconds')
    if (ROOT / args.run).exists() or (ROOT / 'run.request').exists():
        parser.error('Output already exists or another request is pending')
    config = dict(run=args.run, scenario=args.scenario, spatial=args.spatial,
                  duration=args.duration, mode=1, seed=806, fps=60, count=10,singlePass=not args.repeat,lateralSteps=args.lateral_steps,statusYield=args.status_yield,routeRecovery=args.route_recovery,headStability=args.head_stability,headFilterLevel=args.head_filter_level,
                  responsePose=False, ownedSearch=not args.legacy_search, video=args.video,
                  lowerBody=args.lower_body, kneeDiagnostics=args.knee_diagnostics,
                  clipStride=60//args.clip_fps,clipActor=args.clip_actor,statusPattern=args.status_pattern,
                  fixedExpression=args.fixed_expression,width=1280,height=720)
    config.update(expressionVersion=args.expression_version, bodyResponse=args.body_response, postureExpression=args.posture_expression)
    if args.body_response and (args.expression_version == 0 or not args.expression_reference):
        parser.error('Body response requires expression version 1 and a measured Unity reference')
    if args.expression_reference:
        ref = json.loads(args.expression_reference.read_text())
        for key in ('expressionECenter','expressionEScale','expressionHCenter','expressionHScale'):
            config[key] = float(ref[key])
    pending = ROOT / 'run.pending'
    # Exclusive creation protects against two local writers using this helper.
    with pending.open('x') as handle:
        json.dump(config, handle)
    pending.replace(ROOT / 'run.request')
    print(f'Queued {args.run}; completion still requires telemetry, logs and visual checks.')
