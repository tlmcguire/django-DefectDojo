"""
Characterization tests for AutoCreateContextManager (dojo/importers/auto_create_context.py).

The class decides which product, engagement and test an import or reimport lands in, and whether
missing ones get created. Until now it was only reached through REST API import tests that check
the HTTP status, so none of its conflict and error paths were pinned down.
"""
import datetime
from unittest import mock

from crum import impersonate
from django.contrib.auth.models import User
from django.http import QueryDict
from django.utils import timezone

from dojo.importers.auto_create_context import AutoCreateContextManager
from dojo.models import Engagement, Product, Product_Type, Test, Test_Type

from .dojo_test_case import DojoTestCase


class AutoCreateContextTestBase(DojoTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
        cls.product_type = Product_Type.objects.create(name="Existing Type")
        cls.product = Product.objects.create(name="Existing Product", description="d", prod_type=cls.product_type)
        cls.other_product = Product.objects.create(name="Other Product", description="d", prod_type=cls.product_type)
        cls.engagement = cls.make_engagement("Existing Engagement", cls.product)
        cls.scan_type, _ = Test_Type.objects.get_or_create(name="Acunetix Scan")

    @staticmethod
    def make_engagement(name, product):
        return Engagement.objects.create(name=name, product=product, target_start=timezone.now(), target_end=timezone.now())

    def make_test(self, engagement, title="a test", scan_type="Acunetix Scan"):
        return Test.objects.create(
            engagement=engagement, title=title, scan_type=scan_type, test_type=self.scan_type,
            target_start=timezone.now(), target_end=timezone.now(),
        )

    def setUp(self):
        self.manager = AutoCreateContextManager()


class TestProcessObjectFields(AutoCreateContextTestBase):

    def process(self, data):
        self.manager.process_object_fields("product", "product_id", Product, data)
        return data

    def test_processObjectFields_whenGivenAModelInstance_storesItsId(self):
        self.assertEqual(self.product.id, self.process({"product": self.product})["product_id"])

    def test_processObjectFields_whenGivenAnInteger_storesItUnchanged(self):
        self.assertEqual(7, self.process({"product": 7})["product_id"])

    def test_processObjectFields_whenGivenADigitString_storesTheStringNotAnInteger(self):
        self.assertEqual("7", self.process({"product": "7"})["product_id"])

    def test_processObjectFields_whenGivenAList_usesItsFirstElement(self):
        self.assertEqual(3, self.process({"product": [3, 4]})["product_id"])

    def test_processObjectFields_whenGivenANonNumericString_raisesValueErrorNamingTheKey(self):
        with self.assertRaisesMessage(ValueError, "product must be an integer"):
            self.process({"product": "abc"})

    def test_processObjectFields_whenListHoldsANonNumericString_isNotValidated(self):
        # The digit check is an elif of the list check, so it only ever sees top-level strings.
        self.assertEqual("abc", self.process({"product": ["abc"]})["product_id"])

    def test_processObjectFields_whenValueIsMissingOrFalsy_leavesDataUntouched(self):
        for data in [{}, {"product": None}, {"product": 0}, {"product": ""}, {"product": []}]:
            with self.subTest(data=data):
                self.assertNotIn("product_id", self.process(dict(data)))


class TestProcessObjectName(AutoCreateContextTestBase):

    def test_processObjectName_whenGivenAList_replacesItWithItsFirstElement(self):
        data = {"product_name": ["first", "second"]}
        self.manager.process_object_name("product_name", data)
        self.assertEqual("first", data["product_name"])

    def test_processObjectName_whenGivenAString_leavesItAlone(self):
        data = {"product_name": "plain"}
        self.manager.process_object_name("product_name", data)
        self.assertEqual("plain", data["product_name"])

    def test_processObjectName_whenGivenAnEmptyListOrNothing_leavesDataUntouched(self):
        data = {"product_name": []}
        self.manager.process_object_name("product_name", data)
        self.manager.process_object_name("missing", data)
        self.assertEqual({"product_name": []}, data)


class TestProcessImportMetaDataFromDict(AutoCreateContextTestBase):

    def test_processImportMetaDataFromDict_derivesIdsFromObjectsAndFlattensNameLists(self):
        test = self.make_test(self.engagement)
        data = {
            "test": test,
            "engagement": self.engagement,
            "product": self.product,
            "product_type_name": ["Type"],
            "product_name": ["Prod"],
            "engagement_name": ["Eng"],
            "test_title": ["Title"],
        }

        self.manager.process_import_meta_data_from_dict(data)

        self.assertEqual(test.id, data["test_id"])
        self.assertEqual(self.engagement.id, data["engagement_id"])
        self.assertEqual(self.product.id, data["product_id"])
        self.assertEqual(("Type", "Prod", "Eng", "Title"), (data["product_type_name"], data["product_name"], data["engagement_name"], data["test_title"]))

    def test_processImportMetaDataFromDict_whenAnIdIsNotNumeric_raisesValueError(self):
        with self.assertRaisesMessage(ValueError, "engagement must be an integer"):
            self.manager.process_import_meta_data_from_dict({"engagement": "latest"})


class TestFetchers(AutoCreateContextTestBase):

    def test_getTargetProductTypeIfExists_whenNameMatches_returnsIt(self):
        self.assertEqual(self.product_type, self.manager.get_target_product_type_if_exists(product_type_name="Existing Type"))

    def test_getTargetProductTypeIfExists_whenNameUnknownOrMissing_returnsNone(self):
        self.assertIsNone(self.manager.get_target_product_type_if_exists(product_type_name="Nope"))
        self.assertIsNone(self.manager.get_target_product_type_if_exists())

    def test_getTargetProductIfExists_whenNameMatches_returnsIt(self):
        self.assertEqual(self.product, self.manager.get_target_product_if_exists(product_name="Existing Product"))

    def test_getTargetProductIfExists_whenProductTypeNameMatches_returnsIt(self):
        found = self.manager.get_target_product_if_exists(product_name="Existing Product", product_type_name="Existing Type")
        self.assertEqual(self.product, found)

    def test_getTargetProductIfExists_whenNameUnknownOrMissing_returnsNone(self):
        self.assertIsNone(self.manager.get_target_product_if_exists(product_name="Nope"))
        self.assertIsNone(self.manager.get_target_product_if_exists())

    def test_getTargetProductIfExists_whenProductTypeNameConflicts_raisesValueErrorNamingSuppliedType(self):
        with self.assertRaises(ValueError) as caught:
            self.manager.get_target_product_if_exists(product_name="Existing Product", product_type_name="Different Type")
        self.assertIn("Different Type", str(caught.exception))
        self.assertNotIn("Existing Type", str(caught.exception))

    def test_getTargetProductIfExists_whenProductIsUnknown_ignoresTheProductTypeName(self):
        self.assertIsNone(self.manager.get_target_product_if_exists(product_name="Nope", product_type_name="Different Type"))

    def test_getTargetProductByIdIfExists_returnsProductOrNone(self):
        self.assertEqual(self.product, self.manager.get_target_product_by_id_if_exists(product_id=self.product.id))
        self.assertIsNone(self.manager.get_target_product_by_id_if_exists(product_id=0))
        self.assertIsNone(self.manager.get_target_product_by_id_if_exists())

    def test_getTargetEngagementIfExists_whenIdMatches_returnsIt(self):
        self.assertEqual(self.engagement, self.manager.get_target_engagement_if_exists(engagement_id=self.engagement.id))
        self.assertEqual(
            self.engagement,
            self.manager.get_target_engagement_if_exists(engagement_id=self.engagement.id, product=self.product),
        )

    def test_getTargetEngagementIfExists_whenIdBelongsToAnotherProduct_raisesValueError(self):
        with self.assertRaisesMessage(ValueError, "the engagement does not belong to the specified product"):
            self.manager.get_target_engagement_if_exists(engagement_id=self.engagement.id, product=self.other_product)

    def test_getTargetEngagementIfExists_whenNoIdAndNoProduct_returnsNone(self):
        self.assertIsNone(self.manager.get_target_engagement_if_exists(engagement_name="Existing Engagement"))

    def test_getTargetEngagementIfExists_whenNoIdButProduct_findsTheEngagementByName(self):
        found = self.manager.get_target_engagement_if_exists(engagement_name="Existing Engagement", product=self.product)
        self.assertEqual(self.engagement, found)

    def test_getTargetEngagementIfExists_whenNameUnknownOnProduct_returnsNone(self):
        self.assertIsNone(self.manager.get_target_engagement_if_exists(engagement_name="Nope", product=self.product))
        self.assertIsNone(self.manager.get_target_engagement_if_exists(engagement_name="Existing Engagement", product=self.other_product))

    def test_getTargetEngagementIfExists_whenNamesAreDuplicated_returnsTheMostRecentlyCreated(self):
        newer = self.make_engagement("Existing Engagement", self.product)
        found = self.manager.get_target_engagement_if_exists(engagement_name="Existing Engagement", product=self.product)
        self.assertEqual(newer, found)

    def test_getTargetTestIfExists_whenIdMatches_returnsIt(self):
        test = self.make_test(self.engagement)
        self.assertEqual(test, self.manager.get_target_test_if_exists(test_id=test.id))

    def test_getTargetTestIfExists_whenIdBelongsToAnotherEngagement_raisesValueError(self):
        test = self.make_test(self.engagement)
        other_engagement = self.make_engagement("Another Engagement", self.product)
        with self.assertRaisesMessage(ValueError, "the test does not belong to the specified engagement"):
            self.manager.get_target_test_if_exists(test_id=test.id, engagement=other_engagement)

    def test_getTargetTestIfExists_whenNoIdAndNoEngagement_returnsNone(self):
        self.make_test(self.engagement)
        self.assertIsNone(self.manager.get_target_test_if_exists(scan_type="Acunetix Scan"))

    def test_getTargetTestIfExists_whenOnlyScanTypeGiven_returnsTheLastTestOfThatType(self):
        self.make_test(self.engagement, title="first")
        last = self.make_test(self.engagement, title="second")
        self.assertEqual(last, self.manager.get_target_test_if_exists(scan_type="Acunetix Scan", engagement=self.engagement))

    def test_getTargetTestIfExists_whenTitleGiven_matchesOnTitleAndScanType(self):
        wanted = self.make_test(self.engagement, title="wanted")
        self.make_test(self.engagement, title="later but different")
        found = self.manager.get_target_test_if_exists(test_title="wanted", scan_type="Acunetix Scan", engagement=self.engagement)
        self.assertEqual(wanted, found)

    def test_getTargetTestIfExists_whenNothingMatches_returnsNone(self):
        self.make_test(self.engagement, title="a")
        self.assertIsNone(self.manager.get_target_test_if_exists(test_title="zzz", scan_type="Acunetix Scan", engagement=self.engagement))
        self.assertIsNone(self.manager.get_target_test_if_exists(scan_type="Other Scan", engagement=self.engagement))


class TestCreators(AutoCreateContextTestBase):

    def test_getOrCreateProductType_whenItExists_returnsItWithoutCreatingAnother(self):
        before = Product_Type.objects.count()
        self.assertEqual(self.product_type, self.manager.get_or_create_product_type(product_type_name="Existing Type"))
        self.assertEqual(before, Product_Type.objects.count())

    def test_getOrCreateProductType_whenItDoesNotExist_createsIt(self):
        created = self.manager.get_or_create_product_type(product_type_name="Brand New Type")
        self.assertEqual("Brand New Type", Product_Type.objects.get(pk=created.pk).name)

    def test_getOrCreateProduct_whenItExists_returnsItEvenWithoutAutoCreate(self):
        self.assertEqual(self.product, self.manager.get_or_create_product(product_name="Existing Product"))

    def test_getOrCreateProduct_whenMissingAndAutoCreateOff_raisesValueErrorAndCreatesNothing(self):
        before = Product.objects.count()
        with self.assertRaisesMessage(ValueError, "auto_create_context not True, unable to create non-existing product"):
            self.manager.get_or_create_product(product_name="Nope", product_type_name="Existing Type")
        self.assertEqual(before, Product.objects.count())

    def test_getOrCreateProduct_whenMissingAndAutoCreateOn_createsProductAndProductTypeWithNameAsDescription(self):
        product = self.manager.get_or_create_product(
            product_name="Fresh Product", product_type_name="Fresh Type", auto_create_context=True,
        )
        self.assertEqual("Fresh Product", product.description)
        self.assertEqual("Fresh Type", product.prod_type.name)

    def test_getOrCreateProduct_whenExistingProductHasADifferentProductType_raisesValueError(self):
        with self.assertRaises(ValueError):
            self.manager.get_or_create_product(product_name="Existing Product", product_type_name="Different Type", auto_create_context=True)

    def test_getOrCreateEngagement_whenItExistsByName_returnsItWithoutCreatingAnother(self):
        before = Engagement.objects.count()
        found = self.manager.get_or_create_engagement(
            engagement_name="Existing Engagement", product_name="Existing Product", product_type_name="Existing Type",
        )
        self.assertEqual(self.engagement, found)
        self.assertEqual(before, Engagement.objects.count())

    def test_getOrCreateEngagement_whenItExistsById_returnsItWithoutAProductName(self):
        self.assertEqual(self.engagement, self.manager.get_or_create_engagement(engagement_id=self.engagement.id))

    def test_getOrCreateEngagement_whenMissingAndAutoCreateOff_raisesValueErrorAndCreatesNothing(self):
        before = Engagement.objects.count()
        with self.assertRaisesMessage(ValueError, "auto_create_context not True, unable to create non-existing engagement"):
            self.manager.get_or_create_engagement(engagement_name="Nope", product_name="Existing Product")
        self.assertEqual(before, Engagement.objects.count())

    def test_getOrCreateEngagement_whenMissingAndAutoCreateOn_createsACiCdEngagementInProgress(self):
        with impersonate(self.user):
            engagement = self.manager.get_or_create_engagement(
                engagement_name="Nightly", product_name="Existing Product", product_type_name="Existing Type",
                auto_create_context=True, deduplication_on_engagement=True, source_code_management_uri="https://example.test/repo",
            )
        engagement = Engagement.objects.get(pk=engagement.pk)
        self.assertEqual(
            ("Nightly", self.product, "CI/CD", "In Progress", True, "https://example.test/repo", self.user),
            (engagement.name, engagement.product, engagement.engagement_type, engagement.status,
             engagement.deduplication_on_engagement, engagement.source_code_management_uri, engagement.lead),
        )

    def test_getOrCreateEngagement_whenProductAndTypeAreMissingToo_createsAllThree(self):
        engagement = self.manager.get_or_create_engagement(
            engagement_name="Nightly", product_name="Brand New Product", product_type_name="Brand New Type", auto_create_context=True,
        )
        self.assertEqual("Brand New Product", engagement.product.name)
        self.assertEqual("Brand New Type", engagement.product.prod_type.name)

    def _create_with_target_end(self, target_end):
        now = timezone.make_aware(datetime.datetime(2026, 6, 15, 12, 0))
        with mock.patch("dojo.importers.auto_create_context.timezone.now", return_value=now):
            engagement = self.manager.get_or_create_engagement(
                engagement_name="Nightly", product_name="Existing Product", auto_create_context=True, target_end=target_end,
            )
        return engagement, now.date()

    def test_getOrCreateEngagement_whenNoTargetEndGiven_endsOneYearAfterToday(self):
        engagement, today = self._create_with_target_end(None)
        self.assertEqual((today, today + datetime.timedelta(days=365)), (engagement.target_start, engagement.target_end))

    def test_getOrCreateEngagement_whenTargetEndIsInTheFuture_keepsIt(self):
        end = datetime.date(2026, 12, 31)
        engagement, _ = self._create_with_target_end(end)
        self.assertEqual(end, engagement.target_end)

    def test_getOrCreateEngagement_whenTargetEndIsBeforeToday_replacesItWithOneYearAfterToday(self):
        engagement, today = self._create_with_target_end(datetime.date(2020, 1, 1))
        self.assertEqual(today + datetime.timedelta(days=365), engagement.target_end)

    def test_getOrCreateEngagement_whenTargetEndIsToday_keepsIt(self):
        engagement, today = self._create_with_target_end(datetime.date(2026, 6, 15))
        self.assertEqual(today, engagement.target_end)


class TestConvertQueryDictToDict(AutoCreateContextTestBase):

    def test_convertQuerydictToDict_whenGivenSingleValues_returnsThemAsStrings(self):
        self.assertEqual({"a": "1", "b": "2"}, self.manager.convert_querydict_to_dict(QueryDict("a=1&b=2")))

    def test_convertQuerydictToDict_whenAValueIsEmpty_dropsThatKey(self):
        self.assertEqual({"b": "2"}, self.manager.convert_querydict_to_dict(QueryDict("a=&b=2")))

    def test_convertQuerydictToDict_whenAKeyRepeats_keepsOnlyTheLastValue(self):
        # QueryDict.items() yields the last value per key, so the list branch never sees a repeated parameter.
        self.assertEqual({"a": "2"}, self.manager.convert_querydict_to_dict(QueryDict("a=1&a=2")))

    def test_convertQuerydictToDict_whenGivenAPlainDictWithLists_unwrapsSingletonsAndKeepsLongerLists(self):
        converted = self.manager.convert_querydict_to_dict({"one": ["x"], "many": ["x", "y"], "none": [], "scalar": "z"})
        self.assertEqual({"one": "x", "many": ["x", "y"], "scalar": "z"}, converted)
