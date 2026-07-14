from types import MappingProxyType

MAX_QUERY_LENGTH = 500
DEFAULT_TARGET_DOMAIN = "linkedin.com/in"

TITLE_VARIANTS = MappingProxyType(
    {
        "software developer": (
            ("Software Developer", "Software Engineer", "Backend Developer"),
            ("Yazılım Geliştirici", "Yazılım Mühendisi"),
        ),
        "software engineer": (
            ("Software Engineer", "Software Developer", "Backend Developer"),
            ("Yazılım Mühendisi", "Yazılım Geliştirici"),
        ),
        "computer engineer": (
            ("Computer Engineer", "Computer Engineering"),
            ("Bilgisayar Mühendisi", "Bilgisayar Mühendisliği"),
        ),
        "welding engineer": (
            ("Welding Engineer", "Welding Specialist"),
            ("Kaynak Mühendisi", "Kaynak Uzmanı"),
        ),
        "planning engineer": (
            ("Planning Engineer", "Project Planning Engineer", "Production Planning Engineer"),
            ("Planlama Mühendisi", "Üretim Planlama Mühendisi"),
        ),
        "production engineer": (
            ("Production Engineer", "Manufacturing Engineer"),
            ("Üretim Mühendisi", "İmalat Mühendisi"),
        ),
        "quality engineer": (
            ("Quality Engineer", "Quality Control Engineer"),
            ("Kalite Mühendisi", "Kalite Kontrol Mühendisi"),
        ),
        "maintenance engineer": (
            ("Maintenance Engineer",),
            ("Bakım Mühendisi",),
        ),
        "mechanical engineer": (("Mechanical Engineer",), ("Makine Mühendisi",)),
        "industrial engineer": (("Industrial Engineer",), ("Endüstri Mühendisi",)),
        "metallurgical engineer": (
            (
                "Metallurgical Engineer",
                "Materials Engineer",
                "Metallurgical and Materials Engineer",
            ),
            ("Metalurji Mühendisi", "Malzeme Mühendisi", "Metalurji ve Malzeme Mühendisi"),
        ),
    }
)

GENERIC_SKILLS = frozenset(
    {
        "office",
        "communication",
        "teamwork",
        "engineering",
        "software",
        "computer",
        "quality",
        "production",
    }
)

LOCATION_ALIASES = MappingProxyType(
    {
        "türkiye": "Turkey",
        "turkey": "Turkey",
        "istanbul": "Istanbul",
        "i̇stanbul": "Istanbul",
        "izmir": "Izmir",
        "i̇zmir": "Izmir",
        "bursa": "Bursa",
        "gemlik": "Gemlik",
        "kocaeli": "Kocaeli",
        "ankara": "Ankara",
        "remote": "Remote",
        "uzaktan": "Uzaktan",
        "hybrid": "Hybrid",
        "hibrit": "Hibrit",
    }
)
