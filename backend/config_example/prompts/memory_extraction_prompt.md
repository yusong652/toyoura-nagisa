Extract important information from User-Assistant conversations. EVERY fact must clearly state the subject (User, Assistant, or both).

CRITICAL: All facts MUST start with "User", "Assistant", or "User and Assistant". Never create facts without clear subjects.

Examples:

Input: User: I love drinking matcha tea
Assistant: Got it, I'll remember that you enjoy matcha tea
Output: {"facts": ["User loves drinking matcha tea"]}

Input: User: You explain things very clearly
Assistant: Thank you, I'll continue using detailed step-by-step explanations for complex topics
Output: {"facts": ["Assistant is good at explaining complex topics with detailed steps", "User finds Assistant's explanations clear"]}

Input: User: Nice weather today
Assistant: Yes, it is
Output: {"facts": []}

Extract: preferences, skills, knowledge, working styles, successful collaboration patterns. Ignore: greetings, temporary issues, weather talk.