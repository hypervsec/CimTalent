# CimTalent AI Backend — İskelet ve ORM Domain Katmanı

Python 3.12, FastAPI, Pydantic 2 ve SQLAlchemy 2 ile hazırlanmış backend başlangıç
katmanıdır. ORM modelleri, Alembic migration altyapısı ve Job CRUD dikey dilimi hazırdır. Harici arama,
scraping veya gerçek kişisel veri işleme bu aşamada yoktur.

## Kurulum

PowerShell üzerinde `backend` dizininde:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
Copy-Item .env.example .env
```

Yerel PostgreSQL kullanılıyorsa `.env` içindeki `DATABASE_URL` değerini ortama göre
düzenleyin. Health endpointi veritabanı bağlantısı gerektirmez.

## Çalıştırma

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: <http://127.0.0.1:8000/api/v1/health>
- OpenAPI: <http://127.0.0.1:8000/docs>

## Job CRUD API

| Method | Endpoint | Açıklama |
| --- | --- | --- |
| POST | `/api/v1/jobs` | İlan oluşturur |
| GET | `/api/v1/jobs` | İlanları filtreli ve sayfalı listeler |
| GET | `/api/v1/jobs/{job_id}` | Tek ilanı getirir |
| PATCH | `/api/v1/jobs/{job_id}` | Kısmi güncelleme yapar |
| DELETE | `/api/v1/jobs/{job_id}` | İlanı kalıcı olarak siler |
| GET | `/api/v1/jobs/{job_id}/requirements` | İlan gereksinimlerini listeler |

Örnek oluşturma isteği:

```powershell
$body = @{
  company_name = "Example Company"
  title = "Backend Developer"
  description_raw = "Python ve SQL ile API geliştirme"
  city = "Bursa"
  required_skills = @("Python", "SQL")
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs `
  -ContentType application/json -Body $body
```

Liste endpointi `page`, `page_size`, `status`, `source`, `city`, `company_name`,
`title`, `search`, `created_from` ve `created_to` filtrelerini destekler. Sıralama
`sort_by` ve `sort_direction` ile yapılır. `page_size` en fazla 100 olabilir;
toplam sonuç ve sayfa bilgileri response içinde döner.

İzin verilen durum geçişleri:

- `draft → parsed | archived`
- `parsed → sourcing | archived | draft`
- `sourcing → completed | archived | parsed`
- `completed → archived | sourcing`
- `archived → draft`

Domain hataları `error.code`, `error.message`, `error.details` ve `error.request_id`
alanlarını taşıyan standart JSON response olarak döner.

## Rule-based ilan parser'ı

`POST /api/v1/jobs/{job_id}/parse` endpointi ilanın `description_raw` metnini
deterministik olarak ayrıştırır. Parser FastAPI ve SQLAlchemy'den bağımsız saf Python
nesneleri üretir; yapay zekâ, LLM veya harici servis kullanmaz.

Desteklenen kapsam:

- Türkçe ve İngilizce bölüm başlıkları ile required/preferred/optional ayrımı
- Unvan, teknik ve üretim becerileri, deneyim aralıkları ve ay ifadeleri
- Eğitim seviyesi/bölümü, açıkça yazılmış yabancı dil ve yeterlilik seviyesi
- Sertifikalar/standartlar, şehir/ülke/çalışma modu ve temel sektör terimleri
- HTML/entity temizleme, madde normalizasyonu, alias eşleme ve duplicate temizleme
- Her requirement için raw/normalized değer, kaynak, ağırlık, confidence ve evidence

Örnek istek:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/jobs/00000000-0000-0000-0000-000000000000/parse
```

Örnek response özeti:

```json
{
  "job_id": "00000000-0000-0000-0000-000000000000",
  "status": "parsed",
  "parser_version": "rule-based-v1",
  "created_requirement_count": 8,
  "updated_job_fields": ["description_clean", "required_skills", "status"],
  "warnings": [],
  "confidence": 0.9,
  "requirements": []
}
```

Required requirement ağırlığı `1.0`, preferred `0.6`, optional `0.3` değerini
alır. Bölüm başlığı ilk bağlamı verir; cümle içindeki açık sinyaller bunu
daraltabilir. Belirsiz bölümler otomatik olarak required kabul edilmez.

Parse işlemi `draft` ve `parsed` durumlarında çalışır. `sourcing`, `completed` ve
`archived` durumlarında `409` döner. Yeniden parse işleminde mevcut requirement'lar
aynı transaction içinde silinip deterministik sonuçla değiştirilir; bu nedenle kayıt
sayısı büyümez. Yazma hatasında rollback eski requirement'ları ve job durumunu korur.

Parser yalnızca taxonomy ve açık metin kalıplarını tanır. Yazım hatalarını, karmaşık
örtük anlamları veya taxonomy dışı teknolojileri tahmin etmez; ilanın dilinden profil
dili şartı türetmez. Bu sınırlamalar yanlış pozitif üretmemek için bilinçlidir.

## Search query generation ve manuel sonuç importu

Parse edilmiş ilanlardan deterministik Türkçe/İngilizce Google X-Ray sorguları
üretilebilir. Sistem yalnız sorgu metni oluşturur; Google veya LinkedIn'e otomatik
istek göndermez.

| Method | Endpoint | Açıklama |
| --- | --- | --- |
| POST | `/api/v1/jobs/{job_id}/queries/generate` | X-Ray sorguları üretir |
| GET | `/api/v1/jobs/{job_id}/queries` | Sorguları filtreli ve sayfalı listeler |
| GET | `/api/v1/queries/{query_id}` | Tek sorguyu getirir |
| DELETE | `/api/v1/queries/{query_id}` | Sorguyu ve bağlı sonuçları siler |
| POST | `/api/v1/queries/{query_id}/import-results` | Manuel sonuç içe aktarır |
| GET | `/api/v1/queries/{query_id}/results` | Sorgu sonuçlarını listeler |
| GET | `/api/v1/jobs/{job_id}/search-results` | İlan sonuçlarını listeler |
| GET | `/api/v1/search-results/{result_id}` | Tek sonucu getirir |
| DELETE | `/api/v1/search-results/{result_id}` | Sonucu siler |

Desteklenen query stratejileri title+location, title+skills, strict precision,
education+location, industry+title, required-skill focus ve recall sorgularıdır.
Örnekler:

```text
site:linkedin.com/in ("Yazılım Geliştirici" OR "Yazılım Mühendisi") "Bursa"
site:linkedin.com/in ("Software Developer" OR "Backend Developer") ("Python" OR "SQL Server")
```

Generate örneği:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs/JOB_ID/queries/generate" \
  -H "Content-Type: application/json" \
  -d '{"max_queries":10,"languages":["tr","en"],"target_domain":"linkedin.com/in"}'
```

Her query response'u URL-encoded `google_search_url` alanı içerir. Bu URL kullanıcı
tarafından tarayıcıda açılabilir; backend aramayı kendisi yürütmez. Aynı job ve
normalize query anahtarı veritabanı unique constraint'i ve service deduplication ile
tekrar kaydedilmez.

Manuel import `json`, `urls` ve statik `html` formatlarını destekler:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/queries/QUERY_ID/import-results" \
  -H "Content-Type: application/json" \
  -d '{"format":"urls","mode":"merge","payload":["https://linkedin.com/in/demo-profile"]}'
```

`merge` mevcut sonuçları korur ve yalnız yeni URL'leri ekler. `replace`, aynı
transaction içinde sorgunun eski sonuçlarını yeni payload ile değiştirir; hata olursa
rollback eski sonuçları korur. URL normalizer scheme/host/path biçimini düzenler,
fragment ve bilinen tracking parametrelerini kaldırır, işlevsel query parametrelerini
korur. LinkedIn locale hostları `www.linkedin.com/in/<slug>` biçimine çevrilir.

Aynı sorgudaki URL duplicate'ları eklenmez. Farklı sorgulardaki aynı normalize URL
yeni kayıt olarak tutulur ancak `is_duplicate=true` ve `duplicate_of_id` ile en eski
canonical sonuca bağlanır. HTML parser JavaScript çalıştırmaz ve ağ erişimi yapmaz.

Bilinen sınırlamalar: query üretimi yalnız taxonomy ve parse edilmiş açık gereksinimleri
kullanır. HTML parser statik/generic sonuç container'larını işler; canlı Google HTML
yapısının otomatik scraping'i, Google API ve LinkedIn otomasyonu bu aşamada yoktur.

## Candidate discovery, CRUD ve merge

Candidate havuzu canlı scraping yapılmadan, içe aktarılmış `SearchResult` metadata'sından
oluşturulur. LinkedIn `/in/<slug>` profilleri yüksek; metadata taşıyan GitHub kullanıcı ve
kişisel profil sayfaları orta güvenle kabul edilir. LinkedIn company/jobs/school, arama
motoru, geçersiz URL ve kişi sinyali taşımayan sayfalar atlanır. Kimlik eşleme sırası
canonical `normalized_profile_url`, yalnız LinkedIn için `profile_slug` ve yeni Candidate
şeklindedir; isim benzerliği hiçbir zaman otomatik merge yapmaz.

`Candidate.source` profil platformunu değil keşif kanalını gösterir: `google_xray`,
`professional_network`, `imported`, `manual` veya `demo`. Arama sonucu `snippet` metni
`discovery_snippet` alanında tutulur; doğrulanmış profil özeti olan `about` alanına
aktarılmaz. Bu aşama profil sayfasını ziyaret etmez ve LinkedIn login/cookie kullanmaz.

| Method | Endpoint | Açıklama |
| --- | --- | --- |
| POST | `/api/v1/candidates` | Manuel Candidate oluşturur |
| GET | `/api/v1/candidates` | Filtreli, sıralı ve sayfalı liste |
| GET/PATCH/DELETE | `/api/v1/candidates/{candidate_id}` | Getirir, düzeltir veya siler |
| GET | `/api/v1/candidates/{candidate_id}/search-results` | Keşif kaynaklarını listeler |
| GET | `/api/v1/candidates/{candidate_id}/quality` | Deterministik kalite kırılımı |
| GET | `/api/v1/candidates/{candidate_id}/duplicate-suggestions` | Duplicate önerileri |
| POST | `/api/v1/search-results/{result_id}/discover-candidate` | Tek sonuç discovery |
| POST | `/api/v1/jobs/{job_id}/candidates/discover` | Kontrollü bulk discovery |
| POST | `/api/v1/candidates/{target_candidate_id}/merge` | Atomik merge/dry-run |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Demo Engineer","location_raw":"Bursa, Türkiye"}'

curl -X POST http://127.0.0.1:8000/api/v1/jobs/JOB_ID/candidates/discover \
  -H "Content-Type: application/json" \
  -d '{"only_unassigned":true,"max_results":200,"dry_run":true}'

curl "http://127.0.0.1:8000/api/v1/candidates?city=Bursa&min_data_quality=50&sort_by=data_quality_score"

curl -X PATCH http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID \
  -H "Content-Type: application/json" -d '{"current_title":"Backend Engineer"}'

curl http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/duplicate-suggestions

curl -X POST http://127.0.0.1:8000/api/v1/candidates/TARGET_ID/merge \
  -H "Content-Type: application/json" \
  -d '{"source_candidate_ids":["SOURCE_ID"],"field_strategy":"keep_target","dry_run":true}'

curl -X POST http://127.0.0.1:8000/api/v1/candidates/TARGET_ID/merge \
  -H "Content-Type: application/json" \
  -d '{"source_candidate_ids":["SOURCE_ID"],"field_strategy":"prefer_non_empty"}'
```

Kalite skoru ad, profile URL, headline, location, güncel pozisyon/şirket, about,
discovery snippet ve child kayıt sayılarından 0–100 aralığında hesaplanır. Create, update
ve merge sonrasında yenilenir. Duplicate endpoint exact URL/slug ile destekleyici
name+headline+city/company sinyallerini önerir; fuzzy ad tek başına yeterli değildir.

Merge en fazla 20 source kabul eder; `keep_target`, `prefer_non_empty` ve
`prefer_newest` stratejilerini ve mutasyonsuz `dry_run` seçeneğini destekler. SearchResult
ve profil child kayıtları target'a taşınır. Skill/language unique çakışmaları konsolide
edilir; match explanation ve recruiter note birleştirilerek korunur. Source kayıtlar
silinir ve geri alma sağlamayan kalıcı `candidate_merge_audits` kaydı oluşturulur.

Bilinen sınırlamalar: kişisel sayfa eligibility'si yalnız açık metadata sinyallerine
dayanır; fuzzy duplicate sonuçları insan incelemesi gerektirir. Merge audit bir undo
mekanizması değildir. Profil scraping, matching, shortlist CRUD, LLM/embedding ve worker
bu aşamada bilinçli olarak yoktur.

## Kalite kontrolleri

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov=alembic --cov-report=term-missing
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe app tests alembic
.\.venv\Scripts\python.exe -m compileall -q app tests alembic
```

## Migration

`.env` içinde hedef veritabanı ayarlandıktan sonra:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe downgrade base
```

PostgreSQL'e bağlanmadan üretilecek SQL'i incelemek için:

```powershell
.\.venv\Scripts\alembic.exe upgrade head --sql
```

## Dizin yapısı

```text
backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/health.py
│   ├── db/
│   │   ├── base.py
│   │   ├── enums.py
│   │   ├── metadata.py
│   │   ├── models/
│   │   └── session.py
│   ├── schemas/health.py
│   ├── config.py
│   ├── logging.py
│   └── main.py
├── tests/
├── alembic/
├── alembic.ini
├── .env.example
└── pyproject.toml
```

## Candidate enrichment

Enrichment, profil verisini platformdan bağımsız domain DTO'ları üzerinden normalize eder;
provider katmanı ORM nesnesi görmez. `fast` modu temel profil, `deep` modu tüm profesyonel
profil bölümleri için metadata sözleşmesini tanımlar. Bu aşamada çalışan provider `manual`
provider'dır; gerçek LinkedIn DOM parser'ı yoktur.

Import varsayılan olarak `merge` çalışır. `replace_sections` yalnız request'te açıkça bulunan
bölümleri, `replace_all` tüm child koleksiyonları değiştirir. Kimlik alanları için `fill_empty`,
`overwrite_non_null` ve `keep_existing` stratejileri vardır; null değerler profil alanlarını
silmez. Preview ve import aynı deterministik diff motorunu kullanır; preview DB'yi değiştirmez.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/enrichment/preview \
  -H "Content-Type: application/json" \
  -d '{"mode":"fast","identity":{"headline":{"value":"Backend Engineer","source":"manual"}},"skills":[{"raw_name":"Python"}]}'

curl -X POST http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/enrichment/import \
  -H "Content-Type: application/json" \
  -d '{"mode":"deep","import_mode":"merge","experiences":[{"external_key":"exp-1","position_title_raw":"Engineer","is_current":true,"start_date":"2023-01-01"}]}'

curl http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/profile
curl http://127.0.0.1:8000/api/v1/candidates/CANDIDATE_ID/enrichment-runs
```

Deneyim süresi çakışan ayları iki kez saymaz ve UTC tarihine göre deterministik hesaplanır.
Başarılı import sonunda quality score yeniden hesaplanır; FAST profil `partial`, eksiksiz DEEP
profil `scraped` olur. Run kaydı yalnız güvenli özet ve sayaçları saklar; payload/HTML saklamaz.

## Browser ve LinkedIn session altyapısı

Playwright adapter'ı async context manager, timeout, viewport, storage-state ve güvenli kapanış
sağlar. Browser paketi isteğe bağlı kurulur; CI'da Chromium binary zorunlu değildir:

```powershell
pip install -e ".[browser]"
playwright install chromium
python -m app.scripts.create_linkedin_session
python -m app.scripts.check_linkedin_session
```

İlk komut Chromium'u headful açar; kullanıcı adı/parola yalnız LinkedIn sayfasına manuel girilir.
Storage-state `.sessions/` altında atomic yazılır, içeriği loglanmaz ve Git tarafından yok sayılır.
PageGuard login, authwall, checkpoint, challenge, CAPTCHA, rate limit, access denied ve unavailable
sinyallerinde durur; engeli aşmaya çalışmaz. Screenshot kontrollüdür, HTML artifact varsayılan
kapalıdır. HTML açılırsa profil verisi içerebileceği için artifact dizini dikkatle korunmalıdır.

Bilinen sınırlamalar: gerçek LinkedIn profil DOM parsing, People Search, otomatik credential girişi,
CAPTCHA/challenge bypass, proxy, fingerprint gizleme ve insan davranışı taklidi yoktur. Canlı Google
scraping, matching, embedding, LLM, worker, Redis, Celery, Docker ve frontend de eklenmemiştir.

## Sonraki aşama

Bir sonraki güvenli teslimat, mevcut session ve provider sözleşmesini kullanan ancak challenge veya
rate-limit sinyallerinde hemen duran profil parser adapter'ı olabilir. Ayrı kalite kapısı ve yalnız
izinli test fixture'larıyla geliştirilmelidir.
