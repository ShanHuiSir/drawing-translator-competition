"""Offline terminology first, offline neural translation second, human review last."""

import re
from collections import OrderedDict

from .glossary import load_glossary, normalize
from .paths import MODEL_ROOT

# Numbers, tolerance symbols and drawing identifiers are evidence, never guessed.
NUMBER = re.compile(r"(?<![A-Za-z])[-+±]?\d*\.?\d+(?:[°′″%])?")
IDENTIFIER = re.compile(r"^(?:[A-Z]+[-_/])?\d[\w./+°±×'\" -]*$", re.I)


class Translator:
    def __init__(self):
        self.reload()
        self.model = None
        self.tokenizer = None
        self.cache = OrderedDict()

    def reload(self):
        self.terms = load_glossary()
        self.exact = {normalize(k): v for k, v in self.terms.items()}
        self.phrases = sorted(self.terms, key=len, reverse=True)
        self.pattern = re.compile("|".join(r"(?<![a-z])" + r"\s*".join(re.escape(c) for c in p) + r"(?![a-z])" for p in self.phrases), re.I)
        if hasattr(self, "cache"):
            self.cache.clear()

    def _load_model(self):
        """CTranslate2 opens the shipped Argos model directly; no package manager/network."""
        if self.model is not None:
            return True
        candidates = list(MODEL_ROOT.glob("*/model/model.bin"))
        if not candidates:
            return False
        import ctranslate2
        import sentencepiece
        root = candidates[0].parent.parent
        self.tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(root / "sentencepiece.model"))
        self.model = ctranslate2.Translator(str(root / "model"), device="cpu", compute_type="int8", intra_threads=4)
        return True

    def _neural(self, texts):
        # The OPUS training corpus uses sentence case. All-capital drawing notes
        # otherwise get mistaken for names; OCR evidence itself is never modified.
        inputs = [self.tokenizer.encode(t.lower(), out_type=str) for t in texts]
        results = self.model.translate_batch(inputs, beam_size=4, length_penalty=.2,
                                             replace_unknowns=True, max_batch_size=32, max_decoding_length=256)
        return [self.tokenizer.decode(r.hypotheses[0]).replace("▁", " ").strip() for r in results]

    def translate_regions(self, regions):
        """Batch unique lines to amortize inference; bound the in-memory cache."""
        pending = {}
        for r in regions:
            text = r.source.strip()
            key = normalize(text)
            if key in self.exact:
                self._assign(r, self.exact[key], "glossary", False)
            elif not re.search(r"[A-Za-z]{2}", text):
                self._assign(r, text, "identifier", False)
            elif self._identifier(text):
                self._assign(r, text, "identifier", False)
            elif self._template(text):
                self._assign(r, self._template(text), "glossary-template", True)
            elif not re.search(r"[a-z]{2}", self._term_replace(text), re.I):
                self._assign(r, self._term_replace(text), "glossary-template", True)
            elif text in self.cache:
                self._assign(r, *self.cache[text])
            else:
                pending.setdefault(text, []).append(r)
        if not pending:
            return
        neural = self._load_model()
        sources = list(pending)
        # Long phrases use terminology-aware anchors. The neural model sees the entire
        # line and the chosen technical Chinese replaces only exact known English spans.
        outputs = self._neural(sources) if neural else [self._term_replace(t) for t in sources]
        for text, output in zip(sources, outputs):
            method = "offline-nmt" if neural else "glossary-partial"
            warnings = []
            if NUMBER.findall(text) != NUMBER.findall(output):
                # Retry by translating alphabetic chunks only: all numeric substrings
                # remain byte-for-byte intact, including decimal precision and signs.
                parts = re.split(r"([-+±]?\d*\.?\d+[°′″%]?)", text)
                indices = [i for i, p in enumerate(parts) if re.search(r"[a-z]{2}", p, re.I)]
                if neural and indices:
                    trans = self._neural([parts[i] for i in indices])
                    for i, value in zip(indices, trans):
                        parts[i] = value
                    output = "".join(parts)
                else:
                    output = self._term_replace(text)
                warnings.append("含尺寸或公差，已保留原始数字，请复核语义与单位")
            # Even fluent generic NMT is not a certified engineering translation.
            review = True
            if not re.search(r"[\u4e00-\u9fff]", output):
                warnings.append("未得到中文译文，请手动补充术语")
            value = (output, method, review)
            self.cache[text] = value
            while len(self.cache) > 5000:
                self.cache.popitem(last=False)
            for r in pending[text]:
                self._assign(r, *value)
                r.warnings.extend(warnings)

    def _identifier(self, text):
        # A dimension with TAP/DEEP/THRU is translatable. Pure document IDs are kept.
        letters = re.findall(r"[A-Za-z]{2,}", text)
        if any(normalize(x) in self.exact for x in letters):
            return False
        if text in ("TE", "TE Connectivity Ltd.", "MOLEX", "PASSARO") or re.fullmatch(r"[A-Z]{2,5}", text):
            return True
        return bool(IDENTIFIER.fullmatch(text)) or bool(re.fullmatch(r"[A-Z]{1,5}[- ]?\d[-\w/ .]*", text))

    def _term_replace(self, text):
        # Longest matches win. Word boundaries prevent LAND from matching ISLAND.
        return self.pattern.sub(lambda m: self.exact.get(normalize(m.group()), m.group()), text)

    def _template(self, text):
        """Number-capturing engineering templates preserve units and tolerance digits."""
        compact = re.sub(r"\s+", "", text.lower())
        match = re.fullmatch(r"seesheet#?(\d+)(?:forangle)?", compact)
        if match:
            return f"见第 {match[1]} 页" + ("角度说明" if compact.endswith("forangle") else "")
        match = re.fullmatch(r"(\d+)req['’]?d(?:-(.*))?", compact)
        if match:
            return f"需要 {match[1]} 件" + (f"，{match[2].upper()}" if match[2] else "")
        match = re.fullmatch(r"(\d+)(?:plc|places?|pc|pcs)", compact)
        if match:
            return f"{match[1]} 处"
        return None

    @staticmethod
    def _assign(region, value, method, review):
        region.translation = value
        region.translation_method = method
        region.needs_review = review or region.confidence < .85
        region.enabled = method != "identifier"
