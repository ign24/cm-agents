# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

CM Agents UI is a Next.js 16 chat interface for a content management agents system. The UI communicates with a Python backend via WebSocket for real-time chat and REST API for data operations.

## Commands

```bash
# Development
bun dev          # Start dev server at http://localhost:3000

# Build & production
bun run build    # Build for production
bun start        # Run production build

# Linting
bun run lint     # Run ESLint
```

## Tech Stack

- **Framework**: Next.js 16 with App Router (React 19)
- **Package manager**: Bun (see `bun.lock`)
- **State management**: Zustand with persistence middleware
- **Styling**: Tailwind CSS v4 with CSS variables
- **UI components**: shadcn/ui (new-york style) via Radix primitives
- **Icons**: lucide-react

## Architecture

### Directory Structure

```
src/
├── app/              # Next.js App Router pages
├── components/
│   ├── chat/         # Chat feature components (ChatWindow, MessageList, MessageInput)
│   └── ui/           # shadcn/ui primitives
├── hooks/            # Custom React hooks
├── lib/              # Utilities and API client
└── stores/           # Zustand stores
```

### Key Patterns

**WebSocket Communication**: The chat uses WebSocket for real-time messaging. See `src/hooks/useWebSocket.ts` for the connection handling with auto-reconnect and ping/pong keep-alive.

**State Management**: Chat state is managed in `src/stores/chatStore.ts` using Zustand. Session and brand selection are persisted to localStorage.

**API Client**: REST endpoints are accessed via the `ApiClient` class in `src/lib/api.ts`. It handles brands, campaigns, content plans, and generation.

**Path aliases**: Use `@/` to import from `src/` (e.g., `@/components/chat`).

### Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend REST API URL (default: `http://localhost:8000`)
- `NEXT_PUBLIC_WS_URL` - Backend WebSocket URL (default: `ws://localhost:8000`)

### Adding UI Components

Use shadcn/ui CLI to add components:
```bash
bunx shadcn@latest add <component-name>
```

Configuration is in `components.json`.
