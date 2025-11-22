"""
Advanced LLM Response Validation and Quality Assurance
"""

import re
import ast
import json
import logging
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import asyncio

from .utils import log_info
from .monitoring import structured_log
from .circuit_breaker import get_circuit_breaker, retry_with_backoff

monitor = structured_log(__name__)


class LLMResponseValidator:
    """Advanced validation for LLM responses with semantic checking and quality scoring"""

    def __init__(self):
        self.monitor = structured_log(__name__)
        self.quality_threshold = float(os.getenv('LLM_QUALITY_THRESHOLD', '0.6'))
        self.enable_semantic_validation = os.getenv('ENABLE_SEMANTIC_VALIDATION', 'true').lower() == 'true'

    def validate_response(self, response: str, response_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Comprehensive validation of LLM response"""
        context = context or {}

        validation_result = {
            "is_valid": True,
            "quality_score": 1.0,
            "issues": [],
            "warnings": [],
            "sanitized_response": response,
            "validation_metadata": {}
        }

        try:
            # Step 1: Basic structural validation
            self._validate_structure(response, response_type, validation_result)

            # Step 2: Content quality scoring
            quality_score = self._calculate_quality_score(response, response_type, context)
            validation_result["quality_score"] = quality_score

            # Step 3: Semantic validation (if enabled)
            if self.enable_semantic_validation:
                self._validate_semantics(response, response_type, validation_result)

            # Step 4: Security sanitization
            validation_result["sanitized_response"] = self._sanitize_response(response, response_type)

            # Step 5: Determine overall validity
            validation_result["is_valid"] = (
                len(validation_result["issues"]) == 0 and
                quality_score >= self.quality_threshold
            )

            if quality_score < self.quality_threshold:
                validation_result["warnings"].append(
                    f"Quality score {quality_score:.2f} below threshold {self.quality_threshold}"
                )

        except Exception as e:
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"Validation error: {str(e)}")
            self.monitor.error(f"LLM validation failed: {str(e)}")

        return validation_result

    def _validate_structure(self, response: str, response_type: str, result: Dict[str, Any]):
        """Validate basic response structure"""
        if not response or not response.strip():
            result["issues"].append("Empty response")
            return

        if len(response.strip()) < 10:
            result["warnings"].append("Response is very short")

        # Type-specific structural validation
        if response_type == "json":
            self._validate_json_structure(response, result)
        elif response_type == "code":
            self._validate_code_structure(response, result)
        elif response_type == "text":
            self._validate_text_structure(response, result)

    def _validate_json_structure(self, response: str, result: Dict[str, Any]):
        """Validate JSON response structure"""
        try:
            parsed = json.loads(response)
            if not isinstance(parsed, dict):
                result["issues"].append("JSON response must be an object")
            elif len(parsed) == 0:
                result["warnings"].append("Empty JSON object")
        except json.JSONDecodeError as e:
            result["issues"].append(f"Invalid JSON: {str(e)}")

    def _validate_code_structure(self, response: str, result: Dict[str, Any]):
        """Validate code response structure"""
        # Check for basic code patterns
        code_indicators = [
            r'\bfunction\b', r'\bclass\b', r'\bconst\b', r'\blet\b', r'\bvar\b',
            r'\bdef\b', r'\bimport\b', r'\bfrom\b', r'\{', r'\}'
        ]

        has_code_patterns = any(re.search(pattern, response) for pattern in code_indicators)
        if not has_code_patterns:
            result["warnings"].append("Response doesn't contain typical code patterns")

        # Check for balanced braces/brackets
        if not self._check_balanced_delimiters(response):
            result["issues"].append("Unbalanced delimiters (braces, brackets, parentheses)")

    def _validate_text_structure(self, response: str, result: Dict[str, Any]):
        """Validate text response structure"""
        # Basic text validation - ensure it's not just symbols
        if re.match(r'^[^\w\s]*$', response.strip()):
            result["issues"].append("Response contains only symbols")

        # Check for minimum word count
        words = re.findall(r'\b\w+\b', response)
        if len(words) < 3:
            result["warnings"].append("Very few words in response")

    def _calculate_quality_score(self, response: str, response_type: str, context: Dict[str, Any]) -> float:
        """Calculate overall quality score for the response"""
        scores = []

        # Length appropriateness (0-0.2)
        length_score = self._score_length(response, response_type)
        scores.append(("length", length_score, 0.2))

        # Content richness (0-0.3)
        richness_score = self._score_content_richness(response, response_type)
        scores.append(("richness", richness_score, 0.3))

        # Structure coherence (0-0.3)
        coherence_score = self._score_structure_coherence(response, response_type)
        scores.append(("coherence", coherence_score, 0.3))

        # Context relevance (0-0.2)
        relevance_score = self._score_context_relevance(response, context)
        scores.append(("relevance", relevance_score, 0.2))

        # Calculate weighted average
        total_score = sum(score * weight for _, score, weight in scores)
        max_possible = sum(weight for _, _, weight in scores)

        final_score = total_score / max_possible if max_possible > 0 else 0.0

        # Log detailed scoring
        self.monitor.debug(f"Quality scores: {[(name, score) for name, score, _ in scores]} = {final_score:.3f}")

        return min(1.0, max(0.0, final_score))

    def _score_length(self, response: str, response_type: str) -> float:
        """Score response based on length appropriateness"""
        length = len(response.strip())

        if response_type == "json":
            # JSON should be reasonably sized
            if 50 <= length <= 10000:
                return 1.0
            elif length < 50:
                return 0.3
            else:
                return 0.7
        elif response_type == "code":
            # Code can be longer
            if 100 <= length <= 50000:
                return 1.0
            elif length < 100:
                return 0.4
            else:
                return 0.8
        else:
            # Text responses
            if 50 <= length <= 5000:
                return 1.0
            elif length < 50:
                return 0.5
            else:
                return 0.9

    def _score_content_richness(self, response: str, response_type: str) -> float:
        """Score based on content richness and diversity"""
        if response_type == "json":
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    # More keys = richer content
                    key_count = len(parsed)
                    if key_count >= 5:
                        return 1.0
                    elif key_count >= 3:
                        return 0.7
                    else:
                        return 0.4
            except:
                return 0.1
        elif response_type == "code":
            # Check for various code constructs
            constructs = [
                r'\bfunction\b', r'\bclass\b', r'\bif\b', r'\bfor\b', r'\bwhile\b',
                r'\btry\b', r'\bcatch\b', r'\bimport\b', r'\bexport\b'
            ]
            found_constructs = sum(1 for pattern in constructs if re.search(pattern, response))
            return min(1.0, found_constructs / 5.0)
        else:
            # Text richness based on unique words
            words = re.findall(r'\b\w+\b', response.lower())
            unique_words = len(set(words))
            total_words = len(words)
            if total_words == 0:
                return 0.0
            uniqueness_ratio = unique_words / total_words
            return min(1.0, uniqueness_ratio * 2)  # Cap at 50% uniqueness

        return 0.5

    def _score_structure_coherence(self, response: str, response_type: str) -> float:
        """Score based on structural coherence"""
        if response_type == "json":
            try:
                json.loads(response)
                return 1.0
            except:
                return 0.0
        elif response_type == "code":
            # Check for balanced delimiters and basic syntax
            score = 1.0
            if not self._check_balanced_delimiters(response):
                score -= 0.5

            # Check for incomplete statements (ending with operators)
            if re.search(r'[+\-*/=<>!&|]$', response.strip()):
                score -= 0.3

            return max(0.0, score)
        else:
            # Text coherence - check for proper sentence structure
            sentences = re.split(r'[.!?]+', response)
            complete_sentences = sum(1 for s in sentences if len(s.strip()) > 5)
            total_sentences = len([s for s in sentences if s.strip()])
            if total_sentences == 0:
                return 0.0
            return complete_sentences / total_sentences

    def _score_context_relevance(self, response: str, context: Dict[str, Any]) -> float:
        """Score based on context relevance"""
        if not context:
            return 0.8  # Neutral score when no context

        relevance_indicators = 0
        total_indicators = 0

        # Check for expected keywords from context
        if "expected_keywords" in context:
            keywords = context["expected_keywords"]
            total_indicators += len(keywords)
            relevance_indicators += sum(1 for keyword in keywords if keyword.lower() in response.lower())

        # Check for domain-specific terms
        if "domain" in context:
            domain = context["domain"]
            domain_terms = {
                "typescript": ["interface", "type", "const", "function", "class"],
                "python": ["def", "class", "import", "from", "self"],
                "json": ["{", "}", "[", "]", ":", ","]
            }
            expected_terms = domain_terms.get(domain, [])
            if expected_terms:
                total_indicators += len(expected_terms)
                relevance_indicators += sum(1 for term in expected_terms if term in response)

        if total_indicators == 0:
            return 0.8

        return relevance_indicators / total_indicators

    def _validate_semantics(self, response: str, response_type: str, result: Dict[str, Any]):
        """Perform semantic validation (e.g., code compilation)"""
        if response_type == "code":
            self._validate_code_semantics(response, result)
        elif response_type == "json":
            self._validate_json_semantics(response, result)

    def _validate_code_semantics(self, response: str, result: Dict[str, Any]):
        """Validate code by attempting to compile/parse it"""
        # Try to detect language and validate accordingly
        if self._is_typescript_code(response):
            self._validate_typescript_code(response, result)
        elif self._is_python_code(response):
            self._validate_python_code(response, result)
        else:
            result["warnings"].append("Unable to determine code language for semantic validation")

    def _is_typescript_code(self, code: str) -> bool:
        """Check if code appears to be TypeScript"""
        ts_indicators = [r'\binterface\b', r'\btype\b', r'\bconst\b', r'\blet\b', r':\s*\w+', r'=>\s*\{']
        return any(re.search(pattern, code) for pattern in ts_indicators)

    def _is_python_code(self, code: str) -> bool:
        """Check if code appears to be Python"""
        py_indicators = [r'\bdef\b', r'\bclass\b', r'\bimport\b', r'\bfrom\b', r'\bself\b', r':$']
        return any(re.search(pattern, code) for pattern in py_indicators)

    def _validate_typescript_code(self, code: str, result: Dict[str, Any]):
        """Validate TypeScript code compilation"""
        try:
            # Create a temporary file and try to compile with tsc
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as temp_file:
                # Add basic imports that might be needed
                full_code = f"""
import * as obsidian from 'obsidian';
declare module 'obsidian' {{
  export class Plugin {{}}
  export class Editor {{}}
  export class MarkdownView {{}}
  export class MarkdownFileInfo {{}}
}}
{code}
"""
                temp_file.write(full_code)
                temp_file_path = temp_file.name

            # Try to compile
            compile_result = subprocess.run(
                ['npx', 'tsc', '--noEmit', '--target', 'es2018', '--moduleResolution', 'node',
                 '--allowJs', '--checkJs', 'false', '--strict', temp_file_path],
                capture_output=True, text=True, timeout=10
            )

            if compile_result.returncode != 0:
                errors = compile_result.stderr.strip()
                if errors:
                    result["issues"].append(f"TypeScript compilation errors: {errors[:200]}...")
                    result["validation_metadata"]["typescript_errors"] = errors

        except subprocess.TimeoutExpired:
            result["warnings"].append("TypeScript validation timed out")
        except FileNotFoundError:
            result["warnings"].append("TypeScript compiler not available")
        except Exception as e:
            result["warnings"].append(f"TypeScript validation failed: {str(e)}")
        finally:
            # Clean up temp file
            try:
                import os
                os.unlink(temp_file_path)
            except:
                pass

    def _validate_python_code(self, code: str, result: Dict[str, Any]):
        """Validate Python code syntax"""
        try:
            ast.parse(code)
            result["validation_metadata"]["python_syntax"] = "valid"
        except SyntaxError as e:
            result["issues"].append(f"Python syntax error: {str(e)}")
            result["validation_metadata"]["python_syntax"] = "invalid"
        except Exception as e:
            result["warnings"].append(f"Python validation failed: {str(e)}")

    def _validate_json_semantics(self, response: str, result: Dict[str, Any]):
        """Validate JSON semantic correctness"""
        try:
            parsed = json.loads(response)
            # Check for common JSON issues
            if isinstance(parsed, dict):
                # Check for empty required fields
                empty_fields = [k for k, v in parsed.items() if v is None or (isinstance(v, (list, str, dict)) and len(v) == 0)]
                if empty_fields:
                    result["warnings"].extend(f"Empty field: {field}" for field in empty_fields)
        except:
            pass  # JSON parsing errors already caught in structure validation

    def _check_balanced_delimiters(self, text: str) -> bool:
        """Check if delimiters are balanced"""
        stack = []
        delimiters = {'(': ')', '[': ']', '{': '}'}

        for char in text:
            if char in delimiters:
                stack.append(char)
            elif char in delimiters.values():
                if not stack:
                    return False
                if delimiters[stack[-1]] != char:
                    return False
                stack.pop()

        return len(stack) == 0

    def _sanitize_response(self, response: str, response_type: str) -> str:
        """Sanitize response for security and appropriateness"""
        # Remove potentially harmful patterns
        sanitized = response

        # Remove script tags and other potentially dangerous HTML
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'<[^>]+>', '', sanitized)  # Remove all HTML tags

        # For code responses, be more restrictive
        if response_type == "code":
            # Remove potentially dangerous imports or system calls
            dangerous_patterns = [
                r'\bimport\s+os\b',
                r'\bimport\s+subprocess\b',
                r'\bimport\s+sys\b',
                r'\bexec\s*\(',
                r'\beval\s*\(',
                r'\b__import__\s*\('
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, sanitized):
                    self.monitor.warning(f"Potentially dangerous pattern detected in code: {pattern}")

        return sanitized.strip()


class MultiModelFallback:
    """Handle fallback to different LLM models when primary model fails"""

    def __init__(self, primary_llm, fallback_llms: List[Dict[str, Any]] = None):
        self.primary_llm = primary_llm
        self.fallback_llms = fallback_llms or []
        self.monitor = structured_log(__name__)

    def invoke_with_fallback(self, prompt: str, **kwargs) -> str:
        """Invoke LLM with fallback to other models on failure"""
        models_to_try = [self.primary_llm] + [config["llm"] for config in self.fallback_llms]

        for i, llm in enumerate(models_to_try):
            try:
                self.monitor.info(f"Trying model {i+1}/{len(models_to_try)}: {getattr(llm, 'model', 'unknown')}")
                response = llm.invoke(prompt, **kwargs)

                if response and len(response.strip()) > 0:
                    if i > 0:
                        self.monitor.info(f"Successfully used fallback model {i+1}")
                    return response
                else:
                    self.monitor.warning(f"Model {i+1} returned empty response")

            except Exception as e:
                self.monitor.warning(f"Model {i+1} failed: {str(e)}")
                continue

        raise Exception("All LLM models failed to provide a valid response")


# Global instances
response_validator = LLMResponseValidator()

def validate_llm_response(response: str, response_type: str = "text", context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Global function for LLM response validation"""
    return response_validator.validate_response(response, response_type, context)

def get_response_validator() -> LLMResponseValidator:
    """Get the global response validator instance"""
    return response_validator