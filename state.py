from typing import List, Optional, TypedDict, Annotated
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
import operator

class Section(BaseModel):
    title: str = Field(description="The title of the section")
    content: str = Field(description="The content of the section")

class AgentState(TypedDict):
    research_guidelines: str
    researcher_messages: Annotated[List[BaseMessage], operator.add]
    raw_notes: str
    notes: str
    section_outline: str
    sections: List[Section] # The planned sections
    completed_sections: Annotated[List[Section], operator.add] # The written sections
    final_report: str
    topic: str # Input topic
    user_approval: str # User approval status
    user_feedback: str # Feedback for retry

class ResearcherState(TypedDict):
    research_guidelines: str
    researcher_messages: Annotated[List[BaseMessage], operator.add]
    raw_notes: str
    notes: str
    research_iterations: int
    query: str # current query
