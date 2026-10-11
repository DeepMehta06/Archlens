"""Structured diagram specifications produced by the model and compiled to Mermaid by code."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DiagramNode(BaseModel):
    id: str
    label: str
    type: Optional[str] = None


class DiagramEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: Optional[str] = None


class ArchitectureDiagramSpec(BaseModel):
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class ComponentDiagramSpec(BaseModel):
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class SequenceParticipant(BaseModel):
    id: str
    label: str


class SequenceMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    action: str


class SequenceDiagramSpec(BaseModel):
    participants: list[SequenceParticipant] = Field(default_factory=list)
    messages: list[SequenceMessage] = Field(default_factory=list)


class EREntity(BaseModel):
    id: str
    name: str
    attributes: list[str] = Field(default_factory=list)


class ERRelationship(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    cardinality: str
    label: str


class ERDiagramSpec(BaseModel):
    entities: list[EREntity] = Field(default_factory=list)
    relationships: list[ERRelationship] = Field(default_factory=list)


class RequirementTraceLink(BaseModel):
    requirement: str
    component: str


class RequirementTraceabilitySpec(BaseModel):
    requirements: list[DiagramNode] = Field(default_factory=list)
    components: list[DiagramNode] = Field(default_factory=list)
    links: list[RequirementTraceLink] = Field(default_factory=list)
