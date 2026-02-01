# CM-Agents: Documentación para Agentes AI

Este documento describe el sistema de orquestación de agentes para que otro agente AI pueda entenderlo, modificarlo o extenderlo.

## Propósito del Sistema

CM-Agents genera imágenes de productos para redes sociales (Instagram) automatizando el trabajo de un diseñador gráfico. Soporta **múltiples marcas** con identidades visuales independientes y **campañas publicitarias**.

Características principales:
- El producto real (réplica exacta)
- Texto integrado (nombre + precio)
- Logo de la marca insertado automáticamente
- Estilo visual de la referencia
- Consistencia de marca (colores, estilos preferidos)
- Campañas con temas y fechas

## Arquitectura: 3 Agentes en Pipeline

```
[Pinterest Ref] ──┐
                  ├──▶ EXTRACTOR ──▶ DESIGNER ──▶ GENERATOR ──▶ [Imagen Final]
[Producto Real] ──┘
```

### Flujo de Datos

```
Input:
  - style_ref: Path (imagen Pinterest)
  - product_ref: Path (foto producto real)
  - brand: Brand (config marca)
  - product: Product (config producto)

Extractor Output → Designer Input:
  - ReferenceAnalysis
    - layout: LayoutAnalysis
    - style: StyleAnalysis  
    - colors: ColorAnalysis
    - typography: TypographyAnalysis
    - product_visual: ProductVisualAnalysis (descripción exacta del producto)

Designer Output → Generator Input:
  - GenerationPrompt
    - prompt: str (prompt optimizado en inglés)
    - visual_description: str
    - negative_prompt: str
    - params: GenerationParams

Generator Output:
  - GenerationResult
    - image_path: Path
    - cost_usd: float
    - metadata
```

## Archivos Clave

### Agentes (`src/cm_agents/agents/`)

| Archivo | Clase | Modelo AI | Función |
|---------|-------|-----------|---------|
| `extractor.py` | `ExtractorAgent` | Claude Sonnet 4 (Vision) | Analiza imágenes, extrae estilo y descripción exacta del producto |
| `designer.py` | `DesignerAgent` | Claude Sonnet 4 | Construye prompts con best practices 2026, selecciona estilo |
| `generator.py` | `GeneratorAgent` | GPT-Image-1 | Genera imagen final con Responses API |
| `architect.py` | `PromptArchitectAgent` | Claude Sonnet 4 | (Legacy) Versión simple sin knowledge base |

### Modelos (`src/cm_agents/models/`)

| Archivo | Clases | Uso |
|---------|--------|-----|
| `generation.py` | `ReferenceAnalysis`, `GenerationPrompt`, `GenerationResult` | Datos entre agentes |
| `brand.py` | `Brand`, `BrandIdentity`, `BrandAssets`, `StyleConfig`, `ColorPalette` | Configuración completa de marca |
| `product.py` | `Product` | Configuración de producto |
| `campaign.py` | `Campaign`, `CampaignTheme`, `ContentItem` | Campañas publicitarias |

### Orquestación (`src/cm_agents/`)

| Archivo | Clase/Función | Uso |
|---------|---------------|-----|
| `pipeline.py` | `GenerationPipeline` | Orquesta los 3 agentes, maneja flujo completo |
| `cli.py` | Typer commands | Interfaz CLI (`cm generate`, `cm styles`, etc.) |

### Knowledge Base (`knowledge/`)

| Archivo | Contenido |
|---------|-----------|
| `design_2026.json` | Estilos dinámicos, tendencias, guidelines por categoría, principios de diseño |

## Cómo Funciona Cada Agente

### 1. ExtractorAgent

**Entrada**: 2 imágenes (estilo + producto)
**Salida**: `ReferenceAnalysis`

```python
# Prompt clave en DUAL_EXTRACTOR_SYSTEM_PROMPT
# Captura descripción HIPER-DETALLADA del producto para réplica exacta:
# - brand_name, product_type, exact_shape
# - label_design, material_finish, cap_description
# - liquid_visible, unique_features, full_description
```

**Método principal**: `analyze_dual(style_ref_path, product_ref_path)`

### 2. DesignerAgent

**Entrada**: `ReferenceAnalysis`, `Brand`, `Product`, `target_size`, `style`
**Salida**: `GenerationPrompt`

**Características**:
- Carga estilos dinámicamente de `knowledge/design_2026.json`
- Auto-selecciona estilo si `style=None` basado en categoría/mood
- Incluye instrucciones de texto integrado (nombre + precio)
- Enfatiza réplica EXACTA del producto

```python
# Estilos disponibles (dinámicos)
DESIGN_STYLES = get_available_styles()  # Lee de knowledge base

# Método principal
def build_prompt(reference_analysis, brand, product, target_size, style=None):
    # Si style es None, auto-selecciona con _recommend_style()
    # Construye contexto enriquecido para Claude
    # Retorna GenerationPrompt con prompt optimizado
```

### 3. GeneratorAgent

**Entrada**: `GenerationPrompt`, imágenes de referencia, `Brand`, `Product`
**Salida**: `GenerationResult` (imagen guardada)

**Método principal**: `generate_with_image_refs(prompt, reference_images, ...)`
- Usa Responses API de OpenAI para mejor fidelidad
- Incluye imágenes de referencia como contexto
- Fallback a generación simple si Responses API no disponible

## Pipeline de Orquestación

```python
# src/cm_agents/pipeline.py

class GenerationPipeline:
    def __init__(self, generator_model, use_designer=True, design_style=None):
        self.extractor = ExtractorAgent()
        self.prompt_agent = DesignerAgent() if use_designer else PromptArchitectAgent()
        self.generator = GeneratorAgent(model=generator_model)
        self.design_style = design_style

    def run(self, reference_path, brand_dir, product_dir, ...):
        # 1. Cargar configuración
        brand = Brand.load(brand_dir)
        product = Product.load(product_dir)

        # 2. Extractor: Analizar referencias
        reference_analysis = self.extractor.analyze_dual(reference_path, product_ref_path)

        # 3. Designer: Construir prompt
        prompt = self.prompt_agent.build_prompt(
            reference_analysis, brand, product, target_size, style=self.design_style
        )

        # 4. Generator: Generar imagen
        result = self.generator.generate_with_image_refs(prompt, ref_images, ...)

        # 5. Guardar metadatos
        result.save_metadata()

        return results
```

### Campaña por referencias (reference-driven)

Flujo con **3 referencias**: producto, escena y fuente. Fondo + producto se generan **en una sola llamada** (replica exacta); el texto se agrega por día usando la referencia de tipografía.

- **DirectGenerator** (`services/direct_generator.py`):
  - `generate_scene_with_product(product_ref, scene_ref, ...)`: una llamada a Responses API con ambas imágenes; prompt con "exact replica" del producto.
  - `add_text_overlay(..., font_ref=Path)`: agrega headline/precio siguiendo la referencia de tipografía (imagen de muestra).
- **CampaignPipeline.run_reference_driven_campaign(product_ref, scene_ref, font_ref, brand_dir, campaign_plan=None, ...)**: genera una imagen base (escena + producto) y N imágenes finales (una por día, copy distinto). Por defecto 3 días: teaser, main_offer, last_chance.

## Knowledge Base: Sistema de Estilos Dinámico

Los estilos NO están hardcodeados. Se cargan de `knowledge/design_2026.json`:

```json
{
  "styles": {
    "minimal_clean": {
      "name": "Minimal Clean",
      "description": "...",
      "lighting": "soft_studio",
      "composition": "centered",
      "background": ["white", "light gray"],
      "prompt_template": "...",
      "negative_prompt": "..."
    }
    // ... más estilos
  },
  "category_guidelines": {
    "food": {
      "recommended_styles": ["lifestyle_warm", "authentic_imperfect"],
      "lighting": ["natural_window", "golden_hour"],
      "props": ["ceramic dishes", "..."],
      "prompt_additions": ["appetizing", "..."],
      "avoid": ["cold lighting", "..."]
    }
    // ... más categorías
  }
}
```

**Para agregar un estilo**: Solo editar el JSON. El código lo carga automáticamente.

## CLI: Comandos Disponibles

```bash
# Generación
cm generate <producto> <marca> <ref_estilo> [-p <ref_producto>] [--style <estilo>] [--campaign <nombre>]

# Gestión de Marcas
cm brand-list                    # Lista marcas con industria y estilos preferidos
cm brand-create <nombre>         # Wizard interactivo para crear marca
cm brand-show <marca>            # Ver configuración completa (identidad, assets, estilos)

# Gestión de Campañas
cm campaign-create <marca> <nombre>   # Crear campaña con wizard
cm campaign-list <marca>              # Listar campañas (con progreso y estado)
cm campaign-show <marca> <camp>       # Ver detalles y plan de contenido
cm campaign-inpaint <marca> <camp>   # Campaña con inpainting (escena + producto por pasos)
cm campaign-refs <marca> -p <producto> -s <escena> -f <fuente> [--days 3]  # Campaña por referencias (fondo+producto en una llamada, texto con ref de fuente)

# Otros
cm styles [categoria]            # Listar estilos de diseño
cm product-list <marca>          # Listar productos
cm status                        # Estado del sistema
```

## Cómo Extender el Sistema

### Agregar nuevo estilo

1. Editar `knowledge/design_2026.json`
2. Agregar entrada en `styles`
3. (Opcional) Agregar categoría en `category_guidelines`

### Agregar nuevo agente

1. Crear `src/cm_agents/agents/mi_agente.py`
2. Heredar de `BaseAgent`
3. Implementar `_validate_env()`, `name`, `description`
4. Agregar al pipeline si es necesario

### Modificar flujo del pipeline

1. Editar `src/cm_agents/pipeline.py`
2. El método `run()` contiene el flujo principal
3. Los agentes son intercambiables (misma interfaz)

## Variables de Entorno Requeridas

```
ANTHROPIC_API_KEY=sk-ant-...  # Para Extractor y Designer
OPENAI_API_KEY=sk-...         # Para Generator
```

## Costos por Generación

| Agente | ~Costo |
|--------|--------|
| Extractor | $0.003 |
| Designer | $0.005 |
| Generator | $0.040 |
| **Total** | **~$0.05** |

## Archivos de Configuración

### brands/{marca}/brand.json (Modelo Completo)
```json
{
  "name": "Restaurante Mario",
  "industry": "food_restaurant",
  "identity": {
    "tagline": "Sabor de casa",
    "voice": ["familiar", "cálido"],
    "values": ["calidad", "tradición"]
  },
  "assets": {
    "logo": "assets/logo.png",
    "logo_white": "assets/logo-white.png",
    "icon": "assets/icon.png"
  },
  "palette": {
    "primary": "#D32F2F",
    "secondary": "#FFC107",
    "accent": "#4CAF50",
    "gradient": ["#D32F2F", "#FF5252"]
  },
  "typography": {
    "heading": { "font": "fonts/Montserrat-Bold.ttf", "style": "bold" },
    "price": { "font": "fonts/Montserrat-ExtraBold.ttf", "style": "attention-grabbing" }
  },
  "style": {
    "mood": ["cálido", "familiar"],
    "photography_style": "close-up, warm lighting",
    "preferred_design_styles": ["lifestyle_warm", "authentic_imperfect"],
    "avoid": ["cold colors", "clinical look"]
  },
  "text_overlay": {
    "price_badge": { "bg_color": "#D32F2F", "text_color": "#FFFFFF", "position": "bottom-left" },
    "title": { "position": "top-center" },
    "logo": { "position": "top-right", "size": "small" }
  },
  "social_media": {
    "instagram": "@restomario",
    "platforms": ["instagram", "facebook"]
  }
}
```

### brands/{marca}/campaigns/{campaign}/campaign.json
```json
{
  "name": "Promo Verano 2026",
  "description": "Campaña de verano",
  "dates": { "start": "2026-01-15", "end": "2026-02-28" },
  "theme": {
    "style_override": "biophilic_nature",
    "color_accent": "#4CAF50",
    "mood": ["fresco", "veraniego"]
  },
  "products": ["sprite", "coca-cola"],
  "content_plan": [
    { "date": "2026-01-15", "product": "sprite", "size": "feed", "status": "pending" }
  ],
  "hashtags_extra": ["#VeranoMario"]
}
```

### products/{marca}/{producto}/product.json
```json
{
  "name": "Nombre Producto",
  "description": "Descripción",
  "price": "$X.XX",
  "category": "food|beverages|pharmacy|..."
}
```

## Notas Importantes para Modificaciones

1. **El texto se genera integrado en la imagen** - No hay TextOverlayService, el Designer incluye instrucciones de texto en el prompt

2. **El producto debe ser réplica exacta** - El Extractor captura detalles hiper-específicos (marca, etiqueta, forma) para que Generator lo replique fielmente

3. **Estilos son dinámicos** - Nunca hardcodear estilos, siempre usar `get_available_styles()` o cargar de knowledge base

4. **El Designer auto-selecciona estilo** - Prioridad: (1) `brand.style.preferred_design_styles`, (2) categoría del producto, (3) mood de la referencia

5. **Responses API es preferida** - Generator intenta usar Responses API con imágenes de referencia para mejor fidelidad, con fallback a generación simple

6. **Logo se inserta automáticamente** - Si la marca tiene logo en `assets/`, se pasa como 3ra imagen de referencia al Generator

7. **Campañas override estilos** - Si se usa `--campaign`, el estilo de la campaña (`theme.style_override`) tiene prioridad sobre el de la marca

8. **Outputs por campaña** - Con `--campaign`, las imágenes se guardan en `brands/{marca}/campaigns/{camp}/outputs/`

## Estructura de Directorios por Marca

```
brands/{marca}/
├── brand.json              # Configuración completa de marca
├── assets/                 # Assets gráficos
│   ├── logo.png            # Logo principal (se inserta en imágenes)
│   ├── logo-white.png      # Variante para fondos oscuros
│   └── icon.png            # Icono/favicon
├── fonts/                  # Fuentes de la marca
├── references/             # Referencias visuales preferidas
└── campaigns/              # Campañas publicitarias
    └── promo-verano/
        ├── campaign.json   # Configuración de campaña
        └── outputs/        # Imágenes generadas para esta campaña
```

## Métodos Clave del Modelo Brand

```python
# Obtener estilos preferidos de la marca
brand.get_preferred_styles() -> list[str]

# Obtener estilos a evitar
brand.get_avoid_styles() -> list[str]

# Obtener path a un asset (logo, logo_white, icon, watermark)
brand.get_asset_path(brand_dir, "logo") -> Path | None

# Obtener logo (busca en assets.logo, luego en logo legacy)
brand.get_logo_path(brand_dir) -> Path | None

# Categoría de industria para guidelines
brand.get_industry_category() -> str | None
```

## API REST y WebSocket (`src/cm_agents/api/`)

### Arquitectura de la API

```
FastAPI Server (Uvicorn)
├── REST Endpoints (/api/v1/)
│   ├── /chat           - Chat con StrategistAgent
│   ├── /plans          - CRUD de planes de contenido
│   ├── /brands         - Gestión de marcas
│   ├── /campaigns      - Gestión de campañas
│   └── /generate       - Ejecución de generación
├── WebSocket (/api/v1/ws/chat/{session_id})
│   ├── Real-time chat
│   ├── Progress updates
│   └── Plan notifications
└── Security Layer
    ├── Rate limiting (120 req/min)
    ├── Slug validation (anti path-traversal)
    └── API Key opcional
```

### Agente Strategist (`strategist.py`)

**Nuevo en v2.1** - Agente de nivel superior que interpreta lenguaje natural.

```python
class StrategistAgent:
 def chat(message: str, brand: Brand | None, context: list, images: list[str] | None) -> (str, ContentPlan | None):
 """Chat conversacional que puede crear planes. images = data URLs base64 del frontend."""
 
 def create_plan(prompt: str, brand: Brand, brand_dir: Path) -> ContentPlan:
 """Crea un ContentPlan estructurado desde lenguaje natural."""
```

**Imágenes de referencia**:
- El frontend envía imágenes (data URLs base64) vía WebSocket `chat` o REST `POST /chat` con `images`.
- El Strategist las recibe y las pasa a **Claude Vision** (Anthropic) como bloques multimodales.
- No se usa OpenAI SDK ni MCP: solo Anthropic con vision nativo.
- Claude usa las imágenes como estilo Pinterest, producto o inspiración para el plan.

**Manejo de Contexto de Marca (v2.1.1+)**:

El StrategistAgent ahora **carga y enriquece el contexto de marca** antes de generar planes para evitar asunciones incorrectas:

1. **Carga automática de contexto**:
   - Información básica de `brand.json` (nombre, industria, voz, valores, colores, estilos)
   - Productos disponibles (desde `products/{marca}/`)
   - Campañas activas (desde `brands/{marca}/campaigns/`)
   - Assets disponibles (logo, iconos)

2. **Validación de contexto**:
   - Antes de crear planes, valida que tenga información crítica (industria, productos)
   - Si falta información, **pregunta al usuario** en lugar de asumir
   - No asume tipo de negocio (ej: no asume que es una cervecería si no está especificado)

3. **System prompt enriquecido**:
   - Incluye toda la información disponible de la marca en el system prompt
   - Instrucciones explícitas: "NO asumas información que no está especificada"
   - Si no hay marca: muestra advertencia y solicita contexto antes de crear planes

**Ejemplo de comportamiento mejorado**:

```
Usuario: "diseñemos un plan para black friday"
❌ Antes (v2.1.0): Asumía que era una cervecería premium
✅ Ahora (v2.1.1+): "Para crear un plan efectivo para Black Friday, necesito saber: 
   ¿qué tipo de negocio tenés? ¿qué productos o servicios ofrecés?"
```

**Preguntas alineadas con el Pipeline (Build)**:

El Strategist pregunta lo que el **GenerationPipeline** necesita para no fallar:

- **Marca (slug)**: `brands/{slug}/` — se pasa `brand_slug` desde la API.
- **Industria**: en `brand.json` (Designer y estilos).
- **Productos con fotos**: `products/{marca}/{producto}/` con `product.json` y `photos/` (el Generador replica el producto desde la foto).
- **Referencia de estilo**: Pinterest, imágenes adjuntas o `brands/{marca}/references/`.

Cada `ContentPlanItem.product` es el **slug** de un producto existente con fotos (nunca `"producto-general"` si hay productos). `plan.brand` es el slug de la marca para que `execute_generation` resuelva `brand_dir` y `product_dir`.

**Responsabilidades**:
- Entender intención del usuario (`_analyze_intent`)
- Detectar objetivo: promocionar, lanzamiento, engagement, etc.
- Detectar ocasión: día del padre, navidad, black friday
- Detectar tono: urgente, elegante, divertido
- Auto-seleccionar estilo de diseño según marca/industria
- Generar copy suggestions desde templates
- Crear queries para búsqueda de referencias

### Endpoints Principales

#### POST `/api/v1/chat`
Chat REST simple con StrategistAgent.

```json
{
  "message": "Crear post para el día del padre",
  "brand": "resto-mario"
}
```

**Response**: `{ "message": ChatMessage, "plan": ContentPlan | null }`

#### POST `/api/v1/plans`
Crear plan de contenido desde lenguaje natural.

```json
{
  "prompt": "3 posts promocionales para hamburguesas 2x1",
  "brand": "resto-mario",
  "campaign": "promo-verano"  // opcional
}
```

**Response**: `ContentPlan` con items, estimated_cost, reference_queries

#### WebSocket `/api/v1/ws/chat/{session_id}`
Chat en tiempo real con contexto de conversación.

**Mensajes soportados**:
- `{"type": "ping", "data": {}}` → `{"type": "pong"}`
- `{"type": "chat", "data": {"content": "...", "brand": "..."}}` → Stream de respuesta
- `{"type": "approve_plan", "data": {"plan_id": "...", "item_ids": [...]}}` → Confirmación

### Seguridad (`security.py`)

#### Validación de Slugs
```python
def validate_slug(slug: str) -> bool:
    # Solo: [a-z0-9-], 1-64 chars
    # Bloquea: .., /, \, uppercase
    # Anti path-traversal
```

#### Rate Limiting
```python
class RateLimiter:
    # 120 requests/minute por IP
    # Tracking en memoria (sliding window)
    # Header X-Forwarded-For aware
```

#### API Key (Opcional)
```python
# .env
API_KEY=your-secret-key

# Request
X-API-Key: your-secret-key
```

### WebSocket Manager (`websocket/manager.py`)

```python
class ConnectionManager:
    # Múltiples conexiones por session_id
    # Auto-cleanup de conexiones muertas
    # Broadcast y unicast
    
    async def send_chat_message(session_id, role, content, plan)
    async def send_progress(session_id, plan_id, item_id, status, progress)
    async def send_error(session_id, error)
```

## Frontend UI (`ui/`)

### Stack
- **Next.js 16** - App Router con React 19
- **Tailwind 4** - CSS con variables CSS
- **shadcn/ui** - Componentes base (new-york style)
- **Zustand** - Estado global con persistencia
- **Bun** - Package manager y runtime

### Arquitectura
```
ui/src/
├── app/              # Next.js pages
│   ├── page.tsx      # Home con chat
│   └── layout.tsx
├── components/
│   ├── chat/         # ChatWindow, MessageList, MessageInput
│   └── ui/           # shadcn components
├── hooks/
│   └── useWebSocket.ts  # WebSocket con auto-reconnect
├── stores/
│   └── chatStore.ts     # Zustand store
└── lib/
    ├── api.ts           # REST client
    └── utils.ts
```

### Hook useWebSocket

```typescript
const { isConnected, sendChat, lastMessage } = useWebSocket({
  sessionId: 'unique-id',
  onMessage: (msg) => { /* handle */ },
  autoReconnect: true,
  reconnectInterval: 3000
});
```

**Features**:
- Auto-reconexión con backoff
- Ping/pong keep-alive (30s)
- Manejo de desconexiones
- Ref pattern para evitar closures obsoletas

## Testing (`tests/`)

### Cobertura Actual: 36 tests

```
tests/
├── test_api.py         # 10 tests - Health, Brands, Plans, Chat
├── test_security.py    # 13 tests - Validación, Rate limiting
└── test_strategist.py  # 13 tests - KnowledgeBase, Intent detection
```

### Ejecutar Tests

```bash
# Todos los tests
pytest tests/ -v

# Solo seguridad
pytest tests/test_security.py -v

# Con coverage
pytest tests/ --cov=src/cm_agents --cov-report=html
```

### Fixtures Disponibles

```python
@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""

@pytest.fixture
def brands_dir(tmp_path) -> Path:
    """Temporary brands dir with test brand."""

@pytest.fixture
def knowledge_dir(tmp_path) -> Path:
    """Temporary knowledge dir with minimal styles."""
```

## Variables de Entorno

```bash
# AI API Keys (requeridas)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Server
ENVIRONMENT=development|production
HOST=0.0.0.0
PORT=8000

# Security (opcional)
API_KEY=your-secret-key      # Si está set, requiere X-API-Key header
CORS_ORIGINS=["http://localhost:3000"]  # JSON array

# Paths
BRANDS_DIR=brands
OUTPUTS_DIR=outputs
KNOWLEDGE_DIR=knowledge
```

## Templates

- `templates/brand_template.json` - Template para crear nuevas marcas con `cm brand-create`
- `templates/campaign_template.json` - Template para crear campañas con `cm campaign-create`

## Comandos de Desarrollo

```bash
# Backend
pip install -e ".[dev]"     # Instalar con deps de desarrollo
ruff check src/ --fix       # Lint y auto-fix
ruff format src/            # Format código
pytest tests/ -v            # Tests
cm serve --reload           # Dev server con hot-reload

# Frontend
cd ui
bun install                 # Instalar deps
bun dev                     # Dev server
bun run lint                # ESLint
bun run build               # Production build
```
