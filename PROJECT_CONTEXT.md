# CM Agents - Contexto del Proyecto

**Versión:** 2.1.0  
**Estado:** MVP funcional con API conectada, UI operativa, y seguridad básica  
**Fecha de inicio:** 22 de enero de 2026  
**Última actualización:** 24 de enero de 2026

---

## Resumen del Proyecto

Sistema de agentes para automatizar la creación de diseños de redes sociales para Community Managers.

### Workflow Principal (v2.0)

```
Natural Language → StrategistAgent → ContentPlan → Approval → Generation Pipeline
                                          ↓
                   Pinterest Reference → Extractor → Architect → Generator → Output
```

### Agentes

| Agente | Modelo | Función | Costo/imagen |
|---------|---------|-----------|----------------|
| **Strategist** | Claude Sonnet 4 | Interpreta requests y crea ContentPlans | ~$0.003 |
| **Extractor** | Claude Haiku Vision | Analiza imágenes de Pinterest y extrae estilo | ~$0.001 |
| **Architect** | Claude Sonnet/Haiku | Construye prompts optimizados combinando marca + producto | ~$0.002 |
| **Generator** | GPT-5.2 (gpt-image-1.5) | Genera imagen completa | ~$0.04-0.06 |
| **Total** | | | **~$0.05-0.07** |

---

## Stack Tecnológico

| Componente | Tecnología | Versión |
|-----------|--------------|----------|
| Orquestación | Python | 3.11+ |
| LLM Análisis | Anthropic Claude Sonnet 4-5 / Haiku 4.5 | 20250514 |
| Generación Imágenes | OpenAI GPT Image | gpt-image-1.5 |
| Text Overlay | Pillow (PIL) | 10.0+ |
| CLI | Typer | 0.12+ |
| Configuración | Pydantic | 2.0+ |
| Output | Rich | 13.0+ |
| Backend API | FastAPI + Uvicorn | 0.115+ |
| Frontend | Next.js 16 + Tailwind 4 + shadcn/ui | 16.x |
| State | Zustand | 5.x |
| WebSockets | python-websockets | 12+ |
| Testing | pytest + TestClient | 8.0+ |
| Linting | ruff | 0.8+ |

---

## Estructura del Proyecto

```
cm-agents/
├── brands/              # Configuraciones de marcas (JSON)
│   └── {marca}/
│       ├── brand.json
│       └── fonts/
├── products/            # Configuraciones de productos (JSON)
│   └── {marca}/
│       └── {producto}/
│           ├── product.json
│           └── photos/
├── references/          # Imágenes de Pinterest
├── knowledge/           # Marketing Knowledge Base (v2.0)
│   ├── marketing_calendar.json
│   ├── industry_insights.json
│   └── copy_templates.json
├── templates/           # System prompts de agentes
│   └── prompts/
│       ├── extractor.json
│       ├── architect.json
│       ├── generator.json
│       └── text_overlay.json
├── outputs/             # Imágenes generadas con metadata
│   └── {marca}/{YYYY-MM-DD}/
├── src/cm_agents/
│   ├── agents/        # Agentes (Strategist, Extractor, Architect, Generator)
│   ├── api/           # FastAPI backend (v2.0)
│   │   ├── routes/    # Endpoints REST + WebSocket
│   │   ├── websocket/ # Connection manager
│   │   ├── main.py
│   │   └── schemas.py
│   ├── services/       # Text overlay, MCP client
│   ├── models/         # Pydantic models (Brand, Product, Plan)
│   ├── pipeline.py      # Orquestación
│   └── cli.py          # CLI
├── ui/                  # Next.js 15 frontend (v2.0)
│   └── src/
│       ├── app/
│       ├── components/chat/
│       ├── hooks/
│       ├── lib/
│       └── stores/
└── README.md
```

---

## Comandos del CLI

### `cm generate <producto> <marca> <referencia>`

Genera una imagen basada en una referencia de Pinterest.

**Opciones:**
- `--size/-s`: Tamaño ["feed", "story"], default: feed
- `--text/--no-text`: Agregar overlays de texto, default: Sí
- `--model/-m`: Modelo de generación, default: gpt-image-1.5

**Ejemplo:**
```bash
cm generate hamburguesa resto-mario ~/Downloads/pins.png --size feed story
```

### `cm batch <producto> <marca>`

Genera múltiples variantes (una por cada referencia en `references/`).

**Ejemplo:**
```bash
cm batch hamburguesa resto-mario --size feed
```

### `cm brand-list`

Lista todas las marcas configuradas.

### `cm product-list <marca>`

Lista todos los productos de una marca con precios.

### `cm status`

Muestra el estado de la configuración.

### `cm estimate`

Estima el costo de generar imágenes.

### `cm serve [--port PORT] [--reload]`

Inicia el servidor FastAPI.

```bash
cm serve --port 8000 --reload
```

### `cm plan-create "prompt" --brand BRAND [--campaign CAMPAIGN]`

Crea un ContentPlan desde lenguaje natural.

```bash
cm plan-create "Crear post promocional para el día del padre" --brand resto-mario
```

### `cm plan-list [--brand BRAND]`

Lista todos los planes.

### `cm plan-show <id>`

Muestra detalles de un plan.

### `cm plan-approve <id>`

Aprueba un plan para ejecución.

### `cm plan-execute <id>`

Ejecuta la generación de un plan aprobado.

---

## Formatos de Configuración

### brand.json

```json
{
  "name": "Nombre de la marca",
  "handle": "@marca",
  "palette": {
    "primary": "#RRGGBB",
    "secondary": "#RRGGBB",
    "background": "#RRGGBB",
    "text": "#RRGGBB",
    "accent": "#RRGGBB"
  },
  "fonts": {
    "heading": "fonts/fuente.ttf",
    "body": "fonts/fuente.ttf",
    "price": "fonts/fuente.ttf"
  },
  "style": {
    "mood": ["cálido", "familiar", "apetitoso"],
    "photography_style": "close-up, warm lighting, steam visible",
    "preferred_backgrounds": ["rustic wooden table", "warm restaurant ambiance"]
  },
  "text_overlay": {
    "price_badge": {
      "bg_color": "#RRGGBB",
      "text_color": "#RRGGBB",
      "position": "bottom-left",
      "padding": 20
    },
    "title": {
      "color": "#RRGGBB",
      "shadow": true,
      "position": "top-center"
    }
  },
  "hashtags": {
    "always": ["#Marca", "#ComidaCasera"],
    "categories": {
      "categoria": ["#Hashtag1", "#Hashtag2"]
    }
  }
}
```

### product.json

```json
{
  "name": "Nombre del producto",
  "price": "$XX.XX",
  "description": "Descripción corta del producto",
  "visual_description": "Descripción visual detallada para generación de imágenes (MUY IMPORTANTE)",
  "photos": ["photos/product.png"],
  "category": "categoría",
  "tags": ["bestseller", "carne"]
}
```

---

## Costos Estimados (Generación de Imágenes)

| Modelo | Costo/imagen | Descripción |
|--------|---------------|-------------|
| gpt-image-1.5 | $0.06 | Calidad premium, mejor texto |
| gpt-image-1 | $0.04 | Buena calidad, económico |
| gpt-image-1-mini | $0.02 | Rápido, más barato |

**Total por imagen (3 agentes + generación):** ~$0.05-0.07

**40 posts/mes (1 imagen/post):** ~$2-3/mes  
**120 imágenes/mes (batch):** ~$6-9/mes

---

## Decisiones de Diseño Tomadas

### Por qué GPT-5.2 y no FLUX Kontext

**Decisión del usuario:** GPT-5.2 genera mejores resultados desde cero.

**Justificación:**
- GPT-5.2 genera el producto completo desde el prompt
- FLUX Kontext es mejor para "editar/insertar" un producto existente
- En este caso, el producto se genera desde cero, así que GPT-5.2 es ideal

### Variantes vs Merge de Referencias

**Decisión:** Una variante por referencia (no merge).

**Flujo:**
1. Cada referencia de Pinterest = 1 análisis
2. Cada análisis = 1 prompt
3. Cada prompt = 1 imagen generada
4. Resultado: Múlticas opciones para elegir, no una imagen "híbrida"

### JSON para Todo

**Decisión:** JSON para todas las configuraciones.

**Justificación:**
- Consistente con Pydantic
- Fácil de leer/editar manualmente
- Compatibilidad con herramientas JSON

---

## Estado Actual (24/01/2026)

### ✅ Completado

#### Funcionalidad
- [x] StrategistAgent conectado a API REST y WebSocket
- [x] Chat funcional con contexto de conversación
- [x] Creación de planes desde lenguaje natural
- [x] Frontend UI con chat real-time
- [x] WebSocket con auto-reconexión y ping/pong

#### Calidad
- [x] 36 tests pasando (API, Security, Strategist)
- [x] Linting: 127 errores arreglados con ruff
- [x] Frontend build sin errores
- [x] Type checking pasando

#### Seguridad
- [x] Validación de slugs (anti path-traversal)
- [x] Rate limiting (120 req/min)
- [x] Validación de extensiones de archivo
- [x] API Key opcional
- [x] CORS configurable por entorno
- [x] FileResponse con MIME type validation

### 🚧 Pendiente

#### Funcionalidad
- [ ] Conectar GenerationPipeline real (actualmente simulado)
- [ ] Integración MCP Pinterest para búsqueda de referencias
- [ ] Persistencia de conversaciones (SQLite/PostgreSQL)
- [ ] Sistema de aprobación de planes con notificaciones
- [ ] Publicación directa a redes sociales

#### Mejoras Técnicas
- [ ] Tests de integración end-to-end
- [ ] Logging estructurado con context (request_id)
- [ ] Métricas de uso (costos, tiempos, tokens)
- [ ] CI/CD pipeline
- [ ] Docker compose para dev environment

#### Seguridad
- [ ] Auth con JWT tokens
- [ ] Audit logging de accesos
- [ ] Sanitización de logs (ocultar API keys)
- [ ] HTTPS obligatorio en producción
- [ ] Rate limiting por usuario (no solo IP)

### Integraciones Futuras

- [x] Integración MCP (Pinterest, Filesystem)
- [ ] Scheduling automático (Buffer/Metricool API)
- [ ] Publicación directa (Meta Graph API / Instagram MCP)
- [ ] Analytics y tracking
- [ ] Generación de captions automáticos
- [ ] Hashtag optimización

---

## Integración MCP (Model Context Protocol)

### MCPs Instalados

| MCP | Función | Comando |
|-----|---------|--------|
| **filesystem** | Operaciones de archivos | `@modelcontextprotocol/server-filesystem` |
| **pinterest** | Búsqueda y descarga de imágenes | `pinterest-mcp-server` |

### Uso desde CLI

```bash
# Buscar imágenes en Pinterest y descargarlas
cm pinterest-search "food photography minimal" --limit 5

# Listar tools disponibles en un MCP
cm mcp-tools pinterest
```

### Uso desde Python (Agentes)

```python
from cm_agents.services.mcp_client import MCPClientService
import asyncio

async def buscar_referencias():
    service = MCPClientService()
    results = await service.search_pinterest("food photography", limit=10)
    return results

asyncio.run(buscar_referencias())
```

### Configuración Claude Desktop

Archivo: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\Proyectos\\cm-agents"]
    },
    "pinterest": {
      "command": "npx",
      "args": ["pinterest-mcp-server"],
      "env": { "MCP_PINTEREST_DOWNLOAD_DIR": "C:\\Proyectos\\cm-agents\\references" }
    }
  }
}
```

---

## API Keys Necesarias

Configurar en `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx
```

### Obtener Keys:

- **Anthropic**: https://console.anthropic.com/settings/keys
- **OpenAI**: https://platform.openai.com/api-keys

---

## Notes del Usuario

### 22/01/2026
- **Estado:** Implementación MVP completada
- **Lo que funciona:**
  - Estructura del proyecto completa
  - 3 agentes implementados (Extractor, Architect, Generator)
  - Text Overlay con Pillow
  - Pipeline orquestador funcional
  - CLI con Typer
  - Templates de prompts en JSON
  - Marca de ejemplo (resto-mario)
  - Producto de ejemplo (hamburguesa)
- **Lo que falta:**
  - Instalar dependencias
  - Probar con datos reales
  - Corregir errores de LSP ( Pillow/PIL imports)
  - Agregar logging
  - Tests
  - Integración con scheduling

### Tips de Uso

1. **Agrega `visual_description` al product.json:**
   - Es el texto que describe el producto para que GPT-5.2 pueda generarlo fielmente
   - Ejemplo: "A gourmet hamburger with brioche bun golden-brown with sesame seeds, 200g beef patty..."

2. **Usa siempre una referencia de Pinterest:**
   - El flujo está optimizado para este caso
   - Sin referencia, el Architect tendrá que "adivinar" el estilo

3. **Fuentes:**
   - Agrega archivos .ttf en `brands/{marca}/fonts/`
   - El sistema usa fuentes del sistema si no encuentra las personalizadas

4. **Costos:**
   - Revisa con `cm estimate` antes de generar muchos posts
   - Usa `gpt-image-1` para más económico si no necesitas calidad premium

---

## Referencias

### Documentación Utilizada

- **Claude Vision API:** https://docs.anthropic.com/en/build-with-claude/vision
- **OpenAI Image Generation:** https://platform.openai.com/docs/guides/image-generation
- **Best Practices 2026:** Investigadas en enero 2026

### Patrones de Código

- **Type hints:** Python 3.11+ con typing module
- **Data validation:** Pydantic v2
- **Error handling:** Exceptions con mensajes claros
- **Logging:** Rich console output

---

## Comandos de Desarrollo

```bash
# Instalar dependencias
pip install -e .

# Formatear código
ruff check . && ruff format .

# Ejecutar CLI
python -m cm_agents status
```

---

**Última actualización:** 24 de enero de 2026
