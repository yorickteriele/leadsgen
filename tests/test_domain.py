from app.agents.domain import DomainNormalizerAgent


def test_normalizes_protocol_path_and_www() -> None:
    result = DomainNormalizerAgent().normalize("https://www.Example.nl/path?q=1")

    assert result.domain == "example.nl"
    assert result.candidates == ["www.example.nl", "example.nl"]


def test_adds_www_candidate_for_root_domain() -> None:
    result = DomainNormalizerAgent().normalize("example.nl/")

    assert result.domain == "example.nl"
    assert result.candidates == ["example.nl", "www.example.nl"]

