import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';

const SeverityBadge = ({ severity }) => {
  let Icon = CheckCircle;
  let label = severity;
  
  if (severity === 'Critical') {
    Icon = AlertCircle;
  } else if (severity === 'Warning') {
    Icon = AlertTriangle;
  } else if (severity === 'data_error') {
    Icon = XCircle;
    label = 'Data Error';
  } else if (severity === 'unclassified') {
    Icon = HelpCircle;
    label = 'Unclassified';
  }

  return (
    <div className={`badge severity-${severity}`}>
      <Icon size={14} />
      {label}
    </div>
  );
};

export default SeverityBadge;
