"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  images?: string[];
  timestamp: Date;
  plan?: Record<string, unknown>;
}

export type WorkflowMode = "plan" | "build";

interface ChatState {
  // State
  messages: ChatMessage[];
  sessionId: string;
  selectedBrand: string | null;
  selectedCampaign: string | null;
  isLoading: boolean;
  workflowMode: WorkflowMode;

  // Actions
  addMessage: (message: Omit<ChatMessage, "id" | "timestamp">) => void;
  clearMessages: () => void;
  setSessionId: (id: string) => void;
  setSelectedBrand: (brand: string | null) => void;
  setSelectedCampaign: (campaign: string | null) => void;
  setIsLoading: (loading: boolean) => void;
  setWorkflowMode: (mode: WorkflowMode) => void;
  toggleWorkflowMode: () => void;
}

// Generate a unique session ID
const generateSessionId = () => {
  return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      sessionId: generateSessionId(),
      selectedBrand: null,
      selectedCampaign: null,
      isLoading: false,
      workflowMode: "plan" as WorkflowMode,

      addMessage: (message) => {
        const newMessage: ChatMessage = {
          ...message,
          id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date(),
        };
        set((state) => ({
          messages: [...state.messages, newMessage],
        }));
      },

      clearMessages: () => {
        set({ messages: [] });
      },

      setSessionId: (id) => {
        set({ sessionId: id, messages: [] });
      },

      setSelectedBrand: (brand) => {
        set({ selectedBrand: brand });
      },

      setSelectedCampaign: (campaign) => {
        set({ selectedCampaign: campaign });
      },

      setIsLoading: (loading) => {
        set({ isLoading: loading });
      },

      setWorkflowMode: (mode) => {
        set({ workflowMode: mode });
      },

      toggleWorkflowMode: () => {
        set((state) => ({
          workflowMode: state.workflowMode === "plan" ? "build" : "plan",
        }));
      },
    }),
    {
      name: "cm-agents-chat",
      partialize: (state) => ({
        sessionId: state.sessionId,
        selectedBrand: state.selectedBrand,
        selectedCampaign: state.selectedCampaign,
        workflowMode: state.workflowMode,
      }),
    }
  )
);

export default useChatStore;
