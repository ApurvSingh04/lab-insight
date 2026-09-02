import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle } from 'lucide-react';

const SeverityBadge = ({ severity }) => {
  let Icon = CheckCircle;
  
  if (severity === 'Critical') {
    Icon = AlertCircle;
  } else if (severity === 'Warning') {
    Icon = AlertTriangle;
  }

  return (
    <div className="badge">
      <Icon size={14} />
      {severity}
    </div>
  );
};

export default SeverityBadge;
