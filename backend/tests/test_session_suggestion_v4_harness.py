"""Seeded generic schedule errors, v4 CLI dispatch and service persistence."""
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from app.contexts.production.session_suggestions import harness_cli, service
from app.contexts.production.session_suggestions.contracts import CandidateV4, ScheduleOffsetEntry
from app.contexts.production.session_suggestions.harness import parse_manifest, run_manifest
from app.contexts.production.session_suggestions.policy_v4 import POLICY_V4
from app.contexts.production.session_suggestions.scenarios import (
    generate_scenario,
    realistic_schedule_error,
)
from app.shared.ids import EntityId
from tests.test_durable_event_mode_kernel import ACTOR_ID
from tests.test_session_boundary_proposals import boundaries, realized
from tests.test_session_suggestion_policy import at
from tests.test_session_suggestions import Harness


def test_realistic_generator_seed_pin_and_manifest_roundtrip() -> None:
    stage, timeline = realistic_schedule_error(7, timeline=True)
    assert stage == realistic_schedule_error(7)
    encoded = json.dumps((stage, timeline), sort_keys=True)
    assert sha256(encoded.encode()).hexdigest() == (
        '4659ded2483f18522b0fc44dec4cb76f7276897d429bc221ff87d16373b7e681')
    assert len(parse_manifest(json.dumps({'stages': [stage]}))[0].truth) == 30
    stage['schedule'].clear()
    assert len(realistic_schedule_error(7)['schedule']) == 30


@pytest.mark.parametrize('seed', range(1, 21))
def test_realistic_generator_bounded_symmetric_draws_and_cumulative_walk(seed: int) -> None:
    stage, timeline = realistic_schedule_error(seed, slot_seconds=1201, timeline=True)
    talks = timeline['talks']
    duration = 1021
    previous_lateness = talks[0]['start_seconds']
    for i, talk in enumerate(talks):
        length = talk['end_seconds'] - talk['start_seconds']
        assert duration * .6 <= length <= duration * 1.4
        if i:
            gap = talk['start_seconds'] - talks[i - 1]['end_seconds']
            assert 120 <= gap <= 240
            prior_error = talks[i - 1]['end_seconds'] - talks[i - 1]['start_seconds'] - duration
            assert talk['start_seconds'] - i * 1201 == previous_lateness + prior_error + gap - 180
        previous_lateness = talk['start_seconds'] - i * 1201
    assert all(a['end_seconds'] == b['start_seconds'] for a, b in zip(
        timeline['blocks'], timeline['blocks'][1:], strict=False))
    manifest = parse_manifest(json.dumps({'stages': [stage]}))
    a = run_manifest(manifest, policy_version='4')
    assert a == run_manifest(parse_manifest(json.dumps({'stages': [stage]})), policy_version='4')


@pytest.mark.parametrize('dropped,added,tail', [
    (False, False, False), (True, False, False), (False, True, False),
    (True, True, False), (True, True, True)])
def test_realistic_optional_dropped_added_and_after_program(dropped: bool, added: bool,
                                                          tail: bool) -> None:
    stage, replay = realistic_schedule_error(13, talk_count=8, slot_seconds=1800,
                                             dropped=dropped, added=added,
                                             after_program=tail, timeline=True)
    assert len(stage['schedule']) == 8
    assert len(stage['truth']) == len(replay['talks']) == 8 - dropped + added + tail
    assert sum(t['schedule_index'] is None for t in replay['talks']) == added + tail
    scheduled = {t['schedule_index'] for t in replay['talks'] if t['schedule_index'] is not None}
    assert len(scheduled) == 8 - dropped
    for block, data in zip(stage['blocks'], replay['blocks'], strict=True):
        assert block['duration_us'] == (data['end_seconds'] - data['start_seconds']) * 1_000_000
        for a, b in data['holding_intervals']:
            assert data['start_seconds'] <= a < b <= data['end_seconds']
    assert len(parse_manifest(json.dumps({'stages': [stage]}))[0].truth) == len(replay['talks'])


@pytest.mark.parametrize('options', [{'seed': -1}, {'seed': True}, {'talk_count': 1},
                                    {'slot_seconds': 1199}, {'slot_seconds': 1801}])
def test_generator_refuses_invalid_options(options: dict[str, Any]) -> None:
    arguments: dict[str, Any] = {'seed': 1, **options}
    with pytest.raises(ValueError, match='invalid_scenario_options'):
        realistic_schedule_error(**arguments)


def test_harness_v4_cli_override_dispatch_and_sanitized_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.dumps(generate_scenario('clean-day'))

    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, 'read_text', read)
    assert harness_cli.main(['private-path', '--policy-version', '4', '--producer-offset',
                             '2000-01-01T00:00:00Z', '0']) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report['policy_version'] == 4
    assert report['scenarios'][0]['per_seed'][0]['metrics']['recall'] == 1.0
    assert 'private-path' not in output.out and not output.err


def test_service_v4_zero_blocks_replay_offsets_and_default_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h = Harness()
    original = h.run()
    assert original.policy.version == '3'
    monkeypatch.setattr(service, 'POLICY_VERSION', 4)
    setting = h.service.set_offset(event_id=h.event, stage_id=h.stage, command_id=EntityId.new(),
                                  actor_id=ACTOR_ID, entries=(ScheduleOffsetEntry(at(0), 0),))
    run = h.run()
    assert run.policy == POLICY_V4 and run.blocks == ()
    assert run.override_setting_version == setting.version
    assert run.input_digest != original.input_digest
    assert h.run() == h.service.latest_run(h.event, h.stage) == run
    suggestion = h.service.page(h.event, h.stage)[0][0]
    assert suggestion.policy_version == '4' and isinstance(suggestion.candidate, CandidateV4)
    assert suggestion.candidate.schedule_offset_source == 'producer'
    assert h.service.read(h.event, suggestion.id)[0] == suggestion
    assert not h.kernel_repo.list_sessions_for_stage(h.stage)
    with pytest.raises(ValueError, match='does not use schedule blocks'):
        replace(run, blocks=original.blocks)


def test_v4_boundary_proposals_record_actual_version_and_deduplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    h, session, _ = realized()
    monkeypatch.setattr(service, 'POLICY_VERSION', 4)
    run = h.run()
    assert run.boundary_proposals_created == 2
    proposals = boundaries(h).open(h.event, session.id)
    assert all(p.policy_version == '4' for p in proposals)
    h.repository.assets[h.stage] = (replace(h.repository.assets[h.stage][0],
                                           segmentation_ids=(EntityId.new(),)),)
    assert h.run().boundary_proposals_created == 0
    assert boundaries(h).open(h.event, session.id) == proposals
