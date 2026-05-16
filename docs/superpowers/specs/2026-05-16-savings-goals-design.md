# Savings Goals Design

**Date:** 2026-05-16  
**Priority:** 3 (Complements budgets; natural next engagement hook)  
**Complexity:** 3

---

## Overview

Savings Goals is a financial planning feature that helps users track progress toward known future expenses. Instead of manually managing multiple savings targets, users list their upcoming expenses (wedding gift, insurance, Christmas) with target dates, and the system calculates the required monthly savings rate to cover all of them combined. The app alerts users when they fall short and recalculates if deadlines are missed.

**Key Insight:** Savings goals are *expense forecasts*, not allocations. They don't lock money away — they just show "if you want to cover all your upcoming costs, you need to save €X/month."

---

## Data Model

### `SavingsGoal`

```python
class SavingsGoal(models.Model):
    id = UUIDField(primary_key=True, default=uuid4, editable=False)
    wallet = ForeignKey(Wallet, on_delete=models.CASCADE, related_name="savings_goals")
    name = CharField(max_length=255)  # e.g., "Wedding gift", "Car insurance"
    target_amount = DecimalField(max_digits=12, decimal_places=2)  # e.g., 500.00
    target_date = DateField()  # e.g., 2026-05-25
    created_at = DateTimeField(auto_now_add=True)
    status = CharField(
        max_length=20,
        choices=[("active", "Active"), ("completed", "Completed"), ("missed", "Missed")],
        default="active"
    )
    updated_at = DateTimeField(auto_now=True)
```

**Notes:**
- Goals are per-wallet (consistent with transactions, budgets)
- No `initial_allocation` or explicit fund tracking — goals are purely informational
- Status is computed/managed by the system, not user-editable directly

---

## Calculations

### Monthly Savings Needed (Per Goal)

For an active goal:
```
days_until = (target_date - today).days
months_until = max(1, ceil(days_until / 30.44))  # Use 30.44 as avg month length
monthly_needed = target_amount / months_until
```

If `target_date` is in the past, status → "missed".

### Total Monthly Savings (Per Wallet)

```
total_monthly_needed = sum(goal.monthly_needed for goal in active_goals)
```

### Actual Savings (Per Wallet, This Month)

For current month:
```
income = sum(tx.amount for tx in wallet.transactions if tx.amount > 0 and tx.date in current_month)
expenses = sum(abs(tx.amount) for tx in wallet.transactions if tx.amount < 0 and tx.date in current_month)
actual_savings = income - expenses
```

### Progress Status

```
difference = actual_savings - total_monthly_needed

if difference >= 0:
    status = "on_track"
    surplus = difference
else:
    status = "short"
    shortfall = abs(difference)
```

Surplus carries forward to next month's required savings calculation.

---

## API Endpoints

### Goals CRUD

```
GET    /api/wallets/{wallet_id}/goals/
       → List all goals for wallet (active, completed, missed)
       → Response: [{ id, name, target_amount, target_date, status, monthly_needed, created_at }, ...]

POST   /api/wallets/{wallet_id}/goals/
       → Create a new goal
       → Body: { name, target_amount, target_date }
       → Response: { id, name, target_amount, target_date, status, monthly_needed, created_at }

PATCH  /api/wallets/{wallet_id}/goals/{goal_id}/
       → Update goal (name, target_amount, target_date)
       → Body: { name?, target_amount?, target_date? }
       → Response: updated goal object

DELETE /api/wallets/{wallet_id}/goals/{goal_id}/
       → Delete a goal (soft-delete or hard-delete — see edge cases)
       → Response: 204 No Content
```

### Summary Endpoint

```
GET    /api/wallets/{wallet_id}/goals/summary/?month=M&year=Y
       → Get monthly savings summary for a specific month
       → Response: {
           "month": 5,
           "year": 2026,
           "total_monthly_needed": 843.50,
           "actual_savings": 750.00,
           "difference": -93.50,
           "status": "short",  // "on_track" or "short"
           "goals": [
             {
               "id": "...",
               "name": "Wedding gift",
               "target_amount": 500.00,
               "target_date": "2026-05-25",
               "monthly_needed": 500.00,
               "status": "active"
             },
             ...
           ]
         }
```

---

## Frontend Components

### `SavingsGoalsPanel`

Displays on the wallet page (similar to `BudgetPanel`):
- **Summary card:** "You need to save €843/month. This month: €750 saved. (€93 short)" with status badge
- **Goals list:** Each goal shows:
  - Goal name
  - Target date (relative: "in 2 weeks", "in 3 months")
  - Target amount
  - Monthly savings needed (calculated)
  - Progress indicator (simple bar or text)
  - Status badge (active/completed/missed)
  - Edit/delete icons (hover actions)
- **"Add goal" button**

### `SavingsGoalDialog`

Modal for create/edit:
- Text input: goal name
- Currency-aware decimal input: target amount (inherits wallet currency)
- Date picker: target date (calendar or text input)
- Submit/cancel buttons
- Validation: target_date must be in future; target_amount > 0

### Integration Point

Goals section appears on the wallet page, likely below the `BudgetPanel` or in a tab alongside it.

---

## Behavior & Edge Cases

### Status Transitions

| Scenario | Status | Behavior |
|----------|--------|----------|
| Goal created with future date | active | Show in list; include in monthly calculation |
| Goal date reached; user still has time | active | Update `monthly_needed` dynamically |
| Goal date passed; not edited | missed | Mark as missed; remove from calculation; show warning |
| User deletes goal | — | Remove from wallet.goals; recalculate summary |
| User edits target_date | active | Recalculate `monthly_needed` immediately |
| Actual savings >= total needed | — | Show "on_track" badge; no alert |
| Actual savings < total needed | — | Show "short" badge; alert/highlight in UI |

### Handling "Missed" Goals

If a goal's `target_date` has passed and status is still "active":
- System (via serializer or view logic) marks it "missed"
- Display: "Missed on [date]. This goal is no longer included in your savings target."
- User can delete it or edit the target_date to extend it

### Handling Multiple Goals

If you have:
- Goal A: €500 in 1 month (€500/month needed)
- Goal B: €1200 in 12 months (€100/month needed)
- **Total: €600/month needed**

If you save €700 this month:
- You're on track (€100 surplus)
- Surplus carries forward to next month's calculation (next month you'd need €600 - €100 = €500 to stay on pace)
- Surplus is noted in UI but doesn't auto-allocate to any specific goal

### Hard vs. Soft Delete

**Soft delete** (recommended): Mark goal as deleted (soft-delete flag `is_deleted`); exclude from calculations but preserve history.  
**Hard delete**: Remove completely (simpler; user can recreate if needed).

Decision: **Hard delete** for MVP — simpler to implement and matches the "remove and re-add if needed" user model.

### Editing an Active Goal

If user edits a goal (e.g., increases target amount):
- `monthly_needed` recalculates immediately
- Summary updates in real-time
- No retroactive recalculation of past months

---

## Business Logic

### Serializer (`SavingsGoalSerializer`)

- Validate: `target_date` must be in future (or present day) at creation
- Compute: `monthly_needed` in `to_representation()` based on days until target
- Validate: `target_amount` > 0
- Validate: Wallet exists and belongs to authenticated user

### View Logic (`SavingsGoalViewSet`)

- Filter goals by wallet
- Enforce wallet access control (users see only their own wallets' goals)
- Mark goals as "missed" if target_date < today during GET requests
- Summary endpoint aggregates all active goals, calculates actual_savings from transaction data

---

## Testing

### Unit Tests

- Goal creation with valid/invalid dates
- Monthly savings calculation (edge cases: 1 month away, 12 months away)
- Multiple goals: total_monthly_needed is sum of individual monthly_needed
- Actual savings calculation: income - expenses for a given month
- Status badge logic: on_track vs. short

### Integration Tests

- Create goal → verify it appears in summary
- Edit goal → verify monthly_needed updates in summary
- Delete goal → verify it's removed from summary
- Missed goal detection: create goal with past target_date → verify status = "missed"

### Frontend Tests

- Goal creation form: submit valid/invalid data
- Summary card: shows correct total_monthly_needed and actual_savings
- Status badge: displays correct color/text based on on_track vs. short
- Multiple goals: panel shows all; edit/delete actions work

---

## Future Considerations

- **Recurring goals:** E.g., "Save for Christmas gifts every year" (recurs annually)
- **Milestones:** Break a goal into sub-milestones ("€1k by Oct, €2k by Nov, €5k by Dec")
- **Goal categories:** Tag goals (e.g., "travel", "home", "health") for better organization
- **Notifications:** Email or in-app alert if you fall short for 2 consecutive months
- **Historical tracking:** Archive completed goals; show "goals completed this year" stat

---

## Summary

Savings Goals is a lightweight financial planning layer that sits above transactions and budgets. It answers the question: "If I want to cover all my upcoming expenses, how much do I need to save each month?" No complex allocation mechanics — just clear, forward-looking progress tracking.
