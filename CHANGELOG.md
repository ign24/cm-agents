# Changelog

Todos los cambios notables al proyecto se documentan en este archivo.

## [Unreleased]

### Added

- Suite E2E de orquestación en `tests/test_orchestrator_e2e.py` (6 tests) cubriendo:
  - Flujo `OrchestratorCampaignService` -> workers (`research`, `copy`, `design`, `generate`, `qa`).
  - Decisiones dinámicas run/skip (`build=false`, `sin texto`, `tendencias`, `style_ref`).
  - Validación de `artifacts.json` y `report.md`.
  - Mocks de Anthropic/OpenAI para ruta Responses API sin llamadas reales.

### Changed

- Documentación actualizada a **92 tests** (README y AGENTS).
- Se actualizó la sección de knowledge base en README para listar todos los JSON activos:
  `design_2026.json`, `copy_templates.json`, `industry_insights.json`, `marketing_calendar.json`.

### Removed

- Integración MCP/Pinterest eliminada:
  - `src/cm_agents/services/mcp_client.py` eliminado.
  - Dependencia `mcp>=1.7.0` eliminada de `pyproject.toml`.
  - Comando `cm pinterest-search` eliminado del CLI.
  - Comando `cm mcp-tools` eliminado del CLI.
  - `StrategistAgent` ya no busca en Pinterest; solo maneja referencias adjuntas o locales.
  - `CampaignPipeline.run_with_pinterest_search_sync()` eliminado.

### Security

- WebSocket hardening en `chat.py`:
  - Límite de 500 sesiones simultáneas con eviction por LRU.
  - Historial de conversación recortado a 80 mensajes por sesión.
  - Rate limiting por conexión WebSocket: 30 mensajes/minuto.
  - Validación de imágenes entrantes: máximo 5 por mensaje, 5 MB cada una.
- `RateLimiter` (HTTP): `X-Forwarded-For` ya no se confía por defecto. Activar con `TRUST_PROXY=true` solo si hay un reverse-proxy que filtre el header de origen externo.

### Fixed

- Diagrama Mermaid en README ("Strategist como Orquestador") corregido para compatibilidad de render en GitHub.

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
- Herramientas: `cm estimate`.
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
