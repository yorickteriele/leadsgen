from app.agents.website import WebsiteAgent
from app.config import Settings


def test_extracts_contact_and_kvk_from_html() -> None:
    html = """
    <html lang="nl"><head><title>Jansen Onderhoud - Service</title>
    <meta name="description" content="Onderhoud, inspectie en storingen oplossen."></head>
    <body>
      <h1>Jansen Onderhoud</h1>
      <a href="/contact">Contact</a>
      <p>Vraag offerte aanvragen aan via info@jansen.nl of bel 010 123 4567.</p>
      <p>KvK 12345678</p>
    </body></html>
    """

    profile = WebsiteAgent(Settings())._extract_page(
        "https://jansen.nl", html, "Jansen Onderhoud offerte aanvragen info@jansen.nl KvK 12345678"
    )

    assert "info@jansen.nl" in profile.public_business_emails
    assert "12345678" in profile.visible_kvk_numbers
    assert "offerte aanvragen" in profile.detected_pain_points
    assert profile.contact_page_url == "https://jansen.nl/contact"

