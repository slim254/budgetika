"""
Default categories that are created for each new user.

These categories are copied to the user's account on registration,
giving them a starting set they can customize, delete, or extend.
"""

DEFAULT_CATEGORIES = [
    # Income categories (green shades)
    {'name': 'Salary', 'icon': 'banknote', 'color': '#22C55E'},
    {'name': 'Freelance', 'icon': 'laptop', 'color': '#10B981'},
    {'name': 'Investments', 'icon': 'trending-up', 'color': '#059669'},
    {'name': 'Gifts Received', 'icon': 'gift', 'color': '#14B8A6'},

    # Expense categories (various colors for visual distinction)
    {'name': 'Groceries', 'icon': 'shopping-cart', 'color': '#F97316'},
    {'name': 'Dining Out', 'icon': 'utensils', 'color': '#FB923C'},
    {'name': 'Transportation', 'icon': 'car', 'color': '#EAB308'},
    {'name': 'Entertainment', 'icon': 'tv', 'color': '#A855F7'},
    {'name': 'Shopping', 'icon': 'shopping-bag', 'color': '#EC4899'},
    {'name': 'Healthcare', 'icon': 'heart-pulse', 'color': '#EF4444'},
    {'name': 'Utilities', 'icon': 'zap', 'color': '#6366F1'},
    {'name': 'Rent/Mortgage', 'icon': 'home', 'color': '#8B5CF6'},
    {'name': 'Insurance', 'icon': 'shield', 'color': '#0EA5E9'},
    {'name': 'Education', 'icon': 'graduation-cap', 'color': '#06B6D4'},
    {'name': 'Personal Care', 'icon': 'sparkles', 'color': '#D946EF'},
    {'name': 'Gifts Given', 'icon': 'gift', 'color': '#F472B6'},
    {'name': 'Subscriptions', 'icon': 'repeat', 'color': '#64748B'},
    {'name': 'Travel', 'icon': 'plane', 'color': '#0284C7'},
    {'name': 'Other', 'icon': 'more-horizontal', 'color': '#6B7280'},
]
