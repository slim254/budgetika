"use client";

import { useState, useRef } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import {
  CSVParseResponse,
  CSVColumnMapping,
  AmountConfig,
  AmountMode,
  FilterRule,
  FilterOperator,
  CSVExecuteResponse,
} from "@/models/wallets";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

interface CSVImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  onImported: () => void;
  walletId: string;
}

type Step = "upload" | "mapping" | "amount" | "filters" | "review";

const STEPS: { key: Step; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "mapping", label: "Map Columns" },
  { key: "amount", label: "Amount Config" },
  { key: "filters", label: "Filters" },
  { key: "review", label: "Review" },
];

const FILTER_OPERATORS: { value: FilterOperator; label: string }[] = [
  { value: "equals", label: "Equals" },
  { value: "not_equals", label: "Not Equals" },
  { value: "contains", label: "Contains" },
  { value: "not_contains", label: "Not Contains" },
];

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
  const [parseResult, setParseResult] = useState<CSVParseResponse | null>(null);

  // Column mapping state (use special "__none__" value for optional fields)
  const [columnMapping, setColumnMapping] = useState<CSVColumnMapping>({
    amount: "",
    date: "",
    note: "__none__",
    category: "__none__",
    tags: "__none__",
    type: "__none__",
  });

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

  function resetState() {
    setStep("upload");
    setFile(null);
    setParseResult(null);
    setColumnMapping({ amount: "", date: "", note: "__none__", category: "__none__", tags: "__none__", type: "__none__" });
    setAmountConfig({ mode: "signed", income_value: "", expense_value: "" });
    setFilters([]);
    setExecuteResult(null);
    setError("");
    setIsLoading(false);
  }

  function handleClose() {
    resetState();
    onClose();
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
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
      }
    } catch (err) {
      console.error("Failed to parse CSV:", err);
      setError("Failed to parse CSV file. Please check the format.");
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
    mapping.note = "__none__";
    for (const col of columns) {
      if (noteKeywords.some((k) => col.toLowerCase().includes(k))) {
        mapping.note = col;
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

  async function handleExecute() {
    if (!file) return;

    setIsLoading(true);
    setError("");

    try {
      // Convert "__none__" back to empty string or undefined for backend
      const cleanedMapping: Record<string, string> = { ...columnMapping };
      Object.keys(cleanedMapping).forEach(key => {
        if (cleanedMapping[key] === "__none__") {
          cleanedMapping[key] = "";
        }
      });

      console.log("Sending import data:", {
        cleanedMapping,
        amountConfig,
        filters,
      });

      const formData = new FormData();
      formData.append("file", file);
      formData.append("column_mapping", JSON.stringify(cleanedMapping));
      formData.append("amount_config", JSON.stringify(amountConfig));
      formData.append("filters", JSON.stringify(filters));

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
      <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import Transactions from CSV</DialogTitle>
          <DialogDescription>
            Upload a CSV file and map columns to import transactions.
          </DialogDescription>
        </DialogHeader>

        {/* Progress Steps */}
        <div className="flex items-center justify-between mb-6">
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
        <div className="min-h-[300px]">
          {/* Step 1: Upload */}
          {step === "upload" && (
            <div className="space-y-4">
              <div
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                  file ? "border-green-500 bg-green-50" : "border-muted-foreground/25 hover:border-primary"
                )}
                onClick={() => fileInputRef.current?.click()}
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
                  <Label>Note Column (Optional)</Label>
                  <Select
                    value={columnMapping.note || "__none__"}
                    onValueChange={(v) => setColumnMapping({ ...columnMapping, note: v })}
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

          {/* Step 5: Review */}
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
                          {columnMapping.note && columnMapping.note !== "__none__" && (
                            <div className="flex justify-between">
                              <dt className="text-muted-foreground">Note:</dt>
                              <dd>{columnMapping.note}</dd>
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
          <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex justify-between pt-4 border-t">
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
