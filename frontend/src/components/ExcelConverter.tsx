import { useState, useRef, useCallback } from "react";
import * as XLSX from "xlsx";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, Download, X, CheckCircle2, Loader2, Sparkles } from "lucide-react";

interface UploadedFile {
  name: string;
  data: unknown[];
  sheets: string[];
}

type ConversionStatus = "idle" | "converting" | "completed";

const ExcelConverter = () => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [status, setStatus] = useState<ConversionStatus>("idle");
  const [jsonData, setJsonData] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const processExcelFile = (file: File): Promise<UploadedFile> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = e.target?.result;
          const workbook = XLSX.read(data, { type: "array" });
          const allData: unknown[] = [];
          
          workbook.SheetNames.forEach((sheetName) => {
            const worksheet = workbook.Sheets[sheetName];
            const sheetData = XLSX.utils.sheet_to_json(worksheet);
            allData.push({ sheet: sheetName, data: sheetData });
          });

          resolve({
            name: file.name,
            data: allData,
            sheets: workbook.SheetNames,
          });
        } catch (error) {
          reject(error);
        }
      };
      reader.onerror = () => reject(new Error("Failed to read file"));
      reader.readAsArrayBuffer(file);
    });
  };

  const handleFileSelect = async (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const excelFiles = Array.from(selectedFiles).filter(
      (file) =>
        file.name.endsWith(".xlsx") ||
        file.name.endsWith(".xls") ||
        file.name.endsWith(".csv")
    );

    if (excelFiles.length === 0) return;

    setStatus("idle");
    setJsonData(null);

    const processedFiles: UploadedFile[] = [];
    for (const file of excelFiles) {
      try {
        const processed = await processExcelFile(file);
        processedFiles.push(processed);
      } catch (error) {
        console.error(`Error processing ${file.name}:`, error);
      }
    }

    setFiles((prev) => [...prev, ...processedFiles]);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    if (files.length === 1) {
      setStatus("idle");
      setJsonData(null);
    }
  };

  const convertToJson = () => {
    setStatus("converting");
    
    setTimeout(() => {
      const combinedData = files.map((file) => ({
        fileName: file.name,
        sheets: file.data,
      }));

      const json = JSON.stringify(combinedData, null, 2);
      setJsonData(json);
      setStatus("completed");
    }, 800);
  };

  const downloadJson = () => {
    if (!jsonData) return;

    const blob = new Blob([jsonData], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "converted-data.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full">
      <div className="grid md:grid-cols-2 gap-6">
        {/* Upload Section */}
        <div className="glass-card rounded-2xl p-6 animate-fade-in relative overflow-hidden group hover:shadow-card-hover transition-shadow duration-500">
          <div className="absolute -top-16 -right-16 w-32 h-32 bg-gradient-to-br from-primary/20 to-accent rounded-full blur-3xl opacity-60" />
          
          <div className="relative">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center border border-primary/20">
                <Upload className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-display font-semibold text-card-foreground">Upload Files</h2>
                <p className="text-xs text-muted-foreground">Excel files only (.xlsx, .xls, .csv)</p>
              </div>
            </div>

            <div
              className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all duration-300 cursor-pointer ${
                isDragging
                  ? "border-primary bg-primary/5 scale-[1.02]"
                  : "border-border hover:border-primary/50 hover:bg-accent/30"
              }`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                multiple
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files)}
              />
              <div className={`transition-transform duration-300 ${isDragging ? 'scale-110' : ''}`}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-accent/50 flex items-center justify-center">
                  <FileSpreadsheet className="w-6 h-6 text-primary" />
                </div>
                <p className="text-sm font-medium text-card-foreground mb-1">
                  Drop files here or click to browse
                </p>
                <p className="text-xs text-muted-foreground">
                  Supports multiple files
                </p>
              </div>
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="mt-4 space-y-2 animate-slide-up max-h-32 overflow-y-auto">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between bg-gradient-to-r from-success/10 to-accent/30 rounded-lg px-3 py-2.5 border border-success/20"
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-md bg-success/20 flex items-center justify-center">
                        <CheckCircle2 className="w-4 h-4 text-success" />
                      </div>
                      <div>
                        <p className="text-xs font-medium text-card-foreground truncate max-w-[160px]">
                          {file.name}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {file.sheets.length} sheet{file.sheets.length > 1 ? "s" : ""}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      className="p-1.5 rounded-md hover:bg-destructive/10 transition-colors"
                    >
                      <X className="w-3.5 h-3.5 text-muted-foreground hover:text-destructive" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Convert & Download Section */}
        <div className="glass-card rounded-2xl p-6 animate-fade-in relative overflow-hidden group hover:shadow-card-hover transition-shadow duration-500" style={{ animationDelay: '0.1s' }}>
          <div className="absolute -bottom-16 -left-16 w-32 h-32 bg-gradient-to-tr from-success/20 to-primary/20 rounded-full blur-3xl opacity-60" />
          
          <div className="relative h-full flex flex-col">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center border border-primary/20">
                <Sparkles className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="font-display font-semibold text-card-foreground">Convert & Download</h2>
                <p className="text-xs text-muted-foreground">Transform your data to JSON</p>
              </div>
            </div>

            <div className="flex-1 flex flex-col justify-center space-y-4">
              <Button
                onClick={convertToJson}
                disabled={files.length === 0 || status === "converting"}
                className={`w-full h-12 text-sm font-medium rounded-xl transition-all duration-300 ${
                  files.length > 0 && status !== "converting" 
                    ? "btn-gradient" 
                    : ""
                }`}
                size="lg"
              >
                {status === "converting" ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Converting...
                  </>
                ) : (
                  <>
                    <FileSpreadsheet className="w-4 h-4" />
                    Convert to JSON
                  </>
                )}
              </Button>

              {status === "completed" && jsonData && (
                <div className="animate-slide-up">
                  <Button
                    onClick={downloadJson}
                    className="w-full h-12 text-sm font-medium rounded-xl btn-success-gradient text-success-foreground"
                    size="lg"
                  >
                    <Download className="w-4 h-4" />
                    Download JSON File
                  </Button>
                  
                  <div className="mt-3 flex items-center justify-center gap-2 text-xs text-success">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Conversion successful!</span>
                  </div>
                </div>
              )}

              {files.length === 0 && (
                <div className="text-center py-6">
                  <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-muted/50 flex items-center justify-center">
                    <Upload className="w-7 h-7 text-muted-foreground/50" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Upload Excel files to begin
                  </p>
                </div>
              )}

              {files.length > 0 && status === "idle" && (
                <div className="text-center py-4">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-semibold text-primary">{files.length}</span> file{files.length > 1 ? "s" : ""} ready
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Compact Stats Row */}
      <div className="mt-5 flex justify-center gap-8 animate-fade-in" style={{ animationDelay: '0.2s' }}>
        {[
          { label: "Files", value: files.length, icon: FileSpreadsheet },
          { label: "Sheets", value: files.reduce((acc, f) => acc + f.sheets.length, 0), icon: Upload },
          { label: "Status", value: status === "completed" ? "Done" : status === "converting" ? "Working" : "Ready", icon: CheckCircle2 },
        ].map((stat, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
            <stat.icon className="w-3.5 h-3.5 text-primary" />
            <span className="font-medium text-card-foreground">{stat.value}</span>
            <span>{stat.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ExcelConverter;
