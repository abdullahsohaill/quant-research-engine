/**
 * Quant Research Engine — Main App Component
 *
 * Root component that manages the full application state:
 * idle → loading → complete/error
 */

import { useState, useCallback } from 'react';
import './App.css';
import { analyzeStock } from './api/client';
import type { AnalyzeResponse, AnalysisState } from './types';
import Header from './components/Header';
import ChatInput from './components/ChatInput';
import LoadingState from './components/LoadingState';
import AnalysisReport from './components/AnalysisReport';

const EXAMPLE_QUERIES = [
  'Analyze NVIDIA stock',
  'Compare AAPL vs MSFT',
  'Buy/sell brief on AMD',
  'Best semiconductor stocks by valuation',
  'Compare GOOGL vs META Q2 2025',
];

function App() {
  const [state, setState] = useState<AnalysisState>('idle');
  const [response, setResponse] = useState<AnalyzeResponse | null>(null);
  const [currentQuery, setCurrentQuery] = useState('');
  const [statusMessages, setStatusMessages] = useState<string[]>([]);

  const handleSubmit = useCallback(async (query: string) => {
    setState('loading');
    setCurrentQuery(query);
    setResponse(null);
    setStatusMessages(['Validating input...', 'Connecting to AI engine...']);

    try {
      // Use sync endpoint for simplicity
      const result = await analyzeStock({
        query,
        include_critique: true,
      });

      setResponse(result);
      setState(result.success ? 'complete' : 'error');
    } catch (err) {
      setResponse({
        success: false,
        error: err instanceof Error ? err.message : 'An unexpected error occurred',
        warnings: [],
      });
      setState('error');
    }
  }, []);

  const handleNewAnalysis = useCallback(() => {
    setState('idle');
    setResponse(null);
    setCurrentQuery('');
    setStatusMessages([]);
  }, []);

  const handleExampleClick = useCallback((query: string) => {
    handleSubmit(query);
  }, [handleSubmit]);

  return (
    <div className="app">
      <Header />

      <main className="main-content">
        {state === 'idle' && (
          <div className="hero animate-fade-in-up">
            <div className="hero-icon">📊</div>
            <h1>Autonomous Financial Analyst</h1>
            <p>
              Ask any question about stocks, markets, or investments. The AI engine
              will fetch real-time data, run SQL analytics, and generate a structured
              investment memo — fully automated.
            </p>
            <div className="example-queries">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  className="example-chip"
                  onClick={() => handleExampleClick(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {state === 'loading' && (
          <LoadingState
            query={currentQuery}
            statusMessages={statusMessages}
          />
        )}

        {(state === 'complete' || state === 'error') && response && (
          <AnalysisReport
            response={response}
            query={currentQuery}
            onNewAnalysis={handleNewAnalysis}
          />
        )}
      </main>

      {(state !== 'loading' && state !== 'streaming') && (
        <ChatInput
          onSubmit={handleSubmit}
          disabled={false}
          placeholder={
            state === 'idle'
              ? 'Ask about any stock... e.g., "Analyze NVIDIA vs AMD"'
              : 'Ask another question...'
          }
        />
      )}
    </div>
  );
}

export default App;
