import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface DataPoint {
  metric: string;
  value: string;
  as_of_date: string;
}

export interface Source {
  name: string;
  url: string;
  accessed_at: string;
}

export interface InvestmentResponse {
  explanation: string;
  data_points: DataPoint[];
  sources: Source[];
  risk_disclaimer: string;
  confidence_score?: number;
}

export interface ChatResponse {
  session_id: string;
  response: InvestmentResponse;
  processing_time_ms: number;
  cached: boolean;
}

export interface ChatMessageData {
  id: string;
  role: "user" | "bot";
  content: string | InvestmentResponse;
  timestamp: number;
  isStreaming?: boolean;
}

export interface Fund {
  scheme_code: string;
  scheme_name: string;
  category?: string;
  nav?: number;
  nav_date?: string;
}

export interface FundSearchResponse {
  results: Fund[];
  total: number;
}

export interface FundDetail {
  scheme_code: string;
  scheme_name: string;
  fund_house?: string;
  category?: string;
  nav?: number;
  nav_date?: string;
  returns: Record<string, string>;
  aum?: string;
  expense_ratio?: string;
}
