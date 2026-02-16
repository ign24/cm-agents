"use client";

import { useCallback, useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play } from "lucide-react";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { ModeToggle } from "./ModeToggle";

export function ChatWindow() {
  const {
    messages,
    sessionId,
    selectedBrand,
    isLoading,
    workflowMode,
    addMessage,
    setIsLoading,
  } = useChatStore();

  const scrollRef = useRef<HTMLDivElement>(null);

  const handleMessage = useCallback(
    (message: { type: string; data: Record<string, unknown> }) => {
      if (message.type === "chat") {
        const data = message.data as {
          role: string;
          content: string;
          plan?: Record<string, unknown>;
        };
        addMessage({
          role: data.role as "user" | "assistant",
          content: data.content,
          plan: data.plan,
        });
        setIsLoading(false);
      } else if (message.type === "error") {
        const data = message.data as { message: string };
        addMessage({
          role: "system",
          content: `Error: ${data.message}`,
        });
        setIsLoading(false);
      } else if (message.type === "mode_changed") {
        // Backend can notify mode changes if needed
        const data = message.data as { mode: string; message?: string };
        if (data.message) {
          addMessage({
            role: "system",
            content: data.message,
          });
        }
      } else if (message.type === "build_started" || message.type === "build_completed") {
        // Show build progress messages
        const data = message.data as { message?: string };
        if (data.message) {
          addMessage({
            role: "system",
            content: data.message,
          });
        }
        if (message.type === "build_started") {
          setIsLoading(true);
        }
        if (message.type === "build_completed") {
          setIsLoading(false);
        }
      }
    },
    [addMessage, setIsLoading]
  );

  const { isConnected, sendChat, sendBuildOrchestrator } = useWebSocket({
    sessionId,
    onMessage: handleMessage,
  });

  const handleSend = useCallback(
    (content: string, images: string[] = []) => {
      // Add user message immediately
      addMessage({
        role: "user",
        content,
        images: images.length > 0 ? images : undefined,
      });

      // Send via WebSocket with workflow mode context
      setIsLoading(true);
      sendChat(content, images, selectedBrand || undefined, workflowMode);
    },
    [addMessage, sendChat, selectedBrand, setIsLoading, workflowMode]
  );

  const handleBuild = useCallback(() => {
    addMessage({
      role: "user",
      content: "/build",
    });
    setIsLoading(true);
    sendBuildOrchestrator(selectedBrand || undefined);
  }, [addMessage, selectedBrand, sendBuildOrchestrator, setIsLoading]);

  // Auto-scroll to bottom on new messages with improved behavior
  useEffect(() => {
    if (scrollRef.current && messages.length > 0) {
      // Small delay to ensure DOM is updated
      const timeoutId = setTimeout(() => {
        scrollRef.current?.scrollIntoView({ 
          behavior: "smooth",
          block: "end"
        });
      }, 100);
      return () => clearTimeout(timeoutId);
    }
  }, [messages]);

  return (
    <Card className="flex flex-col min-h-[400px] flex-1">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-card/50 backdrop-blur-sm">
        <div className="flex items-center gap-3 min-w-0">
          <div className="min-w-0">
            <h2 className="font-semibold text-lg">Chat con CM Agents</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {selectedBrand
                ? `Marca: ${selectedBrand}`
                : "Selecciona una marca para comenzar"}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px] font-medium">
                Orchestrator listo
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                {workflowMode.toUpperCase()}
              </Badge>
            </div>
          </div>
          <ModeToggle />
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={handleBuild}
            disabled={!isConnected || isLoading || !selectedBrand}
            title="Ejecutar build real con el orquestador"
            className="h-11 min-w-11"
            aria-label="Ejecutar build real"
          >
            <Play className="w-3.5 h-3.5 mr-1" aria-hidden="true" />
            Build
          </Button>
          <div className="relative">
            <span
              className={`w-2.5 h-2.5 rounded-full block transition-all duration-300 ${
                isConnected 
                  ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" 
                  : "bg-red-500"
              }`}
              aria-label={isConnected ? "Conectado" : "Desconectado"}
            />
            {isConnected && (
              <span className="absolute inset-0 w-2.5 h-2.5 rounded-full bg-green-500 animate-ping opacity-75" />
            )}
          </div>
          <span className="text-xs text-muted-foreground font-medium">
            {isConnected ? "Conectado" : "Desconectado"}
          </span>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4">
        <div className="min-h-full">
          <MessageList messages={messages} />
          <div ref={scrollRef} className="h-1" aria-hidden="true" />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-4 bg-card/50 backdrop-blur-sm">
        {isLoading && (
          <div
            className="mb-2 flex items-center gap-2 text-xs text-muted-foreground animate-in fade-in slide-in-from-bottom-2"
            role="status"
            aria-live="polite"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            <span>El asistente está escribiendo…</span>
          </div>
        )}
        <MessageInput onSend={handleSend} disabled={!isConnected || isLoading} />
      </div>
    </Card>
  );
}

export default ChatWindow;
