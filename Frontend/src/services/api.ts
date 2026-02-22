import { ChatResponse, FundSearchResponse, FundDetail } from "../types";

const BASE_URL = "/api/v1";

export interface UserProfile {
  name?: string;
  age?: number;
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  investment_horizon: "short_term" | "medium_term" | "long_term";
  investment_goals: string[];
  monthly_investment_capacity?: number;
}

export interface UserProfileResponse extends UserProfile {
  user_id: string;
  recommended_categories: string[];
  created_at: string;
  updated_at: string;
}

export const api = {
  async chat(message: string, sessionId: string | null, userProfile?: UserProfile): Promise<ChatResponse> {
    console.log("[API] Sending chat request:", { message, sessionId, userProfile });
    console.log("[API] URL:", `${BASE_URL}/chat`);
    
    const body: any = { message, session_id: sessionId };
    if (userProfile) {
      body.user_profile = userProfile;
    }
    
    const response = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    
    console.log("[API] Response status:", response.status);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Chat failed" }));
      console.error("[API] Error:", error);
      throw new Error(error.detail || "Chat failed");
    }
    
    const data = await response.json();
    console.log("[API] Response data:", data);
    return data;
  },

  async createProfile(profile: UserProfile): Promise<UserProfileResponse> {
    const response = await fetch(`${BASE_URL}/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!response.ok) throw new Error("Failed to create profile");
    return response.json();
  },

  async getProfile(userId: string): Promise<UserProfileResponse> {
    const response = await fetch(`${BASE_URL}/profile/${userId}`);
    if (!response.ok) throw new Error("Profile not found");
    return response.json();
  },

  async updateProfile(userId: string, profile: UserProfile): Promise<UserProfileResponse> {
    const response = await fetch(`${BASE_URL}/profile/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!response.ok) throw new Error("Failed to update profile");
    return response.json();
  },

  async getProfileRecommendations(userId: string): Promise<any> {
    const response = await fetch(`${BASE_URL}/profile/${userId}/recommendations`);
    if (!response.ok) throw new Error("Failed to get recommendations");
    return response.json();
  },

  async searchFunds(query: string, limit: number = 20): Promise<FundSearchResponse> {
    const response = await fetch(
      `${BASE_URL}/funds/search?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    if (!response.ok) throw new Error("Search failed");
    return response.json();
  },

  async getFundDetail(schemeCode: string): Promise<FundDetail> {
    const response = await fetch(`${BASE_URL}/funds/${schemeCode}`);
    if (!response.ok) {
      if (response.status === 404) throw new Error("Fund not found");
      throw new Error("Failed to fetch fund details");
    }
    return response.json();
  },

  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${BASE_URL}/health`);
    if (!response.ok) throw new Error("Health check failed");
    return response.json();
  },

  async getMarketTicker(): Promise<{
    items: Array<{
      name: string;
      value: string;
      change: string;
      up: boolean;
      type: string;
    }>;
    updated_at: string;
  }> {
    const response = await fetch(`${BASE_URL}/market/ticker`);
    if (!response.ok) throw new Error("Failed to fetch market ticker");
    return response.json();
  },

  async getMarketOverview(): Promise<{
    indices: Record<string, { value: number; change_percent: number }>;
    updated_at: string;
  }> {
    const response = await fetch(`${BASE_URL}/market/overview`);
    if (!response.ok) throw new Error("Failed to fetch market overview");
    return response.json();
  },

  async resetApplication(): Promise<{ status: string; message: string; timestamp: string }> {
    const response = await fetch(`${BASE_URL}/reset`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Failed to reset application");
    return response.json();
  },

  async getAIRecommendations(preferences: {
    goal: string;
    risk_tolerance: string;
    investment_horizon: string;
    monthly_amount: number;
  }): Promise<{
    categories: string[];
    allocation: Record<string, number>;
    funds: Array<{
      scheme_code?: string;
      scheme_name?: string;
      nav?: number;
      category?: string;
      fund_house?: string;
    }>;
    ai_insight: string;
    reasoning: string;
  }> {
    const response = await fetch(`${BASE_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(preferences),
    });
    if (!response.ok) throw new Error("Failed to get AI recommendations");
    return response.json();
  },
};

export async function* streamChatFetch(message: string, sessionId: string | null) {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) throw new Error("Stream failed");

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  if (!reader) return;

  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        try {
          yield JSON.parse(data);
        } catch (e) {
          console.error("Error parsing SSE data", e);
        }
      }
    }
  }
}
