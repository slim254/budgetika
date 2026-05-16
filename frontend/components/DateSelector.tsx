"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

interface DateSelectorProps {
  onDateChange?: (params: {
    month?: string;
    year?: string;
    date_from?: string;
    date_to?: string;
  }) => void;
}

export default function DateSelector({ onDateChange }: DateSelectorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const currentDate = new Date();
  const currentMonth = String(currentDate.getMonth() + 1).padStart(2, "0");
  const currentYear = String(currentDate.getFullYear());

  const month = searchParams.get("month") || currentMonth;
  const year = searchParams.get("year") || currentYear;

  // Date range mode state
  const [rangeMode, setRangeMode] = useState(false);
  const [dateFrom, setDateFrom] = useState<Date | undefined>(undefined);
  const [dateTo, setDateTo] = useState<Date | undefined>(undefined);

  const goToPreviousMonth = () => {
    let newMonth = parseInt(month) - 1;
    let newYear = parseInt(year);

    if (newMonth < 1) {
      newMonth = 12;
      newYear -= 1;
    }

    const monthStr = String(newMonth).padStart(2, "0");
    router.push(`?month=${monthStr}&year=${newYear}`);
    onDateChange?.({ month: monthStr, year: String(newYear) });
  };

  const goToNextMonth = () => {
    let newMonth = parseInt(month) + 1;
    let newYear = parseInt(year);

    if (newMonth > 12) {
      newMonth = 1;
      newYear += 1;
    }

    const monthStr = String(newMonth).padStart(2, "0");
    router.push(`?month=${monthStr}&year=${newYear}`);
    onDateChange?.({ month: monthStr, year: String(newYear) });
  };

  const goToCurrentMonth = () => {
    router.push(`?month=${currentMonth}&year=${currentYear}`);
    onDateChange?.({ month: currentMonth, year: currentYear });
  };

  const formatDateForAPI = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const handleDateFromChange = (date: Date | undefined) => {
    if (date && dateTo && date > dateTo) {
      alert("Start date must be before end date");
      return;
    }
    setDateFrom(date);
  };

  const handleDateToChange = (date: Date | undefined) => {
    if (date && dateFrom && date < dateFrom) {
      alert("End date must be after start date");
      return;
    }
    setDateTo(date);
  };

  const handleApplyDateRange = () => {
    if (dateFrom && dateTo) {
      const fromStr = formatDateForAPI(dateFrom);
      const toStr = formatDateForAPI(dateTo);
      router.push(`?date_from=${fromStr}&date_to=${toStr}`);
      onDateChange?.({ date_from: fromStr, date_to: toStr });
      setRangeMode(false);
    }
  };

  const handleClearDateRange = () => {
    setDateFrom(undefined);
    setDateTo(undefined);
  };

  if (rangeMode) {
    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <label className="text-sm font-medium">From</label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start">
                  {dateFrom
                    ? dateFrom.toLocaleDateString()
                    : "Pick a start date"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={dateFrom}
                  onSelect={handleDateFromChange}
                  disabled={(date) =>
                    dateTo ? date > dateTo : false
                  }
                />
              </PopoverContent>
            </Popover>
          </div>

          <div className="flex-1">
            <label className="text-sm font-medium">To</label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start">
                  {dateTo ? dateTo.toLocaleDateString() : "Pick an end date"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={dateTo}
                  onSelect={handleDateToChange}
                  disabled={(date) =>
                    dateFrom ? date < dateFrom : false
                  }
                />
              </PopoverContent>
            </Popover>
          </div>
        </div>

        <div className="flex gap-2 justify-end">
          <Button
            variant="outline"
            onClick={() => setRangeMode(false)}
          >
            Back to Month
          </Button>
          <Button
            variant="outline"
            onClick={handleClearDateRange}
          >
            Clear
          </Button>
          <Button
            onClick={handleApplyDateRange}
            disabled={!dateFrom || !dateTo}
          >
            Apply
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between">
      <Button variant="outline" size="icon" onClick={goToPreviousMonth}>
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <div className="flex flex-col items-center gap-2">
        <h2 className="text-xl font-semibold">
          {new Date(parseInt(year), parseInt(month) - 1).toLocaleString(
            "default",
            { month: "long", year: "numeric" }
          )}
        </h2>
        <div className="flex gap-2">
          <Button variant="link" size="sm" onClick={goToCurrentMonth}>
            Today
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setRangeMode(true)}
            className="gap-1"
          >
            Custom Range
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Button variant="outline" size="icon" onClick={goToNextMonth}>
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}
