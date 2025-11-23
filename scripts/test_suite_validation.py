#!/usr/bin/env python3
"""
Simple validation script for the test_suite module
"""

import sys
import os

# Add the agents/agentics/src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents', 'agentics', 'src'))

try:
    # Test basic imports
    from test_suite import validate_llm_test_suite, generate_test_suite_report
    print("✅ Basic imports successful")

    # Test with simple code and tests
    code = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }
}
"""

    tests = """
describe('Calculator', () => {
    it('should add numbers', () => {
        const calc = new Calculator();
        expect(calc.add(2, 3)).toBe(5);
    });
});
"""

    print("✅ Test data prepared")

    # Run validation (without code validator to avoid dependencies)
    result = validate_llm_test_suite(code, tests, include_code_validator=False)
    print("✅ Validation completed")

    # Check result structure
    assert hasattr(result, 'overall_score')
    assert hasattr(result, 'risk_level')
    assert hasattr(result, 'code_execution')
    assert hasattr(result, 'test_execution')
    assert hasattr(result, 'test_code_relationship')
    assert hasattr(result, 'langchain_compliance')
    print("✅ Result structure valid")

    # Generate report
    report = generate_test_suite_report(code, tests, result)
    assert isinstance(report, str)
    assert len(report) > 100
    print("✅ Report generation successful")

    print("\n🎉 All basic validations passed!")
    print(f"Overall Score: {result.overall_score:.1f}/100")
    print(f"Risk Level: {result.risk_level.value}")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)