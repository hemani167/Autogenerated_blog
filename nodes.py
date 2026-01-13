from typing import List, Literal, Annotated
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END
from state import AgentState, ResearcherState, Section
from tools import search_tool
from pydantic import BaseModel, Field
import json
import os
import time

# Initialize LLM
# Ensure GOOGLE_API_KEY is set in environment or passed here.
# Using gemini-2.0-flash-exp to avoid daily limits of 2.5-flash.
# Rate limit is typically 10 RPM.
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0)

def begin_node(state: AgentState):
    """
    Get clarification from the user and generate research guidelines.
    """
    topic = state.get("topic", "")
    print(f"--- Begin Node (Guideline Generation) ---")
    print(f"Topic: {topic}")
    
    feedback = state.get("user_feedback")
    if feedback:
        print(f"\n[Using User Feedback for Refinement]: {feedback}")
        clarification = feedback
        # We also reset completed sections so they are rewritten
        state["completed_sections"] = []
    else:
        clarification = input(f"Please provide any specific clarification or focus for the blog post on '{topic}': ")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant assisting with blog post planning."),
        ("human", "Topic: {topic}\nClarification: {clarification}\n\nPlease generate concise research guidelines for a blog post on this topic.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"topic": topic, "clarification": clarification})
    
    return {"research_guidelines": response.content}

def human_approval(state: AgentState):
    """
    Asks the user for approval or request to edit/retry.
    """
    print("\n--- Human Approval Node ---")
    print("The blog post has been compiled. Here is the content:\n")
    print("="*40)
    print(state.get("final_report", "No content generated."))
    print("="*40 + "\n")
    
    print("To APPROVE: type 'approve', 'yes', or 'ok'.")
    print("To EDIT/RETRY: type your feedback/instructions (e.g., 'rewrite to focus on war').")
    response = input("> ").strip()
    
    if response.lower() in ["approve", "yes", "y", "ok"]:
        return {"user_approval": "approve"}
    else:
        return {"user_approval": "retry", "user_feedback": response}

def research_orchestrator(state: ResearcherState):
    """
    Decides whether to search more or stop.
    """
    time.sleep(15) # Rate limit check (5 RPM limit)
    print(f"--- Research Orchestrator (Iteration {state.get('research_iterations', 0)}) ---")
    guidelines = state.get("research_guidelines")
    notes = state.get("notes", "")
    iterations = state.get("research_iterations", 0)
    
    if iterations >= 5:
        return {"query": "DONE"}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research assistant. Your goal is to gather information based on the following guidelines: {guidelines}. "
                   "Current notes: {notes}. "
                   "Decide if more research is needed. If yes, output a search query. If enough info is gathered, output 'DONE'."),
        ("human", "What should be the next search query? Return ONLY the query or 'DONE'.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"guidelines": guidelines, "notes": notes})
    query = response.content.strip()
    
    return {"query": query, "research_iterations": iterations} # We don't increment here, we increment after search

def perform_search(state: ResearcherState):
    """
    Executes the search and updates notes.
    """
    time.sleep(15) # Rate limit check (5 RPM limit)
    query = state.get("query")
    print(f"--- Performing Search: {query} ---")
    
    if query == "DONE":
        return {"research_iterations": state.get("research_iterations", 0)} # No change
        
    search_result = search_tool(query)
    
    # Update notes using LLM to synthesize
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a research assistant. Update the research notes with the new search results."),
        ("human", "Current Notes: {notes}\n\nNew Search Results for '{query}':\n{results}\n\nPlease synthesize and append relevant information to the notes.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "notes": state.get("notes", ""),
        "query": query,
        "results": search_result
    })
    
    new_notes = response.content
    
    return {
        "notes": new_notes, 
        "research_iterations": state.get("research_iterations", 0) + 1,
        "raw_notes": state.get("raw_notes", "") + f"\n\nQuery: {query}\nResult: {search_result}"
    }

def generate_outline(state: AgentState):
    """
    Generates an outline and section list based on research notes.
    """
    print("--- Generating Outline ---")
    notes = state.get("notes")
    guidelines = state.get("research_guidelines")
    topic = state.get("topic")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a blog editor. Create a blog outline and a list of sections based on the topic and research notes."),
        ("human", "Topic: {topic}\nGuidelines: {guidelines}\nResearch Notes: {notes}\n\n"
                  "Provide the output in JSON format with two keys: 'outline' (string) and 'sections' (list of strings, being the section titles).")
    ])
    
    # Force JSON output if possible, or parse it. 
    # Define a simple schema for structured output to ensure we get what we want
    class OutlineSchema(BaseModel):
        outline: str = Field(description="The blog outline")
        sections: List[str] = Field(description="List of section titles")

    structured_llm = llm.with_structured_output(OutlineSchema)
    
    try:
        response = structured_llm.invoke(prompt.format(topic=topic, guidelines=guidelines, notes=notes))
        # response should be a dict or object matching schema
        
        # If response is a dict
        if isinstance(response, dict):
            outline = response.get("outline", "")
            section_titles = response.get("sections", [])
        else:
            # If pydantic object
            outline = response.outline
            section_titles = response.sections

    except Exception as e:
        # Fallback if structured output fails (e.g. model doesn't support)
        print(f"Structured output failed: {e}. Using raw text.")
        chain = prompt | llm
        raw_response = chain.invoke({"topic": topic, "guidelines": guidelines, "notes": notes})
        # Basic parsing attempt (this is risky, but for demo ok)
        import json
        try:
             data = json.loads(raw_response.content)
             outline = data.get("outline", "")
             section_titles = data.get("sections", [])
        except:
             outline = raw_response.content
             section_titles = ["Introduction", "Main Body", "Conclusion"] # Fallback

    # Initialize empty sections list for the writers
    sections = [Section(title=t, content="") for t in section_titles]
    
    return {"section_outline": outline, "sections": sections}

def write_section(state: AgentState, section_index: int):
    """
    Writes a single section.
    This node needs to receive the specific section to write. 
    However, standard LangGraph nodes take State. 
    To do parallel map-reduce, we usually use Send() to a subgraph or a node that takes a specific input.
    
    For simplicity in this implementation, I'll adapt to how LangGraph `Send` works.
    We'll define a separate state or input for the writer.
    """
    pass 
    # I will implement this logic in the graph definition using `Send`.
    # The node function itself will take a custom input.

def section_writer_node(input_data: dict):
    """
    Writes a section based on the input data.
    Input data will contain: section_title, notes, guidelines.
    """
    time.sleep(15) # Rate limit check (5 RPM limit)
    title = input_data["section_title"]
    notes = input_data["notes"]
    guidelines = input_data["guidelines"]
    
    print(f"--- Writing Section: {title} ---")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a blog writer. Write a blog section based on the title and research notes."),
        ("human", "Title: {title}\nGuidelines: {guidelines}\nNotes: {notes}\n\nWrite the content for this section.")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"title": title, "guidelines": guidelines, "notes": notes})
    
    return {"completed_sections": [Section(title=title, content=response.content)]}

def compile_sections(state: AgentState):
    """
    Compiles all sections into the final report.
    """
    print("--- Compiling Sections ---")
    planned_sections = state.get("sections", [])
    completed_sections = state.get("completed_sections", [])
    
    # Sort completed sections based on the order in planned_sections
    completed_map = {s.title: s.content for s in completed_sections}
    
    full_content = f"# {state.get('topic')}\n\n"
    for section in planned_sections:
        content = completed_map.get(section.title, "Content missing.")
        full_content += f"## {section.title}\n\n{content}\n\n"
        
    return {"final_report": full_content}
    # Or, we gather the results in the graph edge.
    return {"final_report": full_content}
