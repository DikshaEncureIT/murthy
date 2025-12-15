import React from 'react';
import { Loader2 } from 'lucide-react';

interface ConversionStatusProps {
  status: 'idle' | 'converting' | 'complete' | 'error';
  message?: string;
}

const ConversionStatus: React.FC<ConversionStatusProps> = ({ status, message }) => {
  if (status === 'idle') return null;

  if (status === 'converting') {
    return (
      <div className="flex items-center justify-center gap-3 py-4 animate-slide-up">
        <Loader2 className="w-5 h-5 text-primary animate-spin" />
        <p className="text-muted-foreground font-medium">Converting your file...</p>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-4 animate-slide-up">
        <p className="text-destructive font-medium">{message || 'An error occurred during conversion'}</p>
      </div>
    );
  }

  return null;
};

export default ConversionStatus;
