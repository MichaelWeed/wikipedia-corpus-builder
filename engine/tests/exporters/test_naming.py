from corpussieve.exporters.naming import slugify


def test_slugify_path_traversal_and_reserved() -> None:
    assert slugify("../../etc/passwd") == "etc-passwd"
    assert slugify("CON") == "CON_"
    assert slugify("AUX.txt") == "AUX.txt"
    assert slugify("Super_Mario_Bros.") == "Super_Mario_Bros"
    assert slugify("___---") == "untitled"
    assert "/" not in slugify("a/b/c")
    assert "\\" not in slugify("a\\b\\c")
