/**
 * Quant Research Engine — TypeScript Types
 *
 * Shared type definitions for the frontend application.
 */

export interface AnalyzeRequest {
  query: string;
  include_critique?: boolean;
}

export interface ToolCallInfo {
  tool: string;
  args: Record<string, unknown>;
  iteration: number;
  status: string;
  result_length?: number;
  error?: string;
}

export interface AnalysisMetadata {
  query: string;
  started_at?: string;
  completed_at?: string;
  elapsed_seconds?: number;
  iterations: number;
  tool_calls: ToolCallInfo[];
  model: string;
}

export interface AnalyzeResponse {
  success: boolean;
  report?: string;
  critique?: string;
  metadata?: AnalysisMetadata;
  warnings: string[];
  error?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  services: Record<string, unknown>;
  timestamp: string;
}

export interface StreamEvent {
  type: 'status' | 'tool_call' | 'report' | 'critique' | 'error' | 'metadata';
  data: string | Record<string, unknown>;
}

export type AnalysisState = 'idle' | 'loading' | 'streaming' | 'complete' | 'error';
