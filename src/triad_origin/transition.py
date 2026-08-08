"""The deterministic transition contract (Doc 02 §02.2).

Every ORIGIN structure is a pure causal state machine with the signature::

    transition(prior_state_bytes, ordered_input_envelope, immutable_parameter_bundle,
               dependency_quality_snapshot) -> (new_state_bytes, zero_or_more_events)

**No system clock. No I/O. No randomness. No unordered output.** State is represented as a plain
(JSON-serializable) mapping; ``new_state`` and ``events`` are derived only from the four inputs.

This module gives the shared types and a ``run`` driver used identically live and in replay, so
prefix/restart/duplicate invariance (Doc 02 §02.16) is a property of one code path, not two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

State = dict[str, Any]
Envelope = dict[str, Any]
Params = dict[str, Any]
Quality = dict[str, Any]
Event = dict[str, Any]


@dataclass(frozen=True)
class TransitionResult:
    """The pure output of a transition: the next state plus zero or more ordered events."""

    state: State
    events: tuple[Event, ...] = ()


TransitionFn = Callable[[State, Envelope, Params, Quality], TransitionResult]


class DeterministicMachine(Protocol):
    """A pure, owner-specific append-only lifecycle machine (Doc 04 §04.1)."""

    def initial_state(self) -> State: ...

    def transition(
        self, state: State, envelope: Envelope, params: Params, quality: Quality
    ) -> TransitionResult: ...


class MissingParameterError(KeyError):
    """A required semantic parameter is absent. Fail closed — never a code default (Doc 02 §02.15)."""


def require(params: Params, name: str) -> Any:
    """Fetch a required semantic parameter or fail closed.

    A code default for a semantic threshold is a hidden experiment and is forbidden (Doc 02 §02.15).
    """
    if name not in params:
        raise MissingParameterError(
            f"required semantic parameter {name!r} is absent; ORIGIN fails closed (no code default)")
    value = params[name]
    if value is None:
        raise MissingParameterError(f"required semantic parameter {name!r} is null; fail closed")
    return value


@dataclass
class RunResult:
    final_state: State
    events: list[Event] = field(default_factory=list)
    states: list[State] = field(default_factory=list)


def run(
    machine: DeterministicMachine,
    inputs: list[Envelope],
    params: Params,
    quality_of: Callable[[Envelope], Quality] | None = None,
    initial: State | None = None,
) -> RunResult:
    """Drive ``inputs`` (already in deterministic partition order) through ``machine``.

    Used identically for live and replay. ``initial`` allows resuming from a checkpoint state; when
    ``None`` the machine's cold ``initial_state`` is used. The same ``inputs`` prefix always yields
    the same states/events (prefix + restart invariance).
    """
    state = dict(initial) if initial is not None else machine.initial_state()
    out = RunResult(final_state=state)
    for env in inputs:
        quality = quality_of(env) if quality_of else env.get("_quality", {})
        result = machine.transition(state, env, params, quality)
        state = result.state
        out.final_state = state
        out.states.append(state)
        out.events.extend(result.events)
    return out
