from pathlib import Path

# Leading bytes for the image types DefectDojo renders through Pillow. Pillow picks its
# decoder from these bytes, not from the file name, so a name that claims one format must
# not be allowed to carry another (e.g. a TIFF renamed to .png).
IMAGE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
}


def image_content_matches_name(file, name) -> bool:
    """
    Return False when ``name`` has an image extension whose signature ``file`` does not start with.

    Names without a known image extension are not checked and return True. The read
    position of ``file`` is restored before returning.
    """
    signatures = IMAGE_SIGNATURES.get(Path(name).suffix.lower())
    if not signatures:
        return True
    position = file.tell()
    try:
        file.seek(0)
        head = file.read(max(len(s) for s in signatures))
    finally:
        file.seek(position)
    return head.startswith(signatures)
