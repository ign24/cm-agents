# CM Agents - Reglas de Proyecto

## Descripcion del Proyecto
Sistema de orquestacion de agentes AI para automatizar la creacion de contenido visual para redes sociales. Genera imagenes profesionales de productos con calidad de diseno de agencia.

**Version:** 2.1.0
**Stack:** Python 3.11+ (backend), Next.js 16 + Tailwind 4 (frontend)

## Arquitectura de Agentes

```
[Pinterest Ref] + [Producto Real] -> EXTRACTOR -> DESIGNER -> GENERATOR -> [Imagen Final]
```

### Agentes Principales
- **ExtractorAgent** (`src/cm_agents/agents/extractor.py`): Claude Vision - Analiza imagenes y extrae estilo
- **DesignerAgent** (`src/cm_agents/agents/designer.py`): Claude Sonnet - Construye prompts optimizados
- **GeneratorAgent** (`src/cm_agents/agents/generator.py`): GPT-Image-1 - Genera imagen final
- **StrategistAgent** (`src/cm_agents/agents/strategist.py`): Claude Sonnet - Interpreta lenguaje natural y crea planes

## Estructura de Directorios Clave

```
cm-agents/
├── brands/{marca}/           # Configuracion de marcas
│   ├── brand.json            # Identidad visual completa
│   ├── assets/               # Logos e iconos
│   └── campaigns/            # Campanas publicitarias
├── products/{marca}/{prod}/  # Productos por marca
│   ├── product.json
│   └── photos/               # Fotos del producto real
├── knowledge/                # Base de conocimiento
│   └── design_2026.json      # Estilos dinamicos (NO hardcodear)
├── src/cm_agents/
│   ├── agents/               # Los 4 agentes
│   ├── api/                  # FastAPI backend
│   └── pipeline.py           # Orquestacion
└── ui/                       # Next.js frontend
```

## Reglas de Desarrollo

### Estilos de Diseno
- Los estilos son **dinamicos** - se cargan de `knowledge/design_2026.json`
- NUNCA hardcodear estilos en el codigo
- Usar `get_available_styles()` o cargar del knowledge base
- 17 estilos disponibles: minimal_clean, lifestyle_warm, editorial_magazine, etc.

### Generacion de Imagenes
- El producto debe ser **replica exacta** - el Extractor captura detalles hiper-especificos
- El texto se genera **integrado en la imagen** - no hay TextOverlayService separado
- El logo se inserta automaticamente si existe en `assets/`
- Usar Responses API de OpenAI (con fallback a generacion simple)

### Configuracion de Marca
- Archivo: `brands/{marca}/brand.json`
- Incluye: identity, assets, palette, typography, style, text_overlay
- Metodos utiles: `brand.get_preferred_styles()`, `brand.get_logo_path()`

### CLI
Comandos principales:
```bash
cm generate <producto> <marca> <ref> [-p producto.jpg] [--style estilo]
cm brand-list / cm brand-create / cm brand-show
cm campaign-create / cm campaign-list
cm styles [categoria]
cm serve --port 8000 --reload
```

## API y Frontend

### Backend (FastAPI)
- Puerto default: 8000
- Endpoints: `/api/v1/chat`, `/api/v1/plans`, `/api/v1/brands`
- WebSocket: `/api/v1/ws/chat/{session_id}`
- Seguridad: Rate limiting 120 req/min, validacion de slugs

### Frontend (Next.js)
- Puerto default: 3000
- Package manager: Bun
- Componentes: shadcn/ui (new-york style)
- Estado: Zustand con persistencia

## Comandos de Desarrollo

```bash
# Backend
pip install -e .
pytest tests/ -v
ruff check src/ --fix
cm serve --reload

# Frontend
cd ui
bun install
bun dev
bun run lint
```

## Variables de Entorno Requeridas

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
API_KEY=your-secret-key  # Opcional
```

## Testing
- 36 tests automatizados
- Ejecutar: `pytest tests/ -v`
- Tests de: API, seguridad, strategist

## Costos por Generacion
- Extractor: ~$0.003
- Designer: ~$0.005
- Generator: ~$0.04
- **Total: ~$0.05/imagen**

## Notas Importantes

1. **Campanas override estilos** - El estilo de campana tiene prioridad sobre el de marca
2. **El StrategistAgent pregunta lo que el pipeline necesita** - No asume informacion
3. **Productos con fotos** - El pipeline necesita `products/{marca}/{prod}/photos/` para replicar
4. **Sin emojis en codigo** - Usar iconos de MCPs como Flaticon cuando sea necesario para UIs
