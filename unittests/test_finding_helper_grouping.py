"""
Characterization tests for finding grouping in dojo/finding/helper.py:
get_group_by_group_name(), create_finding_group() and group_findings_by().

These pin down what the code does today. Where a behaviour looks accidental rather
than intended, the test name says so and the test records it as it is.
"""
from crum import impersonate
from django.contrib.auth.models import User

from dojo.finding.helper import create_finding_group, get_group_by_group_name, group_findings_by
from dojo.models import Finding, Finding_Group, Test_Type

from .dojo_test_case import DojoTestCase


class TestGetGroupByGroupName(DojoTestCase):

    """get_group_by_group_name only reads attributes of the finding, so unsaved Findings are enough."""

    def test_componentName_whenSet_returnsPrefixedName(self):
        finding = Finding(component_name="openssl")
        self.assertEqual("Findings in: openssl", get_group_by_group_name(finding, "component_name"))

    def test_componentName_whenNull_returnsNone(self):
        self.assertIsNone(get_group_by_group_name(Finding(component_name=None), "component_name"))

    def test_componentName_whenEmptyString_returnsEmptyStringNotNone(self):
        # The file_path and vuln_id_from_tool options turn an empty value into None; this one hands the
        # empty string back unchanged, so callers that test `is None` do not see it as "no group".
        self.assertEqual("", get_group_by_group_name(Finding(component_name=""), "component_name"))

    def test_componentNamePlusVersion_whenBothSet_joinsWithColon(self):
        finding = Finding(component_name="openssl", component_version="3.0.1")
        self.assertEqual("Findings in: openssl:3.0.1", get_group_by_group_name(finding, "component_name+component_version"))

    def test_componentNamePlusVersion_whenOnlyOneSet_writesNoneForTheMissingHalf(self):
        only_name = Finding(component_name="openssl", component_version=None)
        only_version = Finding(component_name=None, component_version="3.0.1")
        self.assertEqual("Findings in: openssl:None", get_group_by_group_name(only_name, "component_name+component_version"))
        self.assertEqual("Findings in: None:3.0.1", get_group_by_group_name(only_version, "component_name+component_version"))

    def test_componentNamePlusVersion_whenNeitherSet_returnsNone(self):
        finding = Finding(component_name=None, component_version=None)
        self.assertIsNone(get_group_by_group_name(finding, "component_name+component_version"))

    def test_filePath_whenSet_returnsFilepathPrefixedName(self):
        finding = Finding(file_path="src/app.py")
        self.assertEqual("Findings in: Filepath src/app.py", get_group_by_group_name(finding, "file_path"))

    def test_filePath_whenEmpty_returnsNone(self):
        self.assertIsNone(get_group_by_group_name(Finding(file_path=""), "file_path"))

    def test_findingTitle_whenSet_returnsTitleAsGroupName(self):
        self.assertEqual("Findings in: SQL injection", get_group_by_group_name(Finding(title="SQL injection"), "finding_title"))

    def test_findingTitle_whenEmpty_returnsEmptyStringNotNone(self):
        # Unlike the other options, an empty title yields "" rather than None, so group_findings_by
        # would not treat such a finding as ungroupable.
        self.assertEqual("", get_group_by_group_name(Finding(title=""), "finding_title"))

    def test_vulnIdFromTool_whenSet_returnsPrefixedId(self):
        finding = Finding(vuln_id_from_tool="CVE-2026-0001")
        self.assertEqual("Findings in: Vulnerability ID CVE-2026-0001", get_group_by_group_name(finding, "vuln_id_from_tool"))

    def test_vulnIdFromTool_whenMissing_returnsNone(self):
        self.assertIsNone(get_group_by_group_name(Finding(vuln_id_from_tool=None), "vuln_id_from_tool"))

    def test_unknownOption_raisesValueErrorNamingTheOption(self):
        with self.assertRaisesMessage(ValueError, "Invalid group_by option severity"):
            get_group_by_group_name(Finding(), "severity")


class TestGroupFindingsBy(DojoTestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user, _ = User.objects.get_or_create(username="admin", defaults={"is_superuser": True})
        product_type = cls.create_product_type(cls, "Grouping Product Type")
        product = cls.create_product(cls, "Grouping Product", prod_type=product_type)
        engagement = cls.create_engagement(cls, "Grouping Engagement", product)
        test_type, _ = Test_Type.objects.get_or_create(name="Grouping Scan")
        cls.test = cls.create_test(cls, engagement=engagement, scan_type=test_type.name, title="Grouping Test")

    def make_finding(self, title, **fields):
        with impersonate(self.user):
            finding = Finding(test=self.test, title=title, severity="High", reporter=self.user, **fields)
            finding.save()
        return finding

    def group_findings(self, findings, option="component_name"):
        with impersonate(self.user):
            return group_findings_by(findings, option)

    def test_groupFindingsBy_whenTwoFindingsShareAComponent_putsBothInOneNewGroup(self):
        a = self.make_finding("a", component_name="openssl")
        b = self.make_finding("b", component_name="openssl")

        groups, grouped, skipped, created = self.group_findings([a, b])

        self.assertEqual((2, 0, 1), (grouped, skipped, created))
        self.assertEqual(1, len(groups))
        group = Finding_Group.objects.get(test=self.test)
        self.assertEqual("Findings in: openssl", group.name)
        self.assertEqual({a.id, b.id}, set(group.findings.values_list("id", flat=True)))

    def test_groupFindingsBy_whenComponentsDiffer_createsOneGroupPerComponent(self):
        a = self.make_finding("a", component_name="openssl")
        b = self.make_finding("b", component_name="zlib")

        groups, grouped, skipped, created = self.group_findings([a, b])

        self.assertEqual((2, 0, 2), (grouped, skipped, created))
        self.assertEqual({"Findings in: openssl", "Findings in: zlib"}, {g.name for g in groups})

    def test_groupFindingsBy_whenAGroupWithThatNameAlreadyExists_addsToItInsteadOfCreating(self):
        existing = Finding_Group.objects.create(test=self.test, name="Findings in: openssl", creator=self.user)
        a = self.make_finding("a", component_name="openssl")

        groups, grouped, skipped, created = self.group_findings([a])

        self.assertEqual((1, 0, 0), (grouped, skipped, created))
        self.assertEqual({existing}, set(groups))
        self.assertEqual([a.id], list(existing.findings.values_list("id", flat=True)))

    def test_groupFindingsBy_whenFindingHasNoGroupableValue_skipsItAndCreatesNoGroup(self):
        a = self.make_finding("a", component_name=None)

        groups, grouped, skipped, created = self.group_findings([a])

        self.assertEqual((0, 1, 0), (grouped, skipped, created))
        self.assertEqual(set(), set(groups))
        self.assertFalse(Finding_Group.objects.filter(test=self.test).exists())

    def test_groupFindingsBy_whenComponentNameIsBlank_skipsItBecauseSaveStoresBlankAsNull(self):
        # Finding.save() turns a blank component_name into None (dojo/finding/models.py), which is what
        # keeps the "" that get_group_by_group_name would return from ever reaching group creation.
        a = self.make_finding("a", component_name="  ")
        self.assertIsNone(a.component_name)

        _, grouped, skipped, created = self.group_findings([a])

        self.assertEqual((0, 1, 0), (grouped, skipped, created))
        self.assertFalse(Finding_Group.objects.filter(test=self.test).exists())

    def test_groupFindingsBy_whenFindingAlreadyInAGroup_leavesItInThatGroup(self):
        old_group = Finding_Group.objects.create(test=self.test, name="Hand made group", creator=self.user)
        a = self.make_finding("a", component_name="openssl")
        old_group.findings.add(a)
        a = Finding.objects.get(pk=a.pk)  # drop the cached finding_group

        groups, grouped, skipped, created = self.group_findings([a])

        self.assertEqual((0, 1, 0), (grouped, skipped, created))
        self.assertEqual(set(), set(groups))
        self.assertEqual({"Hand made group"}, set(Finding_Group.objects.filter(test=self.test).values_list("name", flat=True)))

    def test_groupFindingsBy_whenGivenNoFindings_returnsZeroCountsEvenForAnInvalidOption(self):
        # the option is only validated when a finding is actually looked at
        groups, grouped, skipped, created = self.group_findings([], option="not-an-option")

        self.assertEqual((set(), 0, 0, 0), (set(groups), grouped, skipped, created))

    def test_groupFindingsBy_whenOptionIsInvalidAndAFindingNeedsGrouping_raisesValueError(self):
        a = self.make_finding("a", component_name="openssl")

        with self.assertRaisesMessage(ValueError, "Invalid group_by option not-an-option"):
            self.group_findings([a], option="not-an-option")

    def test_groupFindingsBy_whenOptionIsInvalidButFindingIsAlreadyGrouped_doesNotRaise(self):
        old_group = Finding_Group.objects.create(test=self.test, name="Hand made group", creator=self.user)
        a = self.make_finding("a", component_name="openssl")
        old_group.findings.add(a)
        a = Finding.objects.get(pk=a.pk)

        _, grouped, skipped, _ = self.group_findings([a], option="not-an-option")

        self.assertEqual((0, 1), (grouped, skipped))

    def test_groupFindingsBy_whenGroupNameExceeds255Characters_truncatesGroupNameTo255(self):
        a = self.make_finding("a", component_name="x" * 300)

        self.group_findings([a])

        group = Finding_Group.objects.get(test=self.test)
        self.assertEqual(255, len(group.name))
        self.assertTrue(group.name.startswith("Findings in: xxx"))


class TestCreateFindingGroup(DojoTestCase):

    def test_createFindingGroup_whenGivenNoFindings_raisesValueError(self):
        with self.assertRaisesMessage(ValueError, "cannot create empty Finding Group"):
            create_finding_group([], "any name")
