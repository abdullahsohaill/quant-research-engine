/**
 * ChatInput — Query input component
 */

import { useState, type FormEvent, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSubmit, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSubmit(value.trim());
      setValue('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  };

  return (
    <div className="input-container">
      <form className="input-wrapper" onSubmit={handleSubmit}>
        <div className="input-field-container">
          <input
            id="analysis-input"
            type="text"
            className="input-field"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || 'Ask about any stock...'}
            disabled={disabled}
            autoComplete="off"
          />
          <button
            id="submit-analysis"
            type="submit"
            className="submit-button"
            disabled={disabled || !value.trim()}
          >
            <span>⚡</span>
            Analyze
          </button>
        </div>
        <div className="input-hint">
          Press Enter to analyze · Powered by Gemini + MCP
        </div>
      </form>
    </div>
  );
}
