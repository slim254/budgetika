from decimal import Decimal
from datetime import date as date_type, timedelta, datetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import SavingsGoal, Wallet, Transaction
from wallets.services import SavingsGoalService


def make_client(user):
    """Create an authenticated API client for a user."""
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class TestSavingsGoalModel(TestCase):
    """Tests for SavingsGoal model creation, ordering, and fields."""

    def setUp(self):
        self.user = User.objects.create_user(username="model_tester", password="pass")
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=Decimal("1000")
        )

    def test_create_savings_goal(self):
        """Test basic goal creation with required fields."""
        target_date = date_type.today() + timedelta(days=365)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Vacation Fund",
            target_amount=Decimal("5000.00"),
            target_date=target_date,
        )
        self.assertEqual(goal.name, "Vacation Fund")
        self.assertEqual(goal.target_amount, Decimal("5000.00"))
        self.assertEqual(goal.target_date, target_date)
        self.assertEqual(goal.status, "active")
        self.assertIsNotNone(goal.id)

    def test_goal_has_uuid_primary_key(self):
        """Test that goal ID is a UUID."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() + timedelta(days=30),
        )
        self.assertIsNotNone(goal.id)
        # UUID fields have a specific format
        self.assertTrue(len(str(goal.id)) == 36)  # UUID string length with hyphens

    def test_goal_default_status_is_active(self):
        """Test that new goals default to 'active' status."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() + timedelta(days=30),
        )
        self.assertEqual(goal.status, "active")

    def test_goal_can_have_completed_status(self):
        """Test that goal status can be set to 'completed'."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() + timedelta(days=30),
            status="completed",
        )
        self.assertEqual(goal.status, "completed")

    def test_goal_can_have_missed_status(self):
        """Test that goal status can be set to 'missed'."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() - timedelta(days=1),
            status="missed",
        )
        self.assertEqual(goal.status, "missed")

    def test_goals_ordered_by_target_date(self):
        """Test that goals are ordered by target_date."""
        today = date_type.today()
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="First Goal",
            target_amount=Decimal("1000.00"),
            target_date=today + timedelta(days=60),
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Second Goal",
            target_amount=Decimal("2000.00"),
            target_date=today + timedelta(days=30),
        )
        goal3 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Third Goal",
            target_amount=Decimal("3000.00"),
            target_date=today + timedelta(days=90),
        )

        ordered_goals = SavingsGoal.objects.all()
        self.assertEqual(ordered_goals[0].id, goal2.id)
        self.assertEqual(ordered_goals[1].id, goal1.id)
        self.assertEqual(ordered_goals[2].id, goal3.id)

    def test_goal_timestamps(self):
        """Test that created_at and updated_at are set."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() + timedelta(days=30),
        )
        self.assertIsNotNone(goal.created_at)
        self.assertIsNotNone(goal.updated_at)
        # created_at and updated_at should be very close (within 1 second)
        self.assertLess(abs((goal.created_at - goal.updated_at).total_seconds()), 1)

    def test_goal_string_representation(self):
        """Test __str__ method."""
        target_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Vacation",
            target_amount=Decimal("5000.00"),
            target_date=target_date,
        )
        expected_str = f"Vacation ({target_date})"
        self.assertEqual(str(goal), expected_str)

    def test_goal_on_delete_cascade(self):
        """Test that goals are deleted when wallet is deleted."""
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=date_type.today() + timedelta(days=30),
        )
        goal_id = goal.id
        self.wallet.delete()
        self.assertFalse(SavingsGoal.objects.filter(id=goal_id).exists())


class TestSavingsGoalService(TestCase):
    """Tests for SavingsGoalService calculations."""

    def setUp(self):
        self.user = User.objects.create_user(username="service_tester", password="pass")
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=Decimal("1000")
        )

    def test_months_until_today(self):
        """Test months_until for a target date today."""
        today = date_type.today()
        months = SavingsGoalService.get_months_until(today)
        self.assertEqual(months, 1)

    def test_months_until_tomorrow(self):
        """Test months_until for a target date tomorrow."""
        tomorrow = date_type.today() + timedelta(days=1)
        months = SavingsGoalService.get_months_until(tomorrow)
        self.assertEqual(months, 1)

    def test_months_until_30_days(self):
        """Test months_until for ~30 days in the future."""
        future = date_type.today() + timedelta(days=30)
        months = SavingsGoalService.get_months_until(future)
        self.assertEqual(months, 1)

    def test_months_until_60_days(self):
        """Test months_until for ~60 days in the future."""
        future = date_type.today() + timedelta(days=60)
        months = SavingsGoalService.get_months_until(future)
        self.assertEqual(months, 2)

    def test_months_until_365_days(self):
        """Test months_until for ~365 days in the future."""
        future = date_type.today() + timedelta(days=365)
        months = SavingsGoalService.get_months_until(future)
        self.assertEqual(months, 12)

    def test_months_until_past_date_returns_zero(self):
        """Test months_until for a past date returns 0."""
        past = date_type.today() - timedelta(days=10)
        months = SavingsGoalService.get_months_until(past)
        self.assertEqual(months, 0)

    def test_monthly_needed_single_goal(self):
        """Test monthly_needed calculation for a single goal."""
        target_date = date_type.today() + timedelta(days=30)
        monthly_needed = SavingsGoalService.get_monthly_needed(
            Decimal("1000.00"), target_date
        )
        # Should be roughly 1000 / 1 = 1000
        self.assertEqual(monthly_needed, Decimal("1000.00"))

    def test_monthly_needed_two_months(self):
        """Test monthly_needed for a two-month goal."""
        target_date = date_type.today() + timedelta(days=60)
        monthly_needed = SavingsGoalService.get_monthly_needed(
            Decimal("2000.00"), target_date
        )
        # Should be roughly 2000 / 2 = 1000
        self.assertEqual(monthly_needed, Decimal("1000.00"))

    def test_monthly_needed_zero_months_returns_zero(self):
        """Test monthly_needed for a past target date returns 0."""
        target_date = date_type.today() - timedelta(days=10)
        monthly_needed = SavingsGoalService.get_monthly_needed(
            Decimal("1000.00"), target_date
        )
        self.assertEqual(monthly_needed, Decimal("0"))

    def test_monthly_needed_decimal_amounts(self):
        """Test monthly_needed with decimal amounts is properly quantized."""
        target_date = date_type.today() + timedelta(days=90)
        monthly_needed = SavingsGoalService.get_monthly_needed(
            Decimal("1500.75"), target_date
        )
        # Should have exactly 2 decimal places
        self.assertEqual(monthly_needed.as_tuple().exponent, -2)

    def test_get_total_monthly_needed_no_goals(self):
        """Test get_total_monthly_needed with empty list."""
        total = SavingsGoalService.get_total_monthly_needed([])
        self.assertEqual(total, Decimal("0"))

    def test_get_total_monthly_needed_single_goal(self):
        """Test get_total_monthly_needed with one goal."""
        target_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("1000.00"),
            target_date=target_date,
        )
        total = SavingsGoalService.get_total_monthly_needed([goal])
        self.assertEqual(total, Decimal("1000.00"))

    def test_get_total_monthly_needed_multiple_goals(self):
        """Test get_total_monthly_needed sums multiple goals."""
        target_date = date_type.today() + timedelta(days=30)
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("1000.00"),
            target_date=target_date,
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 2",
            target_amount=Decimal("2000.00"),
            target_date=target_date,
        )
        total = SavingsGoalService.get_total_monthly_needed([goal1, goal2])
        self.assertEqual(total, Decimal("3000.00"))

    def test_get_actual_savings_no_transactions(self):
        """Test get_actual_savings with no transactions returns 0."""
        actual = SavingsGoalService.get_actual_savings(self.wallet, 2024, 1)
        self.assertEqual(actual, Decimal("0"))

    def test_get_actual_savings_income_only(self):
        """Test get_actual_savings with only income."""
        today = date_type.today()
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Salary",
            amount=Decimal("3000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, today.year, today.month
        )
        self.assertEqual(actual, Decimal("3000.00"))

    def test_get_actual_savings_expenses_only(self):
        """Test get_actual_savings with only expenses."""
        today = date_type.today()
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Grocery",
            amount=Decimal("-500.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, today.year, today.month
        )
        self.assertEqual(actual, Decimal("-500.00"))

    def test_get_actual_savings_income_and_expenses(self):
        """Test get_actual_savings with both income and expenses."""
        today = date_type.today()
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Salary",
            amount=Decimal("3000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 1)),
        )
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Rent",
            amount=Decimal("-1000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 5)),
        )
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Grocery",
            amount=Decimal("-500.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, today.year, today.month
        )
        # 3000 - 1000 - 500 = 1500
        self.assertEqual(actual, Decimal("1500.00"))

    def test_get_actual_savings_ignores_other_months(self):
        """Test get_actual_savings filters by month/year correctly."""
        today = date_type.today()
        # Transaction in this month
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="This month",
            amount=Decimal("1000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        # Transaction in different month
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Different month",
            amount=Decimal("5000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(2023, 12, 15)),
        )
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, today.year, today.month
        )
        # Should only count transaction from this month
        self.assertEqual(actual, Decimal("1000.00"))

    def test_mark_missed_goals_past_targets(self):
        """Test mark_missed_goals marks expired active goals as missed."""
        past_date = date_type.today() - timedelta(days=10)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Old Goal",
            target_amount=Decimal("1000.00"),
            target_date=past_date,
            status="active",
        )
        SavingsGoalService.mark_missed_goals(self.wallet)
        goal.refresh_from_db()
        self.assertEqual(goal.status, "missed")

    def test_mark_missed_goals_ignores_future_targets(self):
        """Test mark_missed_goals doesn't affect future goals."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Future Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
            status="active",
        )
        SavingsGoalService.mark_missed_goals(self.wallet)
        goal.refresh_from_db()
        self.assertEqual(goal.status, "active")

    def test_mark_missed_goals_ignores_completed(self):
        """Test mark_missed_goals doesn't change completed goals."""
        past_date = date_type.today() - timedelta(days=10)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Completed Goal",
            target_amount=Decimal("1000.00"),
            target_date=past_date,
            status="completed",
        )
        SavingsGoalService.mark_missed_goals(self.wallet)
        goal.refresh_from_db()
        self.assertEqual(goal.status, "completed")

    def test_get_monthly_summary_structure(self):
        """Test get_monthly_summary returns expected structure."""
        today = date_type.today()
        summary = SavingsGoalService.get_monthly_summary(
            self.wallet, today.year, today.month
        )
        self.assertIn("month", summary)
        self.assertIn("year", summary)
        self.assertIn("total_monthly_needed", summary)
        self.assertIn("actual_savings", summary)
        self.assertIn("difference", summary)
        self.assertIn("status", summary)
        self.assertIn("goals", summary)

    def test_get_monthly_summary_values(self):
        """Test get_monthly_summary calculates correct values."""
        today = date_type.today()
        # Create a goal needing 1000/month
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        # Add income of 1500
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Income",
            amount=Decimal("1500.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )

        summary = SavingsGoalService.get_monthly_summary(
            self.wallet, today.year, today.month
        )
        self.assertEqual(summary["month"], today.month)
        self.assertEqual(summary["year"], today.year)
        self.assertEqual(summary["total_monthly_needed"], Decimal("1000.00"))
        self.assertEqual(summary["actual_savings"], Decimal("1500.00"))
        self.assertEqual(summary["difference"], Decimal("500.00"))
        self.assertEqual(summary["status"], "on_track")

    def test_get_monthly_summary_short_status(self):
        """Test get_monthly_summary returns 'short' when savings fall short."""
        today = date_type.today()
        # Create a goal needing 1000/month
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        # Add income of only 500
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Income",
            amount=Decimal("500.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )

        summary = SavingsGoalService.get_monthly_summary(
            self.wallet, today.year, today.month
        )
        self.assertEqual(summary["status"], "short")
        self.assertEqual(summary["difference"], Decimal("-500.00"))


class TestSavingsGoalSerializer(TestCase):
    """Tests for SavingsGoalSerializer validation."""

    def setUp(self):
        self.user = User.objects.create_user(username="serializer_tester", password="pass")
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=Decimal("1000")
        )

    def test_serializer_reads_all_fields(self):
        """Test serializer reads all expected fields."""
        from wallets.serializers import SavingsGoalSerializer

        target_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            target_date=target_date,
        )
        serializer = SavingsGoalSerializer(goal)
        data = serializer.data

        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("target_amount", data)
        self.assertIn("target_date", data)
        self.assertIn("status", data)
        self.assertIn("monthly_needed", data)
        self.assertIn("created_at", data)

    def test_serializer_monthly_needed_calculation(self):
        """Test serializer calculates monthly_needed correctly."""
        from wallets.serializers import SavingsGoalSerializer

        target_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            target_date=target_date,
        )
        serializer = SavingsGoalSerializer(goal)
        # monthly_needed should be roughly 1000
        self.assertEqual(serializer.data["monthly_needed"], Decimal("1000.00"))

    def test_serializer_validate_target_date_future(self):
        """Test target_date validation accepts future dates."""
        from wallets.serializers import SavingsGoalSerializer

        future_date = (date_type.today() + timedelta(days=30)).isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "1000.00",
            "target_date": future_date,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())

    def test_serializer_validate_target_date_today(self):
        """Test target_date validation accepts today's date."""
        from wallets.serializers import SavingsGoalSerializer

        today = date_type.today().isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "1000.00",
            "target_date": today,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())

    def test_serializer_validate_target_date_past_rejected(self):
        """Test target_date validation rejects past dates on create."""
        from wallets.serializers import SavingsGoalSerializer

        past_date = (date_type.today() - timedelta(days=1)).isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "1000.00",
            "target_date": past_date,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertFalse(serializer.is_valid())
        self.assertIn("target_date", serializer.errors)

    def test_serializer_validate_target_date_allows_past_on_update(self):
        """Test target_date validation allows past dates on update."""
        from wallets.serializers import SavingsGoalSerializer

        # Create goal with future date
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )

        # Update with past date should be allowed
        past_date = (date_type.today() - timedelta(days=1)).isoformat()
        data = {
            "target_date": past_date,
        }
        serializer = SavingsGoalSerializer(goal, data=data, partial=True, context={"request": None})
        self.assertTrue(serializer.is_valid())

    def test_serializer_validate_target_amount_positive(self):
        """Test target_amount validation requires positive amounts."""
        from wallets.serializers import SavingsGoalSerializer

        future_date = (date_type.today() + timedelta(days=30)).isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "1000.00",
            "target_date": future_date,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertTrue(serializer.is_valid())

    def test_serializer_validate_target_amount_zero_rejected(self):
        """Test target_amount validation rejects zero."""
        from wallets.serializers import SavingsGoalSerializer

        future_date = (date_type.today() + timedelta(days=30)).isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "0.00",
            "target_date": future_date,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertFalse(serializer.is_valid())
        self.assertIn("target_amount", serializer.errors)

    def test_serializer_validate_target_amount_negative_rejected(self):
        """Test target_amount validation rejects negative amounts."""
        from wallets.serializers import SavingsGoalSerializer

        future_date = (date_type.today() + timedelta(days=30)).isoformat()
        data = {
            "wallet": str(self.wallet.id),
            "name": "Test",
            "target_amount": "-1000.00",
            "target_date": future_date,
        }
        serializer = SavingsGoalSerializer(data=data, context={"request": None})
        self.assertFalse(serializer.is_valid())
        self.assertIn("target_amount", serializer.errors)

    def test_serializer_validate_wallet_ownership(self):
        """Test serializer validates wallet belongs to user."""
        from wallets.serializers import SavingsGoalSerializer
        from unittest.mock import Mock

        other_user = User.objects.create_user(username="other", password="pass")
        other_wallet = Wallet.objects.create(
            user=other_user, name="Other", currency="usd", initial_value=Decimal("0")
        )

        future_date = (date_type.today() + timedelta(days=30)).isoformat()
        data = {
            "wallet": str(other_wallet.id),
            "name": "Test",
            "target_amount": "1000.00",
            "target_date": future_date,
        }

        mock_request = Mock()
        mock_request.user = self.user
        serializer = SavingsGoalSerializer(
            data=data,
            context={"request": mock_request, "wallet": other_wallet},
        )
        self.assertFalse(serializer.is_valid())

    def test_serializer_read_only_fields(self):
        """Test that read-only fields cannot be set."""
        from wallets.serializers import SavingsGoalSerializer

        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )

        # Try to change read-only fields
        data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "status": "completed",
        }
        serializer = SavingsGoalSerializer(
            goal, data=data, partial=True, context={"request": None}
        )
        self.assertTrue(serializer.is_valid())
        # Fields should not have changed
        self.assertNotEqual(serializer.data["status"], "completed")


class TestSavingsGoalViewSet(TestCase):
    """Tests for SavingsGoal ViewSet CRUD operations and endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(username="viewset_tester", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=Decimal("1000")
        )
        self.other_user = User.objects.create_user(username="other_user", password="pass")
        self.other_wallet = Wallet.objects.create(
            user=self.other_user, name="Other Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.base_url = f"/api/wallets/{self.wallet.id}/goals/"

    def test_list_goals_requires_authentication(self):
        """Test list endpoint requires authentication."""
        client = APIClient()
        response = client.get(self.base_url)
        self.assertEqual(response.status_code, 401)

    def test_list_goals_empty(self):
        """Test list endpoint returns empty list when no goals exist."""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_list_goals_returns_user_goals_only(self):
        """Test list endpoint returns only authenticated user's goals."""
        # Create goal for this user
        future_date = date_type.today() + timedelta(days=30)
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )

        # Create goal for other user
        goal2 = SavingsGoal.objects.create(
            wallet=self.other_wallet,
            name="Goal 2",
            target_amount=Decimal("2000.00"),
            target_date=future_date,
        )

        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(str(response.data[0]["id"]), str(goal1.id))

    def test_create_goal_requires_authentication(self):
        """Test create endpoint requires authentication."""
        client = APIClient()
        data = {
            "name": "Test Goal",
            "target_amount": "1000.00",
            "target_date": (date_type.today() + timedelta(days=30)).isoformat(),
        }
        response = client.post(self.base_url, data, format="json")
        self.assertEqual(response.status_code, 401)

    def test_create_goal_success(self):
        """Test creating a goal successfully."""
        data = {
            "name": "Vacation Fund",
            "target_amount": "5000.00",
            "target_date": (date_type.today() + timedelta(days=365)).isoformat(),
        }
        response = self.client.post(self.base_url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Vacation Fund")
        # API returns amount as string, not Decimal
        self.assertEqual(response.data["target_amount"], "5000.00")
        self.assertEqual(response.data["status"], "active")
        self.assertIn("id", response.data)

    def test_create_goal_sets_wallet(self):
        """Test that create endpoint sets wallet from URL."""
        data = {
            "name": "Test Goal",
            "target_amount": "1000.00",
            "target_date": (date_type.today() + timedelta(days=30)).isoformat(),
        }
        response = self.client.post(self.base_url, data, format="json")
        self.assertEqual(response.status_code, 201)
        goal = SavingsGoal.objects.get(id=response.data["id"])
        self.assertEqual(goal.wallet.id, self.wallet.id)

    def test_create_goal_fails_for_other_users_wallet(self):
        """Test that create fails when wallet belongs to another user."""
        other_url = f"/api/wallets/{self.other_wallet.id}/goals/"
        data = {
            "name": "Test Goal",
            "target_amount": "1000.00",
            "target_date": (date_type.today() + timedelta(days=30)).isoformat(),
        }
        response = self.client.post(other_url, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_goal_validation_past_date(self):
        """Test that create fails with past target date."""
        data = {
            "name": "Test Goal",
            "target_amount": "1000.00",
            "target_date": (date_type.today() - timedelta(days=1)).isoformat(),
        }
        response = self.client.post(self.base_url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("target_date", response.data)

    def test_create_goal_validation_negative_amount(self):
        """Test that create fails with negative target amount."""
        data = {
            "name": "Test Goal",
            "target_amount": "-1000.00",
            "target_date": (date_type.today() + timedelta(days=30)).isoformat(),
        }
        response = self.client.post(self.base_url, data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("target_amount", response.data)

    def test_retrieve_goal_success(self):
        """Test retrieving a goal successfully."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"{self.base_url}{goal.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Test Goal")
        self.assertEqual(response.data["id"], str(goal.id))

    def test_retrieve_goal_not_found(self):
        """Test retrieving non-existent goal returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        url = f"{self.base_url}{fake_id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_goal_other_users_wallet_forbidden(self):
        """Test retrieving goal from other user's wallet returns 404."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.other_wallet,
            name="Other Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"/api/wallets/{self.other_wallet.id}/goals/{goal.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_update_goal_success(self):
        """Test updating a goal successfully."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Original Name",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"{self.base_url}{goal.id}/"
        data = {"name": "Updated Name"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Updated Name")
        goal.refresh_from_db()
        self.assertEqual(goal.name, "Updated Name")

    def test_update_goal_target_amount(self):
        """Test updating goal target amount."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"{self.base_url}{goal.id}/"
        data = {"target_amount": "2000.00"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        # API returns amount as string, not Decimal
        self.assertEqual(response.data["target_amount"], "2000.00")

    def test_update_goal_target_date(self):
        """Test updating goal target date."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"{self.base_url}{goal.id}/"
        new_date = (date_type.today() + timedelta(days=60)).isoformat()
        data = {"target_date": new_date}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 200)

    def test_update_goal_validation_negative_amount(self):
        """Test that update fails with negative amount."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"{self.base_url}{goal.id}/"
        data = {"target_amount": "-1000.00"}
        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_delete_goal_success(self):
        """Test deleting a goal successfully."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        goal_id = goal.id
        url = f"{self.base_url}{goal.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SavingsGoal.objects.filter(id=goal_id).exists())

    def test_delete_goal_not_found(self):
        """Test deleting non-existent goal returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        url = f"{self.base_url}{fake_id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_goal_other_users_wallet_forbidden(self):
        """Test deleting goal from other user's wallet returns 404."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.other_wallet,
            name="Other Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        url = f"/api/wallets/{self.other_wallet.id}/goals/{goal.id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)

    def test_summary_endpoint_requires_authentication(self):
        """Test summary endpoint requires authentication."""
        client = APIClient()
        url = f"{self.base_url}summary/?month=1&year=2024"
        response = client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_summary_endpoint_defaults_to_current_month(self):
        """Test summary endpoint uses current month/year if not specified."""
        url = f"{self.base_url}summary/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        today = date_type.today()
        self.assertEqual(response.data["month"], today.month)
        self.assertEqual(response.data["year"], today.year)

    def test_summary_endpoint_with_params(self):
        """Test summary endpoint with specified month/year."""
        url = f"{self.base_url}summary/?month=5&year=2024"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["month"], 5)
        self.assertEqual(response.data["year"], 2024)

    def test_summary_endpoint_structure(self):
        """Test summary endpoint returns expected structure."""
        url = f"{self.base_url}summary/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("month", response.data)
        self.assertIn("year", response.data)
        self.assertIn("total_monthly_needed", response.data)
        self.assertIn("actual_savings", response.data)
        self.assertIn("difference", response.data)
        self.assertIn("status", response.data)
        self.assertIn("goals", response.data)

    def test_summary_endpoint_includes_active_goals(self):
        """Test summary endpoint includes active goals."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Test Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        today = date_type.today()
        url = f"{self.base_url}summary/?month={today.month}&year={today.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["goals"]), 1)
        self.assertEqual(response.data["goals"][0]["id"], str(goal.id))

    def test_summary_endpoint_excludes_other_users_wallets(self):
        """Test summary endpoint only accesses user's own wallets."""
        url = f"/api/wallets/{self.other_wallet.id}/goals/summary/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_summary_endpoint_invalid_month_param(self):
        """Test summary endpoint with invalid month parameter."""
        url = f"{self.base_url}summary/?month=invalid&year=2024"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_summary_endpoint_invalid_year_param(self):
        """Test summary endpoint with invalid year parameter."""
        url = f"{self.base_url}summary/?month=5&year=invalid"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_summary_endpoint_monthly_needed_calculation(self):
        """Test summary endpoint calculates total_monthly_needed."""
        future_date = date_type.today() + timedelta(days=30)
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 2",
            target_amount=Decimal("2000.00"),
            target_date=future_date,
        )
        today = date_type.today()
        url = f"{self.base_url}summary/?month={today.month}&year={today.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Both should need roughly their full amounts
        self.assertEqual(response.data["total_monthly_needed"], Decimal("3000.00"))

    def test_summary_endpoint_actual_savings_calculation(self):
        """Test summary endpoint calculates actual_savings."""
        today = date_type.today()
        # Add income
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Salary",
            amount=Decimal("3000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        url = f"{self.base_url}summary/?month={today.month}&year={today.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["actual_savings"], Decimal("3000.00"))

    def test_summary_endpoint_on_track_status(self):
        """Test summary endpoint returns 'on_track' when savings exceed needed."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        today = date_type.today()
        # Add more income than needed
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Salary",
            amount=Decimal("2000.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        url = f"{self.base_url}summary/?month={today.month}&year={today.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "on_track")

    def test_summary_endpoint_short_status(self):
        """Test summary endpoint returns 'short' when savings fall short."""
        future_date = date_type.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal",
            target_amount=Decimal("1000.00"),
            target_date=future_date,
        )
        today = date_type.today()
        # Add less income than needed
        Transaction.objects.create(
            wallet=self.wallet,
            created_by=self.user,
            note="Salary",
            amount=Decimal("500.00"),
            currency="usd",
            date=timezone.make_aware(datetime(today.year, today.month, 15)),
        )
        url = f"{self.base_url}summary/?month={today.month}&year={today.year}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "short")

    def test_api_list_returns_ordered_by_target_date(self):
        """Test list endpoint returns goals ordered by target date."""
        today = date_type.today()
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("1000.00"),
            target_date=today + timedelta(days=60),
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 2",
            target_amount=Decimal("2000.00"),
            target_date=today + timedelta(days=30),
        )
        goal3 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 3",
            target_amount=Decimal("3000.00"),
            target_date=today + timedelta(days=90),
        )
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 200)
        # Should be ordered by target_date
        self.assertEqual(response.data[0]["id"], str(goal2.id))
        self.assertEqual(response.data[1]["id"], str(goal1.id))
        self.assertEqual(response.data[2]["id"], str(goal3.id))
