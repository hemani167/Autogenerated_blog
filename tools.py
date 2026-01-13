# from duckduckgo_search import DDGS
from ddgs.ddgs import DDGS

def search_tool(query: str):
    """Search the web for a given query using DuckDuckGo."""
    try:
        results = DDGS().text(query, max_results=5)
        if not results:
            return "No results found."
        return "\n\n".join([f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}" for r in results])
    except Exception as e:
        return f"Search error: {e}"
