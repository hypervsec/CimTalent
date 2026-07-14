from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True, slots=True)
class SelectorSet:
    key: str
    selectors: tuple[str, ...]
    required: bool = False
    confidence_by_selector: tuple[float, ...] = ()
    description: str = ""


DEFAULT_SELECTORS: dict[str, SelectorSet] = {
    "profile.top_card": SelectorSet(
        "profile.top_card", ("section[data-section='top-card']", "#top-card", "main"), True
    ),
    "top_card.name": SelectorSet(
        "top_card.name", ("h1[data-field='name']", "h1", ".top-card-name"), True
    ),
    "top_card.headline": SelectorSet(
        "top_card.headline", ("[data-field='headline']", ".headline", "div.text-body-medium")
    ),
    "top_card.location": SelectorSet(
        "top_card.location", ("[data-field='location']", ".location", "span.top-card-location")
    ),
    "top_card.open_to_work": SelectorSet(
        "top_card.open_to_work",
        ("[data-open-to-work='true']", "[aria-label*='Open to Work']", "[aria-label*='Açık']"),
    ),
    "about.section": SelectorSet(
        "about.section", ("section[data-section='about']", "#about", "section.about")
    ),
    "about.content": SelectorSet(
        "about.content", ("[data-field='about']", ".about-content", "div.description")
    ),
    "experience.list": SelectorSet(
        "experience.list", ("section[data-section='experience']", "#experience", ".experience-list")
    ),
    "experience.item": SelectorSet(
        "experience.item", ("[data-experience-item]", ".experience-item", "li")
    ),
    "education.list": SelectorSet(
        "education.list", ("section[data-section='education']", "#education", ".education-list")
    ),
    "education.item": SelectorSet(
        "education.item", ("[data-education-item]", ".education-item", "li")
    ),
    "skills.list": SelectorSet(
        "skills.list", ("section[data-section='skills']", "#skills", ".skills-list")
    ),
    "skills.item": SelectorSet("skills.item", ("[data-skill-item]", ".skill-item", "li")),
    "certifications.list": SelectorSet(
        "certifications.list",
        ("section[data-section='certifications']", "#certifications", ".certifications-list"),
    ),
    "certifications.item": SelectorSet(
        "certifications.item", ("[data-certification-item]", ".certification-item", "li")
    ),
    "languages.list": SelectorSet(
        "languages.list", ("section[data-section='languages']", "#languages", ".languages-list")
    ),
    "languages.item": SelectorSet(
        "languages.item", ("[data-language-item]", ".language-item", "li")
    ),
}


class SelectorRegistry:
    def __init__(self, selectors: dict[str, SelectorSet] | None = None) -> None:
        self.selectors = selectors or DEFAULT_SELECTORS

    def get(self, key: str) -> SelectorSet:
        return self.selectors[key]

    def first(self, root: BeautifulSoup | Tag, key: str) -> tuple[Tag | None, str | None]:
        selector_set = self.get(key)
        for selector in selector_set.selectors:
            found = root.select_one(selector)
            if found is not None:
                return found, selector
        return None, None

    def all(self, root: BeautifulSoup | Tag, key: str) -> tuple[list[Tag], str | None]:
        selector_set = self.get(key)
        for selector in selector_set.selectors:
            found = root.select(selector)
            if found:
                return found, selector
        return [], None
