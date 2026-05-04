from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from aurora_translator.semantic.models import (
    SemanticBoard,
    SemanticComponent,
    SemanticFootprint,
    SemanticNet,
    SemanticPad,
    SemanticShape,
)


@dataclass(frozen=True, slots=True)
class BoardExportIndex:
    """Reusable board-level lookup tables for AuroraDB export planning."""

    net_names_by_id: dict[str, str]
    nets_by_id: dict[str, SemanticNet]
    components_by_id: dict[str, SemanticComponent]
    pads_by_pin_id: dict[str, list[SemanticPad]]
    shapes_by_id: dict[str, SemanticShape]
    footprints_by_name: dict[str, SemanticFootprint]

    @classmethod
    def from_board(cls, board: SemanticBoard) -> "BoardExportIndex":
        pads_by_pin_id: defaultdict[str, list[SemanticPad]] = defaultdict(list)
        for pad in board.pads:
            if pad.pin_id:
                pads_by_pin_id[pad.pin_id].append(pad)

        return cls(
            net_names_by_id={net.id: net.name for net in board.nets},
            nets_by_id={net.id: net for net in board.nets},
            components_by_id={
                component.id: component for component in board.components
            },
            pads_by_pin_id=dict(pads_by_pin_id),
            shapes_by_id={shape.id: shape for shape in board.shapes},
            footprints_by_name=_footprints_by_name(board.footprints),
        )


def _footprints_by_name(
    footprints: list[SemanticFootprint],
) -> dict[str, SemanticFootprint]:
    return {
        footprint.name.casefold(): footprint
        for footprint in footprints
        if footprint.name
    }
