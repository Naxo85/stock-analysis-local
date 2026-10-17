"""Citation identities shared by tool provenance and report validation.

Only remove sentence punctuation from bare prose URLs. Explicit Markdown
destinations and tool URL fields keep their complete path/query identity.
Never authorize a redirect, another host/path, or links buried in snippets.
"""
import re
from urllib.parse import urlsplit, urlunsplit


def url_identity(url: str) -> str:
    """Canonical resource identity, not redirect guessing or fuzzy matching.

    EDGAR's CIK path segment is a numeric issuer identifier; padding does not
    change it. Accession/document/query remain exact. Other path components,
    hosts, protocols and queries are never substituted.
    """
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    path = parts.path
    if parts.scheme.lower() == 'https' and netloc == 'www.sec.gov':
        match = re.fullmatch(r'/Archives/edgar/data/([0-9]+)/([0-9]{18})/(.+)', path)
        if match:
            path = '/Archives/edgar/data/' + str(int(match[1])) + '/' + match[2] + '/' + match[3]
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, parts.fragment))


def cited_urls(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    explicit = set()
    spans = []
    for match in re.finditer(r'\]\((https?://[^\s<>"\[\]]+)\)', text):
        explicit.add(match[1])
        spans.append(match.span(1))
    for match in re.finditer(r'<(https?://[^\s<>]+)>', text):
        explicit.add(match[1])
        spans.append(match.span(1))
    for match in re.finditer(r'https?://[^\s<>"\'\[\]()]+', text):
        if not any(a <= match.start() < b for a, b in spans):
            explicit.add(match[0].rstrip('.,;:!?'))
    return explicit
