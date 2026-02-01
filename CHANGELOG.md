# Changelog

Todos los cambios notables al proyecto se documentan en este archivo.

## [Unreleased]

### Added

- **Campaña por referencias (reference-driven)** – Flujo con 3 referencias: producto, escena y fuente.
  - **Agente 1:** Genera fondo + producto en **una sola llamada** (replica exacta del producto, estilo de la escena). Método `generate_scene_with_product(product_ref, scene_ref)` en DirectGenerator.
  - **Agente 2:** Agrega texto por día usando referencia de tipografía. Parámetro `font_ref` en `add_text_overlay()`.
  - Pipeline `run_reference_driven_campaign(product_ref, scene_ref, font_ref, brand_dir, ...)` que genera una imagen base y N variaciones con copy distinto por día (por defecto 3 días: teaser, main_offer, last_chance).
- **CLI:** Comando `cm campaign-refs` con opciones `--product`, `--scene`, `--font`, `--brand`, `--days`, `--price`, `--plan`, `--output`.

### Changed

- Prompts de generación usan la palabra **"replica"** / **"exact replica"** para exigir fidelidad al producto de referencia.

---

## [2.1.0] - 2026-01-24

### ✨ Added

#### Funcionalidad
- **StrategistAgent integrado** - Chat y creación de planes desde lenguaje natural
- **API REST completa** - Endpoints para chat, plans, brands, campaigns, generate
- **WebSocket real-time** - Chat en tiempo real con auto-reconexión
- **Frontend Next.js 16** - UI moderna con chat funcional
- **Estado persistente** - Conversaciones guardadas con Zustand

#### Testing
- **36 tests automatizados** - Cobertura de API, seguridad y lógica
  - 10 tests de API (health, brands, plans, chat)
  - 13 tests de seguridad (validación, rate limiting)
  - 13 tests de StrategistAgent (intent detection, plans)
- **Fixtures reutilizables** - Para brands, knowledge base, client

#### Seguridad
- **Validación de slugs** - Anti path-traversal (`[a-z0-9-]` only)
- **Rate limiting** - 120 requests/minuto por IP
- **Validación de archivos** - Solo extensiones seguras (.png, .jpg, etc)
- **API Key opcional** - Protección con header `X-API-Key`
- **CORS configurable** - Estricto en producción
- **MIME type validation** - FileResponse con verificación de tipo

### 🔧 Fixed

#### Backend
- **127 errores de lint** - Auto-fixed con ruff
- **Imports ordenados** - Organizados alfabéticamente
- **F-strings** - Removidos f-strings vacíos
- **Variables sin usar** - Limpiadas

#### Frontend
- **useWebSocket hook** - Fixed "connect accessed before declaration"
- **Type errors** - Todos los errores de TypeScript resueltos
- **Build** - Frontend compila sin errores

### 📝 Changed

- **config.py** - Agregado `API_KEY` y `cors_origins_list` property
- **.env.example** - Actualizado con variables de seguridad
- **Routes** - Todos los endpoints con rate limiting
- **WebSocket** - Usa refs para evitar closures obsoletas

### 📚 Documentation

- **README.md** - Actualizado con features v2.1 y setup completo
- **PROJECT_CONTEXT.md** - Estado actual, completados y pendientes
- **AGENTS.md** - Secciones de API, Security, Testing, Frontend
- **ui/AGENTS.md** - Creado para guía del frontend
- **CHANGELOG.md** - Este archivo

---

## [2.0.0] - 2026-01-22

### Initial MVP Release

- Pipeline de 3 agentes (Extractor, Designer, Generator)
- CLI con Typer
- Modelo de marcas y campañas
- Knowledge base con estilos dinámicos
- FastAPI server basic
- Frontend Next.js scaffolding

---

## Formato

Basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

### Tipos de cambios
- **Added** - Nuevas funcionalidades
- **Changed** - Cambios en funcionalidad existente
- **Deprecated** - Funcionalidad que será removida
- **Removed** - Funcionalidad removida
- **Fixed** - Bug fixes
- **Security** - Vulnerabilidades arregladas
