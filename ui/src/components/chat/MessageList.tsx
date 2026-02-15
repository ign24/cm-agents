"use client";

import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/stores/chatStore";
import { Bot, User, AlertCircle } from "lucide-react";

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12 text-center animate-in fade-in duration-500">
        <Bot className="w-12 h-12 text-muted-foreground mb-4 animate-in zoom-in duration-500 delay-100" />
        <h3 className="font-medium animate-in slide-in-from-bottom-4 duration-500 delay-200">
          ¡Hola! Soy tu asistente de CM Agents
        </h3>
        <p className="text-sm text-muted-foreground mt-2 max-w-md animate-in slide-in-from-bottom-4 duration-500 delay-300">
          Puedo ayudarte a planificar y crear contenido para redes sociales.
          Contame qué necesitás.
        </p>
        <div className="mt-6 text-left text-sm text-muted-foreground animate-in slide-in-from-bottom-4 duration-500 delay-400">
          <p className="font-medium mb-2">Ejemplos de lo que puedo hacer:</p>
          <ul className="space-y-1">
            <li className="transition-colors hover:text-foreground">
              • &ldquo;Crear posts para el día del padre&rdquo;
            </li>
            <li className="transition-colors hover:text-foreground">
              • &ldquo;Promoción de hamburguesas 2x1&rdquo;
            </li>
            <li className="transition-colors hover:text-foreground">
              • &ldquo;Contenido para Black Friday&rdquo;
            </li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((message, index) => (
        <MessageBubble 
          key={message.id} 
          message={message} 
          isLatest={index === messages.length - 1}
        />
      ))}
    </div>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
  isLatest?: boolean;
}

function MessageBubble({ message, isLatest = false }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div
      className={cn(
        "flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300",
        {
          "flex-row-reverse": isUser,
        }
      )}
      style={{ animationDelay: isLatest ? "0ms" : undefined }}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-200",
          {
            "bg-primary text-primary-foreground": isUser,
            "bg-muted": !isUser && !isSystem,
            "bg-destructive/10": isSystem,
          }
        )}
        aria-label={isUser ? "Usuario" : isSystem ? "Sistema" : "Asistente"}
      >
        {isUser ? (
          <User className="w-4 h-4" aria-hidden="true" />
        ) : isSystem ? (
          <AlertCircle className="w-4 h-4 text-destructive" aria-hidden="true" />
        ) : (
          <Bot className="w-4 h-4" aria-hidden="true" />
        )}
      </div>

      {/* Content */}
      <div
        className={cn("flex flex-col max-w-[80%] sm:max-w-[75%]", {
          "items-end": isUser,
        })}
      >
        <div
          className={cn(
            "rounded-lg px-4 py-2.5 transition-all duration-200",
            {
              "bg-primary text-primary-foreground": isUser,
              "bg-muted": !isUser && !isSystem,
              "bg-destructive/10 text-destructive": isSystem,
            }
          )}
        >
          <p className="whitespace-pre-wrap break-words leading-relaxed">
            {message.content}
          </p>

          {/* Show images if present */}
          {message.images && message.images.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {message.images.map((img, i) => (
                <div
                  key={i}
                  className="relative group rounded-lg overflow-hidden border border-border/50 hover:border-border transition-colors"
                >
                  <img
                    src={img}
                    alt={`Imagen de referencia ${i + 1}`}
                    className="max-w-[200px] max-h-[200px] object-cover"
                    loading="lazy"
                  />
                </div>
              ))}
            </div>
          )}

          {/* Show plan preview if present */}
          {message.plan && (
            <div className="mt-3 p-3 bg-background/50 rounded-md text-sm border border-border/50 hover:bg-background/70 transition-colors cursor-pointer">
              <p className="font-medium flex items-center gap-2">
                <span>📋</span>
                Plan creado
              </p>
              <p className="text-xs opacity-70 mt-1">
                Click para ver detalles
              </p>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span 
          className="text-xs text-muted-foreground mt-1.5 px-1"
          aria-label={`Enviado a las ${new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}`}
        >
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}

export default MessageList;
