
from django.contrib.auth import get_user_model
from django.test import TestCase

from .asset_search import search_assets
from .models import Asset, Category, Department
from .services import register_asset


class AssetSearchTests(TestCase):

    def setUp(self):
        self.cs_department = Department.objects.create(
            name="Computer Science",
            code="CS-SEARCH",
        )

        self.eng_department = Department.objects.create(
            name="Engineering",
            code="ENG-SEARCH",
        )

        self.it_category = Category.objects.create(
            name="IT Equipment Search",
        )

        self.furniture_category = Category.objects.create(
            name="Furniture Search",
        )

        self.custodian = get_user_model().objects.create_user(
            username="asset_search_custodian",
            password="TestPassword123!",
        )

        self.monitor = self.create_asset(
            name="Dell Monitor",
            tag="SEARCH-001",
            category=self.it_category,
            department=self.cs_department,
            location="CS Lab",
        )

        self.laptop = self.create_asset(
            name="HP Laptop",
            tag="SEARCH-002",
            category=self.it_category,
            department=self.eng_department,
            location="Engineering Lab",
            condition=Asset.Condition.FAIR,
        )

        self.chair = self.create_asset(
            name="Study Chair",
            tag="SEARCH-003",
            category=self.furniture_category,
            department=self.cs_department,
            location="Study Area",
        )

        self.draft_asset = self.create_asset(
            name="Draft Projector",
            tag="SEARCH-004",
            publication=Asset.Publication.DRAFT,
        )

        self.unsafe_asset = self.create_asset(
            name="Unsafe Printer",
            tag="SEARCH-005",
            condition=Asset.Condition.UNSAFE,
        )

        self.unavailable_asset = self.create_asset(
            name="Unavailable Tablet",
            tag="SEARCH-006",
        )

        stock = self.unavailable_asset.stock
        stock.free = 0
        stock.held = 1
        stock.full_clean()
        stock.save()

    def create_asset(
        self,
        *,
        name,
        tag,
        category=None,
        department=None,
        location="Storage Room",
        condition=Asset.Condition.GOOD,
        publication=Asset.Publication.PUBLISHED,
    ):
        return register_asset(
            name=name,
            asset_tag=tag,
            description=f"{name} for university use",
            category=category or self.it_category,
            department=department or self.cs_department,
            custodian=self.custodian,
            location=location,
            tracking_mode=Asset.TrackingMode.INDIVIDUAL,
            quantity=1,
            condition=condition,
            lifecycle=Asset.Lifecycle.ACTIVE,
            publication=publication,
        )

    # TEST 1: DEFAULT SEARCH

    def test_default_search_returns_available_assets(self):
        results = list(search_assets())

        self.assertEqual(len(results), 3)
        self.assertIn(self.monitor, results)
        self.assertIn(self.laptop, results)
        self.assertIn(self.chair, results)

    # TEST 2: SEARCH BY NAME

    def test_search_by_asset_name(self):
        results = list(
            search_assets(query="monitor")
        )

        self.assertEqual(results, [self.monitor])

    # TEST 3: CASE-INSENSITIVE SEARCH

    def test_search_is_case_insensitive(self):
        results = list(
            search_assets(query="DELL")
        )

        self.assertEqual(results, [self.monitor])

    # TEST 4: SEARCH BY DESCRIPTION

    def test_search_by_description(self):
        results = list(
            search_assets(query="university use")
        )

        self.assertEqual(len(results), 3)

    # TEST 5: SEARCH BY LOCATION

    def test_search_by_location(self):
        results = list(
            search_assets(query="Engineering Lab")
        )

        self.assertEqual(results, [self.laptop])

    # TEST 6: FILTER BY CATEGORY

    def test_filter_by_category(self):
        results = list(
            search_assets(
                category_id=self.furniture_category.pk
            )
        )

        self.assertEqual(results, [self.chair])

    # TEST 7: FILTER BY DEPARTMENT

    def test_filter_by_department(self):
        results = list(
            search_assets(
                department_id=self.eng_department.pk
            )
        )

        self.assertEqual(results, [self.laptop])

    # TEST 8: FILTER BY CONDITION

    def test_filter_by_condition(self):
        results = list(
            search_assets(
                condition=Asset.Condition.FAIR
            )
        )

        self.assertEqual(results, [self.laptop])

    # TEST 9: UNAVAILABLE STOCK

    def test_available_only_filter(self):
        available_results = list(
            search_assets(available_only=True)
        )

        all_eligible_results = list(
            search_assets(available_only=False)
        )

        self.assertNotIn(
            self.unavailable_asset,
            available_results,
        )

        self.assertIn(
            self.unavailable_asset,
            all_eligible_results,
        )

    # TEST 10: NEVER EXPOSE UNSAFE OR DRAFT ASSETS

    def test_search_excludes_unsafe_and_draft_assets(self):
        results = list(
            search_assets(available_only=False)
        )

        self.assertNotIn(self.draft_asset, results)
        self.assertNotIn(self.unsafe_asset, results)
        self.assertEqual(len(results), 4)
