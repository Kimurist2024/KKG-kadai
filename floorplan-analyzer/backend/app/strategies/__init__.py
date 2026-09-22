"""Named, exact alternatives; profiles never change the API or global selection.

Add a module here with @register(seam, name) and add a named AlgorithmProfile
to PROFILES (in that module or here). Modules are discovered once on import.
Call conventions are documented in each seam's module. Selection is resolved
once per analysis, never by a registry lookup inside an edge/segment loop.
"""
from dataclasses import dataclass
from importlib import import_module
from pkgutil import iter_modules


REGISTRIES = {seam: {} for seam in (
    "candidate_search", "interval_clip", "self_intersection", "room_polygons", "overlap_pairs"
)}


def _registry(seam):
    if seam not in REGISTRIES:
        raise KeyError(f"Unknown seam {seam!r}; registered: {', '.join(REGISTRIES)}")
    return REGISTRIES[seam]


def register(seam, name):
    """Register a function/factory; accidental replacement is an error."""
    registry = _registry(seam)

    def decorate(impl):
        if name in registry:
            raise ValueError(f"Already registered: {seam}.{name}")
        registry[name] = impl
        return impl

    return decorate


def get(seam, name):
    registry = _registry(seam)
    if name not in registry:
        raise KeyError(f"Unknown {seam} implementation {name!r}; registered: {', '.join(registry)}")
    return registry[name]


@dataclass(frozen=True)
class AlgorithmProfile:
    candidate_search: str = "auto"
    interval_clip: str = "auto"
    self_intersection: str = "auto"
    room_polygons: str = "batch"
    overlap_pairs: str = "auto"


PROFILES = {
    "default": AlgorithmProfile(),
    # Isolate candidate-search choice for the historical index benchmark.
    "scan_only": AlgorithmProfile(candidate_search="scan"),
    "tree_only": AlgorithmProfile(candidate_search="strtree"),
    "all_pairs": AlgorithmProfile(candidate_search="scan", interval_clip="all_pairs",
                                  self_intersection="all_pairs", room_polygons="per_room",
                                  overlap_pairs="brute"),
}


def resolve_profile(name_or_profile=None):
    if isinstance(name_or_profile, AlgorithmProfile):
        return name_or_profile
    name = "default" if name_or_profile is None else name_or_profile
    if name not in PROFILES:
        raise KeyError(f"Unknown profile {name!r}; registered: {', '.join(PROFILES)}")
    return PROFILES[name]


# A new file with decorators is sufficient; no dispatcher edits are needed.
for _module in sorted(iter_modules(__path__), key=lambda item: item.name):
    if not _module.name.startswith("_"):
        import_module(f"{__name__}.{_module.name}")
