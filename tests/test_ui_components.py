from fairdraw_ui.components import name_plate


def test_user_text_is_html_escaped() -> None:
    html = name_plate("<script>alert(1)</script>", "guest")
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
