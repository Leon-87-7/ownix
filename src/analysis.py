import re
from collections import Counter

STOPWORDS = {
    "this", "that", "what", "have", "with", "from", "they", "there",
    "their", "will", "would", "could", "should", "about", "which",
    "these", "those", "when", "where", "just", "like", "more", "some",
    "into", "than", "then", "also", "been", "were", "being",
}


def extract_key_phrases(transcript: str, max_phrases: int = 8) -> list[str]:
    words = re.findall(r'\b[a-z]{4,}\b', transcript.lower())
    words = [w for w in words if w not in STOPWORDS]
    return [word for word, _ in Counter(words).most_common(max_phrases)]
