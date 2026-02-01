# Configuración de Context7 MCP para Cursor

Context7 proporciona documentación actualizada y versionada directamente en Cursor, evitando que los LLMs generen código desactualizado.

## Opción 1: Remote Server (Recomendado)

Agrega esta configuración a tu archivo de configuración MCP de Cursor.

**Ubicación del archivo:**
- Windows: `%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- O en: `~/.cursor/mcp.json` (si existe)

**Configuración:**

```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "CONTEXT7_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

**Pasos:**
1. Obtén tu API key de [Context7](https://context7.com)
2. Reemplaza `YOUR_API_KEY` con tu clave
3. Guarda el archivo
4. Reinicia Cursor

## Opción 2: Local Server (Sin API Key)

Si prefieres ejecutar el servidor localmente:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

**Requisitos:**
- Node.js 18+ instalado
- No requiere API key

## Uso

Una vez configurado, simplemente agrega `use context7` a tus prompts en Cursor:

```
Crea un middleware de Next.js que verifique un JWT válido en cookies. use context7
```

```
Configura un script de Cloudflare Worker para cachear respuestas JSON de API. use context7
```

Context7 detectará automáticamente la librería que mencionas, obtendrá la documentación más reciente y la inyectará en el contexto del LLM.

## Librerías Soportadas

Context7 soporta documentación actualizada de:
- Next.js
- React
- Tailwind CSS
- shadcn/ui
- FastAPI
- Pydantic
- Supabase
- PyTorch
- Ultralytics
- Y muchas más...

## Verificación

Para verificar que está funcionando:
1. Abre Cursor
2. Escribe un prompt con `use context7`
3. El agente debería usar documentación actualizada de la librería mencionada

## Referencias

- [Documentación oficial de Context7](https://context7.com/docs)
- [Guía de Cursor MCP](https://context7.com/docs/clients/cursor)
- [Blog de Upstash sobre Context7](https://upstash.com/blog/context7-mcp)
