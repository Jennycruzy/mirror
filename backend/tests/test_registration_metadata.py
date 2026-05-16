from mirror.chain.identity import verify_identity_abi
from mirror.chain.registration_file import build_registration_file
from mirror.chain.reputation import brier_feedback_value, verify_reputation_abi


def test_registration_metadata_builder():
    payload = build_registration_file(
        name="MIRROR Red-A v1",
        description="test",
        image="ipfs://image",
        service_endpoint="http://localhost:8000/agents/agent-id",
        identity_registry="0x8004A818BFB912233c491871b3d84c89A494BD9e",
        token_id="1",
        lineage="red-a",
        version=1,
        strategy_hash="abc",
    )
    assert payload["registrations"][0]["agentRegistry"] == "eip155:84532:0x8004A818BFB912233c491871b3d84c89A494BD9e"
    assert payload["registrations"][0]["agentId"] == "1"
    assert payload["mirror_metadata"]["strategy_hash"] == "abc"


def test_erc8004_abis_verified():
    assert verify_identity_abi()["ok"]
    assert verify_reputation_abi()["ok"]


def test_brier_feedback_encoding():
    value, decimals, tag_hash = brier_feedback_value(0.1234)
    assert value == 1234
    assert decimals == 4
    assert len(tag_hash) == 32

