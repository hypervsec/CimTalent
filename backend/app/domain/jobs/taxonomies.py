from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.db.enums import RequirementImportance


@dataclass(frozen=True, slots=True)
class TaxonomyEntry:
    normalized: str
    category: str
    canonical_phrase: str

    @property
    def is_alias(self) -> bool:
        return self.canonical_phrase.casefold() != self.normalized.casefold()


TITLE_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "yazılım geliştirme uzmanı": "software developer",
        "yazılım geliştirici": "software developer",
        "software developer": "software developer",
        "yazılım mühendisi": "software engineer",
        "software engineer": "software engineer",
        "bilgisayar mühendisi": "computer engineer",
        "computer engineer": "computer engineer",
        "backend developer": "backend developer",
        "backend geliştirici": "backend developer",
        "kaynak mühendisi": "welding engineer",
        "welding engineer": "welding engineer",
        "planlama mühendisi": "planning engineer",
        "planning engineer": "planning engineer",
        "üretim mühendisi": "production engineer",
        "production engineer": "production engineer",
        "kalite mühendisi": "quality engineer",
        "quality engineer": "quality engineer",
        "bakım mühendisi": "maintenance engineer",
        "maintenance engineer": "maintenance engineer",
    }
)

TITLE_VARIANTS_TR: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "software developer": ("yazılım geliştirici", "yazılım geliştirme uzmanı"),
        "software engineer": ("yazılım mühendisi",),
        "computer engineer": ("bilgisayar mühendisi",),
        "backend developer": ("backend geliştirici",),
        "welding engineer": ("kaynak mühendisi",),
        "planning engineer": ("planlama mühendisi",),
        "production engineer": ("üretim mühendisi",),
        "quality engineer": ("kalite mühendisi",),
        "maintenance engineer": ("bakım mühendisi",),
    }
)


def _skill_entries() -> Mapping[str, TaxonomyEntry]:
    canonical: dict[str, tuple[str, str]] = {
        "python": ("python", "programming_language"),
        "c#": ("c#", "programming_language"),
        "java": ("java", "programming_language"),
        "javascript": ("javascript", "programming_language"),
        "typescript": ("typescript", "programming_language"),
        "sql": ("sql", "database"),
        "sql server": ("sql server", "database"),
        "postgresql": ("postgresql", "database"),
        "mysql": ("mysql", "database"),
        "oracle": ("oracle", "database"),
        "rest api": ("rest api", "framework"),
        "graphql": ("graphql", "framework"),
        "dotnet": ("dotnet", "framework"),
        "asp.net": ("asp.net", "framework"),
        "asp.net core": ("asp.net core", "framework"),
        "react": ("react", "framework"),
        "angular": ("angular", "framework"),
        "vue": ("vue", "framework"),
        "fastapi": ("fastapi", "framework"),
        "django": ("django", "framework"),
        "flask": ("flask", "framework"),
        "git": ("git", "devops"),
        "docker": ("docker", "devops"),
        "kubernetes": ("kubernetes", "devops"),
        "linux": ("linux", "devops"),
        "azure": ("azure", "cloud"),
        "aws": ("aws", "cloud"),
        "power bi": ("power bi", "data"),
        "excel": ("excel", "office"),
        "power automate": ("power automate", "office"),
        "sharepoint": ("sharepoint", "office"),
        "jde": ("jde", "erp"),
        "jd edwards": ("jd edwards", "erp"),
        "erp": ("erp", "erp"),
        "mrp": ("mrp", "erp"),
        "autocad": ("autocad", "engineering"),
        "solidworks": ("solidworks", "engineering"),
        "catia": ("catia", "engineering"),
        "sap": ("sap", "erp"),
        "primavera p6": ("primavera p6", "project_management"),
        "ms project": ("ms project", "project_management"),
        "iso 9001": ("iso 9001", "quality"),
        "iso 3834": ("iso 3834", "quality"),
        "asme": ("asme", "engineering"),
        "aws d1.1": ("aws d1.1", "engineering"),
        "welding": ("welding", "manufacturing"),
        "welded manufacturing": ("welded manufacturing", "manufacturing"),
        "ndt": ("ndt", "quality"),
        "quality control": ("quality control", "quality"),
        "production planning": ("production planning", "manufacturing"),
        "maintenance": ("maintenance", "manufacturing"),
        "cnc": ("cnc", "manufacturing"),
        "plc": ("plc", "manufacturing"),
        "lean manufacturing": ("lean manufacturing", "manufacturing"),
        "six sigma": ("six sigma", "quality"),
        "5s": ("5s", "quality"),
        "fmea": ("fmea", "quality"),
        "ppap": ("ppap", "quality"),
        "apqp": ("apqp", "quality"),
        "kaizen": ("kaizen", "quality"),
    }
    aliases: dict[str, tuple[str, str]] = {
        "ms sql": ("sql server", "database"),
        "microsoft sql server": ("sql server", "database"),
        "sqlserver": ("sql server", "database"),
        "restful api": ("rest api", "framework"),
        "rest apis": ("rest api", "framework"),
        ".net": ("dotnet", "framework"),
        ".net core": ("dotnet", "framework"),
        "asp.net": ("asp.net", "framework"),
        "js": ("javascript", "programming_language"),
        "ts": ("typescript", "programming_language"),
        "powerbi": ("power bi", "data"),
        "ms excel": ("excel", "office"),
        "kaynaklı imalat": ("welded manufacturing", "manufacturing"),
        "üretim planlama": ("production planning", "manufacturing"),
        "kalite kontrol": ("quality control", "quality"),
        "bakım": ("maintenance", "manufacturing"),
    }
    entries = {
        phrase: TaxonomyEntry(normalized, category, phrase)
        for phrase, (normalized, category) in canonical.items()
    }
    entries.update(
        {
            phrase: TaxonomyEntry(normalized, category, phrase)
            for phrase, (normalized, category) in aliases.items()
        }
    )
    return MappingProxyType(entries)


SKILL_TAXONOMY = _skill_entries()

EDUCATION_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "bilgisayar mühendisliği": "computer engineering",
        "computer engineering": "computer engineering",
        "yazılım mühendisliği": "software engineering",
        "software engineering": "software engineering",
        "elektrik-elektronik mühendisliği": "electrical and electronics engineering",
        "electrical and electronics engineering": "electrical and electronics engineering",
        "elektronik mühendisliği": "electronics engineering",
        "electronics engineering": "electronics engineering",
        "makine mühendisliği": "mechanical engineering",
        "mechanical engineering": "mechanical engineering",
        "endüstri mühendisliği": "industrial engineering",
        "industrial engineering": "industrial engineering",
        "metalurji ve malzeme mühendisliği": "metallurgical and materials engineering",
        "metallurgical and materials engineering": "metallurgical and materials engineering",
        "malzeme mühendisliği": "materials engineering",
        "materials engineering": "materials engineering",
        "mekatronik mühendisliği": "mechatronics engineering",
        "mechatronics engineering": "mechatronics engineering",
        "kimya mühendisliği": "chemical engineering",
        "chemical engineering": "chemical engineering",
        "inşaat mühendisliği": "civil engineering",
        "civil engineering": "civil engineering",
        "işletme": "business administration",
        "business administration": "business administration",
        "iktisat": "economics",
        "economics": "economics",
        "istatistik": "statistics",
        "statistics": "statistics",
    }
)

EDUCATION_LEVELS: Mapping[str, str] = MappingProxyType(
    {
        "lise": "high_school",
        "high school": "high_school",
        "ön lisans": "associate",
        "önlisans": "associate",
        "associate degree": "associate",
        "lisans": "bachelor",
        "bachelor's degree": "bachelor",
        "bachelors degree": "bachelor",
        "yüksek lisans": "master",
        "master's degree": "master",
        "masters degree": "master",
        "doktora": "doctorate",
        "phd": "doctorate",
        "doctorate": "doctorate",
    }
)

LANGUAGES: Mapping[str, str] = MappingProxyType(
    {
        "türkçe": "turkish",
        "turkish": "turkish",
        "ingilizce": "english",
        "english": "english",
        "almanca": "german",
        "german": "german",
        "fransızca": "french",
        "french": "french",
        "ispanyolca": "spanish",
        "spanish": "spanish",
        "arapça": "arabic",
        "arabic": "arabic",
        "rusça": "russian",
        "russian": "russian",
        "italyanca": "italian",
        "italian": "italian",
        "çince": "chinese",
        "chinese": "chinese",
        "japonca": "japanese",
        "japanese": "japanese",
    }
)

LANGUAGE_PROFICIENCIES: Mapping[str, str] = MappingProxyType(
    {
        "başlangıç": "beginner",
        "beginner": "beginner",
        "temel": "elementary",
        "elementary": "elementary",
        "orta": "intermediate",
        "intermediate": "intermediate",
        "upper-intermediate": "upper_intermediate",
        "iyi derecede": "good",
        "iyi": "good",
        "good": "good",
        "çok iyi": "advanced",
        "ileri seviye": "advanced",
        "ileri": "advanced",
        "advanced": "advanced",
        "akıcı": "fluent",
        "fluent": "fluent",
        "ana dil": "native",
        "native": "native",
    }
)

CERTIFICATIONS: Mapping[str, str] = MappingProxyType(
    {
        "iso 9001": "iso 9001",
        "iso9001": "iso 9001",
        "iso 14001": "iso 14001",
        "iso14001": "iso 14001",
        "iso 45001": "iso 45001",
        "iso45001": "iso 45001",
        "iso 3834": "iso 3834",
        "iso3834": "iso 3834",
        "aws d1.1": "aws d1.1",
        "asme section ix": "asme section ix",
        "pmp certificate": "pmp",
        "pmp": "pmp",
        "prince2": "prince2",
        "six sigma green belt": "six sigma green belt",
        "six sigma black belt": "six sigma black belt",
        "iwe": "iwe",
        "iwt": "iwt",
        "cswip": "cswip",
        "ndt level ii": "ndt level 2",
        "ndt level 2": "ndt level 2",
        "cwi": "cwi",
        "scrum master": "scrum master",
        "aws certified solutions architect": "aws certified solutions architect",
        "azure certification": "azure certification",
        "azure certifications": "azure certification",
        "aws certification": "aws certification",
        "aws certifications": "aws certification",
    }
)

LOCATIONS: Mapping[str, str] = MappingProxyType(
    {
        "bursa": "city:bursa",
        "gemlik": "city:gemlik",
        "kocaeli": "city:kocaeli",
        "istanbul": "city:istanbul",
        "ankara": "city:ankara",
        "izmir": "city:izmir",
        "türkiye": "country:turkey",
        "turkey": "country:turkey",
        "remote": "work_mode:remote",
        "uzaktan": "work_mode:remote",
        "hybrid": "work_mode:hybrid",
        "hibrit": "work_mode:hybrid",
        "on-site": "work_mode:on_site",
        "onsite": "work_mode:on_site",
        "ofiste": "work_mode:on_site",
    }
)

INDUSTRIES: Mapping[str, str] = MappingProxyType(
    {
        "software": "software",
        "yazılım": "software",
        "information technology": "information technology",
        "bilgi teknolojileri": "information technology",
        "manufacturing": "manufacturing",
        "üretim": "manufacturing",
        "heavy industry": "heavy industry",
        "ağır sanayi": "heavy industry",
        "steel": "steel",
        "çelik": "steel",
        "piping": "piping",
        "borulama": "piping",
        "welding": "welding",
        "kaynak": "welding",
        "energy": "energy",
        "enerji": "energy",
        "oil and gas": "oil and gas",
        "petrol ve gaz": "oil and gas",
        "lng": "lng",
        "mining": "mining",
        "madencilik": "mining",
        "automotive": "automotive",
        "otomotiv": "automotive",
        "construction": "construction",
        "inşaat": "construction",
        "engineering": "engineering",
        "mühendislik": "engineering",
        "quality": "quality",
        "kalite": "quality",
        "maintenance": "maintenance",
        "bakım": "maintenance",
        "production": "production",
    }
)

SECTION_TITLES: tuple[tuple[str, RequirementImportance], ...] = (
    ("aranan nitelikler", RequirementImportance.REQUIRED),
    ("genel nitelikler", RequirementImportance.OPTIONAL),
    ("iş tanımı", RequirementImportance.OPTIONAL),
    ("görev ve sorumluluklar", RequirementImportance.OPTIONAL),
    ("tercihen", RequirementImportance.PREFERRED),
    ("zorunlu", RequirementImportance.REQUIRED),
    ("gereklilikler", RequirementImportance.REQUIRED),
    ("yetkinlikler", RequirementImportance.OPTIONAL),
    ("eğitim", RequirementImportance.OPTIONAL),
    ("deneyim", RequirementImportance.OPTIONAL),
    ("yabancı dil", RequirementImportance.OPTIONAL),
    ("sertifikalar", RequirementImportance.OPTIONAL),
    ("lokasyon", RequirementImportance.OPTIONAL),
    ("qualifications", RequirementImportance.OPTIONAL),
    ("requirements", RequirementImportance.REQUIRED),
    ("job description", RequirementImportance.OPTIONAL),
    ("responsibilities", RequirementImportance.OPTIONAL),
    ("preferred qualifications", RequirementImportance.PREFERRED),
    ("must have", RequirementImportance.REQUIRED),
    ("nice to have", RequirementImportance.PREFERRED),
    ("education", RequirementImportance.OPTIONAL),
    ("experience", RequirementImportance.OPTIONAL),
    ("languages", RequirementImportance.OPTIONAL),
    ("certifications", RequirementImportance.OPTIONAL),
    ("location", RequirementImportance.OPTIONAL),
)
