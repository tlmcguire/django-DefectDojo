"""
Characterization tests for BaseImporter.sanitize_severity (dojo/importers/base_importer.py).

Every finding a parser returns passes through this method before it is saved, so what it
accepts, rewrites and rejects decides what an import can contain.
"""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from dojo.importers.default_importer import DefaultImporter
from dojo.models import Development_Environment, Engagement, Finding, Product, Product_Type

from .dojo_test_case import DojoTestCase


class TestSanitizeSeverity(DojoTestCase):

    @classmethod
    def setUpTestData(cls):
        user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
        product_type = Product_Type.objects.create(name="Sanitize Product Type")
        product = Product.objects.create(name="Sanitize Product", description="d", prod_type=product_type)
        engagement = Engagement.objects.create(
            name="Sanitize Engagement", product=product, target_start=timezone.now(), target_end=timezone.now(),
        )
        environment, _ = Development_Environment.objects.get_or_create(name="Development")
        # Building an importer needs a user, a lead, an environment, an engagement and a scan type
        # even though sanitize_severity never reads any of them.
        cls.importer = DefaultImporter(
            user=user,
            lead=user,
            scan_date=None,
            environment=environment,
            minimum_severity="Info",
            active=True,
            verified=True,
            sync=True,
            scan_type="Acunetix Scan",
            engagement=engagement,
        )

    def sanitize(self, severity):
        return self.importer.sanitize_severity(Finding(title="t", severity=severity))

    def test_sanitizeSeverity_whenSeverityIsCanonical_keepsItAndSetsNumericalSeverity(self):
        expected = {"Critical": "S0", "High": "S1", "Medium": "S2", "Low": "S3", "Info": "S4"}
        for severity, numerical in expected.items():
            with self.subTest(severity=severity):
                finding = self.sanitize(severity)
                self.assertEqual(severity, finding.severity)
                self.assertEqual(numerical, finding.numerical_severity)

    def test_sanitizeSeverity_returnsTheSameFindingObjectItWasGiven(self):
        finding = Finding(title="t", severity="Informational")
        self.assertIs(finding, self.importer.sanitize_severity(finding))

    def test_sanitizeSeverity_whenSeverityIsAnInfoVariant_rewritesItToInfo(self):
        for raw in ["Informational", "informational", "INFORMATIONAL", "Information", "info", "INFO"]:
            with self.subTest(raw=raw):
                finding = self.sanitize(raw)
                self.assertEqual("Info", finding.severity)
                self.assertEqual("S4", finding.numerical_severity)

    def test_sanitizeSeverity_whenSeverityIsTheWordNone_rewritesItToInfo(self):
        for raw in ["None", "none", "NONE"]:
            with self.subTest(raw=raw):
                self.assertEqual("Info", self.sanitize(raw).severity)

    def test_sanitizeSeverity_whenSeverityMerelyStartsWithInfo_isTreatedAsInfo(self):
        # The check is a prefix match, so any word that begins "info" is accepted and rewritten.
        self.assertEqual("Info", self.sanitize("Informal").severity)

    def test_sanitizeSeverity_whenSeverityIsNotASupportedValue_raisesValidationErrorNamingIt(self):
        with self.assertRaises(ValidationError) as caught:
            self.sanitize("Severe")
        message = caught.exception.messages[0]
        self.assertIn('Finding severity "Severe" is not supported', message)
        self.assertIn("Any of the following are supported", message)

    def test_sanitizeSeverity_whenCaseDiffersOnANonInfoSeverity_isRejected(self):
        # Only the Info family is case-insensitive. "critical" is not folded to "Critical".
        for raw in ["critical", "HIGH", "medium", "low"]:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                self.sanitize(raw)

    def test_sanitizeSeverity_whenSeverityIsEmpty_raisesValidationError(self):
        with self.assertRaises(ValidationError):
            self.sanitize("")

    def test_sanitizeSeverity_whenSeverityIsPythonNone_raisesAttributeErrorNotValidationError(self):
        # The docstring lists "None" as something converted to Info, but a real None crashes on .lower()
        # before any validation happens. Recorded as-is; see the A7 write-up.
        with self.assertRaises(AttributeError):
            self.sanitize(None)
