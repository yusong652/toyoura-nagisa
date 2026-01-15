"""
Gemini API debugging utilities.
"""

import json
import copy
from typing import Dict, Any, List, Optional


class GoogleDebugger:
    """Debug utilities for Gemini API interactions."""

    @staticmethod
    def print_request(contents: List[Dict[str, Any]], config, model: str) -> None:
        """Print debug info for API request."""
        print(f"\n========== Gemini API Request ==========")
        print(f"🤖 Model: {model}")
        print(f"📝 Context items: {len(contents)}")

        config_dict = config.model_dump()
        debug_config = GoogleDebugger._truncate_config(config_dict)

        payload = {"model": model, "contents": contents, "config": debug_config}
        payload = GoogleDebugger._censor_payload(payload)

        print("\nPayload (truncated):")
        GoogleDebugger._print_json(payload)
        print("========== END ==========")

    @staticmethod
    def print_response(response) -> None:
        """Print debug info for successful API response."""
        print(f"\n========== Gemini API Response ==========")

        if hasattr(response, 'error') and response.error:
            print(f"❌ Error: {response.error}")
            return

        if hasattr(response, 'candidates') and response.candidates:
            print(f"📋 Candidates: {len(response.candidates)}")
            for i, candidate in enumerate(response.candidates):
                finish_reason = getattr(candidate, 'finish_reason', 'N/A')
                print(f"  [{i+1}] finish_reason: {finish_reason}")

                if hasattr(candidate, 'content') and candidate.content:
                    parts = getattr(candidate.content, 'parts', []) or []
                    for j, part in enumerate(parts):
                        if hasattr(part, 'text') and part.text:
                            preview = part.text[:100] + "..." if len(part.text) > 100 else part.text
                            is_thought = getattr(part, 'thought', False)
                            thought_marker = " [THOUGHT]" if is_thought else ""
                            print(f"      text[{j}]{thought_marker}: {repr(preview)}")
                        elif hasattr(part, 'function_call') and part.function_call:
                            print(f"      function_call[{j}]: {part.function_call.name}")
        else:
            print("❌ No candidates")

        print("========== END ==========")

    @staticmethod
    def print_streaming_chunk(chunk, chunk_index: int) -> None:
        """Print debug info for streaming chunk."""
        print(f"\n---------- Streaming Chunk [{chunk_index}] ----------")

        if not hasattr(chunk, 'candidates') or not chunk.candidates:
            print("❌ No candidates in chunk")
            print("---------- END ----------")
            return

        candidate = chunk.candidates[0]
        finish_reason = getattr(candidate, 'finish_reason', None)
        print(f"finish_reason: {finish_reason}")

        if not hasattr(candidate, 'content') or not candidate.content:
            print("❌ No content in candidate")
            print("---------- END ----------")
            return

        parts = getattr(candidate.content, 'parts', None)
        if not parts:
            print("❌ No parts in content (parts is None or empty)")
            print(f"   content object: {candidate.content}")
            print("---------- END ----------")
            return

        print(f"parts count: {len(parts)}")
        for j, part in enumerate(parts):
            part_info = []

            # Check for text
            if hasattr(part, 'text'):
                text = part.text
                if text:
                    preview = text[:100] + "..." if len(text) > 100 else text
                    is_thought = getattr(part, 'thought', False)
                    thought_marker = " [THOUGHT]" if is_thought else ""
                    part_info.append(f"text{thought_marker}: {repr(preview)}")
                else:
                    part_info.append("text: <empty string>")

            # Check for function_call
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                part_info.append(f"function_call: {fc.name}")

            # Check for thought_signature
            if hasattr(part, 'thought_signature') and part.thought_signature:
                part_info.append("has_thought_signature: True")

            if part_info:
                print(f"  part[{j}]: {', '.join(part_info)}")
            else:
                print(f"  part[{j}]: <unknown part type> {type(part).__name__}")

        # Print usage metadata if available
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            usage = chunk.usage_metadata
            print(f"usage: prompt={getattr(usage, 'prompt_token_count', 'N/A')}, "
                  f"candidates={getattr(usage, 'candidates_token_count', 'N/A')}, "
                  f"thoughts={getattr(usage, 'thoughts_token_count', 'N/A')}")

        print("---------- END ----------")

    @staticmethod
    def print_streaming_summary(total_chunks: int, empty_chunks: int) -> None:
        """Print summary after streaming completes."""
        print(f"\n========== Streaming Summary ==========")
        print(f"Total chunks: {total_chunks}")
        print(f"Empty chunks (no valid parts): {empty_chunks}")
        print("========== END ==========")

    @staticmethod
    def print_error(error_type: str, model: str, response=None, candidate=None) -> None:
        """Print detailed debug info for API errors."""
        print(f"\n========== Gemini API Error ==========")
        print(f"❌ Error: {error_type}")
        print(f"🤖 Model: {model}")

        if response is not None:
            print(f"\n📦 Response object:")
            print(f"   type: {type(response).__name__}")
            if hasattr(response, 'candidates'):
                print(f"   candidates: {len(response.candidates) if response.candidates else 'None'}")

        if candidate is not None:
            print(f"\n📋 Candidate details:")
            finish_reason = getattr(candidate, 'finish_reason', None)
            safety_ratings = getattr(candidate, 'safety_ratings', None)
            content = getattr(candidate, 'content', None)

            print(f"   finish_reason: {finish_reason}")
            print(f"   safety_ratings: {safety_ratings}")
            print(f"   content: {content}")
            print(f"   content.parts: {getattr(content, 'parts', None) if content else None}")

        print("========== END ==========")

    @staticmethod
    def _truncate_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate long fields in config for debug output."""
        result = {}
        for key, value in config_dict.items():
            if key == "system_instruction" and isinstance(value, str):
                result[key] = GoogleDebugger._truncate(value, 200, "system_instruction")
            elif key == "tools" and isinstance(value, list):
                result[key] = GoogleDebugger._truncate_tools(value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _truncate_tools(tools: list) -> list:
        """Truncate tool descriptions for debug output."""
        result = []
        for tool in tools:
            if not isinstance(tool, dict):
                result.append(f"<{type(tool).__name__}>")
                continue

            tool_copy = tool.copy()
            # Handle google_search and other special tools
            if 'google_search' in tool_copy:
                result.append({'google_search': '<GoogleSearch>'})
                continue
            if 'code_execution' in tool_copy:
                result.append({'code_execution': '<CodeExecution>'})
                continue
            if 'function_declarations' in tool_copy:
                decls = []
                # Use `or []` to handle None values
                for func in tool_copy.get('function_declarations') or []:
                    if isinstance(func, dict):
                        func_copy = func.copy()
                        if 'description' in func_copy:
                            func_copy['description'] = GoogleDebugger._truncate(
                                func_copy['description'], 80, func.get('name', 'func')
                            )
                        if 'parameters' in func_copy:
                            func_copy['parameters'] = {'properties': '...'}
                        decls.append(func_copy)
                    else:
                        decls.append(func)
                tool_copy['function_declarations'] = decls
            result.append(tool_copy)
        return result

    @staticmethod
    def _truncate(text: str, max_len: int, field: str = "text") -> str:
        """Truncate text with info about original length."""
        if not isinstance(text, str):
            return text
        text = ' '.join(text.split())  # Normalize whitespace
        if len(text) <= max_len:
            return text
        return f"{text[:max_len-20]}... [{field}: {len(text)} chars]"

    @staticmethod
    def _censor_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Censor large data fields in payload for logging."""
        payload = copy.deepcopy(payload)

        for content in payload.get("contents", []):
            if not isinstance(content, dict):
                continue
            for part in content.get("parts", []):
                if isinstance(part, dict) and 'inline_data' in part:
                    data = part.get('inline_data', {}).get('data', '')
                    if isinstance(data, str) and len(data) > 200:
                        part['inline_data']['data'] = f"{data[:50]}... [truncated {len(data)} chars]"

        return payload

    @staticmethod
    def _print_json(obj: Any) -> None:
        """Print object as formatted JSON."""
        def convert(o):
            if isinstance(o, dict):
                return {k: convert(v) for k, v in o.items()}
            elif isinstance(o, list):
                return [convert(i) for i in o]
            elif hasattr(o, '__dict__'):
                return GoogleDebugger._convert_sdk_object(o)
            else:
                return o

        try:
            print(json.dumps(convert(obj), indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"(JSON failed: {e})\n{obj}")

    @staticmethod
    def _convert_sdk_object(obj: Any) -> Any:
        """Convert Gemini SDK objects to readable format."""
        type_name = type(obj).__name__

        # Handle Part objects
        if type_name == "Part":
            result = {}

            # Check for thought flag (thinking content)
            if hasattr(obj, 'thought') and obj.thought:
                result['thought'] = True

            # Check for thought_signature (required for Gemini 3 tool calling)
            if hasattr(obj, 'thought_signature') and obj.thought_signature:
                sig = obj.thought_signature
                # Truncate signature for display (it's usually long base64)
                if isinstance(sig, bytes):
                    import base64
                    sig_b64 = base64.b64encode(sig).decode('utf-8')
                else:
                    sig_b64 = str(sig)
                result['thought_signature'] = GoogleDebugger._truncate(sig_b64, 50, "sig")

            if hasattr(obj, 'text') and obj.text:
                result['text'] = GoogleDebugger._truncate(obj.text, 150, "text")
                return result
            elif hasattr(obj, 'function_call') and obj.function_call:
                fc = obj.function_call
                name = getattr(fc, 'name', 'unknown')
                args = getattr(fc, 'args', {})
                args_str = str(args) if args else "{}"
                result['function_call'] = name
                result['args'] = GoogleDebugger._truncate(args_str, 150, "args")
                return result
            elif hasattr(obj, 'function_response') and obj.function_response:
                fr = obj.function_response
                name = getattr(fr, 'name', 'unknown')
                response = getattr(fr, 'response', {})
                response_str = str(response) if response else "{}"
                result['function_response'] = name
                result['response'] = GoogleDebugger._truncate(response_str, 150, "response")
                return result
            elif hasattr(obj, 'inline_data') and obj.inline_data:
                result['inline_data'] = "[binary data]"
                return result

            return result if result else "<Part: empty>"

        # Handle Content objects
        if type_name == "Content":
            result = {}
            if hasattr(obj, 'role'):
                result['role'] = obj.role
            if hasattr(obj, 'parts') and obj.parts:
                result['parts'] = [GoogleDebugger._convert_sdk_object(p) for p in obj.parts]
            return result if result else f"<Content: empty>"

        # Fallback: try model_dump() for pydantic objects
        if hasattr(obj, 'model_dump'):
            try:
                return obj.model_dump()
            except Exception:
                pass

        return f"<{type_name}>"

