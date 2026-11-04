# CLIP BPE vocabulary

`bpe_simple_vocab_16e6.txt.gz` is the byte-pair-encoding merge list used by OpenAI CLIP's text tokenizer, which is also the tokenizer family used by Stable Diffusion 1.x and SDXL text encoders. It is vendored here so prompt token counts can be checked offline and in CI without downloading models.

- Origin: OpenAI CLIP (https://github.com/openai/CLIP), MIT License, Copyright (c) 2021 OpenAI.
- Copy taken from the `open_clip_torch` package (https://github.com/mlfoundations/open_clip), MIT License.

`scripts/clip_tokens.py` is an independent re-implementation of the same BPE counting algorithm, used only to count tokens.
