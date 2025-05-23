# from nagisa_mcp.server import mcp

def register_tools():
    from nagisa_mcp.server import mcp
    @mcp.tool()
    async def translate_text(text: str, target_language: str) -> str:
        # 这里只是模拟翻译，实际应用中应该调用真实的翻译 API
        translations = {
            "你好": {
                "en": "Hello",
                "ja": "こんにちは",
                "ko": "안녕하세요"
            }
        }
        if text in translations and target_language in translations[text]:
            return translations[text][target_language]
        return f"[Translation not available for {text} to {target_language}]" 