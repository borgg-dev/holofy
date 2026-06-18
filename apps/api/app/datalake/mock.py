"""In-memory data-lake sink — records what it received, asserts nothing more.

Stands in for the real EU-region lake writer until that lands behind the same
``DataLakeSink`` Protocol. It keeps every emitted ``TrainingExample`` in a list so a test
can assert *exactly* what crossed the consent boundary — which is the point: the privacy
hard line (only consented records reach the lake) is proven by inspecting this sink, so it
must faithfully record every emission and nothing else.

Idempotent on ``(kind, record_id)`` like the real sink: a re-emitted record updates its one
example in place rather than appending a duplicate, so the consent decision and the lake
example stay one-to-one even across a retry.
"""

from __future__ import annotations

from app.datalake.base import DataLakeSink
from app.schemas.datalake import TrainingExample, TrainingExampleKind


class MockDataLakeSink(DataLakeSink):
    def __init__(self) -> None:
        self._examples: list[TrainingExample] = []

    async def emit(self, example: TrainingExample) -> None:
        key = (example.kind, example.record_id)
        for i, existing in enumerate(self._examples):
            if (existing.kind, existing.record_id) == key:
                self._examples[i] = example
                return
        self._examples.append(example)

    @property
    def examples(self) -> list[TrainingExample]:
        """Every example the sink was handed, in emission order — for assertions."""
        return list(self._examples)

    def examples_of(self, kind: TrainingExampleKind) -> list[TrainingExample]:
        return [e for e in self._examples if e.kind is kind]
