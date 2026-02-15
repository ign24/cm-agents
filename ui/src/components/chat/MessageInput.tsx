"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Image as ImageIcon, X, Loader2 } from "lucide-react";
import { useChatStore } from "@/stores/chatStore";

interface MessageInputProps {
  onSend: (content: string, images?: string[]) => void;
  disabled?: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [message, setMessage] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { workflowMode } = useChatStore();
  
  const modePlaceholders = {
    plan: "Planificá contenido... (Enter para enviar, Shift+Enter para nueva línea, Tab para cambiar modo)",
    build: "Generá imágenes... (Enter para enviar, Shift+Enter para nueva línea, Tab para cambiar modo)",
  };

  const handleSend = () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage && images.length === 0) return;

    onSend(trimmedMessage, images.length > 0 ? images : undefined);
    setMessage("");
    setImages([]);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        const base64 = event.target?.result as string;
        setImages((prev) => [...prev, base64]);
      };
      reader.readAsDataURL(file);
    });

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeImage = (index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      {/* Image previews */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 p-2 bg-muted/50 rounded-lg border border-border/50 animate-in slide-in-from-bottom-2 duration-200">
          {images.map((img, i) => (
            <div 
              key={i} 
              className="relative group animate-in zoom-in duration-200"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <img
                src={img}
                alt={`Vista previa ${i + 1}`}
                className="w-16 h-16 object-cover rounded-md border border-border/50 transition-transform group-hover:scale-105"
              />
              <button
                onClick={() => removeImage(i)}
                className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-2"
                aria-label={`Eliminar imagen ${i + 1}`}
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="flex gap-2 items-end">
        <div className="flex-1 relative">
          <Textarea
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              // Auto-resize
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled ? "Conectando..." : modePlaceholders[workflowMode]
            }
            disabled={disabled}
            className="min-h-[44px] max-h-[120px] resize-none pr-10 transition-all duration-200 focus:ring-2 focus:ring-ring"
            rows={1}
            aria-label="Mensaje"
            aria-describedby="input-helper"
          />
        </div>

        {/* Image upload button */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleImageUpload}
          className="hidden"
          aria-label="Subir imágenes"
        />
        <Button
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Subir imagen de referencia"
          className="transition-all duration-200 hover:scale-105 focus:ring-2 focus:ring-ring"
          aria-label="Subir imagen"
        >
          <ImageIcon className="w-4 h-4" />
        </Button>

        {/* Send button */}
        <Button 
          onClick={handleSend} 
          disabled={disabled || (!message.trim() && images.length === 0)}
          className="transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 focus:ring-2 focus:ring-ring"
          aria-label="Enviar mensaje"
        >
          {disabled ? (
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="w-4 h-4" aria-hidden="true" />
          )}
        </Button>
      </div>

      {/* Helper text */}
      <p 
        id="input-helper"
        className="text-xs text-muted-foreground animate-in fade-in duration-200"
      >
        Tip: Podés subir imágenes de referencia de Pinterest para inspirar el diseño
      </p>
    </div>
  );
}

export default MessageInput;
