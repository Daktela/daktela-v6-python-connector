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
    assert stopped.collect() == []
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
    assert iterator.collect() == []


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
    assert list(stopped.pages()) == [error_response]

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
    assert list(iterator.pages()) == errors


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
