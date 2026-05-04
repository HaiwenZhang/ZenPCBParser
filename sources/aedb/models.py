from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from aurora_translator.sources.aedb.normalizers import (
    normalize_enum_text,
    normalize_int_list,
    normalize_numeric_list,
    normalize_optional_value_list,
    normalize_parameter_map,
    normalize_point,
    normalize_point_list,
    normalize_value,
    normalize_value_list,
)


class SchemaModel(BaseModel):
    """Base model for all serialized AEDB structures."""

    model_config = ConfigDict(extra="forbid")


class DisplayValue(SchemaModel):
    """Numeric values that also preserve the original display string from PyEDB."""

    value: float | int | None = Field(
        default=None,
        description="Numeric value in base units when PyEDB exposes one.",
    )
    display: str = Field(
        ...,
        description="Original string representation returned by PyEDB.",
    )


SerializedValue: TypeAlias = str | bool | int | float | DisplayValue
Point2D: TypeAlias = tuple[float | None, float | None]
ValueField: TypeAlias = Annotated[
    SerializedValue | None, BeforeValidator(normalize_value)
]
PointField: TypeAlias = Annotated[Point2D | None, BeforeValidator(normalize_point)]
PointListField: TypeAlias = Annotated[
    list[Point2D], BeforeValidator(normalize_point_list)
]
NumericListField: TypeAlias = Annotated[
    list[float | int | None] | None, BeforeValidator(normalize_numeric_list)
]
ValueListField: TypeAlias = Annotated[
    list[SerializedValue | None],
    BeforeValidator(normalize_value_list),
]
OptionalValueListField: TypeAlias = Annotated[
    list[SerializedValue | None] | None,
    BeforeValidator(normalize_optional_value_list),
]
IntListField: TypeAlias = Annotated[
    list[int | None], BeforeValidator(normalize_int_list)
]
EnumField: TypeAlias = Annotated[str | int | None, BeforeValidator(normalize_enum_text)]
ParameterMapField: TypeAlias = Annotated[
    dict[str, SerializedValue | None],
    BeforeValidator(normalize_parameter_map),
]


class AEDBMetadata(SchemaModel):
    project_version: str = Field(
        ...,
        description="Aurora Translator project version that produced this AEDB payload.",
    )
    parser_version: str = Field(
        ..., description="AEDB parser version that produced this AEDB payload."
    )
    output_schema_version: str = Field(
        ..., description="AEDB JSON schema version for this payload."
    )
    source: str = Field(..., description="Source .aedb directory path.")
    layout_name: str = Field(..., description="Resolved layout name.")
    backend: Literal["dotnet"] = Field(
        ..., description="PyEDB backend used for parsing."
    )
    pyedb_version: str = Field(..., description="Installed PyEDB version.")
    aedt_version: str = Field(..., description="AEDT version passed into PyEDB.")
    read_only: bool = Field(
        ..., description="Whether the layout was opened in read-only mode."
    )


class SummaryStatistics(SchemaModel):
    layout_size: PointField = Field(
        default=None,
        description="Overall layout size as [width, height] in meters when available.",
    )
    stackup_thickness: float | int | None = Field(
        default=None,
        description="Total stackup thickness in meters when available.",
    )
    num_layers: int | None = Field(
        default=None, description="Layer count reported by PyEDB statistics."
    )
    num_nets: int | None = Field(
        default=None, description="Net count reported by PyEDB statistics."
    )
    num_traces: int | None = Field(
        default=None, description="Trace count reported by PyEDB statistics."
    )
    num_polygons: int | None = Field(
        default=None, description="Polygon count reported by PyEDB statistics."
    )
    num_vias: int | None = Field(
        default=None, description="Via count reported by PyEDB statistics."
    )
    num_discrete_components: int | None = Field(
        default=None,
        description="Discrete component count reported by PyEDB statistics.",
    )
    num_inductors: int | None = Field(
        default=None, description="Inductor count reported by PyEDB statistics."
    )
    num_resistors: int | None = Field(
        default=None, description="Resistor count reported by PyEDB statistics."
    )
    num_capacitors: int | None = Field(
        default=None, description="Capacitor count reported by PyEDB statistics."
    )


class LayoutSummary(SchemaModel):
    material_count: int = Field(..., description="Number of material definitions.")
    layer_count: int = Field(..., description="Number of stackup layers.")
    net_count: int = Field(..., description="Number of nets.")
    component_count: int = Field(..., description="Number of components.")
    padstack_definition_count: int = Field(
        ..., description="Number of padstack definitions."
    )
    padstack_instance_count: int = Field(
        ..., description="Number of padstack instances."
    )
    primitive_count: int = Field(..., description="Number of layout primitives.")
    primitive_type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Primitive counts grouped by primitive type name.",
    )
    path_count: int = Field(..., description="Number of path primitives.")
    polygon_count: int = Field(..., description="Number of polygon primitives.")
    zone_primitive_count: int = Field(..., description="Number of zone primitives.")
    statistics: SummaryStatistics = Field(
        ..., description="Statistics returned by PyEDB."
    )


class MaterialModel(SchemaModel):
    name: str | None = Field(default=None, description="Material name.")
    type: ValueField = Field(
        default=None, description="Material type or PyEDB type string."
    )
    conductivity: ValueField = Field(default=None, description="Conductivity.")
    dc_conductivity: ValueField = Field(default=None, description="DC conductivity.")
    permittivity: ValueField = Field(default=None, description="Relative permittivity.")
    dc_permittivity: ValueField = Field(default=None, description="DC permittivity.")
    permeability: ValueField = Field(default=None, description="Relative permeability.")
    loss_tangent: ValueField = Field(default=None, description="Loss tangent.")
    dielectric_loss_tangent: ValueField = Field(
        default=None,
        description="Dielectric loss tangent.",
    )
    magnetic_loss_tangent: ValueField = Field(
        default=None,
        description="Magnetic loss tangent.",
    )
    mass_density: ValueField = Field(default=None, description="Mass density.")
    poisson_ratio: ValueField = Field(default=None, description="Poisson ratio.")
    specific_heat: ValueField = Field(default=None, description="Specific heat.")
    thermal_conductivity: ValueField = Field(
        default=None,
        description="Thermal conductivity.",
    )
    thermal_expansion_coefficient: ValueField = Field(
        default=None,
        description="Thermal expansion coefficient.",
    )
    youngs_modulus: ValueField = Field(default=None, description="Young's modulus.")
    dielectric_model_frequency: ValueField = Field(
        default=None,
        description="Frequency used for dielectric model extraction when available.",
    )


class LayerModel(SchemaModel):
    name: str | None = Field(default=None, description="Layer name.")
    id: int | None = Field(default=None, description="Layer identifier.")
    type: ValueField = Field(default=None, description="Layer type.")
    material: str | None = Field(default=None, description="Primary material name.")
    fill_material: str | None = Field(default=None, description="Fill material name.")
    dielectric_fill: str | None = Field(
        default=None, description="Dielectric fill material name."
    )
    thickness: ValueField = Field(default=None, description="Layer thickness.")
    lower_elevation: ValueField = Field(default=None, description="Lower elevation.")
    upper_elevation: ValueField = Field(default=None, description="Upper elevation.")
    conductivity: ValueField = Field(default=None, description="Layer conductivity.")
    permittivity: ValueField = Field(default=None, description="Layer permittivity.")
    loss_tangent: ValueField = Field(default=None, description="Layer loss tangent.")
    roughness_enabled: bool | None = Field(
        default=None, description="Whether roughness is enabled."
    )
    is_negative: bool | None = Field(
        default=None, description="Whether the layer is negative."
    )
    is_stackup_layer: bool | None = Field(
        default=None, description="Whether it belongs to the stackup."
    )
    is_via_layer: bool | None = Field(
        default=None, description="Whether it is marked as a via layer."
    )
    color: OptionalValueListField = Field(
        default=None, description="Layer color channels."
    )
    transparency: int | None = Field(
        default=None, description="Layer transparency value."
    )


class NetModel(SchemaModel):
    name: str | None = Field(default=None, description="Net name.")
    is_power_ground: bool | None = Field(
        default=None, description="Whether the net is power or ground."
    )
    component_count: int = Field(..., description="Number of connected components.")
    primitive_count: int = Field(..., description="Number of connected primitives.")
    padstack_instance_count: int = Field(
        ..., description="Number of connected padstack instances."
    )


class PinModel(SchemaModel):
    name: str | None = Field(default=None, description="Pin or pin number name.")
    id: int | None = Field(
        default=None, description="Internal layout object identifier."
    )
    net_name: str | None = Field(default=None, description="Connected net name.")
    position: PointField = Field(default=None, description="Pin XY position in meters.")
    rotation: float | int | None = Field(
        default=None, description="Pin rotation in radians."
    )
    placement_layer: str | None = Field(
        default=None, description="Placement layer name."
    )
    start_layer: str | None = Field(
        default=None, description="Start layer for the pin/via."
    )
    stop_layer: str | None = Field(
        default=None, description="Stop layer for the pin/via."
    )
    padstack_definition: str | None = Field(
        default=None, description="Referenced padstack definition name."
    )
    is_pin: bool | None = Field(
        default=None, description="Whether PyEDB marks this object as a pin."
    )


class ComponentModel(SchemaModel):
    refdes: str | None = Field(default=None, description="Reference designator.")
    component_name: str | None = Field(
        default=None, description="Component instance name."
    )
    part_name: str | None = Field(
        default=None, description="Component part or footprint name."
    )
    type: ValueField = Field(default=None, description="Component type.")
    value: ValueField = Field(default=None, description="Component value.")
    placement_layer: str | None = Field(
        default=None, description="Placement layer name."
    )
    location: PointField = Field(
        default=None, description="Component origin in meters."
    )
    center: PointField = Field(default=None, description="Component center in meters.")
    rotation: float | int | None = Field(
        default=None, description="Component rotation in radians."
    )
    bounding_box: NumericListField = Field(
        default=None,
        description="Component bounding box as [xmin, ymin, xmax, ymax].",
    )
    is_top_mounted: bool | None = Field(
        default=None, description="Whether the component is top mounted."
    )
    enabled: bool | None = Field(
        default=None, description="Whether the component is enabled."
    )
    model_type: ValueField = Field(default=None, description="Assigned model type.")
    numpins: int | None = Field(default=None, description="Number of pins.")
    nets: list[str] = Field(default_factory=list, description="Connected net names.")
    pins: list[PinModel] = Field(default_factory=list, description="Resolved pins.")


class PadPropertyModel(SchemaModel):
    pad_type: EnumField = Field(default=None, description="Pad type enum or label.")
    geometry_type: EnumField = Field(
        default=None, description="Pad geometry enum or label."
    )
    shape: ValueField = Field(default=None, description="Pad shape descriptor.")
    offset_x: ValueField = Field(default=None, description="Pad X offset.")
    offset_y: ValueField = Field(default=None, description="Pad Y offset.")
    rotation: ValueField = Field(default=None, description="Pad rotation.")
    parameters: ParameterMapField = Field(
        default_factory=dict,
        description="Geometry parameters keyed by parameter name.",
    )
    raw_points: PointListField = Field(
        default_factory=list,
        description="Polygonal pad vertices when AEDB stores the pad with polygon geometry.",
    )


class PadstackDefinitionModel(SchemaModel):
    name: str | None = Field(default=None, description="Padstack definition name.")
    material: str | None = Field(default=None, description="Padstack material.")
    hole_type: EnumField = Field(default=None, description="Hole type enum or label.")
    hole_range: str | None = Field(default=None, description="Hole range label.")
    hole_diameter: ValueField = Field(default=None, description="Hole diameter.")
    hole_diameter_string: str | None = Field(
        default=None, description="Original hole diameter string."
    )
    hole_finished_size: ValueField = Field(
        default=None, description="Finished hole size."
    )
    hole_offset_x: ValueField = Field(default=None, description="Hole X offset.")
    hole_offset_y: ValueField = Field(default=None, description="Hole Y offset.")
    hole_rotation: ValueField = Field(default=None, description="Hole rotation.")
    hole_plating_ratio: ValueField = Field(
        default=None, description="Hole plating ratio."
    )
    hole_plating_thickness: ValueField = Field(
        default=None,
        description="Hole plating thickness.",
    )
    hole_properties: OptionalValueListField = Field(
        default=None,
        description="Hole properties list returned by PyEDB.",
    )
    via_layers: OptionalValueListField = Field(
        default=None, description="Layers traversed by the via."
    )
    via_start_layer: str | None = Field(default=None, description="Via start layer.")
    via_stop_layer: str | None = Field(default=None, description="Via stop layer.")
    pad_by_layer: dict[str, PadPropertyModel] = Field(
        default_factory=dict,
        description="Regular pad properties keyed by layer name.",
    )
    antipad_by_layer: dict[str, PadPropertyModel] = Field(
        default_factory=dict,
        description="Anti-pad properties keyed by layer name.",
    )
    thermalpad_by_layer: dict[str, PadPropertyModel] = Field(
        default_factory=dict,
        description="Thermal pad properties keyed by layer name.",
    )


class PadstackInstanceModel(SchemaModel):
    id: int | None = Field(
        default=None, description="Internal layout object identifier."
    )
    name: str | None = Field(default=None, description="Padstack instance name.")
    type: ValueField = Field(default=None, description="Padstack instance type.")
    net_name: str | None = Field(default=None, description="Connected net name.")
    component_name: str | None = Field(
        default=None, description="Owning component name."
    )
    placement_layer: str | None = Field(
        default=None, description="Placement layer name."
    )
    position: PointField = Field(default=None, description="XY position in meters.")
    rotation: float | int | None = Field(
        default=None, description="Rotation in radians."
    )
    start_layer: str | None = Field(default=None, description="Start layer name.")
    stop_layer: str | None = Field(default=None, description="Stop layer name.")
    layer_range_names: OptionalValueListField = Field(
        default=None,
        description="Layer range labels returned by PyEDB.",
    )
    padstack_definition: str | None = Field(
        default=None, description="Referenced padstack definition name."
    )
    is_pin: bool | None = Field(
        default=None, description="Whether PyEDB marks this object as a pin."
    )


class PadstacksModel(SchemaModel):
    definitions: list[PadstackDefinitionModel] = Field(
        default_factory=list,
        description="Padstack definitions.",
    )
    instances: list[PadstackInstanceModel] = Field(
        default_factory=list,
        description="Padstack instances.",
    )


class EndCapStyleModel(SchemaModel):
    valid: bool | None = Field(
        default=None, description="Whether end cap data is valid."
    )
    start: EnumField = Field(default=None, description="Start end cap style.")
    end: EnumField = Field(default=None, description="End end cap style.")


class ArcModel(SchemaModel):
    start: PointField = Field(default=None, description="Arc start point.")
    end: PointField = Field(default=None, description="Arc end point.")
    center: PointField = Field(
        default=None, description="Arc center point when available."
    )
    mid_point: PointField = Field(
        default=None, description="Arc midpoint when available."
    )
    height: float | int | None = Field(default=None, description="Arc height.")
    radius: float | int | None = Field(default=None, description="Arc radius.")
    length: float | int | None = Field(default=None, description="Arc length.")
    is_segment: bool | None = Field(
        default=None, description="Whether the arc is actually a straight segment."
    )
    is_point: bool | None = Field(
        default=None, description="Whether the arc degenerates to a point."
    )
    is_ccw: bool | None = Field(
        default=None, description="Whether the arc direction is counter-clockwise."
    )


class PrimitiveBaseModel(SchemaModel):
    id: int | None = Field(default=None, description="Internal primitive identifier.")
    name: str | None = Field(default=None, description="Primitive name.")
    type: str | None = Field(default=None, description="Primitive type label.")
    aedt_name: str | None = Field(default=None, description="AEDT object name.")
    layer_name: str | None = Field(default=None, description="Owning layer name.")
    net_name: str | None = Field(default=None, description="Connected net name.")
    component_name: str | None = Field(
        default=None, description="Owning component name."
    )
    area: float | int | None = Field(
        default=None, description="Primitive area when available."
    )
    bbox: NumericListField = Field(
        default=None, description="Bounding box as [xmin, ymin, xmax, ymax]."
    )
    is_void: bool | None = Field(
        default=None, description="Whether the primitive is a void."
    )


class PathPrimitiveModel(PrimitiveBaseModel):
    width: ValueField = Field(default=None, description="Trace width.")
    length: float | int | None = Field(default=None, description="Trace length.")
    center_line: PointListField = Field(
        default_factory=list, description="Center line vertices."
    )
    corner_style: EnumField = Field(
        default=None, description="Corner style enum or label."
    )
    end_cap_style: EndCapStyleModel = Field(..., description="End cap styles.")


class PolygonPrimitiveModel(PrimitiveBaseModel):
    raw_points: PointListField = Field(
        default_factory=list, description="Polygon outline points."
    )
    arcs: list[ArcModel] = Field(
        default_factory=list, description="Polygon arc segments."
    )
    is_negative: bool | None = Field(
        default=None, description="Whether the polygon is negative."
    )
    is_zone_primitive: bool | None = Field(
        default=None, description="Whether the polygon is a zone primitive."
    )
    has_voids: bool | None = Field(
        default=None, description="Whether the polygon contains voids."
    )
    void_ids: IntListField = Field(
        default_factory=list, description="Referenced void primitive ids."
    )
    voids: list["PolygonVoidModel"] = Field(
        default_factory=list, description="Void polygon geometries."
    )


class PolygonVoidModel(SchemaModel):
    id: int | None = Field(
        default=None, description="Internal void primitive identifier."
    )
    raw_points: PointListField = Field(
        default_factory=list, description="Void polygon outline points."
    )
    arcs: list[ArcModel] = Field(
        default_factory=list, description="Void polygon arc segments."
    )
    bbox: NumericListField = Field(
        default=None, description="Void bounding box as [xmin, ymin, xmax, ymax]."
    )
    area: float | int | None = Field(
        default=None, description="Void polygon area when available."
    )


class PrimitivesModel(SchemaModel):
    paths: list[PathPrimitiveModel] = Field(
        default_factory=list, description="Path primitives."
    )
    polygons: list[PolygonPrimitiveModel] = Field(
        default_factory=list, description="Polygon primitives."
    )
    zone_primitives: list[PolygonPrimitiveModel] = Field(
        default_factory=list,
        description="Zone primitives represented with polygon fields.",
    )


class AEDBLayout(SchemaModel):
    metadata: AEDBMetadata = Field(
        ..., description="High-level metadata about the parsed layout."
    )
    summary: LayoutSummary = Field(
        ..., description="Fast summary counts and statistics."
    )
    materials: list[MaterialModel] | None = Field(
        default=None,
        description="Material definitions. Omitted in summary-only mode.",
    )
    layers: list[LayerModel] | None = Field(
        default=None,
        description="Ordered stackup layers. Omitted in summary-only mode.",
    )
    nets: list[NetModel] | None = Field(
        default=None,
        description="Resolved nets. Omitted in summary-only mode.",
    )
    components: list[ComponentModel] | None = Field(
        default=None,
        description="Resolved components and pins. Omitted in summary-only mode.",
    )
    padstacks: PadstacksModel | None = Field(
        default=None,
        description="Padstack definitions and instances. Omitted in summary-only mode.",
    )
    primitives: PrimitivesModel | None = Field(
        default=None,
        description="Serialized layout primitives. Omitted in summary-only mode.",
    )
