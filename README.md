# TalentFilter AI / CimTalent AI

> Yapay zekâ destekli iş ilanı analizi, aday keşfi ve açıklanabilir eşleşme platformu.
> AI-powered job analysis, candidate discovery, and explainable matching platform.

---

## Türkçe

### Proje Hakkında

**TalentFilter AI**, iş ilanlarını analiz ederek gerekli unvan, beceri, deneyim, eğitim, dil, sertifika, lokasyon ve sektör bilgilerini çıkaran bir aday bulma ve eşleştirme platformudur.

Sistem uygun arama sorguları üretir, aday profillerini işler ve iş ilanı ile aday arasında `0–100` arası açıklanabilir eşleşme puanı hesaplar.

Bu proje IT stajı kapsamında eğitim ve araştırma amacıyla geliştirilmiştir.

### Özellikler

* Türkçe ve İngilizce iş ilanı analizi
* X-Ray arama sorgusu oluşturma
* SearchResult üzerinden aday keşfi
* Aday profil zenginleştirme
* Veri kalitesi ve duplicate kontrolü
* Açıklanabilir aday eşleşme puanı
* Shortlist ve CSV dışa aktarma
* React dashboard
* Docker Compose desteği

### Teknolojiler

**Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, Alembic, Pytest
**Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query
**Container:** Docker Compose, Nginx

### Kurulum

```bash
git clone <repository-url>
cd TalentFilter
cp .env.example .env
docker compose up -d --build
```

### Adresler

* Frontend: `http://localhost:3000`
* Backend: `http://localhost:8000`
* Swagger: `http://localhost:8000/docs`

### Demo

```bash
docker compose exec backend python -m app.scripts.seed_demo
docker compose exec backend python -m app.scripts.demo_smoke
```

### Test

```bash
docker compose exec backend pytest
docker compose exec backend ruff check .
docker compose exec backend mypy .
```

---

## English

### About

**TalentFilter AI** is a candidate sourcing and matching platform that analyzes job descriptions and extracts requirements such as title, skills, experience, education, language, certification, location, and industry.

It generates sourcing queries, processes candidate profiles, and calculates an explainable matching score between `0` and `100`.

The project was developed for educational and research purposes as part of an IT internship.

### Features

* Turkish and English job parsing
* X-Ray query generation
* Candidate discovery from search results
* Candidate profile enrichment
* Data-quality and duplicate checks
* Explainable candidate matching
* Shortlist and CSV export
* React dashboard
* Docker Compose support

### Technology Stack

**Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, Alembic, Pytest
**Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query
**Container:** Docker Compose, Nginx

### Setup

```bash
git clone <repository-url>
cd TalentFilter
cp .env.example .env
docker compose up -d --build
```

---

## LinkedIn, KVKK and Responsible Use

### Türkçe

Bu proje yalnızca **eğitim, araştırma ve prototip geliştirme amacıyla** hazırlanmıştır.

Proje LinkedIn tarafından geliştirilmemiş veya desteklenmemiştir. LinkedIn kullanım koşullarının, güvenlik önlemlerinin veya CAPTCHA sistemlerinin aşılması amacıyla kullanılmamalıdır.

Kişisel verileri işleyen kullanıcı veya kurum; KVKK, ilgili mevzuat, veri minimizasyonu, güvenlik, saklama ve aydınlatma yükümlülüklerine uymaktan sorumludur.

Yazılımın kullanımından doğabilecek hukuki, idari ve platform kaynaklı sonuçlar tamamen kullanan kişi veya kuruma aittir.

### English

This project is provided only for **education, research, and prototype development**.

It is not developed or endorsed by LinkedIn and must not be used to bypass platform terms, security controls, or CAPTCHA systems.

The user or organization operating the software is responsible for complying with applicable privacy laws, platform rules, data-security requirements, and retention obligations.

All legal, administrative, and contractual responsibility arising from the use of the project belongs to the user.
