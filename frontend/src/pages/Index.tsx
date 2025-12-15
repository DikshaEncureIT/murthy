import React, { useState } from 'react';
import { ArrowRight, Sparkles } from 'lucide-react';
import * as XLSX from 'xlsx';
import { Button } from '@/components/ui/button';
import FileUploadZone from '@/components/FileUploadZone';
import DownloadLink from '@/components/DownloadLink';
import ConversionStatus from '@/components/ConversionStatus';
import { useToast } from '@/hooks/use-toast';

const Index = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [conversionStatus, setConversionStatus] = useState<'idle' | 'converting' | 'complete' | 'error'>('idle');
  const [jsonData, setJsonData] = useState<object | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const { toast } = useToast();

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setConversionStatus('idle');
    setJsonData(null);
    setErrorMessage('');
  };

  const parseExcel = async (file: File): Promise<object> => {
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
    
    const result: Record<string, object[]> = {};
    
    workbook.SheetNames.forEach((sheetName) => {
      const worksheet = workbook.Sheets[sheetName];
      const jsonData = XLSX.utils.sheet_to_json(worksheet) as object[];
      result[sheetName] = jsonData;
    });
    
    // If only one sheet, return the data directly
    if (workbook.SheetNames.length === 1) {
      return result[workbook.SheetNames[0]];
    }
    
    return result;
  };

  const handleConvert = async () => {
    if (!selectedFile) {
      toast({
        title: "No file selected",
        description: "Please upload a file first",
        variant: "destructive",
      });
      return;
    }

    setConversionStatus('converting');
    setErrorMessage('');

    try {
      const fileName = selectedFile.name.toLowerCase();
      
      if (!fileName.endsWith('.xlsx') && !fileName.endsWith('.xls')) {
        throw new Error('Please upload an Excel file (.xlsx or .xls)');
      }

      const result = await parseExcel(selectedFile);

      setJsonData(result);
      setConversionStatus('complete');
      
      toast({
        title: "Conversion successful!",
        description: "Your file has been converted to JSON",
      });
    } catch (error) {
      setConversionStatus('error');
      setErrorMessage(error instanceof Error ? error.message : 'Failed to convert file');
      toast({
        title: "Conversion failed",
        description: error instanceof Error ? error.message : 'An error occurred',
        variant: "destructive",
      });
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center shadow-soft">
              <Sparkles className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold text-foreground">Murthy</span>
          </div>
          <p className="text-sm text-muted-foreground hidden sm:block">
            Excel to JSON Converter
          </p>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6 max-w-xl flex-1">
        <div className="text-center mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            Convert Excel to JSON
          </h1>
          <p className="text-muted-foreground">
            Upload your file and get a clean JSON output in seconds
          </p>
        </div>

        {/* Upload Section */}
        <div className="bg-card rounded-2xl p-5 shadow-card border border-border mb-4">
          <div className="mb-4">
            <h2 className="text-base font-semibold text-foreground mb-1">Step 1: Upload File</h2>
            <p className="text-sm text-muted-foreground">Select or drag an Excel file</p>
          </div>
          
          <FileUploadZone 
            onFileSelect={handleFileSelect} 
            selectedFile={selectedFile} 
          />

          <div className="mt-4 pt-4 border-t border-border">
            <div className="mb-3">
              <h2 className="text-base font-semibold text-foreground mb-1">Step 2: Convert</h2>
              <p className="text-sm text-muted-foreground">Click to transform your file to JSON</p>
            </div>
            
            <Button 
              size="default" 
              className="w-full"
              onClick={handleConvert}
              disabled={!selectedFile || conversionStatus === 'converting'}
            >
              {conversionStatus === 'converting' ? (
                <>Processing...</>
              ) : (
                <>
                  Convert to JSON
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Status */}
        <ConversionStatus status={conversionStatus} message={errorMessage} />

        {/* Download Section */}
        {conversionStatus === 'complete' && jsonData && selectedFile && (
          <div className="mt-4">
            <DownloadLink jsonData={jsonData} fileName={selectedFile.name} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-3">
        <div className="container mx-auto px-4 text-center">
          <p className="text-xs text-muted-foreground">
            Built with Murthy — Fast & Secure File Conversion
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
