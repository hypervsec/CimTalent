from app.db.enums import RequirementImportance
from app.domain.jobs.normalizers import clean_job_text, normalize_for_matching
from app.parsers.jobs.sentence_splitter import split_into_bullets, split_into_sections


def test_clean_job_text_removes_html_and_normalizes_bullets() -> None:
    source = "<h2>Aranan Nitelikler</h2><ul><li> Python&nbsp; bilgisi </li><li>SQL</li></ul>"

    cleaned = clean_job_text(source)

    assert "<" not in cleaned
    assert "- Python bilgisi" in cleaned
    assert "- SQL" in cleaned


def test_clean_job_text_preserves_turkish_and_normalizes_whitespace() -> None:
    assert clean_job_text("  Yazılım   Mühendisi\r\n\r\n Bursa  ") == ("Yazılım Mühendisi\n\nBursa")
    assert normalize_for_matching("İLERİ İngilizce") == "ileri ingilizce"


def test_bullet_and_section_splitting() -> None:
    text = clean_job_text(
        "Requirements:\n1. Minimum 2 years\n* Python\nPreferred Qualifications:\n• Docker"
    )
    sections = split_into_sections(text)

    assert len(sections) == 2
    assert sections[0].inferred_importance is RequirementImportance.REQUIRED
    assert sections[1].inferred_importance is RequirementImportance.PREFERRED
    assert split_into_bullets(sections[0].body) == ("Minimum 2 years", "Python")
