"use client";

import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check } from "lucide-react";

// Predefined color palette
const COLOR_PALETTE = [
  // Row 1 - Reds/Oranges
  "#EF4444",
  "#F97316",
  "#FB923C",
  "#FBBF24",
  "#F59E0B",
  // Row 2 - Yellows/Greens
  "#EAB308",
  "#84CC16",
  "#22C55E",
  "#10B981",
  "#059669",
  // Row 3 - Teals/Blues
  "#14B8A6",
  "#06B6D4",
  "#0EA5E9",
  "#0284C7",
  "#3B82F6",
  // Row 4 - Indigos/Purples
  "#6366F1",
  "#8B5CF6",
  "#A855F7",
  "#D946EF",
  "#EC4899",
  // Row 5 - Pinks/Grays
  "#F472B6",
  "#FB7185",
  "#64748B",
  "#6B7280",
  "#9CA3AF",
];

interface ColorPickerProps {
  value: string;
  onChange: (color: string) => void;
  disabled?: boolean;
}

export function ColorPicker({ value, onChange, disabled }: ColorPickerProps) {
  const [open, setOpen] = useState(false);
  const [customColor, setCustomColor] = useState(value || "#6B7280");

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="w-full justify-start"
          disabled={disabled}
        >
          <div
            className="w-6 h-6 rounded border mr-2"
            style={{ backgroundColor: value || "#6B7280" }}
          />
          {value || "#6B7280"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-3" align="start">
        <div className="space-y-3">
          {/* Color Grid */}
          <div className="grid grid-cols-5 gap-2">
            {COLOR_PALETTE.map((color) => (
              <button
                key={color}
                type="button"
                className={`w-10 h-10 rounded-lg border-2 flex items-center justify-center transition-transform hover:scale-110 ${
                  value === color ? "border-primary" : "border-transparent"
                }`}
                style={{ backgroundColor: color }}
                onClick={() => {
                  onChange(color);
                  setOpen(false);
                }}
              >
                {value === color && (
                  <Check className="h-5 w-5 text-white drop-shadow-md" />
                )}
              </button>
            ))}
          </div>

          {/* Divider */}
          <div className="border-t" />

          {/* Custom Color Input */}
          <div className="flex gap-2">
            <div
              className="w-10 h-10 rounded border shrink-0"
              style={{ backgroundColor: customColor }}
            />
            <Input
              type="text"
              placeholder="#000000"
              value={customColor}
              onChange={(e) => {
                const newColor = e.target.value;
                setCustomColor(newColor);
                // Only apply if it's a valid hex color
                if (/^#[0-9A-Fa-f]{6}$/.test(newColor)) {
                  onChange(newColor);
                }
              }}
              className="font-mono"
            />
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
