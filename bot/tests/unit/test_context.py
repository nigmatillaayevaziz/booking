from app.core.context import begin_request, end_request, get_request_id


def test_request_context_is_scoped_and_reset() -> None:
    assert get_request_id() == "-"

    token = begin_request("request-123")
    try:
        assert get_request_id() == "request-123"
    finally:
        end_request(token)

    assert get_request_id() == "-"
