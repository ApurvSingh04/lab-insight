import React, { useReducer, useCallback, useState } from 'react';
import Papa from 'papaparse';
import LabInput from './components/LabInput';
import ResultsDisplay from './components/ResultsDisplay';

const API_URL = 'http://localhost:8000';

// ── Reducer ─────────────────────────────────────────────────────────────────

const ACTIONS = {
  INIT_RESULTS: 'INIT_RESULTS',
  UPDATE_RESULT: 'UPDATE_RESULT',
  RESET: 'RESET',
};

function labResultsReducer(state, action) {
  switch (action.type) {
    case ACTIONS.INIT_RESULTS:
      return action.payload.map((lab, index) => ({
        id: `${lab.test_name}-${index}`,
        test_name: lab.test_name,
        result: lab.result,
        unit: lab.unit,
        reference_range: lab.reference_range || '',
        min_reference: lab.min_reference ?? null,
        max_reference: lab.max_reference ?? null,
        status: 'pending',
        severity: 'Unknown',
        explanation: '',
        next_steps: '',
      }));

    case ACTIONS.UPDATE_RESULT:
      let updated = false;
      return state.map(item => {
        if (!updated && item.test_name === action.payload.test_name) {
          if (action.payload.status === 'processing_llm' && item.status === 'pending') {
            updated = true;
            return { ...item, ...action.payload };
          }
          if ((action.payload.status === 'done' || action.payload.status === 'error') && (item.status === 'pending' || item.status === 'processing_llm')) {
            updated = true;
            return { ...item, ...action.payload };
          }
        }
        return item;
      });

    case ACTIONS.RESET:
      return [];

    default:
      return state;
  }
}

// ── App ──────────────────────────────────────────────────────────────────────

const App = () => {
  const [results, dispatch] = useReducer(labResultsReducer, []);
  const [isLoading, setIsLoading] = useState(false);
  const [fileName, setFileName] = useState('');
  const [error, setError] = useState(null);
  const [patientContext, setPatientContext] = useState('');

  const handleClear = () => {
    dispatch({ type: ACTIONS.RESET });
    setFileName('');
    setPatientContext('');
    setError(null);
  };

  const parseCSV = (file) =>
    new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (parsed) => {
          const labs = parsed.data
            .map(row => ({
              test_name: row['Test_Name'] || row['Test Name'] || 'Unknown',
              result: row['Result'] || row['Value'] || '0',
              unit: row['Unit'] || '',
              reference_range: row['Reference_Range'] || row['Reference Range'] || null,
              // Pass dataset's numeric bounds and labels directly — no hardcoding needed
              min_reference: row['Min_Reference'] ? parseFloat(row['Min_Reference']) : null,
              max_reference: row['Max_Reference'] ? parseFloat(row['Max_Reference']) : null,
              dataset_status: row['Status'] || null,
              dataset_comment: row['Comment'] || null,
            }))
            .filter(lab => lab.test_name && lab.test_name !== 'Unknown');
          resolve(labs);
        },
        error: reject,
      });
    });

  const handleFileUpload = useCallback(async (file, ctx = '') => {
    setError(null);
    setFileName(file.name);
    setPatientContext(ctx);
    setIsLoading(true);
    dispatch({ type: ACTIONS.RESET });

    try {
      // 1. Parse CSV client-side — instant, no backend call
      const labs = await parseCSV(file);
      if (labs.length === 0) {
        setError('No valid lab data found in the CSV file.');
        setIsLoading(false);
        return;
      }

      // 2. Render all skeleton cards immediately
      dispatch({ type: ACTIONS.INIT_RESULTS, payload: labs });

      // 3. POST all labs to the streaming endpoint
      const response = await fetch(`${API_URL}/analyze_labs_stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          labs,
          patient_context: ctx
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Server error');
      }

      // 4. Read the SSE stream — each event is one completed lab result
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete chunk

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();

          if (payload === '[DONE]') break;

          try {
            const result = JSON.parse(payload);
            if (result.error) {
              setError(`Stream error: ${result.error}`);
            } else {
              // Update the matching pending card live
              dispatch({ type: ACTIONS.UPDATE_RESULT, payload: result });
            }
          } catch (e) {
            console.warn('Failed to parse SSE event:', payload);
          }
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to process the file.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  return (
    <div className="app-container">
      <header className="header">
        <h1>LabInsight</h1>
        <p>AI-powered classification and explanation — results update <em>live</em> as they are analyzed.</p>
      </header>

      <main>
        <LabInput onFileUpload={handleFileUpload} isLoading={isLoading} fileName={fileName} />

        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
          </div>
        )}

        <ResultsDisplay results={results} patientContext={patientContext} onClear={handleClear} />
      </main>
    </div>
  );
};

export default App;
