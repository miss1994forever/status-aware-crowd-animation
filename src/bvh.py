"""Strict BVH reader for the first motion-data feasibility experiment.

Standard library only. Preserves channel order and source units; does not
infer status or retarget a skeleton.
"""
from dataclasses import dataclass
import argparse
import json
import math
from pathlib import Path
import re


@dataclass
class Joint:
    name: str
    parent: int | None
    offset: tuple[float, float, float]
    channels: list[str]
    channel_start: int


@dataclass
class Motion:
    joints: list[Joint]
    frame_time: float
    frames: list[list[float]]

    @property
    def duration(self):
        """Each sample is held for frame_time, including the last sample."""
        return len(self.frames) * self.frame_time

    def frame_at(self, seconds: float, loop: bool = True) -> int:
        if not math.isfinite(seconds):
            raise ValueError("Playback time must be finite")
        seconds = seconds % self.duration if loop else max(0, seconds)
        return min(int(seconds / self.frame_time), len(self.frames) - 1)

    def positions(self, frame: int, *, translation_mode: str = 'offset_plus_channels') -> list[tuple[float, float, float]]:
        """Column-vector FK with an explicit translation convention.

        Legacy ``offset_plus_channels`` adds animated translations to OFFSET.
        Bandai's six-channel data, consistent with its reference Blender
        ARMATURE import, needs ``channels_replace_offset``: on translated
        axes the channel is the local position, not an extra offset.
        Unanimated axes and end sites retain OFFSET. Replacement mode requires
        translations before rotations (as in all current Bandai clips).
        Rotations are post-multiplied in declared order. Source units retained.
        No interpolation: the viewer holds each recorded frame for frame_time.
        """
        if not 0 <= frame < len(self.frames):
            raise IndexError("Frame outside motion")
        if translation_mode not in ('offset_plus_channels', 'channels_replace_offset'):
            raise ValueError('Unknown translation convention')
        worlds = []
        result = []
        for joint in self.joints:
            offset = list(joint.offset)
            if translation_mode == 'channels_replace_offset':
                rotation_seen = False
                for channel in joint.channels:
                    if channel.endswith('rotation'):
                        rotation_seen = True
                    else:
                        if rotation_seen:
                            raise ValueError('Replacement convention requires translations before rotations')
                        offset['XYZ'.index(channel[0])] = 0.
            local = translation(*offset)
            for i, channel in enumerate(joint.channels):
                value = self.frames[frame][joint.channel_start + i]
                axis = "XYZ".index(channel[0])
                if channel.endswith("position"):
                    xyz = [0., 0., 0.]
                    xyz[axis] = value
                    transform = translation(*xyz)
                else:
                    transform = rotation(axis, value)
                local = matmul(local, transform)
            world = local if joint.parent is None else matmul(worlds[joint.parent], local)
            worlds.append(world)
            result.append(tuple(world[i][3] for i in range(3)))
        return result

    def summary(self):
        root = self.joints[0]
        bounds = {}
        for i, channel in enumerate(root.channels):
            if channel.endswith("position"):
                values = [f[root.channel_start + i] for f in self.frames]
                bounds[channel] = [min(values), max(values)]
        return {
            "joints_including_end_sites": len(self.joints),
            "animated_joints": sum(bool(j.channels) for j in self.joints),
            "channels": sum(len(j.channels) for j in self.joints),
            "frames": len(self.frames),
            "fps": 1 / self.frame_time,
            "playback_duration_seconds": len(self.frames) * self.frame_time,
            "first_to_last_sample_seconds": (len(self.frames) - 1) * self.frame_time,
            "root_position_bounds_source_units": bounds,
            "units": "unspecified by BVH; verify before retargeting",
            "status_label": None,
        }


def matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def translation(x, y, z):
    return [[1., 0., 0., x], [0., 1., 0., y], [0., 0., 1., z], [0., 0., 0., 1.]]


def rotation(axis, degrees):
    m = translation(0, 0, 0)
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    a, b = (axis + 1) % 3, (axis + 2) % 3
    m[a][a] = m[b][b] = c
    m[a][b], m[b][a] = -s, s
    return m


def parse(text: str) -> Motion:
    tokens = re.findall(r"\{|\}|[^\s{}]+", text)
    cursor = 0
    joints = []
    channel_count = 0
    valid_channels = {a + t for a in "XYZ" for t in ("position", "rotation")}

    def take(expected=None):
        nonlocal cursor
        if cursor >= len(tokens):
            raise ValueError("Unexpected end of BVH")
        value = tokens[cursor]
        cursor += 1
        if expected is not None and value != expected:
            raise ValueError(f"Expected {expected!r}, got {value!r}")
        return value

    def number():
        value = float(take())
        if not math.isfinite(value):
            raise ValueError("Non-finite BVH value")
        return value

    def joint(parent, kind):
        nonlocal channel_count
        if kind == "End":
            take("Site")
            name = f"{joints[parent].name}:EndSite"
        else:
            name = take()
        take("{")
        take("OFFSET")
        offset = tuple(number() for _ in range(3))
        channels = []
        if kind != "End":
            take("CHANNELS")
            count = int(take())
            if count < 0 or count > 6:
                raise ValueError("Invalid channel count")
            channels = [take() for _ in range(count)]
            if len(set(channels)) != count or any(c not in valid_channels for c in channels):
                raise ValueError("Invalid or duplicate channel")
        index = len(joints)
        joints.append(Joint(name, parent, offset, channels, channel_count))
        channel_count += len(channels)
        while True:
            child = take()
            if child == "}":
                break
            if kind == "End" or child not in ("JOINT", "End"):
                raise ValueError(f"Unexpected hierarchy token {child!r}")
            joint(index, child)

    take("HIERARCHY")
    take("ROOT")
    joint(None, "ROOT")
    take("MOTION")
    take("Frames:")
    count = int(take())
    take("Frame")
    take("Time:")
    frame_time = number()
    if count <= 0 or frame_time <= 0 or channel_count == 0:
        raise ValueError("Motion requires frames, channels and positive frame time")
    if len(tokens) - cursor != count * channel_count:
        raise ValueError("Motion value count does not match frames × channels")
    frames = [[number() for _ in range(channel_count)] for _ in range(count)]
    return Motion(joints, frame_time, frames)


def load(path: Path) -> Motion:
    return parse(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    results = []
    failed = False
    for path in args.paths:
        try:
            results.append({"file": str(path), **load(path).summary()})
        except (OSError, ValueError, RecursionError) as error:
            results.append({"file": str(path), "error": str(error)})
            failed = True
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
