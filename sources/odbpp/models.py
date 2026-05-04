from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    """Base model for serialized ODB++ structures."""

    model_config = ConfigDict(extra="forbid")


class ODBPPMetadata(SchemaModel):
    project_version: str = Field(
        ...,
        description="Aurora Translator project version that produced this ODB++ payload.",
    )
    parser_version: str = Field(
        ..., description="ODB++ parser version that produced this payload."
    )
    output_schema_version: str = Field(
        ..., description="ODB++ JSON schema version for this payload."
    )
    source: str = Field(..., description="Source ODB++ directory or archive path.")
    source_type: Literal["directory", "zip", "tgz", "tar", "unknown"] = Field(
        ...,
        description="Physical source container type detected by the Rust parser.",
    )
    selected_step: str | None = Field(
        default=None,
        description="ODB++ step used for detailed layer, component, and net extraction.",
    )
    backend: Literal["rust-cli", "rust-native"] = Field(
        ..., description="Parser backend used by Aurora Translator."
    )
    rust_parser_version: str = Field(
        ..., description="Version reported by the Rust ODB++ parser implementation."
    )


class ODBPPSummary(SchemaModel):
    step_count: int = Field(
        ..., ge=0, description="Number of ODB++ steps found under steps/."
    )
    layer_count: int = Field(
        ..., ge=0, description="Number of rows parsed from matrix/matrix."
    )
    board_layer_count: int = Field(
        ..., ge=0, description="Number of matrix rows with board context."
    )
    signal_layer_count: int = Field(
        ..., ge=0, description="Number of matrix rows whose type is signal."
    )
    component_layer_count: int = Field(
        ..., ge=0, description="Number of matrix rows whose type is component."
    )
    feature_layer_count: int = Field(
        ..., ge=0, description="Number of selected-step layer feature files parsed."
    )
    feature_count: int = Field(
        ..., ge=0, description="Number of selected-step feature records parsed."
    )
    symbol_count: int = Field(
        default=0,
        ge=0,
        description="Number of ODB++ symbol library feature files parsed.",
    )
    drill_tool_count: int = Field(
        default=0,
        ge=0,
        description="Number of selected-step drill/rout tool records parsed.",
    )
    package_count: int = Field(
        default=0,
        ge=0,
        description="Number of selected-step EDA package definitions parsed.",
    )
    component_count: int = Field(
        ..., ge=0, description="Number of selected-step component records parsed."
    )
    net_count: int = Field(
        ..., ge=0, description="Number of unique selected-step nets discovered."
    )
    profile_record_count: int = Field(
        ..., ge=0, description="Number of profile line records parsed across steps."
    )
    diagnostic_count: int = Field(
        ..., ge=0, description="Number of non-fatal parser diagnostics."
    )
    step_names: list[str] = Field(
        default_factory=list, description="Discovered ODB++ step names."
    )
    layer_names: list[str] = Field(
        default_factory=list, description="Layer names parsed from matrix/matrix."
    )
    net_names: list[str] = Field(
        default_factory=list, description="Unique selected-step net names."
    )


class MatrixRowModel(SchemaModel):
    row: int | None = Field(
        default=None, description="Matrix row or id value when present."
    )
    name: str | None = Field(default=None, description="Layer or matrix row name.")
    context: str | None = Field(
        default=None, description="ODB++ row context, for example board or misc."
    )
    layer_type: str | None = Field(
        default=None, description="ODB++ row type, for example signal or component."
    )
    polarity: str | None = Field(
        default=None, description="Layer polarity when present."
    )
    side: str | None = Field(default=None, description="Layer side when present.")
    start_name: str | None = Field(
        default=None, description="Start layer name for drill or stackup ranges."
    )
    end_name: str | None = Field(
        default=None, description="End layer name for drill or stackup ranges."
    )
    raw_fields: dict[str, str] = Field(
        default_factory=dict, description="Raw matrix row key/value fields."
    )


class MatrixModel(SchemaModel):
    rows: list[MatrixRowModel] = Field(
        default_factory=list, description="Parsed rows from matrix/matrix."
    )


class PointModel(SchemaModel):
    x: float = Field(..., description="X coordinate in the source ODB++ units.")
    y: float = Field(..., description="Y coordinate in the source ODB++ units.")


class ContourVertexModel(SchemaModel):
    record_type: str = Field(
        ..., description="ODB++ contour record kind, for example OB, OS, or OC."
    )
    point: PointModel = Field(..., description="Contour vertex point.")
    center: PointModel | None = Field(
        default=None, description="Arc center point for OC records."
    )
    clockwise: bool | None = Field(
        default=None, description="Arc direction flag for OC records when available."
    )


class SurfaceContourModel(SchemaModel):
    polarity: str | None = Field(
        default=None, description="Surface contour polarity when present."
    )
    vertices: list[ContourVertexModel] = Field(
        default_factory=list, description="Contour vertices."
    )


class LineRecordModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the source file."
    )
    kind: str = Field(..., description="First token or record kind.")
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source record."
    )


class ProfileModel(SchemaModel):
    units: str | None = Field(
        default=None, description="Units declared in the profile file when present."
    )
    records: list[LineRecordModel] = Field(
        default_factory=list, description="Tokenized profile line records."
    )


class StepModel(SchemaModel):
    name: str = Field(..., description="ODB++ step name.")
    profile: ProfileModel | None = Field(
        default=None, description="Step profile records when profile exists."
    )


class FeatureModel(SchemaModel):
    feature_index: int = Field(
        default=0,
        ge=0,
        description="Zero-based ODB++ feature index inside the feature file.",
    )
    kind: str = Field(
        ..., description="ODB++ feature record kind, for example P, L, A, S, T, or B."
    )
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the feature file."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source feature record."
    )
    feature_id: str | None = Field(
        default=None, description="ODB++ ID attribute when present."
    )
    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Parsed semicolon attributes from the feature.",
    )
    polarity: str | None = Field(
        default=None, description="Feature polarity when inferred from the record."
    )
    symbol: str | None = Field(
        default=None,
        description="Referenced ODB++ symbol when inferred from the record.",
    )
    start: PointModel | None = Field(
        default=None,
        description="Start or placement point when coordinates are available.",
    )
    end: PointModel | None = Field(
        default=None, description="End point for line or arc records when available."
    )
    center: PointModel | None = Field(
        default=None, description="Arc center point when available."
    )
    contours: list[SurfaceContourModel] = Field(
        default_factory=list, description="Surface contours for S records."
    )


class LayerFeaturesModel(SchemaModel):
    step_name: str = Field(..., description="ODB++ step that owns this feature file.")
    layer_name: str = Field(..., description="ODB++ layer name.")
    units: str | None = Field(
        default=None, description="Units declared in the feature file when present."
    )
    layer_attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Attributes parsed from the layer attrlist file.",
    )
    symbols: dict[str, str] = Field(
        default_factory=dict, description="Feature-file symbol lookup table."
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Feature-file attribute lookup table."
    )
    text_strings: dict[str, str] = Field(
        default_factory=dict, description="Feature-file text lookup table."
    )
    features: list[FeatureModel] = Field(
        default_factory=list, description="Parsed feature records."
    )


class SymbolDefinitionModel(SchemaModel):
    name: str = Field(
        ..., description="ODB++ symbol name from symbols/<name>/features."
    )
    units: str | None = Field(
        default=None,
        description="Units declared in the symbol feature file when present.",
    )
    features: list[FeatureModel] = Field(
        default_factory=list, description="Parsed symbol feature records."
    )


class DrillToolModel(SchemaModel):
    number: int | None = Field(
        default=None, description="Tool number inside the ODB++ tools block."
    )
    tool_type: str | None = Field(
        default=None, description="ODB++ tool type, for example VIA."
    )
    type2: str | None = Field(default=None, description="Secondary ODB++ tool type.")
    finish_size: float | None = Field(
        default=None, description="Finished hole size from the tools file."
    )
    drill_size: float | None = Field(
        default=None, description="Drill size from the tools file."
    )
    raw_fields: dict[str, str] = Field(
        default_factory=dict, description="Raw tool key/value fields."
    )


class DrillLayerToolsModel(SchemaModel):
    step_name: str = Field(..., description="ODB++ step that owns this tools file.")
    layer_name: str = Field(
        ..., description="ODB++ layer name that owns these tool definitions."
    )
    units: str | None = Field(
        default=None, description="Units declared in the tools file when present."
    )
    thickness: float | None = Field(
        default=None, description="Layer tools file THICKNESS value when present."
    )
    user_params: str | None = Field(
        default=None, description="Layer tools file USER_PARAMS value when present."
    )
    raw_fields: dict[str, str] = Field(
        default_factory=dict,
        description="Top-level tools file fields outside TOOLS blocks.",
    )
    tools: list[DrillToolModel] = Field(
        default_factory=list, description="Parsed tools from the layer tools file."
    )


class PackageBoundsModel(SchemaModel):
    min: PointModel = Field(..., description="Minimum package bounding point.")
    max: PointModel = Field(..., description="Maximum package bounding point.")


class PackageShapeModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the package source."
    )
    kind: str = Field(
        ...,
        description="ODB++ package geometry record kind, for example RC, CR, SQ, or CT.",
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source package geometry record."
    )
    center: PointModel | None = Field(
        default=None, description="Geometry center in package-local coordinates."
    )
    width: float | None = Field(
        default=None, description="Rectangle width when this shape is an RC record."
    )
    height: float | None = Field(
        default=None, description="Rectangle height when this shape is an RC record."
    )
    radius: float | None = Field(
        default=None, description="Circle radius when this shape is a CR record."
    )
    size: float | None = Field(
        default=None, description="Square size value when this shape is an SQ record."
    )
    contours: list[SurfaceContourModel] = Field(
        default_factory=list, description="Contour geometry for package surface shapes."
    )


class PackagePinModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the package source."
    )
    name: str | None = Field(default=None, description="Package pin name.")
    side: str | None = Field(
        default=None, description="Package pin side/type flag from ODB++."
    )
    position: PointModel | None = Field(
        default=None, description="Pin position in package-local coordinates."
    )
    rotation: float | None = Field(
        default=None, description="Pin rotation in source degrees when present."
    )
    electrical_type: str | None = Field(
        default=None, description="ODB++ package pin electrical type flag."
    )
    mount_type: str | None = Field(
        default=None, description="ODB++ package pin mount/type flag."
    )
    feature_id: str | None = Field(
        default=None, description="ODB++ ID attribute for the package pin."
    )
    shapes: list[PackageShapeModel] = Field(
        default_factory=list,
        description="Geometry records associated with this package pin.",
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source package pin record."
    )


class PackageDefinitionModel(SchemaModel):
    step_name: str = Field(
        ..., description="ODB++ step that owns this package definition."
    )
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the EDA data file."
    )
    package_index: int | None = Field(
        default=None,
        description="Package index from the preceding ODB++ package comment.",
    )
    name: str | None = Field(default=None, description="ODB++ package name.")
    feature_id: str | None = Field(
        default=None, description="ODB++ ID attribute for the package definition."
    )
    pitch: float | None = Field(
        default=None, description="Package pitch value when present."
    )
    bounds: PackageBoundsModel | None = Field(
        default=None, description="Package bounding box when present."
    )
    properties: dict[str, str] = Field(
        default_factory=dict, description="Package PRP properties."
    )
    outlines: list[PackageShapeModel] = Field(
        default_factory=list, description="Package outline/body geometry records."
    )
    pins: list[PackagePinModel] = Field(
        default_factory=list, description="Package pin definitions."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source package record."
    )


class ComponentModel(SchemaModel):
    step_name: str = Field(
        ..., description="ODB++ step that owns this component record."
    )
    layer_name: str = Field(..., description="ODB++ component layer name.")
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the component file."
    )
    record_type: str = Field(..., description="Component source record kind.")
    component_index: int | None = Field(
        default=None,
        description="Component index from the component-file comment when present.",
    )
    package_index: int | None = Field(
        default=None, description="Referenced ODB++ package index when present."
    )
    refdes: str | None = Field(
        default=None, description="Reference designator when inferred from tokens."
    )
    package_name: str | None = Field(
        default=None, description="Package name when inferred from tokens."
    )
    part_name: str | None = Field(
        default=None, description="Part name when inferred from tokens."
    )
    location: PointModel | None = Field(
        default=None, description="Component placement point when present."
    )
    rotation: float | None = Field(
        default=None,
        description="Component rotation in source units/degrees when present.",
    )
    mirror: str | None = Field(
        default=None,
        description="Component mirror/orientation source flag when present.",
    )
    properties: dict[str, str] = Field(
        default_factory=dict, description="Component PRP properties."
    )
    pins: list["ComponentPinModel"] = Field(
        default_factory=list, description="Pins owned by this component."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source component record."
    )


class ComponentPinModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the component file."
    )
    record_type: str = Field(
        ..., description="Pin source record kind, usually TOP or BOT."
    )
    pin_index: int | None = Field(
        default=None, description="Pin index in the component record."
    )
    name: str | None = Field(default=None, description="Pin name or number.")
    position: PointModel | None = Field(
        default=None, description="Pin placement point."
    )
    rotation: float | None = Field(
        default=None, description="Pin rotation when present."
    )
    mirror: str | None = Field(
        default=None, description="Pin mirror/orientation source flag when present."
    )
    net_component_index: int | None = Field(
        default=None, description="ODB++ net reference component key."
    )
    net_pin_index: int | None = Field(
        default=None, description="ODB++ net reference pin key."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source pin record."
    )


ComponentModel.model_rebuild()


class NetFeatureRefModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the source net file."
    )
    subnet_type: str | None = Field(
        default=None, description="Current SNT record type associated with this FID."
    )
    class_code: str = Field(
        ..., description="ODB++ FID class code, for example C or H."
    )
    layer_index: int | None = Field(
        default=None, description="Layer index from the EDA LYR table."
    )
    layer_name: str | None = Field(
        default=None, description="Layer name resolved from the EDA LYR table."
    )
    feature_index: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based feature index inside the layer feature file.",
    )
    pin_side: str | None = Field(
        default=None,
        description="Associated component side for FID records following SNT TOP T/B.",
    )
    net_component_index: int | None = Field(
        default=None, description="Associated ODB++ net reference component key."
    )
    net_pin_index: int | None = Field(
        default=None, description="Associated ODB++ net reference pin key."
    )
    tokens: list[str] = Field(default_factory=list, description="Tokenized FID record.")


class NetPinRefModel(SchemaModel):
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the source net file."
    )
    side: str | None = Field(
        default=None, description="Component side resolved from SNT TOP T/B records."
    )
    net_component_index: int | None = Field(
        default=None, description="ODB++ net reference component key."
    )
    net_pin_index: int | None = Field(
        default=None, description="ODB++ net reference pin key."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized SNT pin record."
    )


class NetModel(SchemaModel):
    step_name: str = Field(..., description="ODB++ step that owns this net record.")
    name: str = Field(..., description="Net name.")
    source_file: str = Field(
        ..., description="ODB++ source file where the net was discovered."
    )
    line_number: int = Field(
        ..., ge=1, description="1-based line number inside the source file."
    )
    tokens: list[str] = Field(
        default_factory=list, description="Tokenized source net record."
    )
    feature_refs: list[NetFeatureRefModel] = Field(
        default_factory=list, description="Feature references attached to this net."
    )
    pin_refs: list[NetPinRefModel] = Field(
        default_factory=list,
        description="Component pin references attached to this net.",
    )


class ODBLayout(SchemaModel):
    metadata: ODBPPMetadata = Field(
        ..., description="High-level metadata about the parsed ODB++ source."
    )
    summary: ODBPPSummary = Field(
        ..., description="Fast counts and selected-step summary information."
    )
    matrix: MatrixModel | None = Field(
        default=None, description="ODB++ matrix rows when matrix/matrix exists."
    )
    steps: list[StepModel] = Field(
        default_factory=list, description="Discovered ODB++ steps and profiles."
    )
    symbols: list[SymbolDefinitionModel] | None = Field(
        default=None,
        description="ODB++ symbol library feature definitions. Omitted in summary-only mode.",
    )
    drill_tools: list[DrillLayerToolsModel] | None = Field(
        default=None,
        description="Selected-step drill/rout layer tool definitions. Omitted in summary-only mode.",
    )
    packages: list[PackageDefinitionModel] | None = Field(
        default=None,
        description="Selected-step EDA package and package-pin definitions. Omitted in summary-only mode.",
    )
    layers: list[LayerFeaturesModel] | None = Field(
        default=None,
        description="Selected-step layer features. Omitted in summary-only mode.",
    )
    components: list[ComponentModel] | None = Field(
        default=None,
        description="Selected-step component records. Omitted in summary-only mode.",
    )
    nets: list[NetModel] | None = Field(
        default=None,
        description="Selected-step net records. Omitted in summary-only mode.",
    )
    diagnostics: list[str] = Field(
        default_factory=list, description="Non-fatal parser diagnostics."
    )
