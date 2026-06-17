from app.main import app


def test_swagger_openapi_contains_enrichment_endpoint() -> None:
    spec = app.openapi()
    assert spec["info"]["title"] == "Aresis Lead Enrichment API"
    assert "/enrich-domain" in spec["paths"]
    assert spec["paths"]["/enrich-domain"]["post"]["tags"] == ["enrichment"]
