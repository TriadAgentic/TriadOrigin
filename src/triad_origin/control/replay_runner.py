"""Deterministic replay runner (B07 — same-code replay identity + the exact receipt).

Wraps :func:`triad_origin.journal.replay` — which ALREADY drives ordered inputs through a
:class:`~triad_origin.transition.DeterministicMachine` using the identical code path live and in
replay (Doc 02 §02.16; there is no separate replay implementation to diverge from the live one) —
with the exact tape/config/build/checkpoint/output identity :data:`triad.replay_receipt.v1`
requires.

Two independent runs over byte-identical ``(machine, inputs, params)`` MUST produce
byte-identical receipts (``output_segment_hashes``, ``state_checksums``) — proved directly by this
module's own test battery (run twice, compare), never merely trusted from the journal module's
docstring claim (this repository's "never trust, recompute" discipline).

A checkpoint-resumed replay over the input SUFFIX must byte-match a cold replay over the FULL
input tape — :func:`journal.replay` already enforces this at the state-projection level (Doc 02
§02.16); this module additionally proves the *receipt* itself agrees.

Pure and side-effect-free: no clock, no I/O, no randomness, no network. Every identity field
(``build_commit``, the four digests, ``platform``, ``run_seed``, ``receipt_id``, ``signer``) is
supplied by the caller — none is inferred, defaulted, or read from the environment.
"""

from __future__ import annotations

from .. import contracts
from ..canonical import canonical_json, sha256_hex
from ..checkpoint import Checkpoint
from ..journal import ReplayContext, replay
from ..transition import DeterministicMachine, Envelope, Params

REPLAY_RECEIPT_SCHEMA = "triad.replay_receipt.v1"

_REQUIRED_IDENTITY_FIELDS = (
    "partition", "build_commit", "config_bundle_sha256", "contract_manifest_sha256",
    "parameter_digest", "instrument_digest", "platform", "run_seed", "receipt_id", "signer",
)


class ReplayRunnerError(RuntimeError):
    """A replay run could not produce a valid receipt — fail closed, never a partial receipt."""


def run_replay(
    machine: DeterministicMachine,
    inputs: list[Envelope],
    params: Params,
    *,
    partition: str,
    build_commit: str,
    config_bundle_sha256: str,
    contract_manifest_sha256: str,
    parameter_digest: str,
    instrument_digest: str,
    platform: str,
    run_seed: str,
    receipt_id: str,
    signer: str,
    fidelity_class: str = "EXACT",
    resume_from: Checkpoint | None = None,
    resume_context: ReplayContext | None = None,
    test_suite_result: dict | None = None,
    divergence_links: list | None = None,
) -> dict:
    """Run ``inputs`` through ``machine`` and return a validated ``triad.replay_receipt.v1``
    PAYLOAD (not the full envelope — the caller stamps ``schema``/``event_id``/producer identity).

    Refuses (:class:`ReplayRunnerError`) on a missing/empty identity field, a non-list ``inputs``,
    or a constructed payload that fails :func:`triad_origin.contracts.validate_payload` against
    ``triad.replay_receipt.v1`` — the last case is an internal defect in this function's own
    construction (every field here is caller-trusted, unlike an external candidate's wire
    content), so it fails closed rather than returning a flag.
    """
    local_values = {
        "partition": partition, "build_commit": build_commit,
        "config_bundle_sha256": config_bundle_sha256,
        "contract_manifest_sha256": contract_manifest_sha256,
        "parameter_digest": parameter_digest, "instrument_digest": instrument_digest,
        "platform": platform, "run_seed": run_seed, "receipt_id": receipt_id, "signer": signer,
    }
    for name in _REQUIRED_IDENTITY_FIELDS:
        value = local_values[name]
        if not isinstance(value, str) or not value:
            raise ReplayRunnerError(f"{name} must be a non-empty string")
    if not isinstance(inputs, list):
        raise ReplayRunnerError("inputs must be a list")
    if not isinstance(fidelity_class, str) or not fidelity_class:
        raise ReplayRunnerError("fidelity_class must be a non-empty string")

    try:
        journal, _events = replay(
            machine, inputs, params, partition=partition,
            resume_from=resume_from, resume_context=resume_context,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised named, never swallowed
        raise ReplayRunnerError(f"replay failed for partition {partition!r}: {exc}") from exc

    # ``inputs`` is always the FULL tape offered to this call — matching
    # :func:`triad_origin.journal.replay`'s own contract, which internally re-registers (but does
    # not re-process) any checkpoint-resumed prefix to validate it against the checkpoint's own
    # ``input_prefix_digest``. ``input_offsets`` therefore names the sub-range of NEWLY processed
    # positions within that full tape: ``[0, len(inputs))`` cold, or
    # ``[resume_from.input_offset + 1, len(inputs))`` when resuming (the prefix up to and
    # including ``input_offset`` was already accounted for by the checkpoint's own receipt).
    # ``input_segment_hashes`` hashes the exact bytes handed to this call — independently
    # recomputable by any caller holding the same ``inputs`` list, cold or resumed alike.
    # (``replay()`` above already fails closed if ``inputs`` is shorter than the checkpoint's own
    # consumed prefix, so ``end_offset >= start_offset`` holds here by construction.)
    start_offset = resume_from.input_offset + 1 if resume_from is not None else 0
    end_offset = len(inputs)
    input_segment_hash = sha256_hex(canonical_json(inputs))

    records = journal.records()
    output_bytes = canonical_json([
        {
            "transition_id": r.transition_id,
            "state_seq": r.state_seq,
            "to_state_digest": r.to_state_digest,
            "events_digest": r.events_digest,
        }
        for r in records
    ])
    output_segment_hash = sha256_hex(output_bytes)
    final_state = journal.project()
    projection_checksum = sha256_hex(canonical_json(final_state))
    checkpoint_identity = resume_from.state_checksum if resume_from is not None else "genesis"

    payload = {
        "receipt_id": receipt_id,
        "input_segment_hashes": [input_segment_hash],
        "input_offsets": [[start_offset, end_offset]],
        "fidelity_class": fidelity_class,
        "build_commit": build_commit,
        "config_bundle_sha256": config_bundle_sha256,
        "contract_manifest_sha256": contract_manifest_sha256,
        "parameter_digest": parameter_digest,
        "instrument_digest": instrument_digest,
        "checkpoint_identity": checkpoint_identity,
        "run_seed": run_seed,
        "platform": platform,
        "output_segment_hashes": [output_segment_hash],
        "state_checksums": {"final": projection_checksum},
        "test_suite_result": dict(test_suite_result) if test_suite_result else {},
        "divergence_links": list(divergence_links) if divergence_links else [],
        "signer": signer,
    }
    try:
        contracts.validate_payload(REPLAY_RECEIPT_SCHEMA, payload)
    except contracts.ContractError as exc:
        raise ReplayRunnerError(f"constructed replay receipt failed schema validation: {exc}") \
            from exc
    return payload
