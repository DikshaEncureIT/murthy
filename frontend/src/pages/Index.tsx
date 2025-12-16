import ExcelConverter from "@/components/ExcelConverter";

const Index = () => {
  return (
    <div className="h-screen bg-background relative overflow-hidden flex flex-col">
      {/* Background decorations */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-72 h-72 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-72 h-72 bg-success/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative border-b border-border/50 bg-gradient-to-r from-card/40 via-primary/5 to-card/40 backdrop-blur-xl shrink-0">
        {/* Animated gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-accent/10 to-success/10 opacity-50 animate-pulse" style={{ animationDuration: '3s' }} />

        <div className="container max-w-6xl mx-auto px-6 py-4 relative">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Logo with enhanced gradient */}
              <div className="relative group">
                <div className="absolute inset-0 bg-gradient-to-br from-primary to-accent rounded-xl blur-md opacity-50 group-hover:opacity-75 transition-opacity" />
                <div className="relative w-12 h-12 rounded-xl bg-gradient-to-br from-primary via-primary/90 to-accent flex items-center justify-center shadow-lg shadow-primary/30 group-hover:shadow-primary/50 transition-all duration-300 group-hover:scale-105">
                  <span className="text-primary-foreground font-display font-bold text-2xl">E</span>
                </div>
              </div>

              {/* Title and tagline */}
              <div>
                <h1 className="text-2xl font-display font-bold bg-gradient-to-r from-foreground via-primary to-foreground bg-clip-text text-transparent tracking-tight">
                  Excel to JSON
                </h1>
                <p className="text-xs text-muted-foreground -mt-1 font-medium">
                  Excel to JSON Converter · AI-Powered Table Extraction
                </p>
              </div>
            </div>

            {/* Status badges */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20 backdrop-blur-sm">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-lg shadow-success/50" />
                <span className="text-xs font-semibold text-success">AI Active</span>
              </div>

              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 border border-primary/20 backdrop-blur-sm">
                <svg className="w-3.5 h-3.5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span className="text-xs font-semibold text-primary">Fast Convert</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative flex-1 container max-w-6xl mx-auto px-6 py-6 flex items-center">
        <ExcelConverter />
      </main>
    </div>
  );
};

export default Index;
