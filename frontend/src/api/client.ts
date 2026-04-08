/**
 * Quant Research Engine — API Client
 *
 * HTTP client for communicating with the FastAPI backend.
 * Supports both synchronous and streaming (SSE) requests.
 */

import type { AnalyzeRequest, AnalyzeResponse, HealthResponse, StreamEvent } from '../types';

const API_BASE = '/api';

/**
 * Submit an analysis query and get the full response.
 */
export async function analyzeStock(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Server error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Submit an analysis query with streaming SSE updates.
 * Yields each event as it arrives.
 */
export async function* analyzeStockStream(
  request: AnalyzeRequest
): AsyncGenerator<StreamEvent> {
  const response = await fetch(`${API_BASE}/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6).trim();
        if (data === '[DONE]') return;

        try {
          const event: StreamEvent = JSON.parse(data);
          yield event;
        } catch {
          // Ignore parse errors for partial chunks
        }
      }
    }
  }
}

/**
 * Check backend health status.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  return response.json();
}

/**
 * Trigger database seeding.
 */
export async function seedDatabase(): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${API_BASE}/seed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  return response.json();
}
