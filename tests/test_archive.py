"""Transfer-encoding handling. Offline."""
import gzip
import zlib

import archive


def test_gzip_is_undone():
    # The Archive's id_ endpoint replays the original response bytes, so a site
    # that served gzip comes back gzipped whatever we asked for. Decoded as
    # text it is binary noise that reads like a page which failed to parse.
    body = gzip.compress(b"<html>DEPARTMENTAL APPEALS BOARD</html>")
    assert b"APPEALS BOARD" in archive.decompress(body)


def test_deflate_is_undone():
    body = zlib.compress(b"<html>Civil Remedies Division</html>")
    assert b"Civil Remedies" in archive.decompress(body)


def test_plain_bytes_pass_through():
    body = b"<html>plain</html>"
    assert archive.decompress(body) == body


def test_a_corrupt_stream_is_returned_rather_than_raising():
    # Better a page that fails a content check than a crash mid-collection.
    body = b"\x1f\x8b" + b"not actually gzip"
    assert archive.decompress(body) == body
