"use client";

import { useState, useRef, useEffect } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import { toast } from "sonner";
import {
  CSVParseResponse,
  CSVColumnMapping,
  AmountConfig,
  AmountMode,
  FilterRule,
  FilterOperator,
  CSVExecuteResponse,
  ImportCategorySuggestion,
  Category,
  DateFormatOption,
} from "@/models/wallets";
import { suggestImportCategories } from "@/api/ai";
import { Switch } from "@/components/ui/switch";
import { DynamicIcon } from "@/components/IconPicker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  FileSpreadsheet,
  ArrowRight,
  ArrowLeft,
  Check,
  X,
  AlertCircle,
  Trash2,
  Plus,
  Sparkles,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CSVImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  onImported: () => void;
  walletId: string;
}

type Step = "upload" | "mapping" | "amount" | "filters" | "categorize" | "review";

const STEPS: { key: Step; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "mapping", label: "Map Columns" },
  { key: "amount", label: "Amount Config" },
  { key: "filters", label: "Filters" },
  { key: "categorize", label: "AI Categorize" },
  { key: "review", label: "Review" },
];

const UNCATEGORIZED_VALUE = "__uncategorized__";

const FILTER_OPERATORS: { value: FilterOperator; label: string }[] = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not Equals" },
  { value: "contains", label: "Contains" },
  { value: "not_contains", label: "Not Contains" },
];

const DATE_FORMAT_OPTIONS: { value: DateFormatOption; label: string }[] = [
  { value: "auto", label: "Auto-detected" },
  { value: "DMY", label: "DD/MM/YYYY" },
  { value: "MDY", label: "MM/DD/YYYY" },
  { value: "YMD", label: "YYYY-MM-DD" },
];

const DATE_FORMAT_LABELS: Record<string, string> = {
  DMY: "DD/MM/YYYY",
  MDY: "MM/DD/YYYY",
  YMD: "YYYY-MM-DD",
};

const AMOUNT_MODES: { value: AmountMode; label: string; description: string }[] = [
  { value: "signed", label: "Signed Amount", description: "Amount column has +/- sign" },
  { value: "type_column", label: "Type Column", description: "Separate column for income/expense" },
  { value: "always_expense", label: "Always Expense", description: "All rows are expenses" },
  { value: "always_income", label: "Always Income", description: "All rows are income" },
];

export function CSVImportDialog({
  open,
  onOpenChange,
  onClose,
  onImported,
  walletId,
}: CSVImportDialogProps) {
  const [step, setStep] = useState<Step>("upload");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // File upload state
  const [file, setFile] = useState<File | null>(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [parseResult, setParseResult] = useState<CSVParseResponse | null>(null);

  // Column mapping state (use special "__none__" value for optional fields)
  const [columnMapping, setColumnMapping] = useState<CSVColumnMapping>({
    amount: "",
    date: "",
    note: [],
    category: "__none__",
    tags: "__none__",
    type: "__none__",
  });

  // Date format state (chosen order to resolve ambiguous numeric dates)
  const [dateFormat, setDateFormat] = useState<DateFormatOption>("auto");

  // Amount config state
  const [amountConfig, setAmountConfig] = useState<AmountConfig>({
    mode: "signed",
    income_value: "",
    expense_value: "",
  });

  // Filter state
  const [filters, setFilters] = useState<FilterRule[]>([]);

  // Execute result state
  const [executeResult, setExecuteResult] = useState<CSVExecuteResponse | null>(null);

  // AI categorization state
  const [aiEnabled, setAiEnabled] = useState(true);
  const [categories, setCategories] = useState<Category[]>([]);
  const [suggestions, setSuggestions] = useState<ImportCategorySuggestion[]>([]);
  const [aiOverrides, setAiOverrides] = useState<Record<string, string>>({}); // key -> category_id ("" = Uncategorized)
  const [keywords, setKeywords] = useState<Record<string, string>>({}); // key -> editable merchant keyword
  const [aiFetched, setAiFetched] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiQuotaExceeded, setAiQuotaExceeded] = useState(false);

  // Load the user's categories once when the dialog opens (for override dropdowns).
  useEffect(() => {
    if (!open) return;
    axiosInstance
      .get<Category[]>("wallets/categories/")
      .then((res) =>
        setCategories(res.data.filter((c) => c.is_visible && !c.is_archived))
      )
      .catch(() => {
        /* non-fatal: AI step can still import everything as Uncategorized */
      });
  }, [open]);

  function resetState() {
    setStep("upload");
    setFile(null);
    setIsDraggingFile(false);
    setParseResult(null);
    setColumnMapping({ amount: "", date: "", note: [], category: "__none__", tags: "__none__", type: "__none__" });
    setDateFormat("auto");
    setAmountConfig({ mode: "signed", income_value: "", expense_value: "" });
    setFilters([]);
    setExecuteResult(null);
    setError("");
    setIsLoading(false);
    setAiEnabled(true);
    setSuggestions([]);
    setAiOverrides({});
    setKeywords({});
    setAiFetched(false);
    setAiLoading(false);
    setAiQuotaExceeded(false);
  }

  function handleClose() {
    resetState();
    onClose();
  }

  function applySelectedFile(selectedFile: File) {
    if (!selectedFile.name.endsWith(".csv")) {
      setError("Please select a CSV file");
      return;
    }
    if (selectedFile.size > 5 * 1024 * 1024) {
      setError("File size must not exceed 5MB");
      return;
    }
    setFile(selectedFile);
    setError("");
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      applySelectedFile(selectedFile);
    }
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (!isDraggingFile) setIsDraggingFile(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingFile(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      applySelectedFile(droppedFile);
    }
  }

  async function handleParse() {
    if (!file) return;

    setIsLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await axiosInstance.post<CSVParseResponse>(
        `wallets/${walletId}/import/parse/`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      if (response.data.success) {
        setParseResult(response.data);
        // Try to auto-detect column mappings
        autoDetectMappings(response.data.columns);
        setStep("mapping");
      } else {
        setError(response.data.error || "Failed to parse CSV");
        toast.error("Import failed");
      }
    } catch (err) {
      console.error("Failed to parse CSV:", err);
      setError("Failed to parse CSV file. Please check the format.");
      toast.error("Import failed");
    } finally {
      setIsLoading(false);
    }
  }

  function autoDetectMappings(columns: string[]) {
    const mapping: CSVColumnMapping = { amount: "", date: "" };

    // Amount detection
    const amountKeywords = ["amount", "sum", "value", "price", "total", "kwota"];
    for (const col of columns) {
      if (amountKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.amount = col;
        break;
      }
    }

    // Date detection
    const dateKeywords = ["date", "data", "time", "timestamp", "day"];
    for (const col of columns) {
      if (dateKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.date = col;
        break;
      }
    }

    // Note detection
    const noteKeywords = ["note", "description", "desc", "title", "memo", "opis", "tytul"];
    mapping.note = [];
    for (const col of columns) {
      if (noteKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.note = [col];
        break;
      }
    }

    // Category detection
    const categoryKeywords = ["category", "cat", "kategoria"];
    mapping.category = "__none__";
    for (const col of columns) {
      if (categoryKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.category = col;
        break;
      }
    }

    // Tags detection
    const tagKeywords = ["tag", "tags", "label", "labels"];
    mapping.tags = "__none__";
    for (const col of columns) {
      if (tagKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.tags = col;
        break;
      }
    }

    setColumnMapping(mapping);
  }

  function canProceedFromMapping(): boolean {
    return !!columnMapping.amount && !!columnMapping.date;
  }

  function canProceedFromAmount(): boolean {
    if (amountConfig.mode === "type_column") {
      return columnMapping.type !== "__none__" && !!amountConfig.income_value && !!amountConfig.expense_value;
    }
    return true;
  }

  function addFilter() {
    if (!parseResult) return;
    setFilters([
      ...filters,
      {
        column: parseResult.columns[0] || "",
        operator: "equals",
        value: "",
      },
    ]);
  }

  function updateFilter(index: number, field: keyof FilterRule, value: string) {
    const newFilters = [...filters];
    newFilters[index] = { ...newFilters[index], [field]: value };
    setFilters(newFilters);
  }

  function removeFilter(index: number) {
    setFilters(filters.filter((_, i) => i !== index));
  }

  // Shared payload for both the AI suggest call and the final execute call.
  function buildImportFormData(): FormData | null {
    if (!file) return null;

    // Convert "__none__" back to empty string for the backend.
    const cleanedMapping: Record<string, string | string[]> = { ...columnMapping };
    Object.keys(cleanedMapping).forEach((key) => {
      if (cleanedMapping[key] === "__none__") {
        cleanedMapping[key] = "";
      }
    });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("column_mapping", JSON.stringify(cleanedMapping));
    formData.append("amount_config", JSON.stringify(amountConfig));
    formData.append("filters", JSON.stringify(filters));
    formData.append("date_format", dateFormat);
    return formData;
  }

  async function fetchSuggestions() {
    const formData = buildImportFormData();
    if (!formData) return;

    setAiLoading(true);
    try {
      const res = await suggestImportCategories(walletId, formData);
      setSuggestions(res.data.suggestions);
      // Seed overrides from the AI's picks ("" => Uncategorized) and keywords.
      const seeded: Record<string, string> = {};
      const seededKw: Record<string, string> = {};
      res.data.suggestions.forEach((s) => {
        seeded[s.key] = s.category_id ?? "";
        seededKw[s.key] = s.keyword ?? "";
      });
      setAiOverrides(seeded);
      setKeywords(seededKw);
      setAiQuotaExceeded(res.data.quota_exceeded);
      if (res.data.usage_warning) {
        toast.warning(`AI usage at ${res.data.usage_warning.percent_used}%`);
      }
    } catch (err) {
      console.error("Failed to fetch AI suggestions:", err);
      toast.error("Couldn't fetch AI suggestions — rows will import uncategorized");
      setSuggestions([]);
    } finally {
      setAiLoading(false);
      setAiFetched(true);
    }
  }

  async function handleExecute() {
    if (!file) return;

    setIsLoading(true);
    setError("");

    try {
      const formData = buildImportFormData();
      if (!formData) return;

      // Attach AI overrides. Absent => legacy behavior.
      // Rows with a category AND a keyword become durable rules that cascade to
      // similar rows and persist. Rows with a category but no keyword are
      // one-off exact-signature overrides. "" category = leave Uncategorized.
      if (aiEnabled && suggestions.length > 0) {
        const aiCategories: Record<string, string> = {};
        const rules: { keyword: string; category_id: string }[] = [];
        suggestions.forEach((s) => {
          const categoryId = aiOverrides[s.key];
          if (!categoryId) return; // Uncategorized
          const keyword = (keywords[s.key] || "").trim();
          if (keyword) {
            rules.push({ keyword, category_id: categoryId });
          } else {
            aiCategories[s.key] = categoryId;
          }
        });
        formData.append("ai_categories", JSON.stringify(aiCategories));
        formData.append("rules", JSON.stringify(rules));
      }

      const response = await axiosInstance.post<CSVExecuteResponse>(
        `wallets/${walletId}/import/execute/`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );

      setExecuteResult(response.data);
      if (response.data.success) {
        onImported();
      }
    } catch (err) {
      console.error("Failed to execute import:", err);
      setError("Failed to import transactions. Please try again.");
      toast.error("Import failed");
    } finally {
      setIsLoading(false);
    }
  }

  function goToStep(targetStep: Step) {
    setStep(targetStep);
  }

  function getCurrentStepIndex(): number {
    return STEPS.findIndex((s) => s.key === step);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-none w-screen h-screen max-h-screen sm:rounded-none flex flex-col p-0 gap-0">
        <DialogHeader className="shrink-0 border-b px-6 pt-6 pb-4">
          <DialogTitle>Import Transactions from CSV</DialogTitle>
          <DialogDescription>
            Upload a CSV file and map columns to import transactions.
          </DialogDescription>
        </DialogHeader>

        {/* Progress Steps */}
        <div className="flex items-center justify-between shrink-0 overflow-x-auto border-b px-6 py-4">
          {STEPS.map((s, index) => (
            <div key={s.key} className="flex items-center">
              <div
                className={cn(
                  "flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium",
                  step === s.key
                    ? "bg-primary text-primary-foreground"
                    : getCurrentStepIndex() > index
                    ? "bg-green-500 text-white"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {getCurrentStepIndex() > index ? <Check className="h-4 w-4" /> : index + 1}
              </div>
              <span
                className={cn(
                  "ml-2 text-sm hidden sm:inline",
                  step === s.key ? "font-medium" : "text-muted-foreground"
                )}
              >
                {s.label}
              </span>
              {index < STEPS.length - 1 && (
                <div className="w-8 sm:w-12 h-0.5 mx-2 bg-muted" />
              )}
            </div>
          ))}
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {/* Step 1: Upload */}
          {step === "upload" && (
            <div className="space-y-4">
              <div
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                  file
                    ? "border-green-500 bg-green-50"
                    : isDraggingFile
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-primary"
                )}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {file ? (
                  <div className="space-y-2">
                    <FileSpreadsheet className="h-12 w-12 mx-auto text-green-500" />
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                    >
                      Change File
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Upload className="h-12 w-12 mx-auto text-muted-foreground" />
                    <p className="font-medium">Click to upload CSV file</p>
                    <p className="text-sm text-muted-foreground">or drag and drop</p>
                    <p className="text-xs text-muted-foreground">Maximum file size: 5MB</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Column Mapping */}
          {step === "mapping" && parseResult && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>
                    Amount Column <span className="text-red-500">*</span>
                  </Label>
                  <Select
                    value={columnMapping.amount}
                    onValueChange={(v) => setColumnMapping({ ...columnMapping, amount: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select column..." />
                    </SelectTrigger>
                    <SelectContent>
                      {parseResult.columns.map((col) => (
                        <SelectItem key={col} value={col}>
                          {col}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>
                    Date Column <span className="text-red-500">*</span>
                  </Label>
                  <Select
                    value={columnMapping.date}
                    onValueChange={(v) => setColumnMapping({ ...columnMapping, date: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select column..." />
                    </SelectTrigger>
                    <SelectContent>
                      {parseResult.columns.map((col) => (
                        <SelectItem key={col} value={col}>
                          {col}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Note Column(s) (Optional)</Label>
                  <p className="text-xs text-muted-foreground">
                    Pick one or more columns to merge into the note, in the order you add them.
                  </p>
                  {(columnMapping.note ?? []).length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {(columnMapping.note ?? []).map((col) => (
                        <Badge key={col} variant="secondary" className="gap-1 pr-1">
                          {col}
                          <button
                            type="button"
                            onClick={() =>
                              setColumnMapping({
                                ...columnMapping,
                                note: (columnMapping.note ?? []).filter((c) => c !== col),
                              })
                            }
                            className="rounded-full hover:bg-muted-foreground/20"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  )}
                  {parseResult.columns.filter((col) => !(columnMapping.note ?? []).includes(col))
                    .length > 0 && (
                    <Select
                      key={(columnMapping.note ?? []).length}
                      onValueChange={(v) =>
                        setColumnMapping({
                          ...columnMapping,
                          note: [...(columnMapping.note ?? []), v],
                        })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Add a column..." />
                      </SelectTrigger>
                      <SelectContent>
                        {parseResult.columns
                          .filter((col) => !(columnMapping.note ?? []).includes(col))
                          .map((col) => (
                            <SelectItem key={col} value={col}>
                              {col}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Category Column (Optional)</Label>
                  <Select
                    value={columnMapping.category || "__none__"}
                    onValueChange={(v) => setColumnMapping({ ...columnMapping, category: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select column..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">None</SelectItem>
                      {parseResult.columns.map((col) => (
                        <SelectItem key={col} value={col}>
                          {col}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Tags Column (Optional)</Label>
                  <Select
                    value={columnMapping.tags || "__none__"}
                    onValueChange={(v) => setColumnMapping({ ...columnMapping, tags: v })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select column..." />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">None</SelectItem>
                      {parseResult.columns.map((col) => (
                        <SelectItem key={col} value={col}>
                          {col}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Comma or semicolon separated tag names
                  </p>
                </div>
              </div>

              {(() => {
                // Prefer the per-column detection for the column the user actually
                // mapped as the date column (execute re-scans that column in "auto"
                // mode), falling back to the backend's overall best guess when the
                // mapped column has no per-column entry (e.g. nothing mapped yet).
                const mappedInfo = parseResult.date_formats[columnMapping.date];
                const detectedFormat = mappedInfo?.format ?? parseResult.date_format;
                const detectedAmbiguous = mappedInfo?.ambiguous ?? parseResult.date_format_ambiguous;
                return (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Label>Date Format</Label>
                      {detectedAmbiguous && (
                        <Badge variant="outline" className="gap-1 text-amber-600 border-amber-300">
                          <AlertCircle className="h-3 w-3" /> Ambiguous — please confirm
                        </Badge>
                      )}
                    </div>
                    <Select
                      value={dateFormat}
                      onValueChange={(v) => setDateFormat(v as DateFormatOption)}
                    >
                      <SelectTrigger className="w-full sm:w-[260px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DATE_FORMAT_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Detected format: {DATE_FORMAT_LABELS[detectedFormat] ?? detectedFormat}
                      {detectedAmbiguous
                        ? " — dates in this file could be read more than one way, please verify."
                        : ""}
                    </p>
                  </div>
                );
              })()}

              {/* Sample Data Preview */}
              <div className="mt-4">
                <Label className="mb-2 block">Sample Data ({parseResult.total_rows} total rows)</Label>
                <div className="border rounded-lg overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        {parseResult.columns.map((col) => (
                          <TableHead key={col} className="whitespace-nowrap">
                            {col}
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {parseResult.sample_rows.slice(0, 3).map((row, i) => (
                        <TableRow key={i}>
                          {parseResult.columns.map((col) => (
                            <TableCell key={col} className="whitespace-nowrap">
                              {row[col] || "-"}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Amount Configuration */}
          {step === "amount" && parseResult && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>How should amounts be interpreted?</Label>
                <div className="grid gap-2">
                  {AMOUNT_MODES.map((mode) => (
                    <Card
                      key={mode.value}
                      className={cn(
                        "cursor-pointer transition-colors",
                        amountConfig.mode === mode.value
                          ? "border-primary bg-primary/5"
                          : "hover:border-muted-foreground/50"
                      )}
                      onClick={() => setAmountConfig({ ...amountConfig, mode: mode.value })}
                    >
                      <CardContent className="p-4 flex items-center gap-3">
                        <div
                          className={cn(
                            "w-4 h-4 rounded-full border-2",
                            amountConfig.mode === mode.value
                              ? "border-primary bg-primary"
                              : "border-muted-foreground"
                          )}
                        >
                          {amountConfig.mode === mode.value && (
                            <Check className="h-3 w-3 text-primary-foreground" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium">{mode.label}</p>
                          <p className="text-sm text-muted-foreground">{mode.description}</p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>

              {amountConfig.mode === "type_column" && (
                <div className="space-y-4 mt-4 p-4 border rounded-lg bg-muted/50">
                  <div className="space-y-2">
                    <Label>
                      Type Column <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={columnMapping.type || "__none__"}
                      onValueChange={(v) => setColumnMapping({ ...columnMapping, type: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select column..." />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">Select a column...</SelectItem>
                        {parseResult.columns.map((col) => (
                          <SelectItem key={col} value={col}>
                            {col}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>
                        Income Value <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        placeholder="e.g., Income, Credit, +"
                        value={amountConfig.income_value || ""}
                        onChange={(e) =>
                          setAmountConfig({ ...amountConfig, income_value: e.target.value })
                        }
                      />
                      {columnMapping.type && columnMapping.type !== "__none__" && parseResult.unique_values[columnMapping.type] && (
                        <p className="text-xs text-muted-foreground">
                          Values: {parseResult.unique_values[columnMapping.type].slice(0, 5).join(", ")}
                        </p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label>
                        Expense Value <span className="text-red-500">*</span>
                      </Label>
                      <Input
                        placeholder="e.g., Expense, Debit, -"
                        value={amountConfig.expense_value || ""}
                        onChange={(e) =>
                          setAmountConfig({ ...amountConfig, expense_value: e.target.value })
                        }
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Filters */}
          {step === "filters" && parseResult && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <Label>Row Filters (Optional)</Label>
                  <p className="text-sm text-muted-foreground">
                    Only import rows that match these conditions
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={addFilter}>
                  <Plus className="h-4 w-4 mr-1" /> Add Filter
                </Button>
              </div>

              {filters.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No filters added. All {parseResult.total_rows} rows will be imported.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {filters.map((filter, index) => (
                    <div key={index} className="flex gap-2 items-start p-3 border rounded-lg">
                      <Select
                        value={filter.column}
                        onValueChange={(v) => updateFilter(index, "column", v)}
                      >
                        <SelectTrigger className="w-[150px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {parseResult.columns.map((col) => (
                            <SelectItem key={col} value={col}>
                              {col}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Select
                        value={filter.operator}
                        onValueChange={(v) => updateFilter(index, "operator", v)}
                      >
                        <SelectTrigger className="w-[130px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {FILTER_OPERATORS.map((op) => (
                            <SelectItem key={op.value} value={op.value}>
                              {op.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      <Input
                        placeholder="Value..."
                        value={filter.value}
                        onChange={(e) => updateFilter(index, "value", e.target.value)}
                        className="flex-1"
                      />

                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeFilter(index)}
                        className="text-red-500 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 5: AI Categorize */}
          {step === "categorize" && parseResult && (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4 rounded-lg border p-4">
                <div className="space-y-1">
                  <Label className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    Auto-categorize with AI
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Suggest a category for transactions that don&apos;t already have one,
                    using the whole row as context. Review and adjust below before importing.
                  </p>
                </div>
                <Switch
                  checked={aiEnabled}
                  onCheckedChange={(checked) => setAiEnabled(checked)}
                />
              </div>

              {aiEnabled && !aiFetched && !aiLoading && (
                <div className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
                  <p>Suggest categories for uncategorized transactions using AI.</p>
                  <Button onClick={fetchSuggestions} disabled={isLoading}>
                    <Sparkles className="h-4 w-4 mr-2" /> Suggest Categories
                  </Button>
                </div>
              )}

              {aiEnabled && aiLoading && (
                <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Analyzing transactions…
                </div>
              )}

              {aiEnabled && !aiLoading && aiQuotaExceeded && (
                <div className="flex items-center gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-700">
                  <AlertCircle className="h-4 w-4" />
                  AI quota reached — some rows were left uncategorized.
                </div>
              )}

              {aiEnabled && !aiLoading && aiFetched && suggestions.length === 0 && (
                <div className="py-12 text-center text-muted-foreground">
                  <p>No uncategorized transactions to suggest.</p>
                </div>
              )}

              {aiEnabled && !aiLoading && suggestions.length > 0 && (
                <>
                <p className="text-xs text-muted-foreground">
                  Keep a <span className="font-medium">keyword</span> to teach this category for every
                  transaction containing it — now and on future imports. Clear it to apply the
                  category to this row only.
                </p>
                <div className="border rounded-lg overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Description</TableHead>
                        <TableHead className="whitespace-nowrap text-right"># Txns</TableHead>
                        <TableHead className="w-[160px]">Apply to (keyword)</TableHead>
                        <TableHead className="w-[190px]">Category</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {suggestions.map((s) => (
                        <TableRow key={s.key}>
                          <TableCell className="max-w-[520px]" title={s.signature}>
                            <div className="flex items-center gap-2">
                              <span className="truncate">{s.signature}</span>
                              {s.source === "rule" && (
                                <Badge variant="secondary" className="shrink-0 gap-1">
                                  <Sparkles className="h-3 w-3" /> learned
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">{s.count}</TableCell>
                          <TableCell>
                            <Input
                              value={keywords[s.key] ?? ""}
                              placeholder="(this row only)"
                              onChange={(e) =>
                                setKeywords({ ...keywords, [s.key]: e.target.value })
                              }
                              className="h-9"
                            />
                          </TableCell>
                          <TableCell>
                            <Select
                              value={aiOverrides[s.key] || UNCATEGORIZED_VALUE}
                              onValueChange={(v) =>
                                setAiOverrides({
                                  ...aiOverrides,
                                  [s.key]: v === UNCATEGORIZED_VALUE ? "" : v,
                                })
                              }
                            >
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={UNCATEGORIZED_VALUE}>Uncategorized</SelectItem>
                                {categories.map((c) => (
                                  <SelectItem key={c.id} value={c.id}>
                                    <span className="flex items-center gap-2">
                                      <DynamicIcon name={c.icon} className="h-3.5 w-3.5" />
                                      {c.name}
                                    </span>
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                </>
              )}

              {!aiEnabled && (
                <div className="py-12 text-center text-muted-foreground">
                  <p>AI categorization is off. Transactions will import with their mapped category (if any).</p>
                </div>
              )}
            </div>
          )}

          {/* Step 6: Review */}
          {step === "review" && parseResult && (
            <div className="space-y-4">
              {!executeResult ? (
                <>
                  <div className="grid gap-4">
                    <Card>
                      <CardContent className="p-4">
                        <h4 className="font-medium mb-2">Import Summary</h4>
                        <dl className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">File:</dt>
                            <dd>{file?.name}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Total Rows:</dt>
                            <dd>{parseResult.total_rows}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Amount Mode:</dt>
                            <dd>{AMOUNT_MODES.find((m) => m.value === amountConfig.mode)?.label}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Filters:</dt>
                            <dd>{filters.length > 0 ? `${filters.length} filter(s)` : "None"}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">AI Categorization:</dt>
                            <dd>
                              {aiEnabled && suggestions.length > 0
                                ? `${Object.values(aiOverrides).filter((id) => id).length}/${suggestions.length} categorized`
                                : "Off"}
                            </dd>
                          </div>
                        </dl>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardContent className="p-4">
                        <h4 className="font-medium mb-2">Column Mapping</h4>
                        <dl className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Amount:</dt>
                            <dd>{columnMapping.amount}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-muted-foreground">Date:</dt>
                            <dd>{columnMapping.date}</dd>
                          </div>
                          {columnMapping.note && columnMapping.note.length > 0 && (
                            <div className="flex justify-between">
                              <dt className="text-muted-foreground">Note:</dt>
                              <dd>{columnMapping.note.join(" - ")}</dd>
                            </div>
                          )}
                          {columnMapping.category && columnMapping.category !== "__none__" && (
                            <div className="flex justify-between">
                              <dt className="text-muted-foreground">Category:</dt>
                              <dd>{columnMapping.category}</dd>
                            </div>
                          )}
                          {columnMapping.tags && columnMapping.tags !== "__none__" && (
                            <div className="flex justify-between">
                              <dt className="text-muted-foreground">Tags:</dt>
                              <dd>{columnMapping.tags}</dd>
                            </div>
                          )}
                        </dl>
                      </CardContent>
                    </Card>
                  </div>
                </>
              ) : (
                <div className="space-y-4">
                  {executeResult.success ? (
                    <div className="text-center py-4">
                      <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center mb-4">
                        <Check className="h-8 w-8 text-green-600" />
                      </div>
                      <h3 className="text-lg font-medium text-green-600">Import Complete!</h3>
                    </div>
                  ) : (
                    <div className="text-center py-4">
                      <div className="w-16 h-16 mx-auto bg-red-100 rounded-full flex items-center justify-center mb-4">
                        <X className="h-8 w-8 text-red-600" />
                      </div>
                      <h3 className="text-lg font-medium text-red-600">Import Failed</h3>
                      <p className="text-sm text-muted-foreground">{executeResult.error}</p>
                    </div>
                  )}

                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-medium mb-2">Results</h4>
                      <dl className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <dt className="text-muted-foreground">Total Rows:</dt>
                          <dd>{executeResult.stats.total_rows}</dd>
                        </div>
                        <div className="flex justify-between text-green-600">
                          <dt>Imported:</dt>
                          <dd>{executeResult.stats.imported}</dd>
                        </div>
                        <div className="flex justify-between text-yellow-600">
                          <dt>Skipped (Filtered):</dt>
                          <dd>{executeResult.stats.skipped_filtered}</dd>
                        </div>
                        <div className="flex justify-between text-yellow-600">
                          <dt>Skipped (Duplicates):</dt>
                          <dd>{executeResult.stats.skipped_duplicates}</dd>
                        </div>
                        <div className="flex justify-between text-red-600">
                          <dt>Errors:</dt>
                          <dd>{executeResult.stats.errors}</dd>
                        </div>
                      </dl>
                    </CardContent>
                  </Card>

                  {executeResult.created_categories.length > 0 && (
                    <Card>
                      <CardContent className="p-4">
                        <h4 className="font-medium mb-2">New Categories Created</h4>
                        <div className="flex flex-wrap gap-1">
                          {executeResult.created_categories.map((cat) => (
                            <span
                              key={cat}
                              className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm"
                            >
                              {cat}
                            </span>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {executeResult.created_tags.length > 0 && (
                    <Card>
                      <CardContent className="p-4">
                        <h4 className="font-medium mb-2">New Tags Created</h4>
                        <div className="flex flex-wrap gap-1">
                          {executeResult.created_tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-1 bg-green-100 text-green-700 rounded text-sm"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {executeResult.errors.length > 0 && (
                    <Card>
                      <CardContent className="p-4">
                        <h4 className="font-medium mb-2 text-red-600 flex items-center gap-2">
                          <AlertCircle className="h-4 w-4" /> Errors
                        </h4>
                        <div className="max-h-40 overflow-y-auto space-y-1 text-sm">
                          {executeResult.errors.map((err, i) => (
                            <p key={i} className="text-red-600">
                              Row {err.row}: {err.error}
                            </p>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <div className="shrink-0 mx-6 mb-2 text-sm text-red-600 bg-red-50 p-3 rounded-md flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between shrink-0 border-t px-6 py-4">
          <div>
            {step !== "upload" && !executeResult && (
              <Button
                variant="outline"
                onClick={() => {
                  const idx = getCurrentStepIndex();
                  if (idx > 0) goToStep(STEPS[idx - 1].key);
                }}
                disabled={isLoading}
              >
                <ArrowLeft className="h-4 w-4 mr-2" /> Back
              </Button>
            )}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleClose} disabled={isLoading}>
              {executeResult ? "Close" : "Cancel"}
            </Button>

            {step === "upload" && (
              <Button onClick={handleParse} disabled={!file || isLoading}>
                {isLoading ? "Parsing..." : "Continue"}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}

            {step === "mapping" && (
              <Button
                onClick={() => goToStep("amount")}
                disabled={!canProceedFromMapping() || isLoading}
              >
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}

            {step === "amount" && (
              <Button
                onClick={() => goToStep("filters")}
                disabled={!canProceedFromAmount() || isLoading}
              >
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}

            {step === "filters" && (
              <Button onClick={() => goToStep("categorize")} disabled={isLoading}>
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}

            {step === "categorize" && (
              <Button onClick={() => goToStep("review")} disabled={isLoading}>
                Continue
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}

            {step === "review" && !executeResult && (
              <Button onClick={handleExecute} disabled={isLoading}>
                {isLoading ? "Importing..." : "Import Transactions"}
              </Button>
            )}

            {step === "review" && executeResult && executeResult.success && (
              <Button onClick={handleClose}>Done</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
