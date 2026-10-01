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
import string
from functools import cached_property
from typing import Protocol


class Encoding(Protocol):
    @property
    def ids(self) -> list[int]: ...


class TokenizerBackend(Protocol):
    def token_to_id(self, text: str) -> int | None: ...
    def encode(self, text: str, *, add_special_tokens: bool) -> Encoding: ...
    def decode(self, tokens: list[int]) -> str: ...


class Tokenizer:
    """Simple wrapper around a tokenizers.Tokenizer."""

    def __init__(
        self,
        tokenizer: TokenizerBackend,
        multilingual: bool,
        task: str = "transcribe",
        language: str = "en",
    ) -> None:
        self.tokenizer = tokenizer

        if multilingual:
            if task not in _TASKS:
                raise ValueError(
                    f"'{task}' is not a valid task (accepted tasks: {', '.join(_TASKS)})"
                )

            if language not in _LANGUAGE_CODES:
                raise ValueError(
                    f"'{language}' is not a valid language code "
                    f"(accepted: {', '.join(_LANGUAGE_CODES)})"
                )

            self.task = self._token_id(f"<|{task}|>")
            self.language = self._token_id(f"<|{language}|>")
            self.language_code = language
        else:
            self.task = None
            self.language = None
            self.language_code = "en"

    def _token_id(self, text: str) -> int:
        token = self.tokenizer.token_to_id(text)
        if token is None:
            raise ValueError("required tokenizer token unavailable")
        return token

    @cached_property
    def transcribe(self) -> int:
        return self._token_id("<|transcribe|>")

    @cached_property
    def translate(self) -> int:
        return self._token_id("<|translate|>")

    @cached_property
    def sot(self) -> int:
        return self._token_id("<|startoftranscript|>")

    @cached_property
    def sot_lm(self) -> int:
        return self._token_id("<|startoflm|>")

    @cached_property
    def sot_prev(self) -> int:
        return self._token_id("<|startofprev|>")

    @cached_property
    def eot(self) -> int:
        return self._token_id("<|endoftext|>")

    @cached_property
    def no_timestamps(self) -> int:
        return self._token_id("<|notimestamps|>")

    @cached_property
    def no_speech(self) -> int:
        token = self.tokenizer.token_to_id("<|nospeech|>")
        return token if token is not None else self._token_id("<|nocaptions|>")

    @property
    def timestamp_begin(self) -> int:
        return self.no_timestamps + 1

    @property
    def sot_sequence(self) -> list[int]:
        sequence = [self.sot]

        if self.language is not None:
            sequence.append(self.language)

        if self.task is not None:
            sequence.append(self.task)

        return sequence

    def encode(self, text: str) -> list[int]:
        return self.tokenizer.encode(text, add_special_tokens=False).ids

    def decode(self, tokens: list[int]) -> str:
        text_tokens = [token for token in tokens if token < self.eot]
        return self.tokenizer.decode(text_tokens)

    def decode_with_timestamps(self, tokens: list[int]) -> str:
        outputs: list[str] = []
        pending: list[int] = []
        for token in tokens:
            if token >= self.timestamp_begin:
                outputs.append(self.tokenizer.decode(pending))
                pending = []
                outputs.append(f"<|{(token - self.timestamp_begin) * 0.02:.2f}|>")
            else:
                pending.append(token)
        outputs.append(self.tokenizer.decode(pending))
        return "".join(outputs)

    @cached_property
    def non_speech_tokens(self) -> tuple[int, ...]:
        """
        Returns the list of tokens to suppress in order to avoid any speaker tags or non-speech
        annotations, to prevent sampling texts that are not actually spoken in the audio, e.g.

        - ♪♪♪
        - ( SPEAKING FOREIGN LANGUAGE )
        - [DAVID] Hey there,

        keeping basic punctuations like commas, periods, question marks, exclamation points, etc.
        """
        symbols = list('"#()*+/:;<=>@[\\]^_`{|}~「」『』')
        symbols += (
            "<< >> <<< >>> -- --- -( -[ (' (\" (( )) ((( ))) [[ ]] {{ }} ♪♪ ♪♪♪".split()
        )

        # symbols that may be a single token or multiple tokens depending on the tokenizer.
        # In case they're multiple tokens, suppress the first token, which is safe because:
        # These are between U+2640 and U+267F miscellaneous symbols that are okay to suppress
        # in generations, and in the 3-byte UTF-8 representation they share the first two bytes.
        miscellaneous = set("♩♪♫♬♭♮♯")
        assert all(0x2640 <= ord(c) <= 0x267F for c in miscellaneous)

        # allow hyphens "-" and single quotes "'" between words, but not at the beginning of a word
        result = {self.encode(" -")[0], self.encode(" '")[0]}
        for symbol in symbols + list(miscellaneous):
            for tokens in [
                self.encode(symbol),
                self.encode(" " + symbol),
            ]:
                if len(tokens) == 1 or symbol in miscellaneous:
                    result.add(tokens[0])

        return tuple(sorted(result))

    def split_to_word_tokens(
        self, tokens: list[int]
    ) -> tuple[list[str], list[list[int]]]:
        if self.language_code in {"zh", "ja", "th", "lo", "my", "yue"}:
            # These languages don't typically use spaces, so it is difficult to split words
            # without morpheme analysis. Here, we instead split words at any
            # position where the tokens are decoded as valid unicode points
            return self.split_tokens_on_unicode(tokens)

        return self.split_tokens_on_spaces(tokens)

    def split_tokens_on_unicode(
        self, tokens: list[int]
    ) -> tuple[list[str], list[list[int]]]:
        decoded_full = self.decode_with_timestamps(tokens)
        replacement_char = "\ufffd"

        words: list[str] = []
        word_tokens: list[list[int]] = []
        current_tokens: list[int] = []
        unicode_offset = 0

        for token in tokens:
            current_tokens.append(token)
            decoded = self.decode_with_timestamps(current_tokens)

            try:
                replacement_char_index = decoded.index(replacement_char)
                replacement_char_index += unicode_offset
            except ValueError:
                replacement_char_index = None

            if replacement_char_index is None or (
                replacement_char_index < len(decoded_full)
                and decoded_full[replacement_char_index] == replacement_char
            ):
                words.append(decoded)
                word_tokens.append(current_tokens)
                current_tokens = []
                unicode_offset += len(decoded)

        return words, word_tokens

    def split_tokens_on_spaces(
        self, tokens: list[int]
    ) -> tuple[list[str], list[list[int]]]:
        subwords, subword_tokens_list = self.split_tokens_on_unicode(tokens)
        words: list[str] = []
        word_tokens: list[list[int]] = []

        for subword, subword_tokens in zip(subwords, subword_tokens_list, strict=False):
            special = subword_tokens[0] >= self.eot
            with_space = subword.startswith(" ")
            punctuation = subword.strip() in string.punctuation
            if special or with_space or punctuation or len(words) == 0:
                words.append(subword)
                word_tokens.append(subword_tokens)
            else:
                words[-1] = words[-1] + subword
                word_tokens[-1].extend(subword_tokens)

        return words, word_tokens


_TASKS = ("transcribe",)
_LANGUAGE_CODES = ("en",)
