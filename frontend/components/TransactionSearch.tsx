"use client";

import { useEffect, useRef, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Category, SearchFilters, Tag } from "@/models/wallets";

const EMPTY_FILTERS: SearchFilters = {
  category: "",
  tag: "",
  date_from: "",
  date_to: "",
  min_amount: "",
  max_amount: "",
};

interface TransactionSearchProps {
  categories: Category[];
  tags: Tag[];
  onSearch: (query: string, filters: SearchFilters) => void;
}

export function TransactionSearch({ categories, tags, onSearch }: TransactionSearchProps) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS);
  const [sheetOpen, setSheetOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search query — fire onSearch 400ms after user stops typing
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch(query, filters);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  function handleApply() {
    setSheetOpen(false);
    onSearch(query, filters);
  }

  function handleClearAll() {
    const cleared = EMPTY_FILTERS;
    setFilters(cleared);
    setSheetOpen(false);
    onSearch(query, cleared);
  }

  function setFilter<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search notes..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <Button variant="outline" size="sm" className="relative">
            <SlidersHorizontal className="mr-2 h-4 w-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="ml-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </SheetTrigger>

        <SheetContent className="w-80">
          <SheetHeader>
            <SheetTitle>Filter transactions</SheetTitle>
          </SheetHeader>

          <div className="mt-6 flex flex-col gap-5">
            {/* Category */}
            <div className="flex flex-col gap-1.5">
              <Label>Category</Label>
              <Select
                value={filters.category || "all"}
                onValueChange={(v) => setFilter("category", v === "all" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any category</SelectItem>
                  {categories.filter((c) => !c.is_archived).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Tag */}
            <div className="flex flex-col gap-1.5">
              <Label>Tag</Label>
              <Select
                value={filters.tag || "all"}
                onValueChange={(v) => setFilter("tag", v === "all" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any tag" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any tag</SelectItem>
                  {tags.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Date range */}
            <div className="flex flex-col gap-1.5">
              <Label>Date from</Label>
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilter("date_from", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Date to</Label>
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilter("date_to", e.target.value)}
              />
            </div>

            {/* Amount range */}
            <div className="flex flex-col gap-1.5">
              <Label>Min amount</Label>
              <Input
                type="number"
                placeholder="e.g. -500"
                value={filters.min_amount}
                onChange={(e) => setFilter("min_amount", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Max amount</Label>
              <Input
                type="number"
                placeholder="e.g. 0"
                value={filters.max_amount}
                onChange={(e) => setFilter("max_amount", e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Button onClick={handleApply}>Apply filters</Button>
              {activeFilterCount > 0 && (
                <Button variant="ghost" onClick={handleClearAll}>
                  Clear all
                </Button>
              )}
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
