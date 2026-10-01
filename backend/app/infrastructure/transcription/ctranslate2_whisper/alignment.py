"""Ported from faster-whisper 1.2.1; bounded English inference subset.

MIT License

Copyright (c) 2023 SYSTRAN

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import itertools
from typing import Any

from .features import np
from .tokenizer import Tokenizer


class Alignment:
    """Native alignment output is adapter-local; never crosses the domain port."""

    def __init__(self, model: Any) -> None:
        self.model = model
        self.frames_per_second = 100
        self.tokens_per_second = 50

    def add_word_timestamps(
        self,
        segments: list[Any],
        tokenizer: Tokenizer,
        encoder_output: Any,
        num_frames: int,
        prepend_punctuations: str,
        append_punctuations: str,
        last_speech_timestamp: float,
    ) -> float | None:
        if len(segments) == 0:
            return

        text_tokens: list[list[int]] = []
        text_tokens_per_segment: list[list[list[int]]] = []
        for segment in segments:
            segment_tokens = [
                [token for token in subsegment["tokens"] if token < tokenizer.eot]
                for subsegment in segment
            ]
            text_tokens.append(list(itertools.chain.from_iterable(segment_tokens)))
            text_tokens_per_segment.append(segment_tokens)

        alignments = self.find_alignment(
            tokenizer, text_tokens, encoder_output, num_frames
        )
        median_max_durations: list[tuple[float, float]] = []
        for alignment in alignments:
            word_durations = np.array(
                [word["end"] - word["start"] for word in alignment]
            )
            word_durations = word_durations[word_durations.nonzero()]
            median_duration = (
                np.median(word_durations) if len(word_durations) > 0 else 0.0
            )
            median_duration = min(0.7, float(median_duration))
            max_duration = median_duration * 2

            # hack: truncate long words at sentence boundaries.
            # a better segmentation algorithm based on VAD should be able to replace this.
            if len(word_durations) > 0:
                sentence_end_marks = ".。!！?？"
                # ensure words at sentence boundaries
                # are not longer than twice the median word duration.
                for i in range(1, len(alignment)):
                    if alignment[i]["end"] - alignment[i]["start"] > max_duration:
                        if alignment[i]["word"] in sentence_end_marks:
                            alignment[i]["end"] = alignment[i]["start"] + max_duration
                        elif alignment[i - 1]["word"] in sentence_end_marks:
                            alignment[i]["start"] = alignment[i]["end"] - max_duration

            merge_punctuations(alignment, prepend_punctuations, append_punctuations)
            median_max_durations.append((median_duration, max_duration))

        for segment_idx, segment in enumerate(segments):
            word_index = 0
            time_offset = segment[0]["seek"] / self.frames_per_second
            median_duration, max_duration = median_max_durations[segment_idx]
            for subsegment_idx, subsegment in enumerate(segment):
                saved_tokens = 0
                words: list[Any] = []

                while word_index < len(alignments[segment_idx]) and saved_tokens < len(
                    text_tokens_per_segment[segment_idx][subsegment_idx]
                ):
                    timing = alignments[segment_idx][word_index]

                    if timing["word"]:
                        words.append(
                            dict(
                                word=timing["word"],
                                start=round(time_offset + timing["start"], 2),
                                end=round(time_offset + timing["end"], 2),
                                probability=timing["probability"],
                            )
                        )

                    saved_tokens += len(timing["tokens"])
                    word_index += 1

                # hack: truncate long words at segment boundaries.
                # a better segmentation algorithm based on VAD should be able to replace this.
                if len(words) > 0:
                    # ensure the first and second word after a pause is not longer than
                    # twice the median word duration.
                    if words[0][
                        "end"
                    ] - last_speech_timestamp > median_duration * 4 and (
                        words[0]["end"] - words[0]["start"] > max_duration
                        or (
                            len(words) > 1
                            and words[1]["end"] - words[0]["start"] > max_duration * 2
                        )
                    ):
                        if (
                            len(words) > 1
                            and words[1]["end"] - words[1]["start"] > max_duration
                        ):
                            boundary = max(
                                words[1]["end"] / 2, words[1]["end"] - max_duration
                            )
                            words[0]["end"] = words[1]["start"] = boundary
                        words[0]["start"] = max(0, words[0]["end"] - max_duration)

                    # prefer the segment-level start timestamp if the first word is too long.
                    if (
                        subsegment["start"] < words[0]["end"]
                        and subsegment["start"] - 0.5 > words[0]["start"]
                    ):
                        words[0]["start"] = max(
                            0,
                            min(words[0]["end"] - median_duration, subsegment["start"]),
                        )
                    else:
                        subsegment["start"] = words[0]["start"]

                    # prefer the segment-level end timestamp if the last word is too long.
                    if (
                        subsegment["end"] > words[-1]["start"]
                        and subsegment["end"] + 0.5 < words[-1]["end"]
                    ):
                        words[-1]["end"] = max(
                            words[-1]["start"] + median_duration, subsegment["end"]
                        )
                    else:
                        subsegment["end"] = words[-1]["end"]

                    last_speech_timestamp = subsegment["end"]
                segments[segment_idx][subsegment_idx]["words"] = words
        return last_speech_timestamp


    def find_alignment(
        self,
        tokenizer: Tokenizer,
        text_tokens: list[list[int]],
        encoder_output: Any,
        num_frames: int,
        median_filter_width: int = 7,
    ) -> list[Any]:
        if len(text_tokens) == 0:
            return []

        results = self.model.align(
            encoder_output,
            tokenizer.sot_sequence,
            text_tokens,
            num_frames,
            median_filter_width=median_filter_width,
        )
        return_list: list[Any] = []
        for result, text_token in zip(results, text_tokens, strict=False):
            text_token_probs = result.text_token_probs
            alignments = result.alignments
            text_indices = np.array([pair[0] for pair in alignments])
            time_indices = np.array([pair[1] for pair in alignments])

            words, word_tokens = tokenizer.split_to_word_tokens(
                text_token + [tokenizer.eot]
            )
            if len(word_tokens) <= 1:
                # return on eot only
                # >>> np.pad([], (1, 0))
                # array([0.])
                # This results in crashes when we lookup jump_times with float, like
                # IndexError: arrays used as indices must be of integer (or boolean) type
                return_list.append([])
                continue
            word_boundaries = np.pad(
                np.cumsum([len(t) for t in word_tokens[:-1]]), (1, 0)
            )
            if len(word_boundaries) <= 1:
                return_list.append([])
                continue

            jumps = np.pad(np.diff(text_indices), (1, 0), constant_values=1).astype(
                bool
            )
            jump_times = time_indices[jumps] / self.tokens_per_second
            start_times = jump_times[word_boundaries[:-1]]
            end_times = jump_times[word_boundaries[1:]]
            word_probabilities = [
                float(np.mean(np.asarray(text_token_probs[i:j], dtype=np.float64)))
                for i, j in zip(word_boundaries[:-1], word_boundaries[1:], strict=False)
            ]

            return_list.append(
                [
                    dict(
                        word=word,
                        tokens=tokens,
                        start=start,
                        end=end,
                        probability=probability,
                    )
                    for word, tokens, start, end, probability in zip(
                        words, word_tokens, start_times, end_times, word_probabilities, strict=False
                    )
                ]
            )
        return return_list



def merge_punctuations(alignment: list[Any], prepended: str, appended: str) -> None:
    # merge prepended punctuations
    i = len(alignment) - 2
    j = len(alignment) - 1
    while i >= 0:
        previous = alignment[i]
        following = alignment[j]
        if previous["word"].startswith(" ") and previous["word"].strip() in prepended:
            # prepend it to the following word
            following["word"] = previous["word"] + following["word"]
            following["tokens"] = previous["tokens"] + following["tokens"]
            previous["word"] = ""
            previous["tokens"] = []
        else:
            j = i
        i -= 1

    # merge appended punctuations
    i = 0
    j = 1
    while j < len(alignment):
        previous = alignment[i]
        following = alignment[j]
        if not previous["word"].endswith(" ") and following["word"] in appended:
            # append it to the previous word
            previous["word"] = previous["word"] + following["word"]
            previous["tokens"] = previous["tokens"] + following["tokens"]
            following["word"] = ""
            following["tokens"] = []
        else:
            i = j
        j += 1

