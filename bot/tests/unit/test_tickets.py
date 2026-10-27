from app.services.tickets import ticket_payload, verify_ticket_payload


def test_ticket_signature_is_deterministic_and_verifiable() -> None:
    payload = ticket_payload("TB-20261112-00457", "a" * 32)

    assert payload == ticket_payload("TB-20261112-00457", "a" * 32)
    assert verify_ticket_payload(payload, "a" * 32)


def test_ticket_rejects_tampering_and_wrong_secret() -> None:
    payload = ticket_payload("TB-20261112-00457", "a" * 32)

    assert not verify_ticket_payload(payload.replace("00457", "00458"), "a" * 32)
    assert not verify_ticket_payload(payload, "b" * 32)
    assert not verify_ticket_payload("invalid", "a" * 32)
