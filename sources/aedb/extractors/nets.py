from __future__ import annotations

from collections import Counter, defaultdict
import logging
from typing import Any

from aurora_translator.sources.aedb.models import NetModel, PrimitivesModel
from aurora_translator.sources.aedb.normalizers import safe_getattr
from aurora_translator.shared.logging import log_timing

from .context import ExtractionContext
from .padstack_records import PadstackInstanceRecord


logger = logging.getLogger("aurora_translator.aedb.extractors.nets")


def _call_or_none(value: Any, method_name: str) -> Any:
    try:
        return getattr(value, method_name)()
    except Exception:
        return None


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


def _primitive_raw_object(primitive: Any) -> Any:
    if callable(safe_getattr(primitive, "GetPrimitiveType")):
        return primitive
    return (
        safe_getattr(primitive, "_edb_object")
        or safe_getattr(primitive, "primitive_object")
        or safe_getattr(primitive, "core")
    )


def _padstack_raw_object(padstack: Any) -> Any:
    if callable(safe_getattr(padstack, "GetPositionAndRotationValue")):
        return padstack
    return safe_getattr(padstack, "_edb_padstackinstance") or safe_getattr(
        padstack, "core"
    )


def _net_raw_object(net: Any) -> Any:
    return (
        safe_getattr(net, "_edb_object")
        or safe_getattr(net, "net_object")
        or safe_getattr(net, "net_obj")
    )


def _primitive_net_name(primitive: Any) -> str | None:
    raw_primitive = _primitive_raw_object(primitive)
    if raw_primitive is not None:
        net_name = _dotnet_name_or_none(_call_or_none(raw_primitive, "GetNet"))
        if net_name is not None:
            return net_name
    return safe_getattr(primitive, "net_name")


def _raw_void_primitives(raw_primitive: Any) -> list[Any]:
    if raw_primitive is None:
        return []
    try:
        return [
            item
            for item in raw_primitive.Voids
            if item is not None and not _is_null_dotnet_object(item)
        ]
    except Exception:
        return []


def _count_primitive_tree(raw_primitive: Any, counts: Counter[str]) -> None:
    net_name = _dotnet_name_or_none(_call_or_none(raw_primitive, "GetNet"))
    if net_name:
        counts[net_name] += 1

    for void_primitive in _raw_void_primitives(raw_primitive):
        _count_primitive_tree(void_primitive, counts)


def _count_primitive_and_voids(primitive: Any, counts: Counter[str]) -> None:
    raw_primitive = _primitive_raw_object(primitive)
    if raw_primitive is not None:
        _count_primitive_tree(raw_primitive, counts)
        return

    net_name = safe_getattr(primitive, "net_name")
    if net_name:
        counts[net_name] += 1

    for void_primitive in safe_getattr(primitive, "voids") or []:
        _count_primitive_and_voids(void_primitive, counts)


def _padstack_net_name(padstack: Any) -> str | None:
    raw_padstack = _padstack_raw_object(padstack)
    if raw_padstack is not None:
        net_name = _dotnet_name_or_none(_call_or_none(raw_padstack, "GetNet"))
        if net_name is not None:
            return net_name
    return safe_getattr(padstack, "net_name")


def _padstack_component_name(padstack: Any) -> str | None:
    raw_padstack = _padstack_raw_object(padstack)
    if raw_padstack is not None:
        component_name = _dotnet_name_or_none(
            _call_or_none(raw_padstack, "GetComponent")
        )
        if component_name is not None:
            return component_name
    return safe_getattr(padstack, "component_name")


def _aggregate_net_counts(
    context: ExtractionContext,
    *,
    use_layout_object_index: bool = True,
) -> tuple[Counter[str], Counter[str], dict[str, set[str]]]:
    if use_layout_object_index:
        layout_object_index = context.layout_object_index
        if layout_object_index.scanned:
            return (
                layout_object_index.primitive_counts_by_net,
                layout_object_index.padstack_counts_by_net,
                layout_object_index.component_names_by_net,
            )

    primitive_counts: Counter[str] = Counter()
    padstack_counts: Counter[str] = Counter()
    component_names_by_net: dict[str, set[str]] = defaultdict(set)

    primitives = context.layout_primitives
    with log_timing(logger, "group net primitives", count=len(primitives)):
        for primitive in primitives:
            _count_primitive_and_voids(primitive, primitive_counts)

    padstack_records = context.padstack_instance_records
    with log_timing(logger, "group net padstack records", count=len(padstack_records)):
        for padstack in padstack_records:
            net_name = padstack.count_net_name
            if not net_name:
                continue

            padstack_counts[net_name] += 1
            component_name = padstack.component_refdes
            if component_name:
                component_names_by_net[net_name].add(component_name)

    return primitive_counts, padstack_counts, component_names_by_net


def _aggregate_net_counts_from_sections(
    primitives: PrimitivesModel,
    padstack_records: list[PadstackInstanceRecord],
) -> tuple[Counter[str], Counter[str], dict[str, set[str]]]:
    primitive_counts: Counter[str] = Counter()
    padstack_counts: Counter[str] = Counter()
    component_names_by_net: dict[str, set[str]] = defaultdict(set)

    primitive_count = (
        len(primitives.paths)
        + len(primitives.polygons)
        + len(primitives.zone_primitives)
    )
    with log_timing(logger, "group serialized net primitives", count=primitive_count):
        for primitive in primitives.paths:
            if primitive.net_name:
                primitive_counts[primitive.net_name] += 1
        for primitive in primitives.polygons:
            if primitive.net_name:
                primitive_counts[primitive.net_name] += 1 + len(
                    primitive.void_ids or []
                )
        for primitive in primitives.zone_primitives:
            if primitive.net_name:
                primitive_counts[primitive.net_name] += 1

    with log_timing(logger, "group net padstack records", count=len(padstack_records)):
        for padstack in padstack_records:
            net_name = padstack.count_net_name
            if not net_name:
                continue

            padstack_counts[net_name] += 1
            component_name = padstack.component_refdes
            if component_name:
                component_names_by_net[net_name].add(component_name)

    return primitive_counts, padstack_counts, component_names_by_net


def extract_net(
    net: Any,
    primitive_counts: Counter[str],
    padstack_counts: Counter[str],
    component_names_by_net: dict[str, set[str]],
) -> NetModel:
    raw_net = _net_raw_object(net)
    net_name = _dotnet_name_or_none(raw_net) if raw_net is not None else None
    resolved_name = net_name if net_name is not None else safe_getattr(net, "name")

    return NetModel.model_validate(
        {
            "name": resolved_name,
            "is_power_ground": safe_getattr(net, "is_power_ground"),
            "component_count": len(
                component_names_by_net.get(resolved_name or "", set())
            ),
            "primitive_count": primitive_counts.get(resolved_name or "", 0),
            "padstack_instance_count": padstack_counts.get(resolved_name or "", 0),
        }
    )


def extract_nets(
    context: ExtractionContext, *, use_layout_object_index: bool = True
) -> list[NetModel]:
    net_values = context.nets
    with log_timing(logger, "serialize nets", count=len(net_values)):
        primitive_counts, padstack_counts, component_names_by_net = (
            _aggregate_net_counts(
                context,
                use_layout_object_index=use_layout_object_index,
            )
        )
        return sorted(
            (
                extract_net(
                    net,
                    primitive_counts,
                    padstack_counts,
                    component_names_by_net,
                )
                for net in net_values
            ),
            key=lambda item: item.name or "",
        )


def extract_nets_from_sections(
    context: ExtractionContext, primitives: PrimitivesModel
) -> list[NetModel]:
    net_values = context.nets
    with log_timing(
        logger, "serialize nets from extracted sections", count=len(net_values)
    ):
        primitive_counts, padstack_counts, component_names_by_net = (
            _aggregate_net_counts_from_sections(
                primitives,
                context.padstack_instance_records,
            )
        )
        return sorted(
            (
                extract_net(
                    net,
                    primitive_counts,
                    padstack_counts,
                    component_names_by_net,
                )
                for net in net_values
            ),
            key=lambda item: item.name or "",
        )
