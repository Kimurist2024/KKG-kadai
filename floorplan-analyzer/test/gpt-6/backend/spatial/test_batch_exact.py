import json
import math
import random
import struct

from pydantic_core import to_json
from app.spatial import SegmentIndex


def test_batch_candidates_match_scalar_order_and_boundary_queries():
    rng = random.Random(197)
    segments = [(i, ((rng.uniform(-100, 100), rng.uniform(-100, 100)),
                     (rng.uniform(-100, 100), rng.uniform(-100, 100)))) for i in range(100)]
    edges = [s for _, s in segments] + [((0, 0), (0, 0)), ((1e100, 0), (1e100, 1))]
    for count in (0, 10, 64, 100):
        index = SegmentIndex(segments[:count])
        for tolerance in (0, 1e-9, 2.5, 10):
            assert index.near_many(edges, tolerance) == [index.near(a, b, tolerance) for a, b in edges]
        assert index.near_many([], 10) == []


def test_native_cache_serializer_preserves_float_bits():
    rng = random.Random(731)
    values = [0.0, -0.0, 5e-324, 1.7976931348623157e308]
    for _ in range(10000):
        value = struct.unpack("!d", rng.getrandbits(64).to_bytes(8, "big"))[0]
        if math.isfinite(value):
            values.append(value)
    old = json.loads(json.dumps(values))
    new = json.loads(to_json(values, inf_nan_mode="constants"))
    assert [v.hex() for v in old] == [v.hex() for v in new]
