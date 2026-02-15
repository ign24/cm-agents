/**
 * API client for CM Agents backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Brand {
  name: string;
  slug: string;
  industry: string | null;
  logo_url: string | null;
  campaigns_count: number;
}

export interface Campaign {
  name: string;
  slug: string;
  brand: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  progress: [number, number];
}

export interface ContentPlanItem {
  id: string;
  product: string;
  size: "feed" | "story";
  style: string;
  copy_suggestion: string;
  reference_query: string;
  reference_urls: string[];
  status: "draft" | "approved" | "generated";
}

export interface ContentPlan {
  id: string;
  brand: string;
  intent: {
    objective: string;
    product: string | null;
    occasion: string | null;
    tone: string[];
    constraints: string[];
  };
  items: ContentPlanItem[];
  created_at: string;
  approved_at: string | null;
  estimated_cost: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health() {
    return this.fetch<{ status: string; version: string }>("/health");
  }

  // Brands
  async getBrands(options?: RequestInit) {
    return this.fetch<{ brands: Brand[]; total: number }>(
      "/api/v1/brands",
      options
    );
  }

  async getBrand(slug: string) {
    return this.fetch<Brand>(`/api/v1/brands/${slug}`);
  }

  // Campaigns
  async getCampaigns() {
    return this.fetch<{ campaigns: Campaign[]; total: number }>(
      "/api/v1/campaigns"
    );
  }

  async getBrandCampaigns(brandSlug: string) {
    return this.fetch<{ campaigns: Campaign[]; total: number }>(
      `/api/v1/brands/${brandSlug}/campaigns`
    );
  }

  // Plans
  async getPlans(brand?: string) {
    const query = brand ? `?brand=${brand}` : "";
    return this.fetch<ContentPlan[]>(`/api/v1/plans${query}`);
  }

  async getPlan(planId: string) {
    return this.fetch<ContentPlan>(`/api/v1/plans/${planId}`);
  }

  async createPlan(prompt: string, brand: string, campaign?: string) {
    return this.fetch<ContentPlan>("/api/v1/plans", {
      method: "POST",
      body: JSON.stringify({ prompt, brand, campaign }),
    });
  }

  async approvePlan(planId: string, itemIds?: string[]) {
    return this.fetch<ContentPlan>(`/api/v1/plans/${planId}/approve`, {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds || [] }),
    });
  }

  // Chat
  async sendMessage(message: string, brand?: string, images?: string[]) {
    return this.fetch<{
      message: { role: string; content: string };
      plan: ContentPlan | null;
    }>("/api/v1/chat", {
      method: "POST",
      body: JSON.stringify({ message, brand, images: images || [] }),
    });
  }

  // Generation
  async generate(planId: string, itemIds?: string[]) {
    return this.fetch<{
      plan_id: string;
      results: Array<{
        item_id: string;
        success: boolean;
        output_path: string | null;
      }>;
      total_cost: number;
    }>("/api/v1/generate", {
      method: "POST",
      body: JSON.stringify({ plan_id: planId, item_ids: itemIds || [] }),
    });
  }
}

export const api = new ApiClient();
export default api;
