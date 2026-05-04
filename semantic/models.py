from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from aurora_translator.semantic.version import (
    SEMANTIC_JSON_SCHEMA_VERSION,
    SEMANTIC_PARSER_VERSION,
)
from aurora_translator.version import PROJECT_VERSION


class SchemaModel(BaseModel):
    """Base model for semantic board payloads."""

    model_config = ConfigDict(extra="forbid")


class SourceRef(SchemaModel):
    source_format: Literal["aedb", "auroradb", "odbpp", "brd", "alg", "altium"] = Field(
        ..., description="Source payload format."
    )
    path: str | None = Field(
        default=None, description="Path to the source field inside the format payload."
    )
    raw_id: str | None = Field(
        default=None, description="Original source identifier when available."
    )


class SemanticDiagnostic(SchemaModel):
    severity: Literal["info", "warning", "error"] = Field(
        default="warning", description="Diagnostic severity."
    )
    code: str = Field(..., description="Stable diagnostic code.")
    message: str = Field(..., description="Human-readable diagnostic message.")
    source: SourceRef | None = Field(
        default=None, description="Source field associated with the diagnostic."
    )


class SemanticPoint(SchemaModel):
    x: float = Field(..., description="X coordinate in semantic board units.")
    y: float = Field(..., description="Y coordinate in semantic board units.")


class SemanticMetadata(SchemaModel):
    project_version: str = Field(
        default=PROJECT_VERSION, description="Aurora Translator project version."
    )
    parser_version: str = Field(
        default=SEMANTIC_PARSER_VERSION,
        description="Semantic parser version that produced this payload.",
    )
    output_schema_version: str = Field(
        default=SEMANTIC_JSON_SCHEMA_VERSION,
        description="Semantic JSON schema version.",
    )
    source_format: Literal["aedb", "auroradb", "odbpp", "brd", "alg", "altium"] = Field(
        ..., description="Source payload format."
    )
    source: str | None = Field(
        default=None, description="Source path recorded by the source payload."
    )
    source_step: str | None = Field(
        default=None, description="Source step when the format has a step concept."
    )
    source_parser_version: str | None = Field(
        default=None, description="Parser version of the source payload."
    )
    source_schema_version: str | None = Field(
        default=None, description="JSON schema version of the source payload."
    )


class SemanticSummary(SchemaModel):
    layer_count: int = Field(default=0, ge=0, description="Number of semantic layers.")
    material_count: int = Field(
        default=0, ge=0, description="Number of semantic material definitions."
    )
    shape_count: int = Field(
        default=0, ge=0, description="Number of semantic shape definitions."
    )
    via_template_count: int = Field(
        default=0, ge=0, description="Number of semantic via templates."
    )
    net_count: int = Field(default=0, ge=0, description="Number of semantic nets.")
    component_count: int = Field(
        default=0, ge=0, description="Number of semantic components."
    )
    footprint_count: int = Field(
        default=0, ge=0, description="Number of semantic footprints."
    )
    pin_count: int = Field(default=0, ge=0, description="Number of semantic pins.")
    pad_count: int = Field(default=0, ge=0, description="Number of semantic pads.")
    via_count: int = Field(default=0, ge=0, description="Number of semantic vias.")
    primitive_count: int = Field(
        default=0, ge=0, description="Number of semantic primitives."
    )
    edge_count: int = Field(
        default=0, ge=0, description="Number of semantic connectivity edges."
    )
    diagnostic_count: int = Field(
        default=0, ge=0, description="Number of semantic diagnostics."
    )


class SemanticMaterial(SchemaModel):
    id: str = Field(..., description="Stable semantic material id.")
    name: str = Field(..., description="Material name.")
    role: Literal["metal", "dielectric", "unknown"] = Field(
        default="unknown",
        description="Material role in the stackup.",
    )
    conductivity: str | float | int | None = Field(
        default=None, description="Electrical conductivity when known."
    )
    permittivity: str | float | int | None = Field(
        default=None, description="Relative permittivity when known."
    )
    dielectric_loss_tangent: str | float | int | None = Field(
        default=None,
        description="Dielectric loss tangent when known.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticLayer(SchemaModel):
    id: str = Field(..., description="Stable semantic layer id.")
    name: str = Field(..., description="Layer name.")
    layer_type: str | None = Field(
        default=None, description="Source or normalized layer type."
    )
    role: str | None = Field(
        default=None,
        description="Semantic role such as signal, dielectric, plane, or drill.",
    )
    side: Literal["top", "bottom", "internal"] | None = Field(
        default=None, description="Board side when known."
    )
    order_index: int | None = Field(
        default=None, description="Stack order index when known."
    )
    material: str | None = Field(
        default=None, description="Primary material when known."
    )
    material_id: str | None = Field(
        default=None,
        description="Referenced semantic material id for the primary material.",
    )
    fill_material: str | None = Field(
        default=None, description="Fill material when known."
    )
    fill_material_id: str | None = Field(
        default=None,
        description="Referenced semantic material id for the fill material.",
    )
    thickness: str | float | int | None = Field(
        default=None, description="Layer thickness when known."
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticShape(SchemaModel):
    id: str = Field(..., description="Stable semantic shape id.")
    name: str | None = Field(
        default=None, description="Shape name or source label when known."
    )
    kind: str = Field(
        ...,
        description="Semantic shape kind such as circle, rectangle, rounded_rectangle, or polygon.",
    )
    auroradb_type: str = Field(
        ..., description="AuroraDB geometry item name such as Circle or Rectangle."
    )
    values: list[str | float | int] = Field(
        default_factory=list,
        description="Geometry values in semantic board units, following AuroraDB geometry order.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticViaTemplateLayer(SchemaModel):
    layer_name: str = Field(
        ..., description="Layer name for this via-template pad entry."
    )
    pad_shape_id: str | None = Field(
        default=None, description="Semantic shape id for the regular pad."
    )
    antipad_shape_id: str | None = Field(
        default=None, description="Semantic shape id for the antipad."
    )
    thermal_shape_id: str | None = Field(
        default=None, description="Semantic shape id for the thermal pad."
    )


def _geometry_dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_geometry_dump(item) for item in value]
    if isinstance(value, tuple):
        return [_geometry_dump(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _geometry_dump(item) for key, item in value.items() if item is not None
        }
    return value


class SemanticGeometryModel(BaseModel):
    """Base model for typed semantic geometry hints with metadata escape hatches."""

    model_config = ConfigDict(extra="allow")

    def _plain_items(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def get(self, key: str, default: Any = None) -> Any:
        if key in type(self).model_fields:
            value = getattr(self, key)
            return default if value is None else value
        extra = self.__pydantic_extra__ or {}
        return extra.get(key, default)

    def keys(self):
        return self._plain_items().keys()

    def items(self):
        return self._plain_items().items()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return self.get(key, None) is not None

    def __len__(self) -> int:
        return len(self._plain_items())

    def __bool__(self) -> bool:
        return bool(self._plain_items())

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if (
            value is None
            and key not in type(self).model_fields
            and key not in (self.__pydantic_extra__ or {})
        ):
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    @model_serializer(mode="plain")
    def _serialize(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        fields_set = self.model_fields_set
        for name in type(self).model_fields:
            value = getattr(self, name)
            if value is None:
                continue
            if name not in fields_set and value in ([], {}):
                continue
            data[name] = _geometry_dump(value)
        for key, value in (self.__pydantic_extra__ or {}).items():
            if value is not None:
                data[key] = _geometry_dump(value)
        return data


class SemanticViaTemplateGeometry(SemanticGeometryModel):
    source: str | None = Field(
        default=None, description="Source of via-template geometry hints."
    )
    drill_layer: str | None = Field(
        default=None, description="Source drill layer name."
    )
    symbol: str | None = Field(default=None, description="Source drill or pad symbol.")
    tool: Any = Field(default=None, description="Source drill tool metadata.")
    layer_pad_rotations: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-layer pad and antipad rotations.",
    )
    layer_pad_source: str | None = Field(
        default=None, description="How layer pad geometry was refined."
    )
    antipad_source: str | None = Field(
        default=None, description="How antipad geometry was refined."
    )
    matched_signal_layer_count: int | None = Field(
        default=None, description="Matched signal-layer pad count."
    )
    matched_antipad_layer_count: int | None = Field(
        default=None, description="Matched antipad layer count."
    )


class SemanticFootprintGeometry(SemanticGeometryModel):
    outlines: list[Any] = Field(
        default_factory=list, description="Package or footprint body outlines."
    )
    pads: list[Any] = Field(
        default_factory=list, description="Package-local pad geometry hints."
    )


class SemanticPadGeometry(SemanticGeometryModel):
    shape_id: str | None = Field(
        default=None, description="Referenced semantic shape id."
    )
    package: str | None = Field(default=None, description="Source package name.")
    package_pin: str | None = Field(
        default=None, description="Source package pin name."
    )
    source: str | None = Field(
        default=None, description="Source of pad geometry hints."
    )
    rotation: float | int | str | None = Field(
        default=None, description="Pad rotation."
    )
    shape_kind: str | None = Field(default=None, description="Source shape kind.")
    polarity: str | None = Field(default=None, description="Source pad polarity.")
    mirror_x: bool | None = Field(
        default=None, description="Whether pad geometry mirrors across local X."
    )
    mirror_y: bool | None = Field(
        default=None, description="Whether pad geometry mirrors across local Y."
    )


class SemanticViaGeometry(SemanticGeometryModel):
    rotation: float | int | str | None = Field(
        default=None, description="Via rotation."
    )
    template_refined_from: str | None = Field(
        default=None, description="Original via template before refinement."
    )
    matched_signal_layer_count: int | None = Field(
        default=None, description="Matched signal-layer pad count."
    )
    matched_antipad_layer_count: int | None = Field(
        default=None, description="Matched antipad layer count."
    )


class SemanticBoardOutlineGeometry(SemanticGeometryModel):
    kind: str | None = Field(default=None, description="Board outline geometry kind.")
    auroradb_type: str | None = Field(
        default=None, description="AuroraDB-compatible geometry type."
    )
    source: str | None = Field(
        default=None, description="Source of board outline geometry."
    )
    path_count: int | None = Field(
        default=None, description="Number of source outline paths."
    )
    values: list[Any] = Field(
        default_factory=list, description="Outline geometry values."
    )


class SemanticViaTemplate(SchemaModel):
    id: str = Field(..., description="Stable semantic via template id.")
    name: str = Field(..., description="Via or padstack template name.")
    barrel_shape_id: str | None = Field(
        default=None, description="Semantic shape id for the barrel or drill hole."
    )
    layer_pads: list[SemanticViaTemplateLayer] = Field(
        default_factory=list,
        description="Layer-specific pad, antipad, and thermal-pad shape references.",
    )
    geometry: SemanticViaTemplateGeometry = Field(
        default_factory=SemanticViaTemplateGeometry,
        description="Typed format-neutral via/padstack geometry hints.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticNet(SchemaModel):
    id: str = Field(..., description="Stable semantic net id.")
    name: str = Field(..., description="Net name.")
    role: str | None = Field(
        default=None,
        description="Semantic role such as power, ground, signal, or unknown.",
    )
    pin_ids: list[str] = Field(
        default_factory=list, description="Pins connected to this net."
    )
    pad_ids: list[str] = Field(
        default_factory=list, description="Pads connected to this net."
    )
    via_ids: list[str] = Field(
        default_factory=list, description="Vias connected to this net."
    )
    primitive_ids: list[str] = Field(
        default_factory=list, description="Primitives connected to this net."
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticFootprint(SchemaModel):
    id: str = Field(..., description="Stable semantic footprint id.")
    name: str = Field(..., description="Footprint or package name.")
    part_name: str | None = Field(
        default=None, description="Part name associated with this footprint when known."
    )
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Format-specific footprint or package attributes.",
    )
    pad_ids: list[str] = Field(
        default_factory=list, description="Pads belonging to this footprint."
    )
    geometry: SemanticFootprintGeometry = Field(
        default_factory=SemanticFootprintGeometry,
        description="Typed format-neutral footprint/package geometry hints.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticComponent(SchemaModel):
    id: str = Field(..., description="Stable semantic component id.")
    refdes: str | None = Field(default=None, description="Reference designator.")
    name: str | None = Field(default=None, description="Component instance name.")
    part_name: str | None = Field(default=None, description="Part name.")
    package_name: str | None = Field(
        default=None, description="Package or footprint name."
    )
    footprint_id: str | None = Field(
        default=None, description="Resolved semantic footprint id."
    )
    layer_name: str | None = Field(default=None, description="Placement layer name.")
    side: Literal["top", "bottom", "internal"] | None = Field(
        default=None, description="Mounted side when known."
    )
    value: str | None = Field(default=None, description="Component value when known.")
    location: SemanticPoint | None = Field(
        default=None, description="Component placement point when known."
    )
    rotation: float | int | None = Field(
        default=None, description="Component rotation when known."
    )
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Format-specific component or part attributes.",
    )
    pin_ids: list[str] = Field(
        default_factory=list, description="Pins owned by this component."
    )
    pad_ids: list[str] = Field(
        default_factory=list, description="Pads placed for this component."
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticPin(SchemaModel):
    id: str = Field(..., description="Stable semantic pin id.")
    name: str | None = Field(default=None, description="Pin name or number.")
    component_id: str | None = Field(default=None, description="Owning component id.")
    net_id: str | None = Field(default=None, description="Connected net id.")
    pad_ids: list[str] = Field(
        default_factory=list, description="Pads bound to this pin."
    )
    layer_name: str | None = Field(default=None, description="Placement layer name.")
    position: SemanticPoint | None = Field(
        default=None, description="Pin position when known."
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticPad(SchemaModel):
    id: str = Field(..., description="Stable semantic pad id.")
    name: str | None = Field(
        default=None, description="Pad name, number, or source pad id."
    )
    footprint_id: str | None = Field(
        default=None, description="Owning footprint id when known."
    )
    component_id: str | None = Field(
        default=None, description="Owning component id when this is a placed pad."
    )
    pin_id: str | None = Field(
        default=None, description="Bound semantic pin id when known."
    )
    net_id: str | None = Field(default=None, description="Connected net id when known.")
    layer_name: str | None = Field(
        default=None, description="Pad layer name when known."
    )
    position: SemanticPoint | None = Field(
        default=None, description="Pad position when known."
    )
    padstack_definition: str | None = Field(
        default=None, description="Padstack definition or pad template when known."
    )
    geometry: SemanticPadGeometry = Field(
        default_factory=SemanticPadGeometry,
        description="Typed format-neutral pad geometry hints.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticVia(SchemaModel):
    id: str = Field(..., description="Stable semantic via id.")
    name: str | None = Field(default=None, description="Via instance name when known.")
    template_id: str | None = Field(
        default=None, description="Referenced semantic via template id."
    )
    net_id: str | None = Field(default=None, description="Connected net id.")
    layer_names: list[str] = Field(
        default_factory=list, description="Layers traversed by the via."
    )
    position: SemanticPoint | None = Field(
        default=None, description="Via position when known."
    )
    geometry: SemanticViaGeometry = Field(
        default_factory=SemanticViaGeometry,
        description="Typed format-neutral via geometry hints.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class SemanticArcGeometry(SemanticGeometryModel):
    start: list[float | int | None] | None = Field(
        default=None, description="Arc start point."
    )
    end: list[float | int | None] | None = Field(
        default=None, description="Arc end point."
    )
    center: list[float | int | None] | None = Field(
        default=None, description="Arc center point."
    )
    mid_point: list[float | int | None] | None = Field(
        default=None, description="Arc midpoint."
    )
    height: float | int | None = Field(default=None, description="Arc height.")
    radius: float | int | None = Field(default=None, description="Arc radius.")
    length: float | int | None = Field(default=None, description="Arc length.")
    is_segment: bool | None = Field(
        default=None, description="Whether the arc is a straight segment."
    )
    is_point: bool | None = Field(
        default=None, description="Whether the arc degenerates to a point."
    )
    is_ccw: bool | None = Field(
        default=None, description="Whether the arc direction is counter-clockwise."
    )


class SemanticPolygonVoidGeometry(SemanticGeometryModel):
    raw_points: list[list[float | int | None]] = Field(
        default_factory=list, description="Void outline points."
    )
    arcs: list[SemanticArcGeometry] = Field(
        default_factory=list, description="Void arc segments."
    )
    bbox: list[float | int] | None = Field(
        default=None, description="Void bounding box."
    )
    area: float | int | None = Field(default=None, description="Void area.")
    polarity: str | None = Field(default=None, description="Source contour polarity.")
    source_contour_index: int | None = Field(
        default=None, description="Source contour index."
    )


class SemanticPrimitiveGeometry(SemanticGeometryModel):
    record_kind: str | None = Field(
        default=None, description="Source primitive record kind."
    )
    feature_index: int | None = Field(default=None, description="Source feature index.")
    feature_id: str | int | None = Field(default=None, description="Source feature id.")
    line_number: int | None = Field(default=None, description="Source line number.")
    tokens: list[str] = Field(
        default_factory=list, description="Source feature tokens."
    )
    polarity: str | None = Field(default=None, description="Source polarity.")
    symbol: str | None = Field(default=None, description="Source symbol name.")
    shape_id: str | None = Field(
        default=None, description="Referenced semantic shape id."
    )
    dcode: str | int | None = Field(default=None, description="Source D-code.")
    orientation: str | None = Field(
        default=None, description="Source orientation token."
    )
    rotation: float | int | str | None = Field(
        default=None, description="Primitive rotation."
    )
    mirror_x: bool | None = Field(
        default=None, description="Whether primitive geometry mirrors across local X."
    )
    mirror_y: bool | None = Field(
        default=None, description="Whether primitive geometry mirrors across local Y."
    )
    start: Any = Field(
        default=None, description="Start point or source start geometry."
    )
    end: Any = Field(default=None, description="End point or source end geometry.")
    center: Any = Field(default=None, description="Center point.")
    location: Any = Field(default=None, description="Placement location.")
    width: str | float | int | None = Field(
        default=None, description="Trace or arc width."
    )
    center_line: list[list[float | int | None]] = Field(
        default_factory=list, description="Trace center line."
    )
    raw_points: list[list[float | int | None]] = Field(
        default_factory=list, description="Polygon outline points."
    )
    arcs: list[SemanticArcGeometry] = Field(
        default_factory=list, description="Polygon arc segments."
    )
    voids: list[SemanticPolygonVoidGeometry] = Field(
        default_factory=list, description="Polygon void geometry."
    )
    has_voids: bool | None = Field(
        default=None, description="Whether polygon geometry has voids."
    )
    void_ids: list[str | int] = Field(
        default_factory=list, description="Source polygon void identifiers."
    )
    surface_group_index: int | None = Field(
        default=None, description="Split surface group index."
    )
    surface_group_count: int | None = Field(
        default=None, description="Split surface group count."
    )
    is_negative: bool | None = Field(
        default=None, description="Whether polygon polarity is negative."
    )
    is_void: bool | None = Field(
        default=None, description="Whether polygon geometry is itself a void."
    )
    bbox: list[float | int] | None = Field(
        default=None, description="Primitive bounding box."
    )
    area: float | int | None = Field(default=None, description="Primitive area.")
    clockwise: bool | None = Field(
        default=None, description="Whether arc direction is clockwise."
    )
    is_ccw: bool | None = Field(
        default=None, description="Whether arc direction is counter-clockwise."
    )


class SemanticPrimitive(SchemaModel):
    id: str = Field(..., description="Stable semantic primitive id.")
    kind: str = Field(
        ...,
        description="Semantic primitive kind such as trace, polygon, pad, via, or raw_feature.",
    )
    layer_name: str | None = Field(default=None, description="Owning layer name.")
    net_id: str | None = Field(default=None, description="Connected net id when known.")
    component_id: str | None = Field(
        default=None, description="Owning component id when known."
    )
    geometry: SemanticPrimitiveGeometry = Field(
        default_factory=SemanticPrimitiveGeometry,
        description="Typed format-neutral primitive geometry hints.",
    )
    source: SourceRef = Field(..., description="Source field reference.")


class ConnectivityEdge(SchemaModel):
    kind: Literal[
        "component-footprint",
        "component-pin",
        "component-pad",
        "footprint-pad",
        "pin-pad",
        "pad-net",
        "pin-net",
        "via-net",
        "primitive-net",
        "component-primitive",
    ] = Field(
        ...,
        description="Connectivity edge kind.",
    )
    source_id: str = Field(..., description="Source semantic object id.")
    target_id: str = Field(..., description="Target semantic object id.")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in the inferred edge."
    )


class SemanticBoard(SchemaModel):
    """Format-neutral semantic view derived from a format-specific payload."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://aurora-translator.local/schemas/semantic-{SEMANTIC_JSON_SCHEMA_VERSION}.json",
        },
    )

    metadata: SemanticMetadata = Field(..., description="Semantic payload metadata.")
    units: str | None = Field(
        default=None, description="Canonical coordinate units for semantic points."
    )
    summary: SemanticSummary = Field(
        ..., description="Semantic payload summary counts."
    )
    layers: list[SemanticLayer] = Field(
        default_factory=list, description="Semantic layers."
    )
    materials: list[SemanticMaterial] = Field(
        default_factory=list, description="Semantic material definitions."
    )
    shapes: list[SemanticShape] = Field(
        default_factory=list, description="AuroraDB-profile semantic shapes."
    )
    via_templates: list[SemanticViaTemplate] = Field(
        default_factory=list,
        description="AuroraDB-profile semantic via templates.",
    )
    nets: list[SemanticNet] = Field(default_factory=list, description="Semantic nets.")
    components: list[SemanticComponent] = Field(
        default_factory=list, description="Semantic components."
    )
    footprints: list[SemanticFootprint] = Field(
        default_factory=list, description="Semantic footprints."
    )
    pins: list[SemanticPin] = Field(default_factory=list, description="Semantic pins.")
    pads: list[SemanticPad] = Field(default_factory=list, description="Semantic pads.")
    vias: list[SemanticVia] = Field(default_factory=list, description="Semantic vias.")
    primitives: list[SemanticPrimitive] = Field(
        default_factory=list, description="Semantic primitives."
    )
    connectivity: list[ConnectivityEdge] = Field(
        default_factory=list, description="Semantic connectivity edges."
    )
    diagnostics: list[SemanticDiagnostic] = Field(
        default_factory=list, description="Semantic diagnostics."
    )
    board_outline: SemanticBoardOutlineGeometry = Field(
        default_factory=SemanticBoardOutlineGeometry,
        description="Typed format-neutral board outline/profile geometry hints.",
    )

    def with_computed_summary(self) -> "SemanticBoard":
        summary = SemanticSummary(
            layer_count=len(self.layers),
            material_count=len(self.materials),
            shape_count=len(self.shapes),
            via_template_count=len(self.via_templates),
            net_count=len(self.nets),
            component_count=len(self.components),
            footprint_count=len(self.footprints),
            pin_count=len(self.pins),
            pad_count=len(self.pads),
            via_count=len(self.vias),
            primitive_count=len(self.primitives),
            edge_count=len(self.connectivity),
            diagnostic_count=len(self.diagnostics),
        )
        self.summary = summary
        return self
