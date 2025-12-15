import { useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Upload, FileSpreadsheet, Download, X, CheckCircle2, Loader2, Sparkles, AlertCircle } from "lucide-react";
import { api, ApiError, type ConversionResponse } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface UploadedFile {
  name: string;
  size: number;
  file: File;
  uploaded: boolean;
}

type ConversionStatus = "idle" | "uploading" | "converting" | "completed" | "error";

const ExcelConverter = () => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [status, setStatus] = useState<ConversionStatus>("idle");
  const [conversionData, setConversionData] = useState<ConversionResponse | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleFileSelect = async (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const excelFiles = Array.from(selectedFiles).filter(
      (file) =>
        file.name.endsWith(".xlsx") ||
        file.name.endsWith(".xls")
    );

    if (excelFiles.length === 0) {
      toast({
        title: "Invalid file format",
        description: "Please upload Excel files (.xlsx or .xls)",
        variant: "destructive",
      });
      return;
    }

    setStatus("idle");
    setConversionData(null);
    setErrorMessage("");

    const processedFiles: UploadedFile[] = excelFiles.map((file) => ({
      name: file.name,
      size: file.size,
      file: file,
      uploaded: false,
    }));

    setFiles((prev) => [...prev, ...processedFiles]);

    toast({
      title: "Files added",
      description: `${excelFiles.length} file${excelFiles.length > 1 ? "s" : ""} ready to upload`,
    });
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
      setConversionData(null);
      setErrorMessage("");
    }
  };

  const uploadAndConvert = async () => {
    if (files.length === 0) return;

    setStatus("uploading");
    setErrorMessage("");

    try {
      // Step 1: Upload all files
      toast({
        title: "Uploading files...",
        description: `Uploading ${files.length} file${files.length > 1 ? "s" : ""} to server`,
      });

      for (const fileObj of files) {
        try {
          await api.uploadFile(fileObj.file);

          // Mark file as uploaded
          setFiles((prev) =>
            prev.map((f) =>
              f.name === fileObj.name ? { ...f, uploaded: true } : f
            )
          );

          toast({
            title: "✓ File uploaded",
            description: `${fileObj.name} uploaded successfully`,
          });
        } catch (error) {
          throw new Error(`Failed to upload ${fileObj.name}: ${error instanceof ApiError ? error.detail : String(error)}`);
        }
      }

      // Step 2: Convert files using AI
      setStatus("converting");
      toast({
        title: "Converting files...",
        description: "AI is extracting tables from your Excel files",
      });

      const conversionResponse = await api.convert();
      setConversionData(conversionResponse);
      setStatus("completed");

      toast({
        title: "✓ Conversion successful!",
        description: `Extracted ${conversionResponse.tables_extracted} table${conversionResponse.tables_extracted !== 1 ? "s" : ""} from ${conversionResponse.files_processed} file${conversionResponse.files_processed !== 1 ? "s" : ""}`,
      });
    } catch (error) {
      setStatus("error");
      const errorMsg = error instanceof Error ? error.message : "Conversion failed";
      setErrorMessage(errorMsg);

      toast({
        title: "Conversion failed",
        description: errorMsg,
        variant: "destructive",
      });
    }
  };

  const downloadJson = () => {
    if (!conversionData?.consolidated_results) return;

    const jsonString = JSON.stringify(conversionData.consolidated_results, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "converted-data.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast({
      title: "Download started",
      description: "Your JSON file is being downloaded",
    });

    // Reset UI to initial state after download
    setTimeout(() => {
      setFiles([]);
      setStatus("idle");
      setConversionData(null);
      setErrorMessage("");
      toast({
        title: "Ready for next conversion",
        description: "Upload new files to begin",
      });
    }, 1500);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
                <h2 className="font-display font-semibold text-lg text-card-foreground">Upload Files</h2>
                <p className="text-sm text-muted-foreground">Excel files only (.xlsx, .xls)</p>
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
                accept=".xlsx,.xls"
                multiple
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files)}
              />
              <div className={`transition-transform duration-300 ${isDragging ? 'scale-110' : ''}`}>
                <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-accent to-accent/50 flex items-center justify-center">
                  <FileSpreadsheet className="w-6 h-6 text-primary" />
                </div>
                <p className="text-base font-medium text-card-foreground mb-1">
                  Drop files here or click to browse
                </p>
                <p className="text-sm text-muted-foreground">
                  Supports Excel files (.xlsx, .xls)
                </p>
              </div>
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="mt-4 space-y-2 animate-slide-up max-h-32 overflow-y-auto">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className={`flex items-center justify-between rounded-lg px-3 py-2.5 border ${
                      file.uploaded
                        ? "bg-gradient-to-r from-success/10 to-accent/30 border-success/20"
                        : "bg-muted/50 border-border"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-6 h-6 rounded-md flex items-center justify-center ${
                        file.uploaded ? "bg-success/20" : "bg-primary/20"
                      }`}>
                        {file.uploaded ? (
                          <CheckCircle2 className="w-4 h-4 text-success" />
                        ) : (
                          <FileSpreadsheet className="w-4 h-4 text-primary" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-card-foreground truncate max-w-[160px]">
                          {file.name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(file.size)}
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      className="p-1.5 rounded-md hover:bg-destructive/10 transition-colors"
                      disabled={status === "uploading" || status === "converting"}
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
                <h2 className="font-display font-semibold text-lg text-card-foreground">Convert & Download</h2>
                <p className="text-sm text-muted-foreground">AI-powered table extraction</p>
              </div>
            </div>

            <div className="flex-1 flex flex-col justify-center space-y-4">
              <Button
                onClick={uploadAndConvert}
                disabled={files.length === 0 || status === "uploading" || status === "converting"}
                className={`w-full h-12 text-base font-medium rounded-xl transition-all duration-300 ${
                  files.length > 0 && status !== "uploading" && status !== "converting"
                    ? "btn-gradient"
                    : ""
                }`}
                size="lg"
              >
                {status === "uploading" ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading...
                  </>
                ) : status === "converting" ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Converting with AI...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Upload & Convert
                  </>
                )}
              </Button>

              {status === "error" && errorMessage && (
                <div className="animate-slide-up bg-destructive/10 border border-destructive/20 rounded-xl p-3 flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-destructive mt-0.5 shrink-0" />
                  <p className="text-sm text-destructive">{errorMessage}</p>
                </div>
              )}

              {status === "completed" && conversionData && (
                <div className="animate-slide-up space-y-3">
                  <Button
                    onClick={downloadJson}
                    className="w-full h-12 text-base font-medium rounded-xl btn-success-gradient text-success-foreground"
                    size="lg"
                  >
                    <Download className="w-5 h-5" />
                    Download JSON File
                  </Button>

                  <div className="bg-success/10 border border-success/20 rounded-xl p-3">
                    <div className="flex items-center justify-center gap-2 text-sm text-success mb-2">
                      <CheckCircle2 className="w-4 h-4" />
                      <span className="font-semibold">Conversion successful!</span>
                    </div>
                    <div className="text-xs text-muted-foreground text-center">
                      Extracted {conversionData.tables_extracted} table{conversionData.tables_extracted !== 1 ? "s" : ""} from {conversionData.files_processed} file{conversionData.files_processed !== 1 ? "s" : ""}
                    </div>
                  </div>
                </div>
              )}

              {files.length === 0 && (
                <div className="text-center py-6">
                  <div className="w-14 h-14 mx-auto mb-3 rounded-xl bg-muted/50 flex items-center justify-center">
                    <Upload className="w-7 h-7 text-muted-foreground/50" />
                  </div>
                  <p className="text-base text-muted-foreground">
                    Upload Excel files to begin
                  </p>
                </div>
              )}

              {files.length > 0 && status === "idle" && (
                <div className="text-center py-4">
                  <p className="text-sm text-muted-foreground">
                    <span className="font-semibold text-primary">{files.length}</span> file{files.length > 1 ? "s" : ""} ready to upload
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
          { label: "Uploaded", value: files.filter(f => f.uploaded).length, icon: CheckCircle2 },
          {
            label: "Status",
            value: status === "completed" ? "Done" :
                   status === "converting" ? "Converting" :
                   status === "uploading" ? "Uploading" :
                   status === "error" ? "Error" : "Ready",
            icon: status === "error" ? AlertCircle : CheckCircle2
          },
        ].map((stat, i) => (
          <div key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
            <stat.icon className={`w-4 h-4 ${status === "error" && stat.label === "Status" ? "text-destructive" : "text-primary"}`} />
            <span className="font-medium text-card-foreground">{stat.value}</span>
            <span>{stat.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ExcelConverter;
