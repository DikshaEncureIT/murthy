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
      <header className="relative border-b border-border/50 bg-card/30 backdrop-blur-xl shrink-0">
        <div className="container max-w-6xl mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center shadow-lg shadow-primary/25">
                <span className="text-primary-foreground font-display font-bold text-lg">M</span>
              </div>
              <div>
                <h1 className="text-lg font-display font-bold text-foreground tracking-tight">
                  Murthy
                </h1>
                <p className="text-[10px] text-muted-foreground -mt-0.5">Excel to JSON Converter</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              Processing locally
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
