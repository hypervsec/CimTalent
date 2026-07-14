from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectorSet:
    key: str
    selectors: tuple[str, ...]
    required: bool = False
    description: str = ""


DEFAULT_SELECTORS = {
    "profile.top_card": SelectorSet(
        "profile.top_card", ("[data-linkedin-section='top-card']", ".pv-top-card"), True
    ),
    "top_card.name": SelectorSet("top_card.name", ("[data-field='name']", "h1"), True),
    "top_card.headline": SelectorSet(
        "top_card.headline", ("[data-field='headline']", ".text-body-medium")
    ),
    "top_card.location": SelectorSet(
        "top_card.location", ("[data-field='location']", ".text-body-small")
    ),
    "about.section": SelectorSet(
        "about.section", ("[data-linkedin-section='about']", "section[data-section='about']")
    ),
    "about.content": SelectorSet(
        "about.content", ("[data-field='about']", ".inline-show-more-text")
    ),
    "experience.item": SelectorSet(
        "experience.item", ("[data-linkedin-item='experience']", ".pvs-list__item")
    ),
    "education.item": SelectorSet(
        "education.item", ("[data-linkedin-item='education']", ".pvs-list__item")
    ),
    "skills.item": SelectorSet("skills.item", ("[data-linkedin-item='skill']", ".pvs-list__item")),
    "certifications.item": SelectorSet(
        "certifications.item", ("[data-linkedin-item='certification']", ".pvs-list__item")
    ),
    "languages.item": SelectorSet(
        "languages.item", ("[data-linkedin-item='language']", ".pvs-list__item")
    ),
}
