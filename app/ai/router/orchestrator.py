"""
AI Orchestrator - The Brain's Traffic Controller.

This module implements the intelligent routing system that decides which
AI model should handle each request. It uses Gemini Flash as the fast,
cheap orchestrator that analyzes requests and routes them appropriately.

Routing Logic:
=============

┌──────────────────────────────────────────────────────────────────┐
│                     Incoming Request                              │
│            "Show the calendar on living room TV"                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Gemini Flash Analyzer                          │
│    Analyzes:                                                      │
│    - Is this a device command? YES                                │
│    - Is it simple/direct? YES                                     │
│    - Needs code execution? NO                                     │
│    - Needs deep reasoning? NO                                     │
│                                                                   │
│    Decision: SIMPLE → Handle directly                             │
└───────────────────────────────────────────────────────────────────┘

Task Classification:
===================

SIMPLE (Gemini Flash handles):
- Direct device commands: "Turn on the TV", "Switch to HDMI 2"
- Basic Q&A: "What devices do I have?"
- Status queries: "Is the bedroom TV on?"
- Casual conversation: "Hello", "Thanks"

COMPLEX_EXECUTION (Route to OpenAI GPT):
- Code generation: "Write a script to..."
- API integrations: "Search Google for..."
- Multi-step tools: "Calculate and then..."

COMPLEX_REASONING (Route to Claude):
- Planning: "Plan a movie night setup..."
- Analysis: "Why might my TV keep turning off?"
- Critical decisions: "What's the best automation strategy?"
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

from app.ai.providers import (
    gemini_provider,
    openai_provider,
    AIResponse,
)
from app.ai.prompts.router_prompts import (
    ROUTING_SYSTEM_PROMPT,
    ROUTING_ANALYSIS_PROMPT,
)

logger = logging.getLogger("jarvis.ai.router")


class TaskComplexity(str, Enum):
    """
    Classification of task complexity for routing decisions.
    
    This determines which AI model will handle the request.
    """
    SIMPLE = "simple"  # Gemini handles directly
    COMPLEX_EXECUTION = "complex_execution"  # Route to GPT
    COMPLEX_REASONING = "complex_reasoning"  # Route to Claude
    UNKNOWN = "unknown"  # Default to Gemini


@dataclass
class RoutingDecision:
    """
    The routing decision made by the orchestrator.
    
    Attributes:
        complexity: How complex is the task
        target_provider: Which AI provider should handle it
        reasoning: Why this decision was made
        confidence: How confident the router is (0-1)
        is_device_command: Is this a command for a device
        should_respond_directly: Can we respond without further routing
    """
    complexity: TaskComplexity
    target_provider: str  # "gemini", "openai", "anthropic"
    reasoning: str
    confidence: float
    is_device_command: bool
    should_respond_directly: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "complexity": self.complexity.value,
            "target_provider": self.target_provider,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "is_device_command": self.is_device_command,
            "should_respond_directly": self.should_respond_directly,
        }


class AIRouter:
    """
    The AI Orchestrator - Routes requests to the appropriate AI model.
    
    This is the core of the intelligent routing system. It uses Gemini Flash
    as a fast, cheap analyzer to determine:
    1. What type of request is this?
    2. How complex is it?
    3. Which model should handle it?
    
    Usage:
        router = AIRouter()
        
        # Analyze a request
        decision = await router.analyze_request("Turn on the living room TV")
        print(decision.complexity)  # SIMPLE
        print(decision.is_device_command)  # True
        
        # Process a full request (analyze + route + execute)
        response = await router.process("Turn on the living room TV")
    
    The router optimizes for:
    - Cost: Use cheap Gemini for most requests
    - Speed: Fast routing decisions
    - Quality: Route complex tasks to specialized models
    """
    
    def __init__(self):
        """Initialize the router with all providers."""
        self.orchestrator = gemini_provider  # Fast analyzer
        self.executor = openai_provider  # Code/tools
        self.reasoner = gemini_provider  # Gemini 3 Flash for reasoning (with thinking mode)
        logger.info("AI Router initialized")
    
    async def analyze_request(self, request: str, context: Optional[Dict] = None) -> RoutingDecision:
        """
        Analyze a request and decide how to route it.
        
        This is the first step in processing - we use Gemini Flash to
        quickly analyze the request and determine its complexity.
        
        Args:
            request: The user's natural language request
            context: Optional context (user info, device list, etc.)
            
        Returns:
            RoutingDecision with complexity and target provider
        """
        logger.info(f"Analyzing request: {request[:50]}...")
        
        # Build the analysis prompt
        context_str = ""
        if context:
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2)}"
        
        prompt = ROUTING_ANALYSIS_PROMPT.format(
            request=request,
            context=context_str
        )
        
        # Use Gemini Flash for fast analysis
        response = await self.orchestrator.generate_json(
            prompt=prompt,
            system_prompt=ROUTING_SYSTEM_PROMPT,
        )
        
        if not response.success:
            logger.warning(f"Routing analysis failed: {response.error}")
            # Default to simple/Gemini on failure
            return RoutingDecision(
                complexity=TaskComplexity.SIMPLE,
                target_provider="gemini",
                reasoning="Analysis failed, defaulting to Gemini",
                confidence=0.5,
                is_device_command=False,
            )
        
        # Parse the routing decision
        try:
            decision_data = json.loads(response.content)
            
            # Map complexity string to enum
            complexity_map = {
                "simple": TaskComplexity.SIMPLE,
                "complex_execution": TaskComplexity.COMPLEX_EXECUTION,
                "complex_reasoning": TaskComplexity.COMPLEX_REASONING,
            }
            complexity = complexity_map.get(
                decision_data.get("complexity", "simple").lower(),
                TaskComplexity.SIMPLE
            )
            
            # Map provider string
            provider_map = {
                "simple": "gemini",
                "complex_execution": "openai",
                "complex_reasoning": "anthropic",
            }
            target_provider = provider_map.get(complexity.value, "gemini")
            
            decision = RoutingDecision(
                complexity=complexity,
                target_provider=target_provider,
                reasoning=decision_data.get("reasoning", ""),
                confidence=float(decision_data.get("confidence", 0.8)),
                is_device_command=decision_data.get("is_device_command", False),
                should_respond_directly=decision_data.get("should_respond_directly", False),
            )
            
            logger.info(f"Routing decision: {decision.to_dict()}")
            return decision
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse routing decision: {e}")
            return RoutingDecision(
                complexity=TaskComplexity.SIMPLE,
                target_provider="gemini",
                reasoning="Parse error, defaulting to Gemini",
                confidence=0.5,
                is_device_command=False,
            )
    
    async def process(
        self,
        request: str,
        context: Optional[Dict] = None,
        force_provider: Optional[str] = None,
    ) -> AIResponse:
        """
        Process a request end-to-end: analyze, route, and execute.
        
        This is the main entry point for processing user requests.
        It analyzes the request, determines the appropriate model,
        and returns the response.
        
        Args:
            request: The user's natural language request
            context: Optional context (devices, user info, etc.)
            force_provider: Override routing and use specific provider
            
        Returns:
            AIResponse from the selected provider
        """
        # If provider is forced, skip analysis
        if force_provider:
            provider = self._get_provider(force_provider)
            return await provider.generate(request)
        
        # Analyze the request
        decision = await self.analyze_request(request, context)
        
        # If the orchestrator can handle it directly
        if decision.complexity == TaskComplexity.SIMPLE:
            logger.info("Handling request with Gemini (orchestrator)")
            return await self.orchestrator.generate(
                prompt=request,
                system_prompt=self._get_system_prompt_for_task(decision, context),
            )
        
        # Route to appropriate provider
        provider = self._get_provider(decision.target_provider)
        logger.info(f"Routing request to {decision.target_provider}")
        
        return await provider.generate(
            prompt=request,
            system_prompt=self._get_system_prompt_for_task(decision, context),
        )
    
    def _get_provider(self, provider_name: str):
        """Get the provider instance by name."""
        providers = {
            "gemini": self.orchestrator,
            "openai": self.executor,
            "anthropic": self.reasoner,  # Now also Gemini
        }
        return providers.get(provider_name, self.orchestrator)
    
    def _get_system_prompt_for_task(
        self,
        decision: RoutingDecision,
        context: Optional[Dict] = None
    ) -> str:
        """
        Generate an appropriate system prompt based on the task.
        
        Different tasks need different system prompts to guide the model.
        """
        base_prompt = """You are Jarvis, an intelligent assistant for controlling display devices (TVs, monitors).
You help users manage their screens through natural language commands.

Your capabilities:
- Turn devices on/off
- Switch inputs (HDMI, AV, etc.)
- Control volume
- Answer questions about the system
"""
        
        if context and "devices" in context:
            base_prompt += f"\n\nAvailable devices:\n{json.dumps(context['devices'], indent=2)}"
        
        if decision.is_device_command:
            base_prompt += """

For device commands, extract:
1. The target device (by name)
2. The action to perform
3. Any parameters (input name, volume level, etc.)

Be concise and helpful."""
        
        return base_prompt


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------
ai_router = AIRouter()
