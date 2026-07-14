# TalentFilter AI

> Yapay zekâ destekli iş ilanı analizi, aday keşfi ve açıklanabilir eşleşme platformu.
> AI-powered job analysis, candidate discovery, and explainable matching platform.

---

## Türkçe

### Proje Hakkında

**TalentFilter AI**, insan kaynakları ekiplerinin iş ilanlarını daha hızlı analiz etmesine, uygun adayları keşfetmesine ve adayları açıklanabilir kriterlerle karşılaştırmasına yardımcı olmak için geliştirilmiş bir platformdur.

Sistem; iş ilanı içerisindeki unvan, beceri, deneyim, eğitim, dil, sertifika, lokasyon ve sektör gereksinimlerini çıkarır. Bu gereksinimlere göre arama sorguları üretir, bulunan aday profillerini işler ve iş ilanı ile aday arasında `0–100` arası açıklanabilir bir eşleşme puanı hesaplar.

Proje, IT stajı kapsamında eğitim, araştırma ve prototip geliştirme amacıyla hazırlanmıştır.

### Temel Özellikler

* Türkçe ve İngilizce iş ilanı analizi
* Unvan, beceri, deneyim ve eğitim gereksinimi çıkarımı
* Dil, sertifika, lokasyon ve sektör analizi
* Google X-Ray uyumlu arama sorgusu oluşturma
* SearchResult kayıtlarından aday keşfi
* Aday profil zenginleştirme
* Veri kalitesi puanlama
* Duplicate aday tespiti ve birleştirme
* Açıklanabilir iş–aday eşleşme skoru
* Shortlist yönetimi
* CSV dışa aktarma
* Dashboard, metrik ve grafikler
* Docker Compose desteği

### Sistem Akışı

```text
İş ilanı oluştur
        ↓
İlan gereksinimlerini analiz et
        ↓
Arama sorguları üret
        ↓
Arama sonuçlarını içe aktar
        ↓
Adayları keşfet
        ↓
Aday profillerini zenginleştir
        ↓
Eşleşme puanlarını hesapla
        ↓
Uygun adayları shortlist'e ekle
```

### Teknolojiler

**Backend**

* Python 3.12
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* Pytest
* Ruff
* Mypy

**Frontend**

* React
* TypeScript
* Vite
* Tailwind CSS
* TanStack Query
* Axios
* Recharts
* Vitest

**Container**

* Docker Compose
* Nginx
* PostgreSQL container
* FastAPI backend container
* React frontend container

### Kurulum

```bash
git clone <repository-url>
cd TalentFilter
cp .env.example .env
docker compose up -d --build
```

Servislerin durumunu kontrol etmek için:

```bash
docker compose ps
```

### Uygulama Adresleri

* Frontend: `http://localhost:3000`
* Backend: `http://localhost:8000`
* Swagger: `http://localhost:8000/docs`
* Health Check: `http://localhost:8000/api/v1/health`

### Demo Verileri

Demo kayıtlarını oluşturmak için:

```bash
docker compose exec backend python -m app.scripts.seed_demo
```

Demo akışını doğrulamak için:

```bash
docker compose exec backend python -m app.scripts.demo_smoke
```

Beklenen çıktı:

```text
demo smoke: ok
```

### Test ve Kod Kalitesi

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec backend mypy .
```

Frontend kontrolleri:

```bash
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

---

## English

### About the Project

**TalentFilter AI** is a candidate sourcing and matching platform designed to help human resources teams analyze job descriptions, discover suitable candidates, and compare candidates using explainable criteria.

The system extracts requirements such as title, skills, experience, education, language, certification, location, and industry. It generates sourcing queries, processes candidate profiles, and calculates an explainable job–candidate matching score between `0` and `100`.

The project was developed for educational, research, and prototype purposes as part of an IT internship.

### Key Features

* Turkish and English job-description parsing
* Title, skill, experience, and education extraction
* Language, certification, location, and industry analysis
* Google X-Ray-compatible query generation
* Candidate discovery from search results
* Candidate profile enrichment
* Candidate data-quality scoring
* Duplicate detection and candidate merging
* Explainable job–candidate matching
* Shortlist management
* CSV export
* Dashboard metrics and charts
* Docker Compose support

### Application Workflow

```text
Create a job posting
        ↓
Parse job requirements
        ↓
Generate sourcing queries
        ↓
Import search results
        ↓
Discover candidates
        ↓
Enrich candidate profiles
        ↓
Calculate matching scores
        ↓
Add suitable candidates to the shortlist
```

### Technology Stack

**Backend**

* Python 3.12
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* Pytest
* Ruff
* Mypy

**Frontend**

* React
* TypeScript
* Vite
* Tailwind CSS
* TanStack Query
* Axios
* Recharts
* Vitest

**Container**

* Docker Compose
* Nginx
* PostgreSQL
* FastAPI
* React

### Setup

```bash
git clone <repository-url>
cd TalentFilter
cp .env.example .env
docker compose up -d --build
```

Application URLs:

* Frontend: `http://localhost:3000`
* Backend: `http://localhost:8000`
* Swagger: `http://localhost:8000/docs`

---

## LinkedIn, KVKK and Responsible Use

### Türkçe

Bu proje yalnızca **eğitim, araştırma ve prototip geliştirme amacıyla** hazırlanmıştır.

Proje LinkedIn tarafından geliştirilmemiş, desteklenmemiş veya onaylanmamıştır. LinkedIn adı ve markaları ilgili hak sahiplerine aittir.

Yazılım;

* LinkedIn kullanım koşullarını aşmak,
* CAPTCHA veya güvenlik önlemlerini atlatmak,
* İzinsiz kişisel veri toplamak,
* Adaylar hakkında yalnızca otomatik sistemlere dayalı karar vermek

amacıyla kullanılmamalıdır.

Kişisel verileri işleyen kullanıcı veya kurum; **6698 sayılı KVKK**, ilgili mevzuat, veri minimizasyonu, güvenlik, saklama süresi, aydınlatma ve hukuki işleme şartlarına uygun hareket etmekten sorumludur.

Herkese açık bir profil bilgisinin bulunması, bu bilginin sınırsız şekilde toplanabileceği, saklanabileceği veya tekrar kullanılabileceği anlamına gelmez.

Yazılımın kullanımından doğabilecek hukuki, idari veya platform kaynaklı tüm sorumluluk kullanan kişi ya da kuruma aittir. Proje geliştiricisi, üçüncü kişiler tarafından gerçekleştirilen hukuka veya platform kurallarına aykırı kullanımlardan sorumlu değildir.

Bu açıklama hukuki danışmanlık niteliğinde değildir.

### English

This project is provided only for **education, research, and prototype development**.

It is not developed, sponsored, endorsed, or approved by LinkedIn. LinkedIn names and trademarks belong to their respective owners.

The software must not be used to:

* Circumvent LinkedIn's terms or technical restrictions,
* Bypass CAPTCHA or security controls,
* Collect personal data without a valid legal basis,
* Make recruitment decisions solely through automated scoring.

The user or organization operating the software is responsible for complying with applicable privacy laws, platform rules, data-security requirements, retention obligations, and transparency requirements.

The public availability of profile information does not automatically authorize unrestricted collection, storage, profiling, or reuse.

All legal, administrative, and contractual responsibility arising from the use of the project belongs to the user or organization operating it. The project developer is not responsible for unlawful use or use that violates third-party platform rules.

This notice does not constitute legal advice.
