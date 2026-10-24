from app.slug import slugify


def test_ac1():
    assert slugify("Hello World") == "hello-world"


def test_ac2():
    assert slugify("  Zanni & Friends! ") == "zanni-friends"
