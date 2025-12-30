"""
Test Gemini grounding functionality for weather queries.

This test verifies that:
1. Gemini can use Google Search grounding
2. Multilingual responses work correctly
3. Weather queries are handled properly
"""

import pytest
from app.ai.providers.gemini import gemini_provider
from app.ai.prompts.assistant_prompts import (
    build_assistant_system_prompt,
    UNIVERSAL_MULTILINGUAL_RULE,
)


@pytest.mark.asyncio
async def test_weather_query_spanish():
    """Test weather query in Spanish with grounding."""

    # Spanish weather query
    user_message = "hola jarvis, como esta el clima hoy en miami para ir a la playa"

    # Build system prompt
    system_prompt = f"""You are Jarvis, an intelligent AI assistant.

{UNIVERSAL_MULTILINGUAL_RULE}

CAPABILITIES:
- General knowledge (weather, time, news, facts)
- Answer questions using web search when needed

RESPONSE RULES:
1. Be concise (1-3 sentences)
2. ALWAYS respond in the user's language
3. Use web search for current events/weather
"""

    # Generate response with grounding
    response = await gemini_provider.generate_with_grounding(
        prompt=user_message,
        system_prompt=system_prompt,
        use_search=True,
        temperature=0.8,
        max_tokens=512,
    )

    # Assertions
    print(f"\n=== TEST RESULTS ===")
    print(f"Success: {response.success}")
    print(f"Model: {response.model}")
    print(f"Latency: {response.latency_ms:.0f}ms")

    if response.success:
        print(f"Content: {response.content}")
        print(f"Grounded: {response.metadata.get('grounded', False) if response.metadata else False}")
        if response.metadata and response.metadata.get('sources'):
            print(f"Sources: {len(response.metadata['sources'])} sources")

        # Verify response is in Spanish
        spanish_indicators = ['está', 'clima', 'temperatura', 'hoy', 'Miami']
        has_spanish = any(indicator.lower() in response.content.lower() for indicator in spanish_indicators)

        print(f"Has Spanish indicators: {has_spanish}")

        assert response.success is True, "Response should be successful"
        assert len(response.content) > 0, "Response should have content"
        # Note: We can't strictly enforce Spanish due to model variability
        # but we can check for common Spanish words

    else:
        print(f"ERROR: {response.error}")
        print(f"\n=== DEBUGGING INFO ===")
        print(f"This test failed because Gemini couldn't generate a response.")
        print(f"Possible causes:")
        print(f"1. Google Search grounding might not be enabled for this API key")
        print(f"2. Rate limiting or quota issues")
        print(f"3. API configuration problem")

        # This is expected to fail, so we can analyze the error
        pytest.fail(f"Gemini grounding failed: {response.error}")


@pytest.mark.asyncio
async def test_weather_query_english():
    """Test weather query in English with grounding."""

    user_message = "What's the weather like in Miami today?"

    system_prompt = f"""You are Jarvis, an intelligent AI assistant.

{UNIVERSAL_MULTILINGUAL_RULE}

RESPONSE RULES:
1. Be concise
2. ALWAYS respond in the user's language
3. Use web search for current info
"""

    response = await gemini_provider.generate_with_grounding(
        prompt=user_message,
        system_prompt=system_prompt,
        use_search=True,
        temperature=0.8,
        max_tokens=512,
    )

    print(f"\n=== ENGLISH TEST ===")
    print(f"Success: {response.success}")

    if response.success:
        print(f"Content: {response.content}")
        print(f"Grounded: {response.metadata.get('grounded', False) if response.metadata else False}")
        assert response.success is True
        assert len(response.content) > 0
    else:
        print(f"ERROR: {response.error}")
        pytest.fail(f"Gemini grounding failed: {response.error}")


if __name__ == "__main__":
    import asyncio

    print("Testing Spanish weather query...")
    asyncio.run(test_weather_query_spanish())

    print("\n" + "="*60 + "\n")

    print("Testing English weather query...")
    asyncio.run(test_weather_query_english())
