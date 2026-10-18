from app.instagram_content import account_voice
from app.instagram_content.caption_writer import DEFAULT_BRAND_VOICE, AnthropicCaptionWriter, CaptionWriterConfig


def test_the_dashboard_voice_goes_into_the_prompt_and_empty_restores_the_default():
    account_voice.save("")
    w = AnthropicCaptionWriter(CaptionWriterConfig(api_key="x"))
    assert w._voice() == DEFAULT_BRAND_VOICE and account_voice.is_default()
    account_voice.save("  A cook in Lisbon. Warm, nerdy about bread, never preachy.  ")
    assert w._voice() == "A cook in Lisbon. Warm, nerdy about bread, never preachy."
    assert "nerdy about bread" in w._build_prompt("food", [], "single_image")
    account_voice.save("")
    assert w._voice() == DEFAULT_BRAND_VOICE


def test_an_explicit_voice_in_the_config_wins():
    w = AnthropicCaptionWriter(CaptionWriterConfig(api_key="x", brand_voice="fixed"))
    assert w._voice() == "fixed"
