from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class NormalizedDomain:
    input_domain: str
    domain: str
    candidates: list[str]


class DomainNormalizerAgent:
    def normalize(self, raw_domain: str) -> NormalizedDomain:
        raw = raw_domain.strip().lower()
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or raw).strip(".")
        if host.startswith("www."):
            base = host[4:]
            candidates = [host, base]
        else:
            base = host
            candidates = [host, f"www.{host}"]
        deduped = list(dict.fromkeys(candidates))
        return NormalizedDomain(input_domain=raw_domain, domain=base, candidates=deduped)

