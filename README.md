# CimTalent AI

CimTalent AI için aşamalı geliştirilen işe alım karar destek platformu.

Bu revizyonda test edilmiş backend iskeleti, ORM/Alembic domain katmanı ve temel Job CRUD API bulunmaktadır. Kurulum ve
çalıştırma adımları için [backend/README.md](backend/README.md) belgesine bakın.

## Mevcut aşama

- FastAPI uygulama fabrikası
- Sürümlü API router yapısı
- Pydantic Settings tabanlı konfigürasyon
- Yapılandırılmış JSON loglama ve hassas alan maskeleme
- SQLAlchemy 2 async engine/session temeli
- UTC ve UUID model mixin'leri
- 13 ilişkili ORM domain tablosu ve 14 enum sınıfı
- PostgreSQL JSONB / SQLite JSON uyumlu mutable alanlar
- Async Alembic ve ilk domain migration'ı
- JobPosting şemaları, repository/service katmanı ve CRUD endpoint'leri
- Filtreleme, güvenli sıralama, pagination ve standart domain hata response'ları
- `GET /api/v1/health`
- pytest, coverage, Ruff ve mypy yapılandırması

Parser, matching algoritması, scraping, worker, Docker ve frontend
sonraki aşamalara bırakılmıştır.
