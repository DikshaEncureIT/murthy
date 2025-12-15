import React from 'react';
import { Download, FileJson, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface DownloadLinkProps {
  jsonData: object;
  fileName: string;
}

const DownloadLink: React.FC<DownloadLinkProps> = ({ jsonData, fileName }) => {
  const handleDownload = () => {
    const jsonString = JSON.stringify(jsonData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName.replace(/\.[^/.]+$/, '') + '.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-slide-up bg-card rounded-2xl p-4 shadow-card border border-border">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center">
          <CheckCircle className="w-4 h-4 text-success" />
        </div>
        <div>
          <p className="font-semibold text-foreground text-sm">Conversion Complete!</p>
          <p className="text-xs text-muted-foreground">Your JSON file is ready</p>
        </div>
      </div>
      
      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-xl mb-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <FileJson className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-foreground truncate text-sm">
            {fileName.replace(/\.[^/.]+$/, '')}.json
          </p>
          <p className="text-xs text-muted-foreground">
            {(JSON.stringify(jsonData).length / 1024).toFixed(2)} KB
          </p>
        </div>
      </div>
      
      <Button 
        variant="success" 
        className="w-full" 
        size="default"
        onClick={handleDownload}
      >
        <Download className="w-4 h-4" />
        Download JSON File
      </Button>
    </div>
  );
};

export default DownloadLink;
