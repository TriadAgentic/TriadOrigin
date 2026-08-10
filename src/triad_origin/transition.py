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

from .canonical import canonical_json, loads_canonical, sha256_hex

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


class InputIdentityError(ValueError):
    """An event/revision identity was reused with different canonical bytes."""


def require(params: Params, name: str) -> Any:
    """Fetch a required semantic parameter or fail closed.

    A code default for a semantic threshold is a hidden experiment and is forbidden (Doc 02 §02.15).

    **B01C-BIND-05:** this raw-mapping accessor is a TEST/REPLAY convenience only. Public production
    entrypoints must consume a sealed :class:`~triad_origin.bindings.ResolvedParameterBundle`
    through :func:`require_bundle`; a raw dictionary cannot enter a production formula path.
    """
    if name not in params:
        raise MissingParameterError(
            f"required semantic parameter {name!r} is absent; ORIGIN fails closed (no code default)")
    value = params[name]
    if value is None:
        raise MissingParameterError(f"required semantic parameter {name!r} is null; fail closed")
    return value


def require_bundle(bundle: Any, parameter_id: str) -> Any:
    """Fetch a required parameter from an authenticated, sealed capability, or fail closed.

    B01C-BIND-05: the public production path accepts ONLY an exact
    :class:`~triad_origin.bindings.ResolvedParameterBundle` — the unforgeable capability the
    authenticated loader constructs. A raw dict, a copied/forged dataclass, a subclass, or a
    reloaded marker is refused by an exact-type check *before* any lookup, so a presence-only
    dictionary can never reach a formula. The bundle's own ``require`` face fails closed on an
    absent/blocked/sentinel parameter (never a code default).
    """
    from .bindings import ResolvedParameterBundle, CapabilityForgeryError

    if type(bundle) is not ResolvedParameterBundle:
        raise CapabilityForgeryError(
            "production parameters require a sealed ResolvedParameterBundle; "
            f"got {type(bundle).__name__!r}")
    return bundle.require(parameter_id)


@dataclass(frozen=True)
class RunResult:
    """Detached canonical snapshots; accessors never expose the driver's retained state."""

    _final_state_canonical: bytes = field(repr=False)
    _events_canonical: tuple[bytes, ...] = field(default_factory=tuple, repr=False)
    _states_canonical: tuple[bytes, ...] = field(default_factory=tuple, repr=False)
    _duplicate_count: int = field(default=0, repr=False)

    @property
    def final_state(self) -> State:
        return _object_snapshot(self._final_state_canonical, "final state")

    @property
    def events(self) -> list[Event]:
        return [_object_snapshot(value, "event") for value in self._events_canonical]

    @property
    def states(self) -> list[State]:
        return [_object_snapshot(value, "state") for value in self._states_canonical]

    @property
    def duplicate_count(self) -> int:
        return self._duplicate_count


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
    if quality_of is not None:
        raise TypeError("dependency quality must be recorded in envelope['_quality']")
    state = _snapshot_object(initial if initial is not None else machine.initial_state(), "state")
    params_bytes = canonical_json(_snapshot_object(params, "parameters"))
    states: list[bytes] = []
    events: list[bytes] = []
    seen_inputs: dict[tuple[str, bytes], str] = {}
    seen_fingerprints: set[str] = set()
    duplicate_count = 0
    for offset, env in enumerate(inputs):
        envelope = _snapshot_object(env, "envelope")
        if register_input(envelope, offset, seen_inputs, seen_fingerprints):
            duplicate_count += 1
            continue
        quality = _snapshot_object(envelope.get("_quality", {}), "quality")
        prior_state_bytes = canonical_json(state)
        result = machine.transition(
            _snapshot_object(state, "state"),
            _snapshot_object(envelope, "envelope"),
            _object_snapshot(params_bytes, "parameters"),
            quality,
        )
        if not isinstance(result, TransitionResult):
            raise TypeError("machine transition must return TransitionResult")
        if not isinstance(result.events, tuple) or any(
            not isinstance(event, dict) for event in result.events
        ):
            raise TypeError("transition events must be a tuple of objects")
        state = _snapshot_object(result.state, "state")
        state_bytes = canonical_json(state)
        event_bytes = tuple(
            canonical_json(_snapshot_object(event, "event")) for event in result.events
        )
        if state_bytes == prior_state_bytes and not event_bytes:
            continue
        states.append(state_bytes)
        events.extend(event_bytes)
    return RunResult(
        _final_state_canonical=canonical_json(state),
        _events_canonical=tuple(events),
        _states_canonical=tuple(states),
        _duplicate_count=duplicate_count,
    )


def register_input(
    envelope: Envelope,
    offset: int,
    seen_inputs: dict[tuple[str, bytes], str],
    seen_fingerprints: set[str],
) -> bool:
    """Register canonical event/revision identity; return true for exact retransmission."""
    if not isinstance(envelope, dict):
        raise InputIdentityError("input envelope must be an object")
    encoded = canonical_json(envelope)
    fingerprint = sha256_hex(encoded)
    event_id = envelope.get("event_id", f"in_{offset}")
    if not isinstance(event_id, str) or not event_id:
        raise InputIdentityError("input event_id must be a non-empty string when supplied")
    revision = canonical_json(envelope.get("revision"))
    identity = (event_id, revision)
    prior = seen_inputs.get(identity)
    if prior is not None and prior != fingerprint:
        raise InputIdentityError("same event/revision identity carries conflicting canonical bytes")
    duplicate = fingerprint in seen_fingerprints
    seen_inputs[identity] = fingerprint
    seen_fingerprints.add(fingerprint)
    return duplicate
def _snapshot_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"transition {label} must be an object")
    return _object_snapshot(canonical_json(value), label)


def _object_snapshot(data: bytes, label: str) -> dict[str, Any]:
    value = loads_canonical(data)
    if not isinstance(value, dict):  # pragma: no cover - encoded after object check
        raise TypeError(f"transition {label} must be an object")
    return value
