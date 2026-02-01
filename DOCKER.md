# Docker Deployment Guide

Esta guía explica cómo levantar CM-Agents usando Docker y Docker Compose.

## 📋 Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- Windows 10/11 con WSL2, macOS, o Linux

## 🚀 Inicio Rápido

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd cm-agents
```

### 2. Configurar variables de entorno (opcional)

Crea un archivo `.env` en la raíz del proyecto:

```bash
# API Keys (opcional para demo mode)
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Security (opcional)
API_KEY=your_secret_api_key
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

> **Nota**: Para pruebas locales, las API keys NO son necesarias. El sistema usa un generador de demo que crea imágenes de placeholder.

### 3. Levantar los contenedores

```bash
docker compose up --build
```

Esto construirá y levantará:
- **Backend** (FastAPI) en `http://localhost:8000`
- **Frontend** (Next.js) en `http://localhost:3000`

### 4. Verificar que funciona

En otra terminal, ejecuta:

```bash
python test_docker.py
```

Deberías ver:

```
✅ ALL TESTS PASSED!
```

## 📦 Servicios

### Backend (Puerto 8000)

- **API REST**: `http://localhost:8000/api/v1`
- **Documentación**: `http://localhost:8000/docs`
- **Health check**: `http://localhost:8000/health`
- **WebSocket**: `ws://localhost:8000/ws`

### Frontend (Puerto 3001 si 3000 ocupado)

- **UI Web**: `http://localhost:3001` (o `:3000` si está libre)
- **Runtime**: Bun (`oven/bun:1-alpine`); instala deps con `bun install`, build con `bun run build`
- **Nota**: El compose mapea `3001:3000` si tenés `bun dev` u otro proceso en 3000

## 🛠️ Comandos Útiles

### Ver logs

```bash
# Todos los servicios
docker compose logs -f

# Solo backend
docker compose logs -f backend

# Solo frontend
docker compose logs -f frontend
```

### Ver estado de contenedores

```bash
docker compose ps
```

### Reiniciar servicios

```bash
# Todos
docker compose restart

# Solo un servicio
docker compose restart backend
```

### Detener contenedores

```bash
# Detener sin eliminar
docker compose stop

# Detener y eliminar
docker compose down

# Eliminar todo (incluyendo volúmenes)
docker compose down -v
```

### Reconstruir imágenes

```bash
# Reconstruir todo
docker compose up --build

# Reconstruir sin caché
docker compose build --no-cache
```

## 📁 Volúmenes

Los siguientes directorios se montan desde el host:

- `./brands` → `/app/brands` (read-only) - Configuración de marcas
- `./knowledge` → `/app/knowledge` (read-only) - Base de conocimiento
- `./outputs` → `/app/outputs` - Planes y generaciones
- `./.env` → `/app/.env` (read-only) - Variables de entorno

## 🐛 Troubleshooting

### Backend no inicia

```bash
# Ver logs completos
docker compose logs backend

# Verificar que .env existe (si usas API keys)
ls -la .env

# Verificar que las carpetas existen
ls -la brands/ knowledge/ outputs/
```

### Frontend no se conecta al backend

1. Verifica que el backend esté healthy:
   ```bash
   curl http://localhost:8000/health
   ```

2. Revisa las variables de entorno del frontend en `docker-compose.yml`:
   ```yaml
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_WS_URL=ws://localhost:8000
   ```

### Docker Desktop no inicia

- **Windows**: Asegúrate de que WSL2 esté instalado y configurado
- **macOS**: Verifica que Docker Desktop tenga permisos
- Reinicia Docker Desktop desde el menú

### Puerto ocupado

Si los puertos 3000 u 8000 están ocupados (p. ej. `bun dev` en 3000):

- El compose ya usa **3001** para el frontend cuando 3000 está ocupado. Abrí `http://localhost:3001`.
- Para cambiar manualmente, edita `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Backend en 8001
  - "3001:3000"  # Frontend en 3001 (o 3002 si 3001 también ocupado)
```

## 🔧 Desarrollo con Docker

### Hot reload (desarrollo local sin Docker)

Para desarrollo es más rápido correr sin Docker:

```bash
# Backend
cm serve

# Frontend (en otra terminal)
cd ui
bun dev
```

### Ejecutar comandos dentro del contenedor

```bash
# Backend shell
docker compose exec backend bash

# Ver estructura de archivos
docker compose exec backend ls -la

# Ejecutar comando Python
docker compose exec backend python -c "print('Hello')"
```

## 📊 Monitoreo

### Health checks

Docker Compose incluye health checks automáticos:

```bash
# Ver estado de salud
docker compose ps

# Formato:
# STATUS = Up X seconds (healthy)
```

### Recursos

Ver uso de recursos:

```bash
docker stats cm-agents-backend cm-agents-frontend
```

## 🚢 Producción

Para producción, considera:

1. **Variables de entorno**: Usa secrets manager (no `.env` en el repo)
2. **Reverse proxy**: Nginx o Traefik delante de los contenedores
3. **SSL**: Certificados HTTPS con Let's Encrypt
4. **Logging**: Integrar con sistema centralizado (ELK, Loki)
5. **Monitoreo**: Prometheus + Grafana
6. **Backups**: Automatizar backup de `/outputs`
7. **Scaling**: Usar Docker Swarm o Kubernetes

## 📚 Más información

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Next.js Docker Guide](https://nextjs.org/docs/deployment#docker-image)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/docker/)
