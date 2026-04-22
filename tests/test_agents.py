import pytest
from unittest.mock import AsyncMock, MagicMock


def _mock_completion(content: str):
    choice = MagicMock()
    choice.message.content = content
    choice.finish_reason = "stop"
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_qualify_parses_valid_json(monkeypatch):
    import backend.agents.qualification as qa

    monkeypatch.setattr(
        qa.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion(
            '{"status": "warm", "next_question": "Qual produto?", "collected": {}, "reasoning": "vago"}'
        )),
    )

    result = await qa.qualify(
        [{"role": "user", "content": "Quero saber mais sobre seus produtos"}],
        "Empresa de tecnologia",
        "",
    )

    assert result["status"] == "warm"
    assert result["next_question"] == "Qual produto?"
    assert result["collected"] == {}


@pytest.mark.asyncio
async def test_qualify_returns_fallback_on_invalid_json(monkeypatch):
    import backend.agents.qualification as qa

    monkeypatch.setattr(
        qa.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion("não é json")),
    )

    result = await qa.qualify([], "ctx", "")

    assert result["status"] == "warm"
    assert result["next_question"] is None
    assert result["collected"] == {}


@pytest.mark.asyncio
async def test_qualify_hot_lead(monkeypatch):
    import backend.agents.qualification as qa

    monkeypatch.setattr(
        qa.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion(
            '{"status": "hot", "next_question": null, "collected": {"email": "a@b.com"}, "reasoning": "compra clara"}'
        )),
    )

    result = await qa.qualify(
        [{"role": "user", "content": "Quero comprar o produto X agora, pode me passar o preço?"}],
        "Empresa Solar",
        "Hot: intenção clara de compra",
    )

    assert result["status"] == "hot"
    assert result["next_question"] is None
    assert result["collected"]["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_generate_response_returns_text(monkeypatch):
    import backend.agents.response as ra

    monkeypatch.setattr(
        ra.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion("Qual produto te interessa?")),
    )

    result = await ra.generate_response(
        history=[{"role": "user", "content": "Olá"}],
        next_question="Qual produto te interessa?",
        lead_status="warm",
        agent_prompt="",
        business_context="Empresa X",
    )

    assert result == "Qual produto te interessa?"


@pytest.mark.asyncio
async def test_generate_response_with_catalog_marker(monkeypatch):
    import backend.agents.response as ra

    monkeypatch.setattr(
        ra.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion("Segue nosso catálogo! [ENVIAR_CATALOGO]")),
    )

    result = await ra.generate_response(
        history=[{"role": "user", "content": "Me manda o catálogo"}],
        next_question=None,
        lead_status="warm",
        agent_prompt="",
        has_catalog=True,
    )

    assert "[ENVIAR_CATALOGO]" in result


@pytest.mark.asyncio
async def test_generate_response_empty_returns_empty_string(monkeypatch):
    import backend.agents.response as ra

    monkeypatch.setattr(
        ra.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion("")),
    )

    result = await ra.generate_response(
        history=[{"role": "user", "content": "..."}],
        next_question=None,
        lead_status="cold",
        agent_prompt="",
    )

    assert result == ""


@pytest.mark.asyncio
async def test_generate_followup_context_returns_string(monkeypatch):
    import backend.agents.followup as fu

    monkeypatch.setattr(
        fu.client.chat.completions,
        "create",
        AsyncMock(return_value=_mock_completion("Vi que você perguntou sobre painéis — ainda posso ajudar?")),
    )

    result = await fu.generate_followup_context(
        history=[{"role": "user", "content": "Quero saber sobre painéis solares"}],
        attempt=1,
    )

    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_followup_attempt_2_adds_urgency(monkeypatch):
    import backend.agents.followup as fu

    captured = {}

    async def fake_create(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return _mock_completion("Última chance — ainda posso ajudar com seu projeto?")

    monkeypatch.setattr(fu.client.chat.completions, "create", fake_create)

    await fu.generate_followup_context(history=[], attempt=2)

    system_content = captured["messages"][0]["content"]
    assert "urgência" in system_content.lower() or "urgency" in system_content.lower() or "Crie" in system_content
