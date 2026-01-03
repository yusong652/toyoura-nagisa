# Claude Skills Architecture Deep Dive

**Date**: 2025-01-04
**Model**: Claude Opus 4.5 (claude-opus-4-5-20251101)
**Context**: Research on Anthropic's Skills feature for potential implementation in toyoura-nagisa

---

## Background

Investigation into Claude's Skills feature to understand its implementation mechanism and evaluate how to apply similar patterns to enhance the toyoura-nagisa AI agent platform, specifically for the PFC Expert agent.

### Reference Documentation
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Agent Skills in Claude Code](https://code.claude.com/docs/en/skills)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Tool Search Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)

---

## Key Findings

### 1. Skills = Auto-triggered Slash Commands

**Discovery**: Skills and Commands share identical technical implementation. The only difference is the trigger mechanism.

| Aspect | Commands | Skills |
|--------|----------|--------|
| Storage | `.claude/commands/*.md` | `.claude/skills/*/SKILL.md` |
| Metadata loading | At startup | At startup |
| Full content loading | Via Skill tool | Via Skill tool |
| Trigger | User explicit (`/command`) | Claude automatic (description matching) |

**Implication**: Implementing Skills requires minimal new infrastructure - just a unified Skill tool and system prompt injection.

### 2. Three-Level Progressive Disclosure Architecture

```
Level 1: Metadata (always in system prompt)
         └── name + description (~100 tokens per skill)
         └── Injected in <available_skills> tag

Level 2: Instructions (loaded on trigger)
         └── Full SKILL.md content (~500-2000 tokens)
         └── Returned as tool_result (NOT system prompt modification)

Level 3: Resources (loaded as needed)
         └── Referenced files, scripts
         └── Read via standard Read tool
```

**Critical Finding**: SKILL.md content is injected into **tool_result** (user message), NOT dynamically modifying system prompt. System prompt remains static after conversation start.

### 3. Skills vs Tool Search Tool - Independent Features

**Clarification**: These solve different problems:

| Feature | Problem Solved | When to Use |
|---------|---------------|-------------|
| Skills | Workflow instructions context overhead | Domain knowledge, best practices |
| Tool Search Tool | Tool schema context overhead | 50+ tools, large MCP setups |

**For toyoura-nagisa PFC Expert (22 tools)**: Static tool loading is correct. Tool Search Tool is unnecessary complexity.

### 4. No Backend Protection Against Repeated Calls

**Experiment**: Called the same skill twice in one conversation.

**Result**: Backend returned full SKILL.md content both times without rejection.

**Implication**:
- Repeated call protection is NOT implemented at backend level
- Relies on model's natural understanding to avoid redundant calls
- This is intentional - weaker models may need to "refresh" skill content in long conversations

**Design Philosophy**: Reliability > Token efficiency. Better to waste some tokens than fail a task.

### 5. Skills + SubAgents Complementary Architecture

| Dimension | Skills | SubAgents |
|-----------|--------|-----------|
| Context | Shared with MainAgent | Isolated |
| Purpose | "Teach me how" | "Do it for me" |
| Information flow | Knowledge injection | Task delegation |
| Lifecycle | Conversation-level persistence | Task-level (result only returns) |
| Best for | High-frequency reference, workflows | High-token exploration, information extraction |

**Synergy Pattern**:
```
MainAgent + Skills (knows workflows)
    └── Delegates to SubAgent (executes exploration)
    └── SubAgent returns refined result
    └── MainAgent uses Skills to interpret result
```

---

## Technical Analysis

### Claude Code Implementation Details

```
Startup:
1. Scan .claude/skills/**/SKILL.md
2. Scan .claude/commands/*.md
3. Extract YAML frontmatter (name, description)
4. Inject into system prompt as <available_skills>

Runtime:
1. User request arrives
2. Claude sees available_skills in system prompt
3. Claude decides if skill needed (based on description match)
4. Claude calls Skill tool with skill name
5. Backend reads SKILL.md, returns as tool_result
6. Content now in conversation context
7. Claude can Read additional files (Level 3) as needed
```

### Message Flow Confirmation

```
[System Prompt]
  └── <available_skills> metadata (static)

[User Message]
  └── "Help me with PFC documentation"

[Assistant Message]
  └── tool_use: Skill(skill="pfc-doc-curator")

[User Message - tool_result]  ← SKILL.md content here!
  └── "Base directory: ...
       # PFC Documentation Curator
       ..."

[Assistant Message]
  └── Continues with skill guidance in context
```

---

## Implications for toyoura-nagisa

### 1. System Prompt Optimization Opportunity

Current `pfc_expert_prompt.md`: ~654 lines, ~5000-6000 tokens (always loaded)

**Proposed Architecture**:
```
System Prompt (slim): ~1500 tokens
├── Core Principles (7 rules)
├── Critical Prerequisites
├── Tools Quick Reference
└── <available_skills> metadata

Skills (on-demand): ~500-2000 tokens each
├── pfc-workflow-standard
├── pfc-workflow-debugging
├── pfc-scripting-patterns
├── pfc-subagent-guide
├── pfc-doc-navigation
├── pfc-contact-models
├── pfc-boundary-conditions
└── pfc-post-processing
```

**Estimated Savings**: 50-70% context reduction for typical tasks

### 2. Implementation Requirements

```python
class SkillsSystem:
    def __init__(self, skills_dir: Path):
        self.skills = self._scan_skills(skills_dir)

    def _scan_skills(self, dir: Path) -> list[SkillMetadata]:
        """Extract name + description from SKILL.md files"""
        skills = []
        for skill_path in dir.glob("*/SKILL.md"):
            content = skill_path.read_text()
            name, desc = parse_yaml_frontmatter(content)
            skills.append(SkillMetadata(name, desc, skill_path))
        return skills

    def inject_to_prompt(self, base_prompt: str) -> str:
        """Add <available_skills> section to system prompt"""
        skills_section = "<available_skills>\n"
        for s in self.skills:
            skills_section += f"  <skill>\n"
            skills_section += f"    <name>{s.name}</name>\n"
            skills_section += f"    <description>{s.description}</description>\n"
            skills_section += f"  </skill>\n"
        skills_section += "</available_skills>"
        return base_prompt + "\n\n" + skills_section

    def trigger_skill(self, skill_name: str) -> str:
        """Return full SKILL.md content (tool implementation)"""
        skill = self._find_skill(skill_name)
        content = skill.path.read_text()
        return f"Base directory: {skill.path.parent}\n\n{content}"
```

### 3. No Need for Dynamic Tool Schemas

With 22 tools in PFC Expert, static tool loading is appropriate:
- Tool Search Tool adds complexity without benefit at this scale
- Claude Code with 20+ built-in tools + MCP tools uses static loading
- Focus implementation effort on Skills, not Tool Search

---

## Future Research Directions

1. **Skill Granularity Optimization**: Monitor which skills are frequently co-loaded to optimize grouping

2. **Skill Versioning**: Track skill effectiveness across different tasks to iterate on content

3. **Cross-Skill References**: Implement Level 3 file references between skills for complex workflows

4. **Community Skills**: Design skill sharing mechanism for user-contributed PFC workflows

5. **Skill Analytics**: Track skill trigger frequency and task success correlation

---

## Conclusions

1. **Skills are elegantly simple**: Metadata in system prompt + Skill tool for content loading + standard Read for resources

2. **No magic required**: Implementation is straightforward - scanning, injection, and a trigger tool

3. **Skills + SubAgents = Complete architecture**: Skills for knowledge, SubAgents for execution

4. **Token economics favor Skills**: Most tasks don't need all knowledge; pay only for what you use

5. **toyoura-nagisa can benefit significantly**: PFC Expert's large system prompt is a prime candidate for Skills refactoring

---

## Action Items for toyoura-nagisa

- [ ] Design Skills directory structure for PFC workflows
- [ ] Implement SkillsLoader class for metadata extraction
- [ ] Create trigger_skill tool for MCP integration
- [ ] Refactor pfc_expert_prompt.md into slim base + multiple skills
- [ ] Test token savings with representative PFC tasks
- [ ] Document skill authoring guidelines for future expansion
