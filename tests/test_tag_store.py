import pytest

from tagging import tag_store


@pytest.fixture(autouse=True)
def clean_tags():
    tag_store.init_db()
    with tag_store._connect() as conn:
        conn.execute("DELETE FROM file_tags")
        conn.execute("DELETE FROM tags")


def _names(file_path):
    return {t["name"] for t in tag_store.get_file_tags(file_path)}


def test_auto_tags_replace_auto_but_keep_manual():
    tag_store.set_file_tags("/f.jpg", ["beach", "sunset"], parent_map={"beach": "nature"})
    tag_store.add_manual_tag("/f.jpg", "holiday")
    tag_store.set_file_tags("/f.jpg", ["ocean"])

    assert _names("/f.jpg") == {"ocean", "holiday"}


def test_files_by_parent_tag_include_children():
    tag_store.set_file_tags("/a.jpg", ["beach"], parent_map={"beach": "nature"})
    tag_store.set_file_tags("/b.jpg", ["forest"], parent_map={"forest": "nature"})

    assert set(tag_store.get_files_by_tag("nature")) == {"/a.jpg", "/b.jpg"}
    assert tag_store.get_files_by_tag("beach") == ["/a.jpg"]


def test_remove_and_delete_file_tags():
    tag_store.set_file_tags("/a.jpg", ["beach", "sky"])
    tag_store.remove_tag_from_file("/a.jpg", "sky")
    assert _names("/a.jpg") == {"beach"}

    tag_store.delete_file_tags("/a.jpg")
    assert _names("/a.jpg") == set()


def test_clear_all_file_tags():
    tag_store.set_file_tags("/a.jpg", ["beach"])
    tag_store.set_file_tags("/b.jpg", ["sky"])
    tag_store.clear_all_file_tags()

    assert _names("/a.jpg") == _names("/b.jpg") == set()
