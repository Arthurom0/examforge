import os


def test_settings_roundtrip(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/settings").json()["api_key_configured"] is False

    r = client.put("/api/settings", json={"api_key": "sk-ant-test-1234567890", "effort": "medium"}).json()
    assert r["api_key_configured"] and r["api_key_hint"] == "…7890" and r["effort"] == "medium"
    assert "sk-ant-test" not in str(r)  # never echoed back
    env_text = open(os.environ["EXAMFORGE_ENV_FILE"]).read()
    assert "ANTHROPIC_API_KEY=sk-ant-test-1234567890" in env_text

    r = client.put("/api/settings", json={"api_key": ""}).json()
    assert r["api_key_configured"] is False
