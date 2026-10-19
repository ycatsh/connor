import zipfile
from datetime import date
from pathlib import Path

import pytest

from connor.core.extract import extract

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_DAY = date(2026, 10, 19)


def flat(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize(
    "name",
    [
        "lab_report.docx",
        "lab_report.odt",
        "lab_report.pdf",
        "lab_report.rtf",
        "lab_report.doc",
    ],
)
def test_documents_yield_their_text(name: str) -> None:
    text = flat(extract(FIXTURES / name, 2000).text)

    assert "Photosynthesis Lab Report" in text
    assert "Course BIO101, section 2." in text
    assert "which supports the inverse square law" in text


@pytest.mark.parametrize(
    "name", ["lab_report.docx", "lab_report.odt", "lab_report.pdf", "lab_report.rtf"]
)
def test_table_cells_stay_separate_words(name: str) -> None:
    text = flat(extract(FIXTURES / name, 2000).text)

    assert "10 cm" in text
    assert "42" in text.split()
    assert "Distance" in text.split()


@pytest.mark.parametrize(
    "name", ["lab_report.docx", "lab_report.odt", "lab_report.pdf", "lab_report.rtf"]
)
def test_document_metadata_title(name: str) -> None:
    assert extract(FIXTURES / name, 2000).title == "Photosynthesis Lab Report"


def test_pdf_metadata_created_date() -> None:
    assert extract(FIXTURES / "lab_report.pdf", 2000).created == FIXTURE_DAY


def test_odt_reads_title_and_created_date_from_meta(tmp_path: Path) -> None:
    path = tmp_path / "minutes.odt"
    office = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    text = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "content.xml",
            f'<office:document-content xmlns:office="{office}" xmlns:text="{text}">'
            "<office:body><office:text><text:p>Board <text:span>minutes</text:span>"
            "</text:p></office:text></office:body></office:document-content>",
        )
        archive.writestr(
            "meta.xml",
            f'<office:document-meta xmlns:office="{office}" '
            'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><office:meta>'
            "<dc:title>Board Minutes</dc:title>"
            "<meta:creation-date>2023-11-30T08:15:00</meta:creation-date>"
            "</office:meta></office:document-meta>",
        )

    result = extract(path, 2000)

    assert result.text == "Board minutes"
    assert result.title == "Board Minutes"
    assert result.created == date(2023, 11, 30)


@pytest.mark.parametrize("name", ["lab_report.docx", "lab_report.odt"])
def test_table_rows_stay_on_one_line(name: str) -> None:
    lines = extract(FIXTURES / name, 2000).text.splitlines()

    assert "Distance Bubbles" in lines
    assert "10 cm 42" in lines


@pytest.mark.parametrize("name", ["grades.xlsx", "grades.ods"])
def test_spreadsheets_read_rows_in_order(name: str) -> None:
    text = extract(FIXTURES / name, 2000).text

    assert "Student Quiz Midterm Final" in text.splitlines()
    assert "Grace 9 84 91" in text.splitlines()


def test_legacy_spreadsheet_yields_its_strings() -> None:
    text = extract(FIXTURES / "grades.xls", 2000).text

    assert "Grace" in text
    assert "Midterm" in text


@pytest.mark.parametrize("name", ["slides.pptx", "slides.odp"])
def test_slides_read_in_order(name: str) -> None:
    result = extract(FIXTURES / name, 2000)
    text = flat(result.text)

    assert "Prophase: chromosomes condense" in text
    assert "Four haploid cells" in text
    assert text.index("Mitosis") < text.index("Meiosis")
    assert result.title == "Cell Division Overview"


def test_epub_reads_chapters_and_title() -> None:
    result = extract(FIXTURES / "novel.epub", 2000)

    assert "The lighthouse keeper climbed the spiral stairs" in flat(result.text)
    assert result.title == "The Lighthouse Keeper"


def test_pdf_without_text_is_empty() -> None:
    result = extract(FIXTURES / "blank.pdf", 2000)

    assert result.text == ""
    assert result.title == ""


def test_html_skips_scripts_and_styles(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(
        "<html><head><title>Field Trip Notes</title>"
        "<style>.x { color: red }</style><script>track()</script></head>"
        "<body><h1>Day one</h1><p>We walked to the &amp; river.</p>"
        "<noscript>enable js</noscript></body></html>"
    )

    result = extract(page, 2000)

    assert result.title == "Field Trip Notes"
    assert result.text.splitlines() == ["Day one", "We walked to the & river."]


def test_email_reads_subject_date_and_plain_body(tmp_path: Path) -> None:
    mail = tmp_path / "invoice.eml"
    mail.write_bytes(
        b"From: billing@acme.example\r\n"
        b"To: someone@example.com\r\n"
        b"Subject: Invoice 4471 from Acme Supplies\r\n"
        b"Date: Tue, 14 Oct 2025 09:30:00 +0000\r\n"
        b"MIME-Version: 1.0\r\n"
        b'Content-Type: multipart/alternative; boundary="b1"\r\n\r\n'
        b"--b1\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Amount due: 120.00\r\nThank you.\r\n"
        b"--b1\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
        b"<p>Amount due: <b>120.00</b></p>\r\n"
        b"--b1--\r\n"
    )

    result = extract(mail, 2000)

    assert result.title == "Invoice 4471 from Acme Supplies"
    assert result.created == date(2025, 10, 14)
    assert result.text.splitlines() == ["Amount due: 120.00", "Thank you."]


def test_html_only_email_is_turned_into_text(tmp_path: Path) -> None:
    mail = tmp_path / "news.eml"
    mail.write_bytes(
        b"Subject: Weekly news\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n\r\n"
        b"<html><body><h2>Headline</h2><p>Story text.</p></body></html>\r\n"
    )

    assert extract(mail, 2000).text.splitlines() == ["Headline", "Story text."]


def test_markdown_title_comes_from_the_first_heading(tmp_path: Path) -> None:
    note = tmp_path / "plan.md"
    note.write_text("intro line\n# Study Plan\n\nRead chapter 4.\n")

    result = extract(note, 2000)

    assert result.title == "Study Plan"
    assert "Read chapter 4." in result.text


def test_text_whitespace_is_tidied(tmp_path: Path) -> None:
    note = tmp_path / "notes.txt"
    note.write_text("  first   line \n\n\n\tsecond\tline  \n")

    assert extract(note, 2000).text == "first line\nsecond line"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("caf\xe9 menu".encode("latin-1"), "caf\xe9 menu"),
        ("\ufeffhello world".encode("utf-16-le"), "hello world"),
        ("\ufeffhello world".encode("utf-16-be"), "hello world"),
        ("\ufeffbom utf8".encode(), "bom utf8"),
        ("na\xefve r\xe9sum\xe9".encode(), "na\xefve r\xe9sum\xe9"),
    ],
)
def test_text_encodings(tmp_path: Path, data: bytes, expected: str) -> None:
    note = tmp_path / "note.txt"
    note.write_bytes(data)

    assert extract(note, 2000).text == expected


@pytest.mark.parametrize("name", ["big.txt", "big.csv", "script.py"])
def test_text_is_cut_at_the_limit(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("word " * 50_000)

    text = extract(path, 300).text

    assert 250 <= len(text) <= 300


def test_documents_are_cut_at_the_limit() -> None:
    assert len(extract(FIXTURES / "lab_report.docx", 120).text) <= 120


@pytest.mark.parametrize("suffix", [".docx", ".odt", ".xlsx", ".pptx", ".epub", ".pdf"])
def test_corrupt_files_give_empty_text(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"broken{suffix}"
    path.write_bytes(b"\x00\x01not really a document" * 20)

    result = extract(path, 2000)

    assert (result.title, result.text, result.created) == ("", "", None)


def test_zip_without_expected_parts_gives_empty_text(tmp_path: Path) -> None:
    path = tmp_path / "odd.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("readme.txt", "hello")

    assert extract(path, 2000).text == ""


def test_oversized_zip_member_is_not_read(tmp_path: Path) -> None:
    path = tmp_path / "bomb.docx"
    body = b"<w:document><w:body>" + b" " * 60_000_000 + b"</w:body></w:document>"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", body)

    assert extract(path, 2000).text == ""


def test_unknown_types_and_missing_files_give_empty_text(tmp_path: Path) -> None:
    photo = tmp_path / "IMG_2041.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0 jpeg bytes")

    assert extract(photo, 2000).text == ""
    assert extract(tmp_path / "gone.pdf", 2000).text == ""


def test_docx_reads_created_date_from_core_properties(tmp_path: Path) -> None:
    path = tmp_path / "memo.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hel</w:t></w:r>'
            "<w:r><w:t>lo</w:t></w:r></w:p></w:body></w:document>",
        )
        archive.writestr(
            "docProps/core.xml",
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/'
            '2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"'
            ' xmlns:dcterms="http://purl.org/dc/terms/"><dc:title>Memo</dc:title>'
            "<dcterms:created>2024-03-05T10:00:00Z</dcterms:created>"
            "</cp:coreProperties>",
        )

    result = extract(path, 2000)

    assert result.text == "Hello"
    assert result.title == "Memo"
    assert result.created == date(2024, 3, 5)
