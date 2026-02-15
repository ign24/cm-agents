# Changelog

Todos los cambios notables al proyecto se documentan en este archivo.

## [Unreleased]

### Added

### Changed

### Fixed

---

## [0.1.0] - 2026-02-15

### Added

- Pipeline de generación de imágenes para redes sociales (producto + estilo) con orquestación por agentes:
  - `CreativeEngine` (Claude Sonnet 4 Vision): analiza referencias + genera prompts en 1 sola llamada.
  - `GeneratorAgent` (GPT-Image-1.5): genera imagen final vía Responses API.
  - `StrategistAgent` (Claude Sonnet 4): interpreta lenguaje natural, crea planes de contenido.
- API REST + WebSocket (chat, planes, marcas, campañas, generación).
- Frontend `ui/` (Next.js 16) incluido dentro del repo.
- Knowledge base `knowledge/design_2026.json` con 17 estilos y guidelines por categoría.
- Campañas:
  - `cm campaign-inpaint` (inpainting en pasos).
  - `cm campaign-refs` (producto+escena+fuente) con variaciones de ángulo por día.
- Planes de contenido: `cm plan-create`, `plan-list`, `plan-show`, `plan-approve`, `plan-execute`.
- Herramientas: `cm pinterest-search`, `cm mcp-tools`, `cm estimate`.
- Registro de estilos dinámico (`styles.py`) cargado desde knowledge base.

### Changed

- `cm campaign-refs`: genera una imagen por día con ángulo/composición distinto del producto y agrega texto por día (sin `--price`).

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
