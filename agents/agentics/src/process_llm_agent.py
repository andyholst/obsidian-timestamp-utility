import json
import logging
import os
import hashlib
import asyncio
from functools import lru_cache

from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from .base_agent import BaseAgent
from .state import State
from .utils import safe_json_dumps, remove_thinking_tags, log_info, parse_json_response
from .mcp_client import get_mcp_client
from .performance import get_response_cache, get_memory_manager
from .llm_validator import validate_llm_response, MultiModelFallback
from .circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException

class ProcessLLMAgent(BaseAgent):
    def __init__(self, llm_client, prompt_template, fallback_llms=None):
        super().__init__("ProcessLLM")
        self.llm = llm_client
        self.prompt_template = prompt_template
        self.max_retries = int(os.getenv('LLM_MAX_RETRIES', 3))
        self.monitor.logger.setLevel(logging.INFO)
        log_info(self.name, f"Initialized with max retries: {self.max_retries}")

        # Initialize MultiModelFallback for LLM failure recovery
        self.multi_model_fallback = MultiModelFallback(llm_client, fallback_llms or [])

        # Create LCEL chain for processing
        self.processing_chain = self._create_processing_chain()

        # Use global performance utilities
        self.response_cache = get_response_cache()
        self.memory_manager = get_memory_manager()

    def _get_cache_key(self, ticket_content: str) -> str:
        """Generate a cache key for the ticket content."""
        return hashlib.md5(ticket_content.encode()).hexdigest()

    def _create_processing_chain(self):
        """Create LCEL chain for LLM processing with validation and fallback support."""
        def invoke_with_fallback(prompt):
            """Invoke LLM with fallback support"""
            try:
                return self.multi_model_fallback.invoke_with_fallback(prompt)
            except Exception as e:
                self.monitor.error(f"All LLM models failed: {str(e)}")
                raise

        return (
            RunnablePassthrough.assign(
                ticket_content=self._prepare_ticket_content
            )
            | self.prompt_template
            | RunnableLambda(invoke_with_fallback)
            | RunnableLambda(self._process_response)
        )

    def _prepare_ticket_content(self, inputs):
        """Prepare ticket content for the prompt with MCP context enhancement."""
        state = inputs
        ticket_content = state.get('refined_ticket', state.get('ticket_content', ''))
        log_info(self.name, f"Ticket content source: {'refined_ticket' if 'refined_ticket' in state else 'ticket_content'}")

        # If ticket_content is a dict, convert to string for the prompt
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)

        # Try to enhance with MCP context
        try:
            mcp_client = get_mcp_client()
            context_query = f"Context for software development task: {ticket_content[:200]}..."
            log_info(self.name, f"Retrieving MCP context for: {context_query[:100]}...")

            # Run async MCP call in sync context
            context = asyncio.run(mcp_client.get_context(context_query, max_tokens=8192))
            if context and context.strip():
                enhanced_content = f"CONTEXT FROM MCP:\n{context}\n\nORIGINAL TICKET:\n{ticket_content}"
                log_info(self.name, f"Enhanced ticket content with MCP context (length: {len(enhanced_content)})")
                ticket_content = enhanced_content
            else:
                log_info(self.name, "No MCP context available, using original ticket content")
        except Exception as e:
            log_info(self.name, f"MCP context retrieval failed: {str(e)}, using original ticket content")

        log_info(self.name, f"Final ticket content length: {len(ticket_content)}")
        log_info(self.name, f"Final ticket content: {ticket_content[:500]}...")
        return ticket_content

    def _process_response(self, response):
        """Process and validate LLM response with robust parsing and advanced validation."""
        clean_response = remove_thinking_tags(response)
        log_info(self.name, f"Cleaned LLM response length: {len(clean_response)}")
        log_info(self.name, f"Cleaned LLM response: {clean_response[:500]}...")

        # Define validation requirements for structured ticket data
        required_keys = {'title', 'description', 'requirements', 'acceptance_criteria', 'implementation_steps', 'npm_packages', 'manual_implementation_notes'}
        fallback_defaults = {
            'title': 'Untitled Task',
            'description': 'No description provided',
            'requirements': [],
            'acceptance_criteria': [],
            'implementation_steps': [],
            'npm_packages': [],
            'manual_implementation_notes': ''
        }

        # Use robust parsing with validation
        result = parse_json_response(clean_response, required_keys, fallback_defaults)

        # Additional type validation with coercion
        if not isinstance(result['requirements'], list):
            result['requirements'] = []
        if not isinstance(result['acceptance_criteria'], list):
            result['acceptance_criteria'] = []
        if not isinstance(result['implementation_steps'], list):
            result['implementation_steps'] = []
        if not isinstance(result['npm_packages'], list):
            result['npm_packages'] = []
        if not isinstance(result['manual_implementation_notes'], str):
            result['manual_implementation_notes'] = str(result['manual_implementation_notes'])

        # Advanced LLM response validation
        validation_context = {
            "expected_keywords": ["title", "description", "requirements", "acceptance_criteria"],
            "domain": "json"
        }
        validation_result = validate_llm_response(json.dumps(result), "json", validation_context)

        if not validation_result["is_valid"]:
            log_info(self.name, f"LLM response validation failed: {validation_result['issues']}")
            if validation_result["quality_score"] < 0.5:
                log_info(self.name, "Low quality response, using fallback defaults")
                # Use fallback defaults for critical missing fields
                for key, default in fallback_defaults.items():
                    if key not in result or not result[key]:
                        result[key] = default

        log_info(self.name, f"Valid result parsed and validated: {json.dumps(result, indent=2)}")
        return result

    def process(self, state: State) -> State:
        """
        Process ticket content with LLM to extract structured task details and update the state.
        """
        log_info(self.name, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.name, "Starting LLM processing with LCEL chain")

        # Check cache first
        ticket_content = state.get('refined_ticket', state.get('ticket_content', ''))
        if isinstance(ticket_content, dict):
            ticket_content = json.dumps(ticket_content)
        cache_key = self._get_cache_key(ticket_content)

        cached_result = self.response_cache.get(cache_key)
        if cached_result:
            log_info(self.name, "Using cached LLM response")
            # Track memory usage for cached result
            self.memory_manager.track_object(f"cached_result_{cache_key}", cached_result)
            state['result'] = cached_result
            log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
            return state

        for attempt in range(self.max_retries):
            log_info(self.name, f"Attempt {attempt + 1} of {self.max_retries} to invoke LLM chain")
            try:
                try:
                    result = get_circuit_breaker("llm_processing").call(lambda: self.processing_chain.invoke(state))
                except CircuitBreakerOpenException as e:
                    self.monitor.error(f"Circuit breaker open for LLM processing: {str(e)}")
                    raise
                except Exception as e:
                    self.monitor.error(f"LLM processing failed: {str(e)}")
                    raise
                # Cache the successful result with TTL
                self.response_cache.set(cache_key, result, ttl=3600)  # 1 hour TTL
                # Track memory usage
                self.memory_manager.track_object(f"llm_result_{cache_key}", result)
                state['result'] = result
                log_info(self.name, "LLM processing completed successfully")
                log_info(self.name, f"After processing in {self.name}: {safe_json_dumps(state, indent=2)}")
                return state
            except (ValueError, json.JSONDecodeError) as e:
                self.monitor.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    self.monitor.error(f"Invalid LLM response after {self.max_retries} attempts: {str(e)}")
                    raise ValueError(f"Invalid LLM response after {self.max_retries} attempts: {str(e)}")
        return state