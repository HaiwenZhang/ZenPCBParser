from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from aurora_translator.sources.aedb.normalizers import (
    safe_getattr,
    safe_zone_primitives,
)
from aurora_translator.shared.logging import log_field_block, log_timing

from .padstack_records import (
    PadstackInstanceRecord,
    build_padstack_instance_records,
)
from .precision import COORDINATE_DIGITS


logger = logging.getLogger("aurora_translator.aedb.extractors.context")


@dataclass
class LayoutObjectIndex:
    """Aggregated data from one scan of EDB layout object instances."""

    scanned: bool
    object_count: int
    component_instances_by_id: dict[int, Any]
    primitive_counts_by_net: Counter[str]
    padstack_counts_by_net: Counter[str]
    component_names_by_net: dict[str, set[str]]


@dataclass(frozen=True, slots=True)
class ComponentLayoutRecord:
    """Plain Python geometry extracted from a component layout object instance."""

    center: list[float] | None
    bounding_box: list[float] | None


@dataclass(frozen=True, slots=True)
class LayoutPrimitiveCollection:
    """Raw layout primitive collection plus where it came from."""

    values: list[Any]
    from_active_layout: bool


@dataclass(frozen=True, slots=True)
class LayoutPrimitiveGroups:
    """One-pass primitive classification used by path/polygon/zone extraction."""

    paths: list[Any]
    polygons: list[Any]
    zones: list[Any]
    others: int


def _is_null_dotnet_object(value: Any) -> bool:
    try:
        return bool(value.IsNull())
    except Exception:
        return value is None


def _dotnet_name_or_none(value: Any) -> str | None:
    if value is None or _is_null_dotnet_object(value):
        return None
    try:
        return value.GetName()
    except Exception:
        return None


def _call_or_none(value: Any, method_name: str) -> Any:
    try:
        return getattr(value, method_name)()
    except Exception:
        return None


def _component_raw_object(component: Any) -> Any:
    return safe_getattr(component, "edbcomponent") or safe_getattr(
        component, "_edb_object"
    )


def _component_id(raw_component: Any) -> int | None:
    if raw_component is None:
        return None
    try:
        return int(raw_component.GetId())
    except Exception:
        return None


def _active_layout_collection(pedb: Any, collection_name: str) -> list[Any] | None:
    active_layout = safe_getattr(pedb, "active_layout")
    if active_layout is None:
        return None
    try:
        return list(getattr(active_layout, collection_name))
    except Exception:
        return None


def _primitive_type_name(primitive: Any) -> str:
    primitive_type = _call_or_none(primitive, "GetPrimitiveType")
    if primitive_type is not None:
        return str(_call_or_none(primitive_type, "ToString") or primitive_type)
    return str(safe_getattr(primitive, "type") or "")


def _primitive_is_zone(primitive: Any) -> bool:
    is_zone = _call_or_none(primitive, "IsZonePrimitive")
    if is_zone is not None:
        try:
            return bool(is_zone)
        except Exception:
            return False

    return bool(safe_getattr(primitive, "is_zone_primitive"))


def _layout_object_id(value: Any) -> int | None:
    object_id = _call_or_none(value, "GetId")
    if object_id is None:
        return None
    try:
        return int(object_id)
    except Exception:
        return None


def _point_xy_rounded(
    point: Any, digits: int = COORDINATE_DIGITS
) -> list[float] | None:
    if point is None:
        return None
    try:
        return [
            round(point.X.ToDouble(), digits),
            round(point.Y.ToDouble(), digits),
        ]
    except Exception:
        return None


def _component_layout_record(component_instance: Any) -> ComponentLayoutRecord:
    center = None
    bounding_box = None

    try:
        center = _point_xy_rounded(component_instance.GetCenter())
    except Exception:
        center = None

    try:
        bbox = component_instance.GetBBox()
        bounding_box = [
            round(bbox.Item1.X.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item1.Y.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item2.X.ToDouble(), COORDINATE_DIGITS),
            round(bbox.Item2.Y.ToDouble(), COORDINATE_DIGITS),
        ]
    except Exception:
        bounding_box = None

    return ComponentLayoutRecord(center=center, bounding_box=bounding_box)


@dataclass
class ExtractionContext:
    """Cached PyEDB collections shared by all extractors during one parse run."""

    pedb: Any

    @cached_property
    def materials(self) -> list[Any]:
        return list(self.pedb.materials.materials.values())

    @cached_property
    def layers(self) -> list[Any]:
        return list(self.pedb.stackup.layers.values())

    @cached_property
    def signal_layer_names(self) -> list[str]:
        return list(self.pedb.stackup.signal_layers.keys())

    @cached_property
    def nets(self) -> list[Any]:
        return list(self.pedb.nets.nets.values())

    @cached_property
    def components(self) -> list[Any]:
        return list(self.pedb.components.instances.values())

    @cached_property
    def layout_object_index(self) -> LayoutObjectIndex:
        component_instances_by_id: dict[int, Any] = {}
        primitive_counts_by_net: Counter[str] = Counter()
        padstack_counts_by_net: Counter[str] = Counter()
        component_names_by_net: dict[str, set[str]] = defaultdict(set)

        try:
            layout_instance = self.pedb.layout_instance
            collection = layout_instance.GetAllLayoutObjInstances()
        except Exception:
            return LayoutObjectIndex(
                scanned=False,
                object_count=0,
                component_instances_by_id=component_instances_by_id,
                primitive_counts_by_net=primitive_counts_by_net,
                padstack_counts_by_net=padstack_counts_by_net,
                component_names_by_net=component_names_by_net,
            )

        try:
            items = collection.Items
        except Exception:
            return LayoutObjectIndex(
                scanned=False,
                object_count=0,
                component_instances_by_id=component_instances_by_id,
                primitive_counts_by_net=primitive_counts_by_net,
                padstack_counts_by_net=padstack_counts_by_net,
                component_names_by_net=component_names_by_net,
            )

        object_count = 0
        for layout_obj_instance in items:
            object_count += 1
            try:
                layout_obj = layout_obj_instance.GetLayoutObj()
                obj_type = str(layout_obj.GetObjType())
            except Exception:
                continue

            if obj_type == "Primitive":
                net_name = _dotnet_name_or_none(layout_obj.GetNet())
                if net_name:
                    primitive_counts_by_net[net_name] += 1
                continue

            if obj_type == "PadstackInstance":
                net_name = _dotnet_name_or_none(layout_obj.GetNet())
                if not net_name:
                    continue

                padstack_counts_by_net[net_name] += 1
                component_name = _dotnet_name_or_none(layout_obj.GetComponent())
                if component_name:
                    component_names_by_net[net_name].add(component_name)
                continue

            if obj_type == "Group":
                try:
                    layout_obj_id = int(layout_obj.GetId())
                except Exception:
                    continue

                component_instances_by_id[layout_obj_id] = layout_obj_instance

        return LayoutObjectIndex(
            scanned=True,
            object_count=object_count,
            component_instances_by_id=component_instances_by_id,
            primitive_counts_by_net=primitive_counts_by_net,
            padstack_counts_by_net=padstack_counts_by_net,
            component_names_by_net=component_names_by_net,
        )

    @cached_property
    def component_instances_by_id(self) -> dict[int, Any]:
        component_instances_by_id: dict[int, Any] = {}
        try:
            layout_instance = self.pedb.layout_instance
        except Exception:
            return component_instances_by_id

        for component in self.components:
            raw_component = _component_raw_object(component)
            component_id = _component_id(raw_component)
            if raw_component is None or component_id is None:
                continue

            try:
                component_instance = layout_instance.GetLayoutObjInstance(
                    raw_component, None
                )
            except Exception:
                continue
            if _is_null_dotnet_object(component_instance):
                continue

            component_instances_by_id[component_id] = component_instance

        return component_instances_by_id

    @cached_property
    def component_layout_records_by_id(self) -> dict[int, ComponentLayoutRecord]:
        component_layout_records_by_id: dict[int, ComponentLayoutRecord] = {}
        try:
            layout_instance = self.pedb.layout_instance
        except Exception:
            return component_layout_records_by_id

        for component in self.components:
            raw_component = _component_raw_object(component)
            component_id = _component_id(raw_component)
            if raw_component is None or component_id is None:
                continue

            component_instance = None
            try:
                component_instance = layout_instance.GetLayoutObjInstance(
                    raw_component, None
                )
                if _is_null_dotnet_object(component_instance):
                    continue
                component_layout_records_by_id[component_id] = _component_layout_record(
                    component_instance
                )
            except Exception:
                continue
            finally:
                component_instance = None

        return component_layout_records_by_id

    @cached_property
    def padstack_definitions(self) -> list[Any]:
        return list(self.pedb.padstacks.definitions.values())

    @cached_property
    def padstack_instances(self) -> list[Any]:
        raw_instances = _active_layout_collection(self.pedb, "PadstackInstances")
        if raw_instances is not None:
            return raw_instances
        return list(self.pedb.padstacks.instances.values())

    @cached_property
    def padstack_instance_records(self) -> list[PadstackInstanceRecord]:
        return build_padstack_instance_records(
            self.padstack_instances, self.signal_layer_names, None
        )

    @cached_property
    def layout_primitive_collection(self) -> LayoutPrimitiveCollection:
        with log_timing(logger, "collect layout primitives"):
            raw_primitives = _active_layout_collection(self.pedb, "Primitives")
            if raw_primitives is not None:
                return LayoutPrimitiveCollection(
                    values=raw_primitives, from_active_layout=True
                )
            return LayoutPrimitiveCollection(
                values=list(self.pedb.layout.primitives), from_active_layout=False
            )

    @cached_property
    def layout_primitives(self) -> list[Any]:
        return self.layout_primitive_collection.values

    @cached_property
    def layout_primitive_groups(self) -> LayoutPrimitiveGroups:
        paths: list[Any] = []
        polygons: list[Any] = []
        zones: list[Any] = []
        others = 0

        with log_timing(
            logger, "classify layout primitives", count=len(self.layout_primitives)
        ):
            for primitive in self.layout_primitives:
                primitive_type = _primitive_type_name(primitive)
                if primitive_type == "Path":
                    paths.append(primitive)
                elif primitive_type in {"Polygon", "Rectangle", "Circle"}:
                    polygons.append(primitive)
                else:
                    others += 1

                if _primitive_is_zone(primitive):
                    zones.append(primitive)

        log_field_block(
            logger,
            "Classified layout primitives",
            fields={
                "paths": len(paths),
                "polygons": len(polygons),
                "zones": len(zones),
                "others": others,
            },
        )
        return LayoutPrimitiveGroups(
            paths=paths, polygons=polygons, zones=zones, others=others
        )

    @cached_property
    def fixed_zone_primitives(self) -> list[Any]:
        active_layout = safe_getattr(self.pedb, "active_layout")
        if active_layout is None:
            return []

        with log_timing(logger, "collect fixed zone primitive"):
            fixed_zone = _call_or_none(active_layout, "GetFixedZonePrimitive")
            if fixed_zone is None or _is_null_dotnet_object(fixed_zone):
                return []
            return [fixed_zone]

    @cached_property
    def layout_paths(self) -> list[Any]:
        return self.layout_primitive_groups.paths

    @cached_property
    def layout_polygons(self) -> list[Any]:
        return self.layout_primitive_groups.polygons

    @cached_property
    def zone_primitives(self) -> list[Any]:
        groups = self.layout_primitive_groups
        zones = list(groups.zones)
        seen_ids = {
            object_id
            for item in zones
            if (object_id := _layout_object_id(item)) is not None
        }
        for fixed_zone in self.fixed_zone_primitives:
            object_id = _layout_object_id(fixed_zone)
            if object_id is not None and object_id in seen_ids:
                continue
            if object_id is not None:
                seen_ids.add(object_id)
            zones.append(fixed_zone)

        if zones or self.layout_primitive_collection.from_active_layout:
            return zones

        active_layout = safe_getattr(self.pedb, "active_layout")
        try:
            with log_timing(logger, "collect zone primitives fallback", heartbeat=True):
                return list(active_layout.GetZonePrimitives())
        except Exception:
            pass
        return safe_zone_primitives(self.pedb.layout)
