"""tools.layout_qa — Layout QA analyzer for Langrisser III scripts.

Phase 1 surface: `analyze` CLI that reads `scripts/<lang>/scen*E.txt`,
classifies each entry by layout profile, simulates how the engine
distributes the text into lines/balloons under deterministic
budget-exhaustion wrapping, and emits a JSON metrics report.

Subpackage layout (per SOLID separation of concerns):

    parser.py      — split scen files into Entry/Segment structs
    classifier.py  — state machine assigning layout profiles
    simulator.py   — budget-exhaustion wrap simulation
    metrics.py     — aggregate + status buckets + JSON shape
    cli.py         — analyze command entry point

Tile cost measurement lives in `tools/text_measure.py` (single-
responsibility), reused via greedy-bigram mirroring of the canonical
encoder at `tools/d00_tools.py:154-285`.
"""

SCHEMA_VERSION = '0.3.1'

__all__ = ['SCHEMA_VERSION']
