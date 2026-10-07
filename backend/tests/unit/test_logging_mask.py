from app.core.logging import mask_pii


def test_nfr02_masks_email_and_phone():
    out = mask_pii("notify asha.rao@example.org at +91-98450-12345")
    assert "asha.rao@example.org" not in out
    assert "a***@example.org" in out
    assert "12345" not in out and out.endswith("45")


def test_nfr02_mask_leaves_plain_text():
    assert mask_pii("checkout ACC-000123 ok") == "checkout ACC-000123 ok"
