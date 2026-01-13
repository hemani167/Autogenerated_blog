from langgraph.graph import StateGraph, END, START
from langgraph.constants import Send
from state import AgentState, ResearcherState
from nodes import (
    begin_node,
    human_approval,
    research_orchestrator,
    perform_search,
    generate_outline,
    section_writer_node,
    compile_sections
)

# Researcher Subgraph
researcher_workflow = StateGraph(ResearcherState)
researcher_workflow.add_node("research_orchestrator", research_orchestrator)
researcher_workflow.add_node("perform_search", perform_search)

researcher_workflow.add_edge(START, "research_orchestrator")

def should_continue_research(state):
    if state.get("query") == "DONE":
        return END
    return "perform_search"

researcher_workflow.add_conditional_edges("research_orchestrator", should_continue_research)
researcher_workflow.add_edge("perform_search", "research_orchestrator")

researcher_graph = researcher_workflow.compile()

# Main Graph
workflow = StateGraph(AgentState)
workflow.add_node("begin_node", begin_node)
workflow.add_node("researcher", researcher_graph)
workflow.add_node("generate_outline", generate_outline)
workflow.add_node("section_writer", section_writer_node) # Node for parallel execution
workflow.add_node("compile_sections", compile_sections)
workflow.add_node("human_approval", human_approval)

workflow.add_edge(START, "begin_node")
workflow.add_edge("begin_node", "researcher")
workflow.add_edge("researcher", "generate_outline")

def map_sections(state: AgentState):
    """
    Map the sections to the writers.
    """
    sections = state.get("sections", [])
    notes = state.get("notes")
    guidelines = state.get("research_guidelines")
    
    return [
        Send("section_writer", {
            "section_title": s.title,
            "notes": notes,
            "guidelines": guidelines
        }) for s in sections
    ]

workflow.add_conditional_edges("generate_outline", map_sections, ["section_writer"])
workflow.add_edge("section_writer", "compile_sections")
workflow.add_edge("compile_sections", "human_approval")

def check_approval(state: AgentState):
    if state.get("user_approval") == "retry":
        return "begin_node"
    return END

workflow.add_conditional_edges("human_approval", check_approval, ["begin_node", END])

app = workflow.compile()
