from app.agents.classification import ClassificationAgent
from app.agents.website import WebsiteResult
from app.models import WebsiteProfile


def test_sidn_example_domain_is_landing_page() -> None:
    result = WebsiteResult(
        has_website=True,
        profile=WebsiteProfile(
            title="SIDN",
            meta_description="example domain name by SIDN",
            summary="This domain name has been registered by SIDN.",
            detected_company_names=["SIDN"],
        ),
    )

    status = ClassificationAgent().classify_domain_status(True, result)

    assert status == "landing_page"

