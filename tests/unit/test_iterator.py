"""Tests for PaginatedIterator."""

from typing import Any, List

import pytest

from daktela import DaktelaException, DaktelaQuery, DaktelaResponse, PaginatedIterator


class FakeClient:
    def __init__(self, responses: List[DaktelaResponse | DaktelaException]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, int | None, int | None]] = []

    def get(self, endpoint: str, query: DaktelaQuery) -> DaktelaResponse:
        self.calls.append((endpoint, query.get_skip(), query.get_take()))
        response = self.responses.pop(0)
        if isinstance(response, DaktelaException):
            raise response
        return response


def response(
    data: Any,
    *,
    total: int | None = None,
    errors: list[Any] | None = None,
) -> DaktelaResponse:
    return DaktelaResponse(200, data=data, total=total, errors=errors)


def iterator_for(*items: dict[str, Any]) -> PaginatedIterator:
    client = FakeClient([response(list(items), total=len(items))])
    return PaginatedIterator(client, "users", page_size=max(1, len(items)))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page_size": 0},
        {"max_items": -1},
        {"max_error_pages": 0},
    ],
)
def test_invalid_configuration(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        PaginatedIterator(FakeClient([]), "users", **kwargs)  # type: ignore[arg-type]


def test_iterates_pages_and_stops_at_total() -> None:
    client = FakeClient(
        [
            response([{"id": 1}, {"id": 2}], total=14),
            response([{"id": 3}, {"id": 4}], total=14),
        ]
    )
    iterator = PaginatedIterator(
        client,  # type: ignore[arg-type]
        "Users",
        DaktelaQuery().skip(10),
        page_size=2,
    )

    assert [item["id"] for item in iterator] == [1, 2, 3, 4]
    assert client.calls == [("Users", 10, 2), ("Users", 12, 2)]
    assert iterator.total == 14
    assert iterator.items_yielded == 4
    assert iterator.last_response is not None
    assert iterator.last_error is None


def test_short_and_empty_pages_stop_iteration() -> None:
    short_client = FakeClient([response([{"id": 1}])])
    iterator = PaginatedIterator(short_client, "users", page_size=2)  # type: ignore[arg-type]
    assert iterator.collect() == [{"id": 1}]
    assert short_client.responses == []

    empty_client = FakeClient([response([])])
    iterator = PaginatedIterator(empty_client, "users", page_size=2)  # type: ignore[arg-type]
    assert iterator.first() is None
    assert iterator.is_empty()


def test_zero_max_items_does_not_request() -> None:
    client = FakeClient([])
    iterator = PaginatedIterator(client, "users", max_items=0)  # type: ignore[arg-type]
    assert iterator.collect() == []
    assert list(iterator.pages()) == []
    assert client.calls == []


def test_max_items_reduces_last_request() -> None:
    client = FakeClient(
        [
            response([{"id": 1}, {"id": 2}], total=10),
            response([{"id": 3}], total=10),
        ]
    )
    iterator = PaginatedIterator(
        client, "users", page_size=2, max_items=3  # type: ignore[arg-type]
    )
    assert [item["id"] for item in iterator] == [1, 2, 3]
    assert client.calls[-1] == ("users", 2, 1)


def test_request_exception_stops_by_default() -> None:
    error = DaktelaException("failure", 500)
    iterator = PaginatedIterator(FakeClient([error]), "users")  # type: ignore[arg-type]
    with pytest.raises(DaktelaException, match="failure"):
        next(iterator)
    assert iterator.last_error is error


def test_request_exception_can_be_skipped() -> None:
    error = DaktelaException("failure", 500)
    client = FakeClient([error, response([{"id": 2}], total=2)])
    iterator = PaginatedIterator(
        client,
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    assert iterator.collect() == [{"id": 2}]
    assert iterator.last_error is error
    assert client.calls == [("users", 0, 1), ("users", 1, 1)]


def test_skipped_request_exceptions_are_bounded() -> None:
    errors = [DaktelaException("failure", 500), DaktelaException("failure", 500)]
    iterator = PaginatedIterator(
        FakeClient(errors),
        "users",
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    with pytest.raises(DaktelaException):
        next(iterator)


def test_api_error_response_stop_and_skip() -> None:
    stopped = PaginatedIterator(
        FakeClient([response(None, errors=["failure"])]), "users"  # type: ignore[arg-type]
    )
    with pytest.raises(DaktelaException, match="failure"):
        stopped.collect()
    assert stopped.last_response is not None

    client = FakeClient(
        [response(None, errors=["failure"]), response([{"id": 2}], total=2)]
    )
    skipped = PaginatedIterator(
        client,
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    assert skipped.collect() == [{"id": 2}]


def test_api_error_responses_are_bounded() -> None:
    iterator = PaginatedIterator(
        FakeClient(
            [
                response(None, errors=["failure"]),
                response(None, errors=["failure"]),
            ]
        ),
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    with pytest.raises(DaktelaException, match="failure"):
        iterator.collect()


def test_pages_yields_metadata_and_stops_at_total() -> None:
    first = response([{"id": 1}, {"id": 2}], total=4)
    second = response([{"id": 3}, {"id": 4}], total=4)
    client = FakeClient([first, second])
    iterator = PaginatedIterator(client, "users", page_size=2)  # type: ignore[arg-type]
    assert list(iterator.pages()) == [first, second]
    assert iterator.total == 4
    assert iterator.last_response is second


def test_pages_stop_on_short_or_empty_page() -> None:
    short = response([{"id": 1}])
    iterator = PaginatedIterator(
        FakeClient([short]), "users", page_size=2  # type: ignore[arg-type]
    )
    assert list(iterator.pages()) == [short]

    empty = response([])
    iterator = PaginatedIterator(
        FakeClient([empty]), "users", page_size=2  # type: ignore[arg-type]
    )
    assert list(iterator.pages()) == [empty]


def test_pages_error_handling() -> None:
    error_response = response(None, errors=["failure"])
    stopped = PaginatedIterator(
        FakeClient([error_response]), "users"  # type: ignore[arg-type]
    )
    seen: list[DaktelaResponse] = []
    with pytest.raises(DaktelaException, match="failure"):
        seen.extend(stopped.pages())
    assert seen == [error_response]

    success = response([{"id": 2}], total=2)
    skipped = PaginatedIterator(
        FakeClient([error_response, success]),
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    assert list(skipped.pages()) == [error_response, success]


def test_pages_api_errors_are_bounded() -> None:
    errors = [
        response(None, errors=["failure"]),
        response(None, errors=["failure"]),
    ]
    iterator = PaginatedIterator(
        FakeClient(errors),
        "users",
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    seen: list[DaktelaResponse] = []
    with pytest.raises(DaktelaException, match="failure"):
        seen.extend(iterator.pages())
    assert seen == errors


def test_pages_request_exception_handling() -> None:
    error = DaktelaException("failure", 500)
    stopped = PaginatedIterator(FakeClient([error]), "users")  # type: ignore[arg-type]
    with pytest.raises(DaktelaException):
        list(stopped.pages())

    success = response([{"id": 2}], total=2)
    skipped = PaginatedIterator(
        FakeClient([error, success]),
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    assert list(skipped.pages()) == [success]
    assert skipped.last_error is error


def test_pages_request_exceptions_are_bounded() -> None:
    errors = [DaktelaException("failure", 500), DaktelaException("failure", 500)]
    iterator = PaginatedIterator(
        FakeClient(errors),
        "users",
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    with pytest.raises(DaktelaException):
        list(iterator.pages())


def test_collection_helpers() -> None:
    assert iterator_for({"id": 1}, {"id": 2}).count() == 2
    assert not iterator_for({"id": 1}).is_empty()

    seen: list[tuple[int, int]] = []
    iterator_for({"id": 2}, {"id": 3}).each(
        lambda item, index: seen.append((index, item["id"]))
    )
    assert seen == [(0, 2), (1, 3)]

    filtered = iterator_for({"id": 1}, {"id": 2})
    assert list(filtered.filter(lambda item: item["id"] % 2 == 0)) == [{"id": 2}]

    mapped = iterator_for({"id": 1}, {"id": 2})
    assert list(mapped.map(lambda item: item["id"] * 10)) == [10, 20]


class SlicingClient:
    """Serves a fixed dataset and caps page size like a real server may."""

    def __init__(self, size: int, max_take: int, *, report_total: bool = True) -> None:
        self.data = [{"id": index} for index in range(size)]
        self.max_take = max_take
        self.report_total = report_total
        self.calls: list[tuple[int | None, int | None]] = []

    def get(self, endpoint: str, query: DaktelaQuery) -> DaktelaResponse:
        self.calls.append((query.get_skip(), query.get_take()))
        skip = query.get_skip() or 0
        take = min(query.get_take() or self.max_take, self.max_take)
        total = len(self.data) if self.report_total else None
        return response(self.data[skip : skip + take], total=total)


def test_server_capped_page_size_does_not_truncate_iteration() -> None:
    client = SlicingClient(size=250, max_take=50)
    iterator = PaginatedIterator(client, "users", page_size=100)  # type: ignore[arg-type]
    assert [item["id"] for item in iterator] == list(range(250))
    assert [skip for skip, _ in client.calls] == [0, 50, 100, 150, 200]


def test_server_capped_pages_respect_max_items() -> None:
    client = SlicingClient(size=250, max_take=50)
    iterator = PaginatedIterator(
        client, "users", page_size=100, max_items=120  # type: ignore[arg-type]
    )
    assert len(iterator.collect()) == 120
    assert client.calls[-1] == (100, 20)


def test_server_capped_page_size_does_not_truncate_pages() -> None:
    client = SlicingClient(size=120, max_take=50)
    iterator = PaginatedIterator(client, "users", page_size=100)  # type: ignore[arg-type]
    assert [len(page) for page in iterator.pages()] == [50, 50, 20]


def test_short_page_without_total_still_ends_iteration() -> None:
    client = SlicingClient(size=30, max_take=50, report_total=False)
    iterator = PaginatedIterator(client, "users", page_size=100)  # type: ignore[arg-type]
    assert len(iterator.collect()) == 30
    assert len(client.calls) == 1


def test_api_error_response_raises_when_stopping_on_error() -> None:
    failed = DaktelaResponse(200, data=None, total=5, errors=["partial failure"])
    iterator = PaginatedIterator(FakeClient([failed]), "users")  # type: ignore[arg-type]
    with pytest.raises(DaktelaException, match="partial failure") as raised:
        iterator.collect()
    assert raised.value.errors == ["partial failure"]
    assert raised.value.status_code == 200
    assert iterator.last_error is raised.value
    assert iterator.last_response is failed


def test_pages_raise_after_yielding_api_error_response() -> None:
    failed = response(None, errors=["failure"])
    iterator = PaginatedIterator(FakeClient([failed]), "users")  # type: ignore[arg-type]
    pages = iterator.pages()
    assert next(pages) is failed
    with pytest.raises(DaktelaException, match="failure"):
        next(pages)
    assert iterator.last_error is not None


def test_skipped_api_error_response_is_recorded() -> None:
    client = FakeClient([response(None, errors=["failure"]), response([{"id": 2}], total=2)])
    iterator = PaginatedIterator(
        client,
        "users",
        page_size=1,
        stop_on_error=False,
        max_error_pages=2,
    )  # type: ignore[arg-type]
    assert iterator.collect() == [{"id": 2}]
    assert iterator.last_error is not None
    assert iterator.last_error.errors == ["failure"]


def test_mixing_items_and_pages_is_rejected() -> None:
    items_first = iterator_for({"id": 1}, {"id": 2})
    next(items_first)
    with pytest.raises(RuntimeError, match="pages"):
        next(items_first.pages())

    pages_first = iterator_for({"id": 1})
    next(pages_first.pages())
    with pytest.raises(RuntimeError, match="pages"):
        next(pages_first)


def test_full_pages_without_total_continue_until_short_page() -> None:
    client = SlicingClient(size=120, max_take=50, report_total=False)
    iterator = PaginatedIterator(client, "users", page_size=50)  # type: ignore[arg-type]
    assert len(iterator.collect()) == 120
    assert [skip for skip, _ in client.calls] == [0, 50, 100]
