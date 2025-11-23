import logging
import json
import asyncio
from typing import Dict, Any

from .base_agent import BaseAgent
from .state import State
from .utils import safe_json_dumps, log_info
from .mcp_client import get_mcp_client

class FeedbackAgent(BaseAgent):
    def __init__(self):
        super().__init__("FeedbackAgent")
        self.logger.setLevel(logging.INFO)
        self.feedback_history = []
        log_info(self.name, "Initialized FeedbackAgent for collecting generation metrics")

    def process(self, state: State) -> State:
        log_info(self.logger, f"Before processing in {self.name}: {safe_json_dumps(state, indent=2)}")
        log_info(self.logger, "Collecting feedback metrics from generation process")

        # Collect metrics
        metrics = self._collect_metrics(state)

        # Store in feedback history
        self.feedback_history.append(metrics)

        # Add to state for potential use by other agents
        state['feedback_metrics'] = metrics

        # Store in memory for continuous improvement
        if 'memory' not in state:
            state['memory'] = {}
        if 'feedback_history' not in state['memory']:
            state['memory']['feedback_history'] = []
        state['memory']['feedback_history'].append(metrics)

        # Store metrics in MCP memory for persistence
        try:
            mcp_client = get_mcp_client()
            metrics_key = f"feedback_{metrics.get('ticket_title', 'unknown')}_{metrics.get('timestamp', 'now')}"
            metrics_json = json.dumps(metrics)
            success = asyncio.run(mcp_client.store_memory(metrics_key, metrics_json))
            if success:
                log_info(self.logger, f"Stored feedback metrics in MCP memory: {metrics_key}")
            else:
                log_info(self.logger, "Failed to store feedback metrics in MCP memory")
        except Exception as e:
            log_info(self.logger, f"MCP memory storage failed: {str(e)}")

        # Initialize conversation history if not present
        if 'conversation_history' not in state:
            state['conversation_history'] = []

        log_info(self.logger, f"Collected metrics: {json.dumps(metrics, indent=2)}")
        log_info(self.logger, f"After processing in {self.name}: feedback collected")
        return state

    def _collect_metrics(self, state: State) -> Dict[str, Any]:
        """Collect various metrics from the generation process."""
        metrics = {
            'timestamp': state.get('timestamp', None),
            'ticket_title': state.get('result', {}).get('title', ''),
            'has_generated_code': bool(state.get('generated_code', '').strip()),
            'has_generated_tests': bool(state.get('generated_tests', '').strip()),
            'code_length': len(state.get('generated_code', '')),
            'test_length': len(state.get('generated_tests', '')),
            'existing_tests_passed': state.get('existing_tests_passed', 0),
            'existing_coverage': state.get('existing_coverage_all_files', 0.0),
            'post_tests_passed': state.get('post_integration_tests_passed', 0),
            'post_coverage': state.get('post_integration_coverage_all_files', 0.0),
            'coverage_improvement': state.get('coverage_improvement', 0.0),
            'tests_improvement': state.get('tests_improvement', 0),
            'relevant_code_files_count': len(state.get('relevant_code_files', [])),
            'relevant_test_files_count': len(state.get('relevant_test_files', [])),
            'available_dependencies_count': len(state.get('available_dependencies', [])),
        }

        # Calculate derived metrics
        if metrics['existing_tests_passed'] > 0:
            metrics['test_success_rate'] = metrics['post_tests_passed'] / metrics['existing_tests_passed']
        else:
            metrics['test_success_rate'] = 0.0

        metrics['code_to_test_ratio'] = metrics['test_length'] / max(metrics['code_length'], 1)

        return metrics

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary statistics from all feedback."""
        if not self.feedback_history:
            return {}

        total_generations = len(self.feedback_history)
        successful_generations = sum(1 for m in self.feedback_history if m['has_generated_code'])

        avg_coverage_improvement = sum(m['coverage_improvement'] for m in self.feedback_history) / total_generations
        avg_test_improvement = sum(m['tests_improvement'] for m in self.feedback_history) / total_generations
        avg_code_length = sum(m['code_length'] for m in self.feedback_history) / total_generations
        avg_test_length = sum(m['test_length'] for m in self.feedback_history) / total_generations

        return {
            'total_generations': total_generations,
            'success_rate': successful_generations / total_generations,
            'avg_coverage_improvement': avg_coverage_improvement,
            'avg_test_improvement': avg_test_improvement,
            'avg_code_length': avg_code_length,
            'avg_test_length': avg_test_length,
        }

    def retrieve_historical_feedback(self, ticket_title: str) -> Dict[str, Any]:
        """Retrieve historical feedback for a similar ticket from MCP memory."""
        try:
            mcp_client = get_mcp_client()
            # Try to find similar feedback in memory
            memory_key = f"feedback_{ticket_title}"
            stored_metrics = asyncio.run(mcp_client.retrieve_memory(memory_key))
            if stored_metrics:
                return json.loads(stored_metrics)
        except Exception as e:
            log_info(self.logger, f"Failed to retrieve historical feedback: {str(e)}")
        return {}
