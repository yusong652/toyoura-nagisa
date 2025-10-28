"""
Gemini Streaming Chunk Structure Analysis

专注分析Gemini流式输出的chunk结构：
1. 每个chunk包含哪些parts
2. 如何区分thinking和text
3. chunk是否会跨越多个parts

Usage:
    uv run python -m backend.tests.gemini_chunk_structure_test
"""

import asyncio
import os
from datetime import datetime


# 测试提示词 - 设计为触发thinking
TEST_PROMPTS = {
    "with_thinking": "Solve this step by step: If a train travels 120 km in 2 hours, what is its average speed?",
    "simple_text": "Write a haiku about coding.",
}


def print_separator(text="", char="=", length=80):
    """打印分隔线"""
    if text:
        padding = (length - len(text) - 2) // 2
        print(f"{char * padding} {text} {char * padding}")
    else:
        print(char * length)


async def analyze_gemini_chunks():
    """详细分析Gemini streaming chunks的结构"""
    print_separator("GEMINI CHUNK STRUCTURE ANALYSIS")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        from google import genai
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from config.llm import get_llm_settings

        settings = get_llm_settings()
        gemini_config = settings.get_gemini_config()
        client = genai.Client(api_key=gemini_config.google_api_key)
        print(f"✓ Gemini client initialized\n")

        for test_name, prompt in TEST_PROMPTS.items():
            print_separator(f"TEST: {test_name.upper()}", "-")
            print(f"Prompt: {prompt}\n")

            chunk_count = 0

            # 配置：启用thinking
            from google.genai import types
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=2000  # 允许最多2000 tokens的thinking
                )
            )

            stream = await client.aio.models.generate_content_stream(
                model='gemini-2.0-flash-thinking-exp-01-21',  # 使用支持thinking的模型
                contents=prompt,
                config=config
            )

            async for chunk in stream:
                chunk_count += 1

                print(f"\n{'='*80}")
                print(f"CHUNK #{chunk_count}")
                print(f"{'='*80}")

                # 1. 基本类型信息
                print(f"\n[1. Basic Info]")
                print(f"  Chunk type: {type(chunk).__name__}")
                print(f"  Has 'text': {hasattr(chunk, 'text')}")
                print(f"  Has 'candidates': {hasattr(chunk, 'candidates')}")

                # 2. 所有属性
                attrs = [attr for attr in dir(chunk) if not attr.startswith('_')]
                print(f"\n[2. All Attributes]")
                print(f"  {', '.join(attrs)}")

                # 3. 分析candidates
                if hasattr(chunk, 'candidates') and chunk.candidates:
                    print(f"\n[3. Candidates Analysis]")
                    print(f"  Candidates count: {len(chunk.candidates)}")

                    for cand_idx, candidate in enumerate(chunk.candidates):
                        print(f"\n  --- Candidate #{cand_idx} ---")

                        # 检查content
                        if hasattr(candidate, 'content'):
                            content = candidate.content
                            print(f"    Content type: {type(content).__name__}")

                            # 检查parts
                            if hasattr(content, 'parts'):
                                parts = content.parts
                                print(f"    Parts count: {len(parts)}")

                                # 详细分析每个part
                                for part_idx, part in enumerate(parts):
                                    print(f"\n      ╔═══ Part #{part_idx} ═══╗")
                                    print(f"      Part type: {type(part).__name__}")

                                    # 检查part的所有属性
                                    part_attrs = [attr for attr in dir(part) if not attr.startswith('_')]
                                    print(f"      Attributes: {', '.join(part_attrs[:10])}...")  # 只显示前10个

                                    # 检查thought标志（Gemini用这个标识thinking）
                                    if hasattr(part, 'thought'):
                                        thought_flag = part.thought
                                        if thought_flag:
                                            print(f"      ⚠️  THOUGHT FLAG: True (This is a thinking part!)")
                                        else:
                                            print(f"      ℹ️  THOUGHT FLAG: False/None (This is regular text)")

                                    # 检查text属性
                                    if hasattr(part, 'text'):
                                        text_val = part.text
                                        if text_val:
                                            print(f"      ✓ TEXT content:")
                                            print(f"        Length: {len(text_val)}")
                                            print(f"        Preview: {repr(text_val[:100])}")
                                        else:
                                            print(f"      ✗ TEXT is None/empty")

                                    # 检查thought_signature（thinking的签名）
                                    if hasattr(part, 'thought_signature'):
                                        sig = part.thought_signature
                                        if sig:
                                            print(f"      🔏 THOUGHT_SIGNATURE found: {len(sig)} bytes")

                                    # 检查function_call属性
                                    if hasattr(part, 'function_call'):
                                        fc = part.function_call
                                        if fc:
                                            print(f"      🔧 FUNCTION_CALL found:")
                                            print(f"        {fc}")

                                    # 检查其他可能的内容类型
                                    content_fields = ['inline_data', 'file_data', 'video_metadata']
                                    for field in content_fields:
                                        if hasattr(part, field) and getattr(part, field):
                                            print(f"      📎 {field.upper()} found")

                                    print(f"      ╚═══════════════╝")

                        # 检查finish_reason
                        if hasattr(candidate, 'finish_reason'):
                            finish_reason = candidate.finish_reason
                            if finish_reason:
                                print(f"    Finish reason: {finish_reason}")

                # 4. 直接访问.text属性
                if hasattr(chunk, 'text'):
                    text = chunk.text
                    if text:
                        print(f"\n[4. Direct .text Access]")
                        print(f"  Text length: {len(text)}")
                        print(f"  Text content: {repr(text[:150])}")
                    else:
                        print(f"\n[4. Direct .text Access]")
                        print(f"  Text is None/empty")

                # 只详细打印前5个chunk
                if chunk_count >= 5:
                    print(f"\n{'─'*80}")
                    print(f"[Continuing to count remaining chunks...]")
                    # 继续计数但不打印详情
                    async for _ in stream:
                        chunk_count += 1
                    break

            print(f"\n{'='*80}")
            print(f"Summary: Total {chunk_count} chunks received")
            print(f"{'='*80}\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(analyze_gemini_chunks())
