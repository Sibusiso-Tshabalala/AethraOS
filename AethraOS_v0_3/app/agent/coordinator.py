from app.agent.agents import AGENTS, Agent


class AgentCoordinator:
    """
    Routes user requests to an appropriate specialised agent.

    This first version uses lightweight keyword-based routing.
    All agents share the existing Aethra AI model and tool system.
    """

    def __init__(self):

        self.agents = AGENTS

    def select_agent(self, message: str) -> Agent:

        text = message.lower()

        # Computer interaction requests.
        computer_keywords = [
            "open ",
            "launch ",
            "start ",
            "click ",
            "move the mouse",
            "move my mouse",
            "type ",
            "press ",
            "scroll ",
            "take a screenshot",
            "look at my screen",
            "see my screen",
            "what is on my screen",
            "what's on my screen",
            "read the screen",
            "screen text",
            "ocr",
            "computer specifications",
            "computer specs",
            "system information",
            "chrome",
            "edge",
            "file explorer",
            "explorer",
            "word",
            "excel",
            "powershell",
            "command prompt",
        ]

        if any(keyword in text for keyword in computer_keywords):
            return self.agents["computer"]

        # File-related requests.
        file_keywords = [
            "create a file",
            "create file",
            "make a file",
            "write a file",
            "save a file",
            "list my downloads",
            "show my downloads",
            "downloads folder",
            "read this file",
            "file contents",
        ]

        if any(keyword in text for keyword in file_keywords):
            return self.agents["file"]

        # Coding and software development requests.
        coding_keywords = [
            "python",
            "javascript",
            "typescript",
            "java ",
            "c#",
            "html",
            "css",
            "sql",
            "code",
            "coding",
            "program",
            "programming",
            "debug",
            "debugging",
            "traceback",
            "exception",
            "syntax error",
            "function",
            "class ",
            "api",
            "database",
            "software development",
        ]

        if any(keyword in text for keyword in coding_keywords):
            return self.agents["coding"]

        # Research requests.
        research_keywords = [
            "research ",
            "research:",
            "investigate ",
            "find information",
            "look up ",
            "compare ",
            "gather information",
            "sources for",
            "what are the latest",
            "latest information",
            "in-depth analysis",
        ]

        if any(keyword in text for keyword in research_keywords):
            return self.agents["research"]

        # General assistant is the fallback.
        return self.agents["general"]

    def get_agent_instructions(self, message: str) -> str:

        agent = self.select_agent(message)

        return (
            f"\n\nACTIVE SPECIALIST: {agent.name}\n"
            f"ROLE: {agent.description}\n\n"
            f"SPECIALIST INSTRUCTIONS:\n"
            f"{agent.instructions}\n"
        )

    def get_agent_name(self, message: str) -> str:

        return self.select_agent(message).name