# Implementation Plan: Tags & Categories Features

## Overview
Add enhanced features for Categories and Tags in the budgeting app:
- **Predefined categories** (seeded in DB, copy-on-edit)
- **Visibility toggles** (hide from dropdowns, show on existing transactions)
- **Icons** (Lucide icons for both categories and tags)
- **Colors** (already exists for categories, add to tags)

---

## Phase 1: Backend Model Changes

### Files to modify:
- `/backend/wallets/models.py`

### Changes:

**UserTransactionCategory** - Add fields:
```python
# Allow NULL user for predefined categories (shared across all users)
user = models.ForeignKey(User, ..., null=True, blank=True)

# NEW fields
is_predefined = models.BooleanField(default=False)  # System-provided category
is_visible = models.BooleanField(default=True)      # Toggle visibility
```

**UserTransactionTag** - Add fields:
```python
icon = models.CharField(max_length=50, blank=True)   # Lucide icon name
color = models.CharField(max_length=7, default='#3B82F6')
is_visible = models.BooleanField(default=True)
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

### Migration:
```bash
python manage.py makemigrations wallets --name add_category_tag_features
python manage.py migrate
```

---

## Phase 2: Backend Management Command

### Files to create:
- `/backend/wallets/management/__init__.py`
- `/backend/wallets/management/commands/__init__.py`
- `/backend/wallets/management/commands/seed_categories.py`

### Predefined categories to seed:
| Name | Icon | Color |
|------|------|-------|
| Salary | banknote | #22C55E |
| Freelance | laptop | #10B981 |
| Investments | trending-up | #059669 |
| Gifts Received | gift | #14B8A6 |
| Groceries | shopping-cart | #F97316 |
| Dining Out | utensils | #FB923C |
| Transportation | car | #EAB308 |
| Entertainment | tv | #A855F7 |
| Shopping | shopping-bag | #EC4899 |
| Healthcare | heart-pulse | #EF4444 |
| Utilities | zap | #6366F1 |
| Rent/Mortgage | home | #8B5CF6 |
| Insurance | shield | #0EA5E9 |
| Education | graduation-cap | #06B6D4 |
| Personal Care | sparkles | #D946EF |
| Gifts Given | gift | #F472B6 |
| Subscriptions | repeat | #64748B |
| Travel | plane | #0284C7 |
| Other | more-horizontal | #6B7280 |

Run: `python manage.py seed_categories`

---

## Phase 3: Backend Serializers

### Files to modify:
- `/backend/wallets/serializers.py`

### Changes:

**CategorySerializer**:
- Add `is_predefined`, `is_visible` to fields
- Make `is_predefined` read-only

**TagSerializer**:
- Add `icon`, `color`, `is_visible` to fields

---

## Phase 4: Backend Views

### Files to modify:
- `/backend/wallets/views.py`

### Changes:

**UserCategoryList.get_queryset()**:
- Return user's categories + predefined categories (where `user=None`)
- Add `?include_hidden=true` query param support
- Filter by `is_visible` unless include_hidden

**UserCategoryDetail.perform_update()**:
- Implement copy-on-write for predefined categories:
  - If updating predefined → create user-specific copy
  - If user already has copy → update existing copy

**UserCategoryDetail.perform_destroy()**:
- Prevent deletion of predefined categories
- Soft delete (archive) user categories

**UserTagList.get_queryset()**:
- Add `?include_hidden=true` query param support

### DRF Educational Comments to include:
- Why ForeignKey (one-to-many relationships)
- Why ModelSerializer (automatic field generation, validation)
- Why generics.* vs ViewSet (explicit URLs, learning-friendly)
- Permission classes vs queryset filtering (access vs data isolation)
- Soft delete pattern benefits
- Copy-on-write pattern explanation

---

## Phase 5: Frontend TypeScript Models

### Files to modify:
- `/frontend/models/wallets.ts`

### Changes:
```typescript
interface Category {
  // ... existing
  is_predefined: boolean;  // NEW
  is_visible: boolean;     // NEW
}

interface Tag {
  // ... existing
  icon: string;        // NEW
  color: string;       // NEW
  is_visible: boolean; // NEW
}
```

---

## Phase 6: Frontend Icon Picker Component

### Files to create:
- `/frontend/components/IconPicker.tsx`

### Features:
- Popover with searchable grid of Lucide icons
- Curated list of ~60 budget-relevant icons
- `DynamicIcon` helper component to render icon by name
- Uses existing Command component for search

---

## Phase 7: Frontend Color Picker Component

### Files to create:
- `/frontend/components/ColorPicker.tsx`

### Features:
- Popover with color grid (25 predefined colors)
- Custom hex input field
- Color preview swatch

---

## Phase 8: Frontend Settings Page

### Files to modify:
- `/frontend/app/settings/page.tsx`

### Changes:
- Add visibility toggle column (Eye/EyeOff icons)
- Display icon + color in table rows
- Show lock icon for predefined categories
- Add IconPicker and ColorPicker to create/edit dialogs
- Show warning when editing predefined category
- Fetch with `?include_hidden=true`

---

## Phase 9: Frontend Transaction Dialog

### Files to modify:
- `/frontend/components/TransactionDialog.tsx`

### Changes:
- Filter categories/tags by `is_visible` in dropdowns
- BUT include transaction's current category/tags even if hidden
- Display icon + color in dropdown items
- Show EyeOff indicator for hidden items (when shown)

---

## Phase 10: Frontend Transaction List

### Files to modify:
- `/frontend/app/wallet/[id]/page.tsx`

### Changes:
- Display category with icon + color badge
- Display tags as colored pills with icons

---

## File Summary

| Action | File |
|--------|------|
| CREATE | `/backend/wallets/management/__init__.py` |
| CREATE | `/backend/wallets/management/commands/__init__.py` |
| CREATE | `/backend/wallets/management/commands/seed_categories.py` |
| MODIFY | `/backend/wallets/models.py` |
| MODIFY | `/backend/wallets/serializers.py` |
| MODIFY | `/backend/wallets/views.py` |
| CREATE | `/frontend/components/IconPicker.tsx` |
| CREATE | `/frontend/components/ColorPicker.tsx` |
| MODIFY | `/frontend/models/wallets.ts` |
| MODIFY | `/frontend/app/settings/page.tsx` |
| MODIFY | `/frontend/components/TransactionDialog.tsx` |
| MODIFY | `/frontend/app/wallet/[id]/page.tsx` |

---

## Complexity Estimates

| Feature | Priority | Complexity |
|---------|----------|------------|
| Categories (predefined, toggle, icons/colors) | 5 | 3 |
| Tags (icons, colors, toggle) | 5 | 2 |

Total estimated phases: 10
Backend: Phases 1-4
Frontend: Phases 5-10

---

## Testing Checklist

- [ ] Migration runs without errors
- [ ] Seed command creates predefined categories
- [ ] User sees predefined + own categories
- [ ] Editing predefined creates user copy
- [ ] Toggle visibility hides from dropdowns
- [ ] Hidden categories still show on existing transactions
- [ ] Icon picker works
- [ ] Color picker works
- [ ] Tags have icon/color/visibility
- [ ] Transaction list shows icons/colors
