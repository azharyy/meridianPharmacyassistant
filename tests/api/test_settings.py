"""The staff key comes from MERIDIAN_STAFF_KEY, with the README's default."""

from api.settings import DATA, staff_key


def test_the_staff_key_has_a_default_and_can_be_set():
    assert staff_key({}) == "dev-staff-key"
    assert staff_key({"MERIDIAN_STAFF_KEY": "  shop-key  "}) == "shop-key"


def test_the_data_folder_holds_the_seeded_files():
    assert {"orders.json", "stock.json", "stores.yaml"} <= {path.name for path in DATA.iterdir()}
