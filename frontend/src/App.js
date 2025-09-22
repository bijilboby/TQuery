import React, { useState } from 'react';
import './App.css';
import TQueryLogo from './logo.png';

function App() {
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredHistory, setFilteredHistory] = useState([]);

  const handleAsk = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setAnswer('');

    try {
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ query })
      });

      if (!res.ok) {
        throw new Error(`API Error: ${res.status}`);
      }

      const data = await res.json();
      setAnswer(data.answer);
      setHistory(prev => [{ question: query, answer: data.answer }, ...prev]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    setQuery('');
    setAnswer('');
    setError('');
    setShowSuggestions(false);
  };

  const handleInputFocus = () => {
    if (history.length > 0) {
      setFilteredHistory(history.slice(0, 5)); // Show last 5 questions
      setShowSuggestions(true);
    }
  };

  const handleInputBlur = () => {
    // Delay hiding to allow clicking on suggestions
    setTimeout(() => setShowSuggestions(false), 200);
  };

  const handleSuggestionClick = (suggestion) => {
    setQuery(suggestion);
    setShowSuggestions(false);
  };

  const handleInputChange = (e) => {
    const value = e.target.value;
    setQuery(value);
    
    if (value.trim() && history.length > 0) {
      const filtered = history
        .filter(item => item.question.toLowerCase().includes(value.toLowerCase()))
        .slice(0, 5);
      setFilteredHistory(filtered);
      setShowSuggestions(filtered.length > 0);
    } else if (value.trim() === '' && history.length > 0) {
      setFilteredHistory(history.slice(0, 5));
      setShowSuggestions(true);
    } else {
      setShowSuggestions(false);
    }
  };

  const handleClearInput = () => {
    setQuery('');
    setShowSuggestions(false);
    setError('');
    setAnswer('');
  };

  return (
    <div className="container">
      <div className="logo-container">
        <img src={TQueryLogo} alt="TQuery Logo" className="logo" />
      </div>
      <p className="subtitle">Ask anything about your t-shirt inventory</p>

      <div className="input-group">
        <div className="input-container">
          <input
            type="text"
            placeholder="e.g., how many levis shirts have with a small size"
            value={query}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
          />
          {query && (
            <button
              type="button"
              className="clear-btn"
              onClick={handleClearInput}
              title="Clear input"
            >
              ✕
            </button>
          )}
          {showSuggestions && filteredHistory.length > 0 && (
            <div className="suggestions-dropdown">
              {filteredHistory.map((item, idx) => (
                <div
                  key={idx}
                  className="suggestion-item"
                  onMouseDown={() => handleSuggestionClick(item.question)}
                >
                  {item.question}
                </div>
              ))}
            </div>
          )}
        </div>
        <button onClick={handleAsk} disabled={loading}>
          {loading ? "Loading..." : "Ask"}
        </button>
      </div>

      {answer && (
        <div className="response success">
          <strong>✅ Answer:</strong>
          <p>{answer}</p>
          <button className="next-btn" onClick={handleNext}>
            Ask Next Question
          </button>
        </div>
      )}

      {error && (
        <div className="response error">
          <strong>❌ Error:</strong> <p>{error}</p>
        </div>
      )}

      {history.length > 0 && (
        <div className="history">
          <h2>🕘 Previous Queries</h2>
          <ul>
            {history.map((item, idx) => (
              <li key={idx}>
                <strong>Q:</strong> {item.question}
                <br />
                <strong>A:</strong> {item.answer}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;
