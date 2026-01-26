from abc import ABC, abstractmethod
from typing import Dict, Any, Union, List, Optional
from pathlib import Path
from .document import Document

class ProcessingResult:
    """Standardized result from an agent processing a document."""
    def __init__(self, document_id: str, status: str, extracted_content: Any = None, errors: List[str] = None):
        self.document_id = document_id
        self.status = status
        self.extracted_content = extracted_content
        self.errors = errors or []

class BaseVisionLanguageModel(ABC):
    """Abstract base class for all Vision Language Models (Local or Cloud)."""
    
    @abstractmethod
    def load(self) -> None:
        """Load model into memory or initialize API client."""
        pass
    
    @abstractmethod
    def unload(self) -> None:
        """Free resources."""
        pass
    
    @abstractmethod
    def process(self, image: Union[str, Path, bytes], prompt: str, **kwargs) -> Dict[str, Any]:
        """Process image/content with prompt."""
        pass

class BaseAgent(ABC):
    """Abstract base class for Document Processing Agents."""
    
    def __init__(self, name: str, model: Optional[BaseVisionLanguageModel] = None):
        self.name = name
        self.model = model

    @abstractmethod
    def can_handle(self, document: Document) -> bool:
        """Decide if this agent can process the document."""
        pass
    
    @abstractmethod
    async def process(self, document: Document, **kwargs) -> ProcessingResult:
        """Process the document and extract information."""
        pass
    
    @abstractmethod
    def validate(self, result: ProcessingResult) -> bool:
        """Validate the processing result."""
        pass

class BasePipelineStage(ABC):
    """Abstract base class for Pipeline Stages."""
    
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute stage and return updated context."""
        pass
    
    @abstractmethod
    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Ensure context has required inputs."""
        pass

class BaseRouter(ABC):
    """Abstract base class for Document Routing."""
    @abstractmethod
    async def route(self, document: Document) -> BaseAgent:
        """Select best agent for document."""
        pass
    
    @abstractmethod
    def register_agent(self, agent: BaseAgent, priority: int = 0) -> None:
        """Register agent with priority."""
        pass
