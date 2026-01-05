"use client";

import { useState, useEffect, FormEvent } from "react";
import { axiosInstance } from "@/api/axiosInstance";
import { Transaction, Category, Tag, Currency, TransactionFormData } from "@/models/wallets";
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
import { Switch } from "@/components/ui/switch";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Check, ChevronsUpDown, Plus, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { DynamicIcon } from "@/components/IconPicker";
import { useMemo } from "react";

interface TransactionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  onSaved: () => void;
  onCategoriesChanged: () => void;
  onTagsChanged: () => void;
  transaction: Transaction | null;
  walletId: string;
  categories: Category[];
  tags: Tag[];
  currency: Currency;
  keepOpen: boolean;
  onKeepOpenChange: (keepOpen: boolean) => void;
}

export function TransactionDialog({
  open,
  onOpenChange,
  onClose,
  onSaved,
  onCategoriesChanged,
  onTagsChanged,
  transaction,
  walletId,
  categories,
  tags,
  currency,
  keepOpen,
  onKeepOpenChange,
}: TransactionDialogProps) {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  // Track type separately since we need to apply it to amount sign
  const [transactionType, setTransactionType] = useState<"income" | "expense">("expense");
  const [formData, setFormData] = useState<TransactionFormData>({
    note: "",
    amount: 0,  // Always stored as positive in form, sign applied on submit
    currency: currency,
    date: new Date().toISOString().split("T")[0],
    category: null,
    tag_ids: [],
  });

  // Category combobox state
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState("");

  // Create category dialog state
  const [createCategoryOpen, setCreateCategoryOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [createCategoryError, setCreateCategoryError] = useState("");

  // Tag combobox state
  const [tagOpen, setTagOpen] = useState(false);
  const [tagSearch, setTagSearch] = useState("");

  // Create tag dialog state
  const [createTagOpen, setCreateTagOpen] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [isCreatingTag, setIsCreatingTag] = useState(false);
  const [createTagError, setCreateTagError] = useState("");

  // Filter to only show visible categories in dropdown
  // BUT still show the transaction's current category even if hidden
  const visibleCategories = useMemo(() => {
    const visible = categories.filter(cat => cat.is_visible);

    // If editing and current category is hidden, include it
    if (transaction?.category && !transaction.category.is_visible) {
      const currentCategory = categories.find(c => c.id === transaction.category?.id);
      if (currentCategory && !visible.find(c => c.id === currentCategory.id)) {
        return [currentCategory, ...visible];
      }
    }

    return visible;
  }, [categories, transaction]);

  // Filter categories based on search (from visible categories)
  const filteredCategories = visibleCategories.filter((cat) =>
    cat.name.toLowerCase().includes(categorySearch.toLowerCase())
  );

  // Check if "uncategorized" matches the search
  const showUncategorized = !categorySearch ||
    "uncategorized".includes(categorySearch.toLowerCase());

  // Show create option when searching and no exact match exists
  const showCreateOption = categorySearch.trim() &&
    !categories.some((cat) => cat.name.toLowerCase() === categorySearch.toLowerCase().trim());

  // Get selected category name for display
  const selectedCategory = categories.find((cat) => cat.id === formData.category);

  // Filter to only show visible tags in dropdown
  // BUT still show currently selected hidden tags
  const visibleTags = useMemo(() => {
    const visible = tags.filter(tag => tag.is_visible);

    // Include currently selected hidden tags
    if (formData.tag_ids.length > 0) {
      const hiddenSelectedTags = tags.filter(
        t => !t.is_visible && formData.tag_ids.includes(t.id)
      );
      return [...hiddenSelectedTags, ...visible];
    }

    return visible;
  }, [tags, formData.tag_ids]);

  // Filter tags based on search (from visible tags)
  const filteredTags = visibleTags.filter((tag) =>
    tag.name.toLowerCase().includes(tagSearch.toLowerCase())
  );

  // Show create tag option when searching and no exact match exists
  const showCreateTagOption = tagSearch.trim() &&
    !tags.some((tag) => tag.name.toLowerCase() === tagSearch.toLowerCase().trim());

  // Get selected tags for display
  const selectedTags = tags.filter((tag) => formData.tag_ids.includes(tag.id));

  async function handleCreateCategory() {
    if (!newCategoryName.trim()) {
      setCreateCategoryError("Category name is required");
      return;
    }

    setIsCreatingCategory(true);
    setCreateCategoryError("");

    try {
      const response = await axiosInstance.post<Category>("wallets/categories/", {
        name: newCategoryName.trim(),
      });
      // Select the newly created category
      setFormData({ ...formData, category: response.data.id });
      setCreateCategoryOpen(false);
      setNewCategoryName("");
      setCategorySearch("");
      onCategoriesChanged(); // Refresh categories list
    } catch (err) {
      console.error("Failed to create category:", err);
      setCreateCategoryError("Failed to create category. Please try again.");
    } finally {
      setIsCreatingCategory(false);
    }
  }

  function handleOpenCreateCategory() {
    setNewCategoryName(categorySearch); // Pre-fill with current search
    setCategoryOpen(false);
    setCreateCategoryOpen(true);
  }

  async function handleCreateTag() {
    if (!newTagName.trim()) {
      setCreateTagError("Tag name is required");
      return;
    }

    setIsCreatingTag(true);
    setCreateTagError("");

    try {
      const response = await axiosInstance.post<Tag>("wallets/tags/", {
        name: newTagName.trim(),
      });
      // Add the newly created tag to selected tags
      setFormData({ ...formData, tag_ids: [...formData.tag_ids, response.data.id] });
      setCreateTagOpen(false);
      setNewTagName("");
      setTagSearch("");
      onTagsChanged(); // Refresh tags list
    } catch (err) {
      console.error("Failed to create tag:", err);
      setCreateTagError("Failed to create tag. Please try again.");
    } finally {
      setIsCreatingTag(false);
    }
  }

  function handleOpenCreateTag() {
    setNewTagName(tagSearch); // Pre-fill with current search
    setTagOpen(false);
    setCreateTagOpen(true);
  }

  function handleToggleTag(tagId: string) {
    if (formData.tag_ids.includes(tagId)) {
      setFormData({ ...formData, tag_ids: formData.tag_ids.filter(id => id !== tagId) });
    } else {
      setFormData({ ...formData, tag_ids: [...formData.tag_ids, tagId] });
    }
  }

  // Reset form when dialog opens or transaction changes
  useEffect(() => {
    if (open) {
      if (transaction) {
        // Determine type from amount sign
        const isIncome = Number(transaction.amount) > 0;
        setTransactionType(isIncome ? "income" : "expense");
        setFormData({
          note: transaction.note,
          amount: Math.abs(Number(transaction.amount)),  // Store absolute value in form
          currency: transaction.currency,
          date: transaction.date.split("T")[0],  // Handle ISO date format
          category: transaction.category?.id || null,
          tag_ids: transaction.tags?.map(t => t.id) || [],
        });
      } else {
        setTransactionType("expense");
        setFormData({
          note: "",
          amount: 0,
          currency: currency,
          date: new Date().toISOString().split("T")[0],
          category: null,
          tag_ids: [],
        });
      }
      setError("");
      setFieldErrors({});
      setCategorySearch("");
      setTagSearch("");
    }
  }, [transaction, currency, open]);

  function validateForm(): boolean {
    const errors: Record<string, string> = {};

    if (!formData.amount || formData.amount <= 0) {
      errors.amount = "Amount is required and must be greater than 0";
    }

    if (!formData.date) {
      errors.date = "Date is required";
    }

    if (!formData.note.trim()) {
      errors.note = "Note is required";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function clearFieldError(field: string) {
    if (fieldErrors[field]) {
      setFieldErrors(prev => {
        const updated = { ...prev };
        delete updated[field];
        return updated;
      });
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      // Apply sign based on transaction type
      const signedAmount = transactionType === "expense"
        ? -Math.abs(formData.amount)
        : Math.abs(formData.amount);

      const payload = {
        note: formData.note,
        amount: signedAmount,
        currency: formData.currency,
        date: formData.date,
        category_id: formData.category,  // Backend expects category_id for write
        tag_ids: formData.tag_ids,  // Backend expects tag_ids for write
        wallet: walletId,
      };

      if (transaction) {
        await axiosInstance.put(`transactions/${transaction.id}/`, payload);
        onSaved();
        onClose();
      } else {
        await axiosInstance.post("transactions/", payload);
        onSaved();

        if (keepOpen) {
          // Reset form for next entry, keep dialog open
          setFormData({
            note: "",
            amount: 0,
            currency: currency,
            date: new Date().toISOString().split("T")[0],
            category: formData.category, // Keep category for convenience
            tag_ids: formData.tag_ids, // Keep tags for convenience
          });
          // Don't close - user can continue adding
        } else {
          onClose();
        }
      }
    } catch (err) {
      console.error("Failed to save transaction:", err);
      setError("Failed to save transaction. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {transaction ? "Edit Transaction" : "Add Transaction"}
          </DialogTitle>
          <DialogDescription>
            {transaction
              ? "Update the details of your transaction."
              : "Add a new transaction to your wallet."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="transaction_type">Type</Label>
            <Select
              value={transactionType}
              onValueChange={(value: "income" | "expense") => setTransactionType(value)}
            >
              <SelectTrigger id="transaction_type">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="income">Income</SelectItem>
                <SelectItem value="expense">Expense</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="amount">Amount</Label>
            <Input
              id="amount"
              name="amount"
              type="number"
              step="0.01"
              min="0"
              placeholder="0.00"
              value={formData.amount || ""}
              onChange={(e) => {
                setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 });
                clearFieldError("amount");
              }}
              disabled={isLoading}
              className={fieldErrors.amount ? "border-red-500" : ""}
            />
            {fieldErrors.amount && (
              <p className="text-sm text-red-600">{fieldErrors.amount}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="date">Date</Label>
            <Input
              id="date"
              name="date"
              type="date"
              value={formData.date}
              onChange={(e) => {
                setFormData({ ...formData, date: e.target.value });
                clearFieldError("date");
              }}
              disabled={isLoading}
              className={fieldErrors.date ? "border-red-500" : ""}
            />
            {fieldErrors.date && (
              <p className="text-sm text-red-600">{fieldErrors.date}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Category (Optional)</Label>
            <Popover open={categoryOpen} onOpenChange={setCategoryOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={categoryOpen}
                  className="w-full justify-between font-normal"
                  disabled={isLoading}
                >
                  {selectedCategory ? (
                    <span className="flex items-center gap-2">
                      <div
                        className="w-5 h-5 rounded flex items-center justify-center"
                        style={{ backgroundColor: selectedCategory.color + "20" }}
                      >
                        <DynamicIcon
                          name={selectedCategory.icon || "circle"}
                          className="h-3 w-3"
                          style={{ color: selectedCategory.color }}
                        />
                      </div>
                      {selectedCategory.name}
                    </span>
                  ) : (
                    "Select category..."
                  )}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                <Command shouldFilter={false}>
                  <CommandInput
                    placeholder="Search categories..."
                    value={categorySearch}
                    onValueChange={setCategorySearch}
                  />
                  <CommandList>
                    {!showUncategorized && filteredCategories.length === 0 && !showCreateOption && (
                      <CommandEmpty>No category found.</CommandEmpty>
                    )}
                    <CommandGroup>
                      {showUncategorized && (
                        <CommandItem
                          value=""
                          onSelect={() => {
                            setFormData({ ...formData, category: null });
                            setCategoryOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              !formData.category ? "opacity-100" : "opacity-0"
                            )}
                          />
                          Uncategorized
                        </CommandItem>
                      )}
                      {filteredCategories.map((cat) => (
                        <CommandItem
                          key={cat.id}
                          value={cat.id}
                          onSelect={() => {
                            setFormData({ ...formData, category: cat.id });
                            setCategoryOpen(false);
                            setCategorySearch("");
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.category === cat.id ? "opacity-100" : "opacity-0"
                            )}
                          />
                          <div
                            className="w-5 h-5 rounded mr-2 flex items-center justify-center"
                            style={{ backgroundColor: cat.color + "20" }}
                          >
                            <DynamicIcon
                              name={cat.icon || "circle"}
                              className="h-3 w-3"
                              style={{ color: cat.color }}
                            />
                          </div>
                          {cat.name}
                          {!cat.is_visible && (
                            <EyeOff className="h-3 w-3 ml-auto text-muted-foreground" />
                          )}
                        </CommandItem>
                      ))}
                      {showCreateOption && (
                        <CommandItem
                          onSelect={handleOpenCreateCategory}
                          className="text-primary"
                        >
                          <Plus className="mr-2 h-4 w-4" />
                          Create &ldquo;{categorySearch}&rdquo;
                        </CommandItem>
                      )}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>

          <div className="space-y-2">
            <Label>Tags (Optional)</Label>
            <Popover open={tagOpen} onOpenChange={setTagOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={tagOpen}
                  className="w-full justify-between font-normal"
                  disabled={isLoading}
                >
                  {selectedTags.length > 0 ? (
                    <span className="flex items-center gap-1 flex-wrap">
                      {selectedTags.slice(0, 3).map(t => (
                        <span
                          key={t.id}
                          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs"
                          style={{ backgroundColor: t.color + "20", color: t.color }}
                        >
                          <DynamicIcon name={t.icon || "tag"} className="h-3 w-3" />
                          {t.name}
                        </span>
                      ))}
                      {selectedTags.length > 3 && (
                        <span className="text-xs text-muted-foreground">
                          +{selectedTags.length - 3} more
                        </span>
                      )}
                    </span>
                  ) : (
                    "Select tags..."
                  )}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                <Command shouldFilter={false}>
                  <CommandInput
                    placeholder="Search tags..."
                    value={tagSearch}
                    onValueChange={setTagSearch}
                  />
                  <CommandList>
                    {filteredTags.length === 0 && !showCreateTagOption && (
                      <CommandEmpty>No tags found.</CommandEmpty>
                    )}
                    <CommandGroup>
                      {filteredTags.map((tag) => (
                        <CommandItem
                          key={tag.id}
                          value={tag.id}
                          onSelect={() => handleToggleTag(tag.id)}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.tag_ids.includes(tag.id) ? "opacity-100" : "opacity-0"
                            )}
                          />
                          <div
                            className="w-5 h-5 rounded mr-2 flex items-center justify-center"
                            style={{ backgroundColor: tag.color + "20" }}
                          >
                            <DynamicIcon
                              name={tag.icon || "tag"}
                              className="h-3 w-3"
                              style={{ color: tag.color }}
                            />
                          </div>
                          {tag.name}
                          {!tag.is_visible && (
                            <EyeOff className="h-3 w-3 ml-auto text-muted-foreground" />
                          )}
                        </CommandItem>
                      ))}
                      {showCreateTagOption && (
                        <CommandItem
                          onSelect={handleOpenCreateTag}
                          className="text-primary"
                        >
                          <Plus className="mr-2 h-4 w-4" />
                          Create &ldquo;{tagSearch}&rdquo;
                        </CommandItem>
                      )}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {selectedTags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {selectedTags.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                    style={{ backgroundColor: tag.color + "20", color: tag.color }}
                  >
                    <DynamicIcon name={tag.icon || "tag"} className="h-3 w-3" />
                    {tag.name}
                    <button
                      type="button"
                      onClick={() => handleToggleTag(tag.id)}
                      className="hover:opacity-70"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="note">Note</Label>
            <Input
              id="note"
              name="note"
              type="text"
              placeholder="e.g., Grocery shopping"
              value={formData.note}
              onChange={(e) => {
                setFormData({ ...formData, note: e.target.value });
                clearFieldError("note");
              }}
              disabled={isLoading}
              className={fieldErrors.note ? "border-red-500" : ""}
            />
            {fieldErrors.note && (
              <p className="text-sm text-red-600">{fieldErrors.note}</p>
            )}
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between pt-4">
            {!transaction && (
              <div className="flex items-center gap-2">
                <Switch
                  id="keep-open"
                  checked={keepOpen}
                  onCheckedChange={onKeepOpenChange}
                />
                <Label htmlFor="keep-open" className="text-sm text-muted-foreground cursor-pointer">
                  Keep open
                </Label>
              </div>
            )}
            <div className={`flex gap-3 ${transaction ? 'ml-auto' : ''}`}>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading
                  ? "Saving..."
                  : transaction
                  ? "Update Transaction"
                  : "Add Transaction"}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>

    {/* Create Category Dialog - separate from main dialog to avoid nesting issues */}
    <Dialog open={createCategoryOpen} onOpenChange={setCreateCategoryOpen}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Create Category</DialogTitle>
          <DialogDescription>
            Add a new category for your transactions.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="new-category-name">Name</Label>
            <Input
              id="new-category-name"
              placeholder="e.g., Groceries"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCreateCategory();
                }
              }}
              disabled={isCreatingCategory}
              autoFocus
            />
          </div>
          {createCategoryError && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
              {createCategoryError}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => setCreateCategoryOpen(false)}
            disabled={isCreatingCategory}
          >
            Cancel
          </Button>
          <Button onClick={handleCreateCategory} disabled={isCreatingCategory}>
            {isCreatingCategory ? "Creating..." : "Create"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>

    {/* Create Tag Dialog */}
    <Dialog open={createTagOpen} onOpenChange={setCreateTagOpen}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>Create Tag</DialogTitle>
          <DialogDescription>
            Add a new tag for your transactions.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="new-tag-name">Name</Label>
            <Input
              id="new-tag-name"
              placeholder="e.g., vacation"
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleCreateTag();
                }
              }}
              disabled={isCreatingTag}
              autoFocus
            />
          </div>
          {createTagError && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
              {createTagError}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            onClick={() => setCreateTagOpen(false)}
            disabled={isCreatingTag}
          >
            Cancel
          </Button>
          <Button onClick={handleCreateTag} disabled={isCreatingTag}>
            {isCreatingTag ? "Creating..." : "Create"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
