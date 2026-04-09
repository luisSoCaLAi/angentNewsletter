"""
Research Agent — finds the top 3 hottest AI topics of the week using
Claude Opus 4.6 with the web_search server-side tool.
"""

import json
import re
import time
from datetime import datetime
import anthropic
from config import ANTHROPIC_API_KEY

SYSTEM_PROMPT = """You are an AI industry research analyst for SoCal AI Solutions, \
an AI consulting company that helps small and medium businesses across the US adopt AI.

Your job is to find the top 3 hottest AI topics RIGHT NOW this week. Prioritize:
- Practical AI tools and platforms SMBs can actually use today
- Major product launches or significant capability updates
- AI automation wins with real business ROI examples
- Trends that are generating buzz in the business community

Search for recent news (last 7 days). After researching, return ONLY a valid JSON object \
with NO extra text, markdown, or explanation. Use this exact structure:

{
  "topics": [
    {
      "title": "Concise, engaging title (max 8 words)",
      "summary": "2-3 sentences explaining why this is hot right now and why it matters",
      "key_points": [
        "Specific fact or development #1",
        "Specific fact or development #2",
        "Specific fact or development #3"
      ],
      "business_impact": "One sentence on how this specifically helps small/medium businesses",
      "sources": ["https://source1.com", "https://source2.com"]
    }
  ]
}"""


class ResearchAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def research(self) -> list[dict]:
        """
        Run the research pipeline. Returns a list of 3 topic dicts.
        Handles the pause_turn case for the server-side web_search tool.
        """
        today = datetime.now().strftime("%B %d, %Y")
        messages = [
            {
                "role": "user",
                "content": (
                    f"Today is {today}. Research the top 3 hottest AI topics this week. "
                    "Search for the latest news, product launches, and business AI developments "
                    "from the past 7 days. Focus on what matters most for SMBs. "
                    "Return your findings as a JSON object following the specified format exactly."
                ),
            }
        ]

        # Single call — cap web searches at 5 to control token costs.
        # No agentic loop: the model gets one turn to research and return JSON.
        for attempt in range(4):
            try:
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
                    messages=messages,
                )
                break
            except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
                if attempt == 3:
                    raise
                status = getattr(e, "status_code", None)
                if status not in (429, 529):
                    raise
                wait = 65
                print(f"   API rate-limited/overloaded (HTTP {status}) — waiting {wait}s before retry ({attempt + 1}/3)...")
                time.sleep(wait)

        return self._parse_topics(response)

    def _parse_topics(self, response) -> list[dict]:
        """Extract and validate the JSON topics from the response."""
        for block in response.content:
            if block.type != "text":
                continue

            text = block.text.strip()

            # Try direct parse first
            try:
                data = json.loads(text)
                return self._validate_topics(data["topics"])
            except (json.JSONDecodeError, KeyError):
                pass

            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
            try:
                data = json.loads(text.strip())
                return self._validate_topics(data["topics"])
            except (json.JSONDecodeError, KeyError):
                pass

            # Last resort: find JSON object in the text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    return self._validate_topics(data["topics"])
                except (json.JSONDecodeError, KeyError):
                    pass

        raise ValueError(
            "Research agent could not produce valid JSON topics. "
            "Check that web_search is returning results."
        )

    def _validate_topics(self, topics: list) -> list[dict]:
        """Ensure each topic has the required fields, filling defaults if needed."""
        required = {"title", "summary", "key_points", "business_impact", "sources"}
        validated = []
        for topic in topics[:3]:
            for field in required:
                if field not in topic:
                    if field in {"key_points", "sources"}:
                        topic[field] = []
                    else:
                        topic[field] = ""
            validated.append(topic)
        if not validated:
            raise ValueError("No topics returned by research agent.")
        return validated
