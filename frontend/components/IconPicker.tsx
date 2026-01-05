"use client";

import { useState, useMemo } from "react";
import * as LucideIcons from "lucide-react";
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
  CommandList,
} from "@/components/ui/command";
import { Button } from "@/components/ui/button";

// Curated list of icons suitable for budgeting categories
const BUDGET_ICONS = [
  // Income
  "banknote",
  "wallet",
  "piggy-bank",
  "coins",
  "credit-card",
  "landmark",
  // Shopping
  "shopping-cart",
  "shopping-bag",
  "store",
  "tag",
  "percent",
  // Food & Dining
  "utensils",
  "coffee",
  "pizza",
  "apple",
  "wine",
  // Transportation
  "car",
  "bus",
  "train",
  "plane",
  "bike",
  "fuel",
  // Home
  "home",
  "bed",
  "sofa",
  "lamp",
  "key",
  // Health
  "heart-pulse",
  "pill",
  "stethoscope",
  "activity",
  // Entertainment
  "tv",
  "gamepad-2",
  "music",
  "film",
  "ticket",
  "popcorn",
  // Education
  "graduation-cap",
  "book-open",
  "pen",
  "library",
  // Communication
  "phone",
  "smartphone",
  "wifi",
  "monitor",
  // Personal
  "sparkles",
  "scissors",
  "shirt",
  "glasses",
  // Travel
  "map",
  "compass",
  "luggage",
  "tent",
  "sun",
  // Utilities
  "zap",
  "droplet",
  "flame",
  "thermometer",
  // Finance
  "trending-up",
  "trending-down",
  "bar-chart",
  "pie-chart",
  // Other
  "gift",
  "heart",
  "star",
  "briefcase",
  "building",
  "shield",
  "lock",
  "repeat",
  "calendar",
  "clock",
  "more-horizontal",
  "circle",
  "square",
  "triangle",
];

interface IconPickerProps {
  value: string;
  onChange: (icon: string) => void;
  disabled?: boolean;
}

// Helper to convert kebab-case to PascalCase for Lucide components
function toPascalCase(str: string): string {
  return str
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join("");
}

// Get the Lucide icon component by name
function getIconComponent(
  iconName: string
): React.ComponentType<{ className?: string; style?: React.CSSProperties }> | null {
  if (!iconName) return null;
  const pascalName = toPascalCase(iconName);
  const IconComponent = (
    LucideIcons as Record<
      string,
      React.ComponentType<{ className?: string; style?: React.CSSProperties }>
    >
  )[pascalName];
  return IconComponent || null;
}

export function IconPicker({ value, onChange, disabled }: IconPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filteredIcons = useMemo(() => {
    if (!search) return BUDGET_ICONS;
    return BUDGET_ICONS.filter((icon) =>
      icon.toLowerCase().includes(search.toLowerCase())
    );
  }, [search]);

  const SelectedIcon = value ? getIconComponent(value) : null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          <span className="flex items-center gap-2">
            {SelectedIcon && <SelectedIcon className="h-4 w-4" />}
            {value || "Select icon..."}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[300px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search icons..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>No icon found.</CommandEmpty>
            <CommandGroup>
              <div className="grid grid-cols-6 gap-1 p-2">
                {filteredIcons.map((iconName) => {
                  const IconComponent = getIconComponent(iconName);
                  if (!IconComponent) return null;

                  return (
                    <button
                      key={iconName}
                      type="button"
                      className={`p-2 rounded hover:bg-accent flex items-center justify-center ${
                        value === iconName
                          ? "bg-accent ring-2 ring-primary"
                          : ""
                      }`}
                      onClick={() => {
                        onChange(iconName);
                        setOpen(false);
                        setSearch("");
                      }}
                      title={iconName}
                    >
                      <IconComponent className="h-5 w-5" />
                    </button>
                  );
                })}
              </div>
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

// Utility component to render an icon by name
export function DynamicIcon({
  name,
  className = "h-4 w-4",
  style,
}: {
  name: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const IconComponent = getIconComponent(name);
  if (!IconComponent) {
    // Fallback to Circle if icon not found
    return <LucideIcons.Circle className={className} style={style} />;
  }
  return <IconComponent className={className} style={style} />;
}
