from app.interop.sip2 import Sip2Codec, sip2_checksum


def test_fr03_sip2_checksum_known_value():
    msg = "9900302.00AY1AZ"
    assert sip2_checksum(msg) == f"{(-sum(msg.encode()) & 0xFFFF):04X}"
    assert len(sip2_checksum(msg)) == 4


def test_fr03_sip2_parse_checkout_fields():
    code, fixed, fields = Sip2Codec.parse(
        "11YN20261005    10150020261005    101500AOMAIN|AAM123456|ABACC-000001|AC|AY1AZF00F"
    )
    assert code == "11" and fixed == "YN20261005    10150020261005    101500"
    assert fields["AA"] == "M123456" and fields["AB"] == "ACC-000001" and fields["AO"] == "MAIN"
    assert fields["AY"] == "1" and fields["AZ"] == "F00F"


def test_fr03_sip2_build_appends_sequence_and_valid_checksum():
    message = Sip2Codec.build("98", "YYYYNN00500320261005    101500" + "2.00", {"AO": "MAIN"}, seq="3")
    assert message.startswith("98") and "|AY3AZ" in message
    body, checksum = message[:-4], message[-4:]
    assert sip2_checksum(body) == checksum
