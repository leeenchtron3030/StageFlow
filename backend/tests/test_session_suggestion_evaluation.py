import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.contexts.production.session_suggestions.contracts import Span
from app.contexts.production.session_suggestions.evaluate_cli import main
from app.contexts.production.session_suggestions.evaluation import evaluate_accuracy
from tests.test_session_suggestion_policy import at
from tests.test_session_suggestions import Harness


def test_hand_computed_recall_errors_percentiles_and_both_edges_within_60() -> None:
    truth = tuple(Span(at(i * 2000), at(i * 2000 + 1000)) for i in range(4))
    predicted = (Span(at(10), at(1020)), Span(at(2060), at(3060)), Span(at(4090), at(5120)))
    result = evaluate_accuracy(predicted, truth)
    assert asdict(result) == {
        "truth_count": 4, "suggestion_count": 3, "matched_count": 3, "recall": 0.75,
        "median_start_error_seconds": 60.0, "p95_start_error_seconds": 90.0,
        "median_end_error_seconds": 60.0, "p95_end_error_seconds": 120.0,
        "count_within_60_seconds": 2,
    }
    assert evaluate_accuracy(tuple(reversed(predicted)), tuple(reversed(truth))) == result


def test_matching_is_one_to_one_iou_inclusive_and_maximizes_recall() -> None:
    truth = (Span(at(0), at(100)), Span(at(50), at(150)))
    # First suggestion can match either target; second can only match the second.
    predictions = (Span(at(25), at(125)), Span(at(75), at(175)))
    assert evaluate_accuracy(predictions, truth).matched_count == 2
    assert evaluate_accuracy((truth[0], truth[0]), truth[:1]).matched_count == 1
    assert evaluate_accuracy((Span(at(0), at(200)),), truth[:1]).recall == 1
    assert evaluate_accuracy((Span(at(0), at(200.001)),), truth[:1]).recall == 0


def test_empty_no_matches_and_real_suggestion_contract_inputs() -> None:
    empty = evaluate_accuracy((), ())
    assert empty.recall == 0 and empty.median_start_error_seconds is None
    assert empty.p95_end_error_seconds is None and empty.count_within_60_seconds == 0
    truth = (Span(at(0), at(100)),)
    assert evaluate_accuracy((Span(at(1000), at(1100)),), truth).matched_count == 0
    suggestion = Harness().suggestion()
    assert evaluate_accuracy((suggestion,), (suggestion.candidate.span,)).recall == 1
    assert evaluate_accuracy((suggestion.candidate,), (suggestion.candidate.span,)).recall == 1


def test_cli_only_emits_sanitized_aggregate_numbers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.dumps([{"start": at(0).isoformat(), "end": at(100).isoformat(),
                           "private_title": "must never appear"}])

    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, "read_text", read)
    assert main(["private-ground-truth.json", "private-suggestions.json"]) == 0
    output = capsys.readouterr()
    assert not output.err and "private" not in output.out and "2026" not in output.out
    values = json.loads(output.out)
    assert values["recall"] == 1 and values["count_within_60_seconds"] == 1
    assert all(type(v) in (int, float) or v is None for v in values.values())


@pytest.mark.parametrize("payload", ["private invalid content", "{}", '[{"start":"private"}]',
                                     '[{"start":"2026-01-01","end":"2026-01-02"}]'])
def test_cli_invalid_input_never_echoes_data_or_path(
    payload: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def read(*args: object, **kwargs: object) -> str:
        return payload

    monkeypatch.setattr(Path, "read_text", read)
    assert main(["private-ground-truth.json", "private-suggestions.json"]) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err


def test_cli_missing_file_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def missing(*args: object, **kwargs: object) -> str:
        raise OSError("private filename")

    monkeypatch.setattr(Path, "read_text", missing)
    assert main(["private-ground-truth.json", "private-suggestions.json"]) == 1
    assert capsys.readouterr().out == '{"error_count": 1}\n'


@pytest.mark.parametrize("arguments", [
    [], ["private-ground-truth.json"],
    ["private-ground-truth.json", "private-suggestions.json", "private-extra"],
    ["private-ground-truth.json", "private-suggestions.json", "--private-option=secret"],
    ["--private-option", "private-ground-truth.json", "private-suggestions.json"],
    ["--help=private-value"],
])
def test_cli_invalid_arguments_never_echo_caller_input(
    arguments: list[str], capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(arguments) == 1
    output = capsys.readouterr()
    assert output.out == '{"error_count": 1}\n' and not output.err
