import zipfile
from io import BytesIO

from datetime import date

from scripts.download_domainmetadata_nl_domains import default_download_date, domains_from_zip


def test_domains_from_zip_extracts_csv_domains() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("domains.csv", "domain\nwww.alpha.nl\nhttps://beta.nl/path\n")

    assert domains_from_zip(buffer.getvalue()) == ["alpha.nl", "beta.nl"]


def test_default_download_date_is_yesterday() -> None:
    assert default_download_date(date(2026, 6, 17)) == "2026-06-16"
