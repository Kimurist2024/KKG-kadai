import math

from app.analyzer import analyze, analyze_uncached, clear_geometry_cache
from app.schemas import AnalysisSettings, MaskFile


def mask(gap=1, *, second=True):
    contours = [{
        "id": 1, "label_id": 1, "room_name": "A",
        "vertices": [{"x": 0, "y": 0}, {"x": 100, "y": 0},
                     {"x": 100, "y": 100}, {"x": 0, "y": 100}],
    }]
    if second:
        contours.append({
            "id": 2, "label_id": 1, "room_name": "B",
            "vertices": [{"x": 100 + gap, "y": 0}, {"x": 200 + gap, "y": 0},
                         {"x": 200 + gap, "y": 100}, {"x": 100 + gap, "y": 100}],
        })
    return MaskFile.model_validate({"image_width": 300, "image_height": 200, "contours": contours})


def settings(reference="centerline"):
    return AnalysisSettings(scale_px=100, scale_m=1, geometry_mode="regularized_shared",
                            boundary_reference=reference)


def test_default_raw_response_keeps_legacy_shape():
    response = analyze_uncached(mask(second=False)).model_dump(mode="json")
    assert "geometry_processing" not in response
    assert "geometry_mode" not in response["settings"]
    assert "canonical_edge_id" not in response["rooms"][0]["edges"][0]
    assert response["rooms"][0]["floor_area_px2"] == 10_000


def test_centerline_mode_builds_one_shared_canonical_edge():
    response = analyze_uncached(mask(), settings())
    processing = response.geometry_processing
    assert processing is not None
    assert processing.applied_mode == "regularized_shared"
    assert processing.graph is not None
    assert processing.graph.shared_edge_count == 1
    assert processing.max_displacement_px == 0.5
    left = response.rooms[0].edges[1].canonical_edge_id
    right = response.rooms[1].edges[3].canonical_edge_id
    assert left == right
    assert response.summary.overlap_floor_area_m2 == 0


def test_soft_regularization_reduces_direction_residual_without_hard_snapping():
    noisy = mask(second=False)
    noisy.contours[0].vertices[1].y = 2
    response = analyze_uncached(noisy, settings("unknown"))
    processing = response.geometry_processing
    assert processing is not None and processing.dominant_angle_deg is not None
    assert processing.applied_mode == "regularized_shared"
    raw_angle = math.degrees(math.atan2(2, 100))
    corrected = response.rooms[0].vertices
    corrected_angle = math.degrees(math.atan2(
        corrected[1].y - corrected[0].y, corrected[1].x - corrected[0].x))
    assert abs(corrected_angle - processing.dominant_angle_deg) < abs(raw_angle - processing.dominant_angle_deg)
    assert 0 < processing.max_displacement_px < 3


def test_unknown_reference_does_not_snap_distinct_room_boundaries():
    response = analyze_uncached(mask(), settings("unknown"))
    processing = response.geometry_processing
    assert processing is not None and processing.graph is not None
    assert processing.graph.shared_edge_count == 0
    assert processing.max_displacement_px < 1e-9


def test_t_junction_splits_long_edge_and_shares_all_atomic_boundaries():
    plan = MaskFile.model_validate({"image_width": 300, "image_height": 300, "contours": [
        {"id": 1, "label_id": 1, "vertices": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 200}, {"x": 0, "y": 200}]},
        {"id": 2, "label_id": 1, "vertices": [{"x": 100, "y": 0}, {"x": 200, "y": 0}, {"x": 200, "y": 100}, {"x": 100, "y": 100}]},
        {"id": 3, "label_id": 1, "vertices": [{"x": 100, "y": 100}, {"x": 200, "y": 100}, {"x": 200, "y": 200}, {"x": 100, "y": 200}]},
    ]})
    response = analyze_uncached(plan, settings())
    processing = response.geometry_processing
    assert processing is not None and processing.graph is not None
    assert processing.graph.shared_edge_count == 3
    assert len(response.rooms[0].edges[1].canonical_edge_ids) == 2
    assert set(response.rooms[0].edges[1].canonical_edge_ids) == {
        response.rooms[1].edges[3].canonical_edge_id,
        response.rooms[2].edges[3].canonical_edge_id,
    }


def test_malformed_hole_forces_raw_fallback_instead_of_being_dropped():
    plan = mask(second=False)
    plan.contours[0].holes = [[{"x": 10, "y": 10}, {"x": 20, "y": 10}]]
    response = analyze_uncached(plan, settings())
    processing = response.geometry_processing
    assert processing is not None
    assert processing.applied_mode == "raw_fallback"
    assert processing.reject_reason == "invalid_input_topology"


def test_large_area_change_falls_back_to_original_geometry():
    response = analyze_uncached(mask(gap=3), settings())
    processing = response.geometry_processing
    assert processing is not None
    assert processing.applied_mode == "raw_fallback"
    assert processing.reject_reason == "area_change_limit"
    assert response.rooms[0].floor_area_px2 == 10_000


def test_geometry_modes_have_separate_cache_entries_and_are_deterministic():
    clear_geometry_cache()
    raw = analyze(mask()).model_dump(mode="json")
    corrected = analyze(mask(), settings()).model_dump(mode="json")
    corrected_again = analyze(mask(), settings()).model_dump(mode="json")
    assert raw["rooms"][0]["vertices"][1]["x"] == 100
    assert corrected["rooms"][0]["vertices"][1]["x"] == 100.5
    assert corrected == corrected_again
