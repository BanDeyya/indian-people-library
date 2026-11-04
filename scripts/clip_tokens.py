"""Count CLIP text-encoder tokens offline (the tokenizer family used by SD 1.x and SDXL).

Independent re-implementation of CLIP's byte-pair-encoding, using the vocabulary vendored
in third_party/clip (OpenAI CLIP, MIT). Used only for counting, never for generation.
SDXL reads 77 tokens including the start and end tokens, so the content budget is 75.
"""
from __future__ import annotations

import gzip
import html
from functools import lru_cache
from pathlib import Path

import regex

VOCAB = Path(__file__).resolve().parent.parent / "third_party" / "clip" / "bpe_simple_vocab_16e6.txt.gz"
_PAT = regex.compile(r"""'s|'t|'re|'ve|'m|'ll|'d|[\p{L}]+|[\p{N}]|[^\s\p{L}\p{N}]+""", regex.IGNORECASE)


@lru_cache(maxsize=1)
def _byte_map() -> dict[int, str]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, map(chr, cs)))


@lru_cache(maxsize=1)
def _ranks() -> dict[tuple[str, str], int]:
    lines = gzip.open(VOCAB).read().decode("utf-8").split("\n")[1:49152 - 256 - 2 + 1]
    return {tuple(line.split()): i for i, line in enumerate(lines)}


@lru_cache(maxsize=20000)
def _bpe_len(token: str) -> int:
    ranks = _ranks()
    word = list(token[:-1]) + [token[-1] + "</w>"]
    while len(word) > 1:
        pairs = {(word[i], word[i + 1]) for i in range(len(word) - 1)}
        best = min(pairs, key=lambda p: ranks.get(p, float("inf")))
        if best not in ranks:
            break
        merged, i = [], 0
        while i < len(word):
            if i < len(word) - 1 and (word[i], word[i + 1]) == best:
                merged.append(word[i] + word[i + 1])
                i += 2
            else:
                merged.append(word[i])
                i += 1
        word = merged
    return len(word)


def count(text: str) -> int:
    """Number of content tokens (start/end tokens not included)."""
    text = " ".join(html.unescape(html.unescape(text)).split()).lower()
    bm = _byte_map()
    return sum(_bpe_len("".join(bm[b] for b in piece.encode("utf-8"))) for piece in _PAT.findall(text))


def approx(text: str) -> int:
    """Rough token estimate for encoders we cannot run offline (T5, Qwen): words x 1.35."""
    return int(len(text.split()) * 1.35) + 1
