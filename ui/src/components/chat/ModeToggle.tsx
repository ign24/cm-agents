"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useChatStore, WorkflowMode } from "@/stores/chatStore";
import { FileText, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export function ModeToggle() {
  const { workflowMode, toggleWorkflowMode } = useChatStore();

  // Handle Tab key shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only trigger if not typing in an input/textarea
      if (
        e.key === "Tab" &&
        !(
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement
        )
      ) {
        e.preventDefault();
        toggleWorkflowMode();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleWorkflowMode]);

  const modeConfig: Record<
    WorkflowMode,
    { label: string; icon: React.ReactNode; description: string; color: string }
  > = {
    plan: {
      label: "PLAN",
      icon: <FileText className="w-3.5 h-3.5" aria-hidden="true" />,
      description: "Planificación de contenido",
      color: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    },
    build: {
      label: "BUILD",
      icon: <Sparkles className="w-3.5 h-3.5" aria-hidden="true" />,
      description: "Generación de imágenes",
      color: "bg-emerald-500/10 text-emerald-700 border-emerald-500/20",
    },
  };

  const currentMode = modeConfig[workflowMode];

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggleWorkflowMode}
      className={cn(
        "relative flex items-center gap-2 h-11 px-3 transition-all duration-200 hover:scale-105",
        currentMode.color
      )}
      title={`Modo: ${currentMode.description} (Presiona Tab para cambiar)`}
      aria-label={`Cambiar modo. Actual: ${currentMode.description}`}
    >
      {currentMode.icon}
      <span className="font-semibold text-xs">{currentMode.label}</span>
      <Badge
        variant="secondary"
        className="ml-1 h-4 px-1.5 text-[10px] font-mono bg-muted/50"
      >
        Tab
      </Badge>
    </Button>
  );
}

export default ModeToggle;
