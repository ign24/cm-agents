# CM Agents

Sistema de orquestación de agentes AI para automatizar la creación de contenido visual para redes sociales. Genera imágenes profesionales de productos con calidad de diseño de agencia, tomando inspiración de Pinterest y aplicando best practices de diseño 2026.

**Versión:** 2.1.0 | **Tests:** 116 pasando | **Seguridad:** Validación + Rate limiting

> **Estado:** MVP en desarrollo activo. No recomendado para producción sin hardening adicional (ver [REVIEW_SENIOR_ENGINEER.md](REVIEW_SENIOR_ENGINEER.md) para detalles).

## 🎯 Qué hace

1. **Chat Inteligente**: Habla en lenguaje natural para crear planes de contenido
2. **Analiza** imágenes de referencia de Pinterest (estilo visual)
3. **Extrae** detalles exactos de productos reales (para réplica perfecta)
4. **Diseña** prompts profesionales aplicando tendencias 2026 y tu identidad de marca
5. **Genera** imágenes con producto, texto integrado, logo y estilo de la referencia

**Resultado**: Imágenes listas para Instagram con consistencia de marca, perfectas para campañas publicitarias.

### ✨ Nuevo en v2.1

- ✅ **API REST + WebSocket** funcional con chat en tiempo real
- ✅ **Frontend Next.js 16** con UI moderna y responsive
- ✅ **StrategistAgent conectado** - Crea planes desde lenguaje natural
- ✅ **116 tests automatizados** - API, seguridad, y lógica de negocio
- ✅ **Seguridad básica** - Validación de inputs, rate limiting, CORS
- ✅ **Type-safe** - TypeScript + Pydantic con validaciones

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GENERATION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  EXTRACTOR   │───▶│   DESIGNER   │───▶│  GENERATOR   │                  │
│  │              │    │              │    │              │                  │
│  │ Claude Vision│    │ Claude 4.5   │    │ GPT-Image-1  │                  │
│  │              │    │              │    │              │                  │
│  │ • Estilo     │    │ • Best       │    │ • Genera     │                  │
│  │ • Layout     │    │   Practices  │    │   imagen     │                  │
│  │ • Colores    │    │   2026       │    │   final      │                  │
│  │ • Producto   │    │ • Prompts    │    │ • Texto      │                  │
│  │   (réplica)  │    │   optimizados│    │   integrado  │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                    KNOWLEDGE BASE                           │           │
│  │  knowledge/design_2026.json                                 │           │
│  │  • 17 estilos de diseño (dinámicos)                        │           │
│  │  • Guidelines por categoría (food, pharmacy, wine...)      │           │
│  └─────────────────────────────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Instalación

### Backend

```bash
# 1. Clonar e instalar
git clone <repo>
cd cm-agents
pip install -e .

# 2. Configurar API keys
cp .env.example .env
# Editar .env:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# API_KEY=your-secret-key  # Opcional: Requiere X-API-Key header

# 3. Verificar
cm status

# 4. Iniciar servidor API
cm serve --port 8000 --reload
```

### Frontend

```bash
cd ui
bun install
bun dev  # http://localhost:3000
```

### Tests

```bash
# Backend
pytest tests/ -v

# Frontend
cd ui
bun run lint
bun run build
```

## 📝 Uso

### Generación básica

```bash
# Con imagen del producto real (RECOMENDADO)
cm generate sprite resto-mario references/estilo.jpg -p references/sprite.webp

# Con estilo específico
cm generate sprite resto-mario ref.jpg -p producto.webp --style minimal_clean

# Múltiples tamaños (feed + story)
cm generate sprite resto-mario ref.jpg -p producto.webp -s feed -s story

# Asociar a una campaña
cm generate sprite resto-mario ref.jpg -p producto.webp --campaign promo-verano
```

### Gestión de Marcas

```bash
# Crear nueva marca (wizard interactivo)
cm brand-create mi-tienda

# Ver todas las marcas
cm brand-list

# Ver configuración completa de una marca
cm brand-show resto-mario
```

### Gestión de Campañas

```bash
# Crear campaña
cm campaign-create resto-mario promo-verano-2026

# Listar campañas de una marca
cm campaign-list resto-mario

# Ver detalles de campaña
cm campaign-show resto-mario promo-verano-2026
```

### Campaña por referencias (3 referencias)

Flujo con **1 producto + 1 escena + 1 fuente**: genera fondo y producto en **una sola llamada** (replica exacta) y agrega texto por día usando la referencia de tipografía. Por defecto 3 días (teaser, main_offer, last_chance).

```bash
cm campaign-refs resto-mario --product foto-producto.jpg --scene escena-fondo.png --font tipografia-muestra.png
cm campaign-refs resto-mario -p producto.png -s escena.png -f fuente.png --days 3 --price "$2.75" --output outputs/mi-campana
```

### Estilos disponibles

```bash
# Ver todos los estilos
cm styles

# Estilos por categoría
cm styles pharmacy
cm styles wine_spirits
cm styles food
```

**17 estilos incluidos**: minimal_clean, lifestyle_warm, editorial_magazine, authentic_imperfect, biophilic_nature, pharmacy_clinical, pharmacy_wellness, wine_elegant, wine_casual, medical_professional, luxury_premium, tech_futuristic, artisan_craft, eco_sustainable, pet_friendly, kids_playful, sports_dynamic

### Otros comandos

```bash
cm product-list resto-mario # Listar productos
cm status                   # Estado del sistema
cm estimate                 # Estimar costos
```

## 📁 Estructura

```
cm-agents/
├── brands/                      # Configuraciones de marcas
│   └── resto-mario/
│       ├── brand.json           # Identidad de marca completa
│       ├── assets/              # Logos e iconos
│       │   ├── logo.png
│       │   └── logo-white.png
│       ├── fonts/               # Fuentes de la marca
│       ├── references/          # Referencias de estilo
│       └── campaigns/           # Campañas publicitarias
│           └── promo-verano/
│               ├── campaign.json
│               └── outputs/
├── products/                    # Productos por marca
│   └── resto-mario/
│       └── sprite/
│           └── product.json
├── references/                  # Referencias globales
├── knowledge/                   # Base de conocimiento
│   └── design_2026.json         # Estilos y guidelines
├── templates/                   # Templates para crear marcas/campañas
│   ├── brand_template.json
│   └── campaign_template.json
├── outputs/                     # Imágenes generadas (sin campaña)
└── src/cm_agents/
    ├── agents/                  # Los 3 agentes
    ├── models/                  # Modelos (Brand, Product, Campaign)
    ├── pipeline.py              # Orquestación
    └── cli.py                   # CLI
```

## ⚙️ Configuración

### brand.json (Identidad de Marca Completa)
```json
{
  "name": "Restaurante Mario",
  "industry": "food_restaurant",
  "identity": {
    "tagline": "Sabor de casa",
    "voice": ["familiar", "cálido", "cercano"],
    "values": ["calidad", "tradición", "frescura"]
  },
  "assets": {
    "logo": "assets/logo.png",
    "logo_white": "assets/logo-white.png"
  },
  "palette": {
    "primary": "#D32F2F",
    "secondary": "#FFC107",
    "accent": "#4CAF50",
    "gradient": ["#D32F2F", "#FF5252"]
  },
  "style": {
    "mood": ["cálido", "familiar", "apetitoso"],
    "photography_style": "close-up, warm lighting",
    "preferred_design_styles": ["lifestyle_warm", "authentic_imperfect"],
    "avoid": ["cold colors", "clinical look"]
  },
  "text_overlay": {
    "price_badge": { "bg_color": "#D32F2F", "position": "bottom-left" },
    "title": { "position": "top-center" },
    "logo": { "position": "top-right", "size": "small" }
  }
}
```

### campaign.json (Campaña Publicitaria)
```json
{
  "name": "Promo Verano 2026",
  "description": "Campaña de verano con descuentos en bebidas",
  "dates": { "start": "2026-01-15", "end": "2026-02-28" },
  "theme": {
    "style_override": "biophilic_nature",
    "mood": ["fresco", "veraniego"]
  },
  "products": ["sprite", "coca-cola"],
  "hashtags_extra": ["#VeranoMario"]
}
```

### product.json
```json
{
  "name": "Sprite",
  "description": "Refrescante bebida sabor lima-limón",
  "price": "$2.50",
  "category": "beverages"
}
```

## 🎨 Agregar Estilos

Los estilos son **dinámicos** - solo editar `knowledge/design_2026.json`:

```json
{
  "styles": {
    "mi_estilo": {
      "name": "Mi Estilo",
      "description": "...",
      "lighting": "soft_studio",
      "prompt_template": "...",
      "negative_prompt": "..."
    }
  }
}
```

No se requiere modificar código.

## 💰 Costos

| Componente | Costo/imagen |
|------------|--------------|
| Extractor (Claude) | ~$0.003 |
| Designer (Claude) | ~$0.005 |
| Generator (GPT-Image) | ~$0.04 |
| **Total** | **~$0.05** |

## 📔 Documentación

- **[AGENTS.md](AGENTS.md)** - Documentación técnica detallada del sistema de agentes
- **[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)** - Contexto completo del proyecto y decisiones
- **[ui/AGENTS.md](ui/AGENTS.md)** - Guía específica del frontend
- **[tests/](tests/)** - Suite de tests con ejemplos de uso

## 🚀 Features

### Core
- **Multi-marca**: Gestiona múltiples negocios con identidades visuales independientes
- **Campañas**: Organiza contenido en campañas publicitarias con fechas y temas
- **17 estilos de diseño**: Cargados dinámicamente desde knowledge base
- **Assets centralizados**: Logos, iconos y fuentes organizados por marca
- **Logo automático**: Inserta el logo de la marca en las imágenes generadas

### API & UI
- **REST API + WebSocket**: Comunicación en tiempo real con el frontend
- **Chat inteligente**: Crea planes de contenido desde lenguaje natural
- **UI moderna**: Next.js 16 con Tailwind 4 y shadcn/ui
- **Estado persistente**: Conversaciones y preferencias guardadas
- **Auto-reconexión**: WebSocket robusto con manejo de desconexiones

### Seguridad
- **Validación de inputs**: Anti path-traversal y XSS
- **Rate limiting**: 120 requests/minuto
- **API Key opcional**: Protección con header X-API-Key
- **CORS configurable**: Estricto en producción
- **116 tests**: Cobertura de API, seguridad y lógica

## 📄 Licencia

MIT License

---

**CM Agents** - Automatización de diseño para Community Managers con AI 🚀
