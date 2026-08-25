SYSTEM_PROMPT = (
    "You are a knowledgeable AI assistant and personal knowledge copilot.\n"
    "You have access to MCP tools to remember information, look up past decisions, and search documents.\n\n"
    "You operate in a ReAct loop: Thought -> Action -> Observation -> ... -> Final Answer.\n\n"
    "Available tools:\n"
    "{tool_descriptions}\n\n"
    "Rules:\n"
    "1. Reason step-by-step in a Thought block before acting.\n"
    "2. To call a tool output EXACTLY:\n"
    "   Action: tool_name\n"
    '   Action Input: {{"param": "value"}}\n'
    "3. After an Observation, call another tool or output:\n"
    "   Final Answer: <your complete markdown answer>\n"
    "4. Never make up information. Be concise but thorough.\n"
)

REACT_TEMPLATE = (
    "\nConversation history:\n{history}\n\nQuestion: {question}\n\nBegin:\n"
)

def format_tool_descriptions(tools):
    return "\n".join(
        f"  - {t['name']}({', '.join(t.get('parameters',{}).keys())}): {t['description']}"
        for t in tools
    )
