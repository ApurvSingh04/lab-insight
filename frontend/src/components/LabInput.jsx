import React, { useRef } from 'react';
import { Upload, FileText } from 'lucide-react';

const LabInput = ({ onFileUpload, isLoading, fileName }) => {
  const fileInputRef = useRef(null);

  const [context, setContext] = React.useState('');

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onFileUpload(file, context);
      // Reset so the same file can be re-uploaded
      e.target.value = '';
    }
  };

  return (
    <div className="input-section glass-panel">
      <div className="input-icon">
        <FileText size={40} strokeWidth={1.5} />
      </div>
      <h2>Upload Lab Results</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
        Upload a CSV file — results will appear <strong>live</strong> as the AI analyzes each test.
      </p>

      <div style={{ marginBottom: '1.5rem', textAlign: 'left', width: '100%', maxWidth: '400px' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500, fontSize: '0.9rem' }}>
          Patient Context (Optional)
        </label>
        <textarea 
          placeholder="e.g. 65yo Female, Type 2 Diabetic on Metformin..."
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={isLoading}
          style={{
            width: '100%',
            padding: '0.75rem',
            borderRadius: '8px',
            border: '1px solid var(--panel-border)',
            background: 'rgba(0,0,0,0.2)',
            color: 'var(--text-primary)',
            minHeight: '80px',
            fontFamily: 'inherit',
            resize: 'vertical'
          }}
        />
      </div>

      <input
        type="file"
        accept=".csv"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      <button
        className="upload-btn"
        onClick={() => fileInputRef.current?.click()}
        disabled={isLoading}
      >
        {isLoading ? (
          <>
            <div className="loader" />
            Analyzing...
          </>
        ) : (
          <>
            <Upload size={20} />
            {fileName ? 'Upload Another CSV' : 'Select CSV File'}
          </>
        )}
      </button>

      {fileName && (
        <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          📄 {fileName}
        </p>
      )}
    </div>
  );
};

export default LabInput;
