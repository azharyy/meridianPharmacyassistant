"""The fetch asks openFDA per ingredient, keeps up to four usable labels, pauses and saves."""

import json
from urllib.parse import parse_qs, urlparse

import httpx

from scripts import fetch_labels
from tests.scripts.test_label_text import label

PHONE = {"stop_use": ["Call 1-800-222-1222."]}


def openfda(pages: dict[tuple[str, int], httpx.Response]):
    """A fake openFDA answering by (ingredient, skip); anything else is a 404."""
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        params = parse_qs(urlparse(str(request.url)).query)
        search, skip = params["search"][0], int(params["skip"][0])
        for (name, page_skip), response in pages.items():
            if f'"{name}"' in search and skip == page_skip:
                return response
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    return httpx.Client(transport=httpx.MockTransport(handle)), seen


def page(*labels: dict) -> httpx.Response:
    return httpx.Response(200, json={"results": list(labels)})


def test_keeps_up_to_four_usable_labels_and_pauses_after_each_request():
    results = [label(set_id=f"set-{n}") for n in range(6)]
    results.insert(1, label(set_id="set-phone", **PHONE))
    http, seen = openfda({("placeholderine", 0): page(*results)})
    pauses = []
    kept = fetch_labels.fetch(
        http, {"allergy": ["placeholderine", "missingine"]}, wait=lambda: pauses.append(1)
    )
    assert [found["set_id"] for found in kept["placeholderine"]] == [
        "set-0",
        "set-1",
        "set-2",
        "set-3",
    ]
    assert kept["missingine"] == []
    assert len(pauses) == len(seen) == 2


def test_a_full_page_without_enough_usable_labels_leads_to_the_next_page():
    full_page = [label(set_id=f"phone-{n}", **PHONE) for n in range(99)] + [label(set_id="a")]
    http, seen = openfda(
        {
            ("placeholderine", 0): page(*full_page),
            ("placeholderine", 100): page(label(set_id="b")),
        }
    )
    kept = fetch_labels.fetch(http, {"allergy": ["placeholderine"]}, wait=lambda: None)
    assert [found["set_id"] for found in kept["placeholderine"]] == ["a", "b"]
    assert len(seen) == 2


def test_the_query_asks_for_otc_labels_of_one_ingredient_newest_first():
    query = fetch_labels.query("bismuth subsalicylate", skip=100)
    assert query["search"] == (
        'openfda.generic_name:"bismuth subsalicylate" AND openfda.product_type:"HUMAN OTC DRUG"'
    )
    assert (query["sort"], query["limit"], query["skip"]) == ("effective_time:desc", 100, 100)


def test_each_label_is_saved_as_fetched_under_its_set_id_replacing_old_ones(tmp_path):
    (tmp_path / "stale.json").write_text("{}", encoding="utf-8")
    kept = {"placeholderine": [label(set_id="set-0001")]}
    [path] = fetch_labels.save(kept, tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == ["set-0001.json"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == kept["placeholderine"][0]
    assert (saved["set_id"], saved["effective_time"]) == ("set-0001", "20260101")


def test_about_thirty_ingredients_across_the_seven_categories():
    ingredients = [name for names in fetch_labels.INGREDIENTS.values() for name in names]
    assert set(fetch_labels.INGREDIENTS) == {
        "allergy",
        "pain and fever",
        "cough and cold",
        "digestive",
        "skin",
        "sleep",
        "eye care",
    }
    assert 27 <= len(set(ingredients)) <= 33
