from dataclasses import dataclass, field
import dns.resolver


@dataclass
class DnsResult:
    has_dns: bool = False
    has_mx: bool = False
    nameservers: list[str] = field(default_factory=list)
    mail_provider: str | None = None
    records: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class DnsAgent:
    def __init__(self, resolver: dns.resolver.Resolver | None = None) -> None:
        self.resolver = resolver or dns.resolver.Resolver()

    def collect(self, domain: str) -> DnsResult:
        result = DnsResult()
        for record_type in ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "CAA"]:
            try:
                answers = self.resolver.resolve(domain, record_type, lifetime=5.0)
                values = [answer.to_text().strip('"') for answer in answers]
                result.records[record_type] = values
            except Exception as exc:  # DNS failures should not stop enrichment.
                result.errors.append(f"{record_type}: {exc.__class__.__name__}")

        result.has_dns = any(
            result.records.get(record_type) for record_type in ["A", "AAAA", "CNAME", "MX", "NS"]
        )
        result.has_mx = bool(result.records.get("MX"))
        result.nameservers = [
            ns.rstrip(".").lower() for ns in result.records.get("NS", [])
        ]
        result.mail_provider = self._infer_mail_provider(result.records.get("MX", []))
        return result

    def _infer_mail_provider(self, mx_records: list[str]) -> str | None:
        joined = " ".join(mx_records).lower()
        if "google.com" in joined or "googlemail.com" in joined:
            return "Google Workspace"
        if "outlook.com" in joined or "protection.outlook.com" in joined:
            return "Microsoft 365"
        if "transip" in joined:
            return "TransIP"
        if "mijndomein" in joined:
            return "Mijndomein"
        if "strato" in joined:
            return "Strato"
        return None

