import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from dojo.file_uploads.models import FileUpload
from dojo.file_uploads.validators import image_content_matches_name
from dojo.models import FileAccessToken, Finding, User
from unittests.dojo_test_case import versioned_fixtures

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
TIFF = b"II*\x00" + b"\x00" * 32


class TestImageContentMatchesName(TestCase):

    def test_matching_signatures_pass(self):
        self.assertTrue(image_content_matches_name(BytesIO(PNG), "a.png"))
        self.assertTrue(image_content_matches_name(BytesIO(JPEG), "a.JPEG"))
        self.assertTrue(image_content_matches_name(BytesIO(b"GIF89a..."), "a.gif"))

    def test_mislabelled_image_fails(self):
        self.assertFalse(image_content_matches_name(BytesIO(TIFF), "photo.png"))
        self.assertFalse(image_content_matches_name(BytesIO(PNG), "photo.jpeg"))
        self.assertFalse(image_content_matches_name(BytesIO(b""), "empty.png"))

    def test_non_image_names_are_not_checked(self):
        self.assertTrue(image_content_matches_name(BytesIO(TIFF), "report.pdf"))

    def test_read_position_is_restored(self):
        f = BytesIO(PNG)
        f.seek(5)
        image_content_matches_name(f, "a.png")
        self.assertEqual(5, f.tell())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
@versioned_fixtures
class TestFileUploadRejectsMislabelledImages(TestCase):

    fixtures = ["dojo_testdata.json"]

    def test_clean_rejects_tiff_named_png(self):
        upload = FileUpload(title="photo.png", file=ContentFile(TIFF, name="photo.png"))
        with self.assertRaisesMessage(ValidationError, "does not match its .png extension"):
            upload.clean()

    def test_clean_accepts_real_png(self):
        FileUpload(title="photo.png", file=ContentFile(PNG, name="photo.png")).clean()

    def test_api_upload_rejects_tiff_named_png(self):
        client = APIClient()
        client.force_authenticate(User.objects.get(username="admin"))
        finding = Finding.objects.first()
        resp = client.post(
            reverse("finding-files", args=(finding.id,)),
            {"title": "photo", "file": SimpleUploadedFile("photo.png", TIFF)},
            format="multipart",
        )
        self.assertEqual(400, resp.status_code, resp.content[:500])
        self.assertFalse(finding.files.exists())

    def test_image_view_refuses_mislabelled_stored_file(self):
        # A file stored before content validation existed bypasses clean().
        admin = User.objects.get(username="admin")
        stored = FileUpload.objects.create(title="old.png", file=ContentFile(TIFF, name="old.png"))
        token = FileAccessToken.objects.create(user=admin, file=stored, size="small")
        resp = self.client.get(reverse("download_finding_pic", args=(token.token,)))
        # PermissionDenied is rendered by dojo.views.custom_unauthorized_view (403 page, HTTP 400).
        self.assertTemplateUsed(resp, "403.html")
        self.assertFalse(resp.streaming)
