"""Uncached, alternating experiments. Serialization/comparison is outside timing."""
import math
import statistics
import struct
import time
from dataclasses import asdict

from .analyzer import analyze_uncached
from .strategies import AlgorithmProfile, REGISTRIES, get, resolve_profile


def first_difference(expected, actual, path="$"):
    """First differing field, including type, key/list order and IEEE-754 bits."""
    def difference(left, right, reason):
        return dict(path=path, expected=left, actual=right, reason=reason)

    if type(expected) is not type(actual):
        return difference(expected, actual, "type")
    if isinstance(expected, dict):
        if list(expected) != list(actual):
            return difference(list(expected), list(actual), "keys/order")
        for key in expected:
            found = first_difference(expected[key], actual[key], f"{path}.{key}")
            if found is not None:
                return found
    elif isinstance(expected, list):
        for index, (left, right) in enumerate(zip(expected, actual)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found is not None:
                return found
        if len(expected) != len(actual):
            return difference(expected, actual, "length")
    elif isinstance(expected, float):
        if struct.pack("!d", expected) != struct.pack("!d", actual):
            return difference(expected, actual, "float bits")
    elif expected != actual:
        return difference(expected, actual, "value")
    return None


def _signature(result):
    return [(result.model_dump(mode="json", **options), result.model_dump_json(**options))
            for options in ({}, {"exclude_unset": True})]


def compare(mask, settings, profiles, reps, *, alternate=True):
    """Return {profile_name: statistics, raw_ms, equality, first difference}.

    profiles accepts names or AlgorithmProfile values (labelled profile_<index>).
    Each profile runs five warmups and reps measurements, forward on even rounds
    and backward on odd rounds. alternate=False keeps the supplied order.
    A separate default reference is computed even when default is not requested.
    All runs are checked, including warmups; no differing result is hidden by a
    later matching one. Timings exclude output comparison and JSON serialization.
    """
    if not isinstance(reps, int) or isinstance(reps, bool) or reps < 1:
        raise ValueError("reps must be a positive integer")
    selected = []
    for index, value in enumerate(profiles):
        name = f"profile_{index}" if isinstance(value, AlgorithmProfile) else value
        profile = resolve_profile(value)
        for seam in REGISTRIES:
            get(seam, getattr(profile, seam))
        if any(name == previous for previous, _ in selected):
            raise ValueError(f"Duplicate profile: {name}")
        selected.append((name, profile))
    if not selected:
        raise ValueError("profiles must not be empty")

    reference = _signature(analyze_uncached(mask, settings, profile="default"))
    rows = {name: dict(profile=asdict(profile), raw_ms=[], json_equal=True,
                       bits_equal=True, matches_default=True, difference=None)
            for name, profile in selected}
    for round_index in range(reps + 5):
        order = reversed(selected) if alternate and round_index % 2 else selected
        for name, profile in order:
            start = time.perf_counter_ns()
            result = analyze_uncached(mask, settings, profile=profile)
            elapsed = (time.perf_counter_ns() - start) / 1e6
            row = rows[name]
            if round_index >= 5:
                row["raw_ms"].append(elapsed)
            for index, ((expected, expected_json), (actual, actual_json)) in enumerate(
                    zip(reference, _signature(result))):
                path = "$" if index == 0 else "$[exclude_unset]"
                diff = first_difference(expected, actual, path)
                row["bits_equal"] &= diff is None
                row["json_equal"] &= expected_json == actual_json
                if diff is None and expected_json != actual_json:
                    diff = dict(path=path, expected=expected_json, actual=actual_json,
                                reason="JSON serialization")
                if row["difference"] is None and diff is not None:
                    row["difference"] = diff
            row["matches_default"] = row["bits_equal"] and row["json_equal"]
            # Do not charge destruction of the previous profile's response to
            # the next profile when its result is assigned inside the timer.
            del result
    for row in rows.values():
        values = sorted(row["raw_ms"])
        row.update(median_ms=statistics.median(values),
                   p95_ms=values[math.ceil(.95 * len(values)) - 1], min_ms=values[0])
    return rows
