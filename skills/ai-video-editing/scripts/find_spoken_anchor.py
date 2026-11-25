"""Find all literal spoken keyword candidates on a confirmed transcript clock.

Match ignores punctuation/spacing and letter case. Returned intervals always
cover whole timestamped tokens: a substring is never assigned invented subword
times. Read/listen to candidates before using them as visual or subtitle cues.
"""

import argparse
import json
import math
from pathlib import Path
import unicodedata

from review_window import read_words


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def find_anchors(words, query, *, line=None, context=None, start=0, end=math.inf, origin=0):
    needle = normalized(query)
    if not needle:
        raise ValueError("Keyword must contain letters or numbers")
    if not (math.isfinite(origin) and origin >= 0 and math.isfinite(start) and 0 <= start < end <= math.inf):
        raise ValueError("Use a nonnegative origin and an increasing output-clock start/end window")
    if line is not None and not any("line_id" in word for word in words):
        raise ValueError("--line requires a transcript with lines and line IDs")
    context_key = normalized(context) if context else ""
    if context and not context_key:
        raise ValueError("Context must contain letters or numbers")
    groups = {}
    for word in words:
        if line is None or word.get("line_id") == str(line):
            groups.setdefault(word.get("line_index", 0), []).append(word)
    candidates = []
    for group in groups.values():
        text, positions, token_ranges = "", [], []
        for index, word in enumerate(group):
            token = normalized(word["text"])
            token_ranges.append((len(text), len(text) + len(token)))
            text += token
            positions.extend([index] * len(token))
        cursor = 0
        while True:
            hit = text.find(needle, cursor)
            if hit < 0:
                break
            cursor = hit + 1  # Keep repeated and overlapping occurrences.
            first, last = positions[hit], positions[hit + len(needle) - 1]
            source_end = max(word["end"] for word in group[first:last + 1])
            local_start, local_end = group[first]["start"] - origin, source_end - origin
            context_words = group[max(0, first - 8):min(len(group), last + 9)]
            context_text = "".join(word["text"] for word in context_words)
            if local_start < start or local_end > end or (context_key and context_key not in normalized(context_text)):
                continue
            exact_tokens = hit == token_ranges[first][0] and hit + len(needle) == token_ranges[last][1]
            candidates.append({"start": local_start, "end": local_end,
                               "source_start": group[first]["start"], "source_end": source_end,
                               "precision": "word-boundaries" if exact_tokens else "covering-token-interval",
                               "matched_tokens": "".join(word["text"] for word in group[first:last + 1]),
                               "line_id": group[first].get("line_id"), "context": context_text})
    return sorted(candidates, key=lambda hit: hit["start"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timings", type=Path)
    parser.add_argument("keyword")
    parser.add_argument("--line", help="line ID, or 1-based line number if input has no IDs")
    parser.add_argument("--context", help="required phrase within eight surrounding tokens")
    parser.add_argument("--start", type=float, default=0, help="earliest candidate start on the OUTPUT clock")
    parser.add_argument("--end", type=float, default=math.inf, help="latest candidate end on the OUTPUT clock")
    parser.add_argument("--origin", type=float, default=0, help="source-clock audio start of an excerpt; subtract explicitly, default 0")
    parser.add_argument("--line-words-local", action="store_true", help="confirm sentence-local words before adding global_start")
    args = parser.parse_args()
    try:
        words = read_words(args.timings, line_words_local=args.line_words_local)
        matches = find_anchors(words, args.keyword, line=args.line, context=args.context,
                               start=args.start, end=args.end, origin=args.origin)
        print(json.dumps({"timings": str(args.timings.resolve()), "keyword": args.keyword,
                          "origin_subtracted": args.origin, "matches": matches,
                          "matching": "casefolded alphanumeric text; token intervals only",
                          "listening_review_required": True}, ensure_ascii=True, indent=2))
        return 0 if matches else 1
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as error:
        parser.exit(2, f"Spoken anchor unavailable: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
