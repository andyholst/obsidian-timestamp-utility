# Architecture Flow Diagram — Anti-Slop Agentics System

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         make run-agentics                                    │
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────────────────────┐ │
│  │ check-deps   │───▶│ Python      │───▶│ Output: success/fail + result   │ │
│  │ (curl, etc)  │    │ Workflow    │    │ Generated files in src/generated/│ │
│  └─────────────┘    │ (LangGraph) │    │ Integration tests in main.test.ts│ │
│                      └─────────────┘    └──────────────────────────────────┘ │
│                                                                             │
│  Key principle: "The eval loop is the system. Without it, you're shipping   │
│  every flip of the coin." — fix_the_slop.md                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Step-by-Step Flow

```
                              ┌──────────────────┐
                              │   START           │
                              │ make run-agentics │
                              └────────┬─────────┘
                                       │
                              ┌────────▼─────────┐
                              │  CHECK DEPS       │
                              │  • Ollama running │
                              │  • GITHUB_TOKEN   │
                              │  • Dagger engine  │
                              └────────┬─────────┘
                                       │
          ┌────────────────────────────▼────────────────────────────┐
          │              LANGGRAPH WORKFLOW                          │
          │                                                          │
          │  ┌────────────┐   ┌────────────┐   ┌────────────────┐   │
          │  │ 1. FETCH    │──▶│ 2. CLARIFY │──▶│ 3. PLAN        │   │
          │  │    ISSUE    │   │    TICKET  │   │    IMPLEMENT   │   │
          │  └────────────┘   └────────────┘   └────────┬───────┘   │
          │                                              │           │
          │  ┌────────────┐   ┌──────────────────────────▼────────┐  │
          │  │ 4. EXTRACT  │──▶│ 5. GENERATE CODE + TESTS          │  │
          │  │    CODE     │   │                                   │  │
          │  │ • main.ts   │   │  ┌─────────────────────────────┐  │  │
          │  │ • main.test │   │  │  LLM generates .ts code     │  │  │
          │  └────────────┘   │  │  LLM generates .ts tests    │  │  │
          │                    │  └─────────────┬───────────────┘  │  │
          │                    │                │                  │  │
          │                    │  ┌─────────────▼───────────────┐  │  │
          │                    │  │  EVAL GATE (2 Hard Gates)   │  │  │
          │                    │  │                             │  │  │
          │                    │  │  Gate 1: TESTS PASS         │  │  │
          │                    │  │  • npx jest → returncode 0  │  │  │
          │                    │  │  ─────────────────────────  │  │  │
          │                    │  │  Gate 2: CODE-TEST CONSIST  │  │  │
          │                    │  │  • Test imports = code exprt│  │  │
          │                    │  │  ─────────────────────────  │  │  │
          │                    │  │  Gate 3: SYNTAX CHECK       │  │  │
          │                    │  │  • Balanced braces {}       │  │  │
          │                    │  │  • Balanced parens ()       │  │  │
          │                    │  │  • No const reassignment    │  │  │
          │                    │  │  ─────────────────────────  │  │  │
          │                    │  │  Gate 4: COMPILATION        │  │  │
          │                    │  │  • tsc --noEmit → pass      │  │  │
          │                    │  │  ─────────────────────────  │  │  │
          │                    │  │  Gate 5: SCORE ≥ 0.7        │  │  │
          │                    │  │  • 7 criteria weighted      │  │  │
          │                    │  │  • test_quality ≥ threshold │  │  │
          │                    │  │  ─────────────────────────  │  │  │
          │                    │  │  HARD: Gates 1-2 → total=0  │  │  │
          │                    │  │  SOFT: Gates 3-5 weighted   │  │  │
          │                    │  └─────────────┬───────────────┘  │  │
          │                    │                │                  │  │
          │                    │     ┌──────────┴──────────┐       │  │
          │                    │     │                     │       │  │
          │                    │  ┌──▼───┐            ┌───▼───┐   │  │
          │                    │  │ PASS │            │ FAIL  │   │  │
          │                    │  └──┬───┘            └───┬───┘   │  │
          │                    │     │                  │        │  │
          │                    │     │           ┌──────▼──────┐ │  │
          │                    │     │           │ retry < 3?  │ │  │
          │                    │     │           │ YES → retry │ │  │
          │                    │     │           │ NO  → output│ │  │
          │                    │     │           └──────┬──────┘ │  │
          │                    │     │                  │        │  │
          │                    │  ┌──▼──────────────────▼──┐     │  │
          │                    │  │  INTEGRATE (if PASS)   │     │  │
          │                    │  │                         │     │  │
          │                    │  │  1. Write generated.ts  │     │  │
          │                    │  │  2. Add import to main  │     │  │
          │                    │  │  3. Add addCommand      │     │  │
          │                    │  │  4. Write generated    │     │  │
          │                    │  │     test file (separate)│     │  │
          │                    │  │  5. Append integration │     │  │
          │                    │  │     tests to main.test │     │  │
          │                    │  └──────────┬──────────────┘     │  │
          │                    │             │                    │  │
          │                    └─────────────┼────────────────────┘  │
          │                                  │                       │
          │                    ┌─────────────▼───────────────┐       │
          │                    │ 6. TEST (post-integration)  │       │
          │                    │  • npx jest ALL tests       │       │
          │                    │  • main.test.ts             │       │
          │                    │  • generated tests          │       │
          │                    │  • other plugin tests       │       │
          │                    └─────────────┬───────────────┘       │
          │                                  │                       │
          │                    ┌─────────────▼───────────────┐       │
          │                    │ 7. OUTPUT                   │       │
          │                    │  • success = integrated     │       │
          │                    │  • result dict              │       │
          │                    │  • eval scores              │       │
          │                    └─────────────┬───────────────┘       │
          └──────────────────────────────────┼───────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  END                 │
                              │  • success=True/False│
                              │  • generated files   │
                              │  • integrated files  │
                              └─────────────────────┘
```

## The 2 Hard Gates (Eval Gate Detail)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GENERATED OUTPUT: code.ts + tests.ts                                       │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  GATE 1: TESTS PASS  │
                    │  npx jest tests.ts   │
                    │                      │
                    │  returncode == 0?    │──NO──▶ FAIL (total=0)
                    └──────────┬───────────┘
                               │ YES
                    ┌──────────▼──────────┐
                    │  GATE 2: CONSISTENCY │
                    │  imports == exports? │
                    │                      │
                    │  All imports match?  │──NO──▶ FAIL (total=0)
                    └──────────┬───────────┘
                               │ YES
                    ┌──────────▼──────────┐
                    │  WEIGHTED GATES      │
                    │  (NOT hard gates)    │
                    │                      │
                    │  Gate 3: SYNTAX      │
                    │  • Balanced braces   │
                    │  • Balanced parens   │
                    │  • No const reassign │
                    │                      │
                    │  Gate 4: COMPILATION │
                    │  • tsc --noEmit      │
                    │                      │
                    │  Gate 5: SCORE ≥ 0.7 │
                    │  • 7 criteria weight │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼──────────┐
                    │  ALL CHECKS PASSED   │
                    │  → INTEGRATE         │
                    │  → main.ts updated   │
                    │  → main.test updated │
                    └─────────────────────┘
```

## 7 Quality Criteria (Weighted Scoring)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CRITERION              │ WEIGHT │ WHAT IT CHECKS                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  compiles_successfully  │  0.25  │ tsc --noEmit passes (weighted only)       │
│  tests_pass             │  0.20  │ npx jest returns 0 (HARD GATE)           │
│  test_quality           │  0.20  │ Tests are comprehensive (not trivial)    │
│  has_actionable_output  │  0.15  │ Non-empty code produced                  │
│  structural_integrity   │  0.10  │ Balanced braces/parens, valid syntax     │
│  requirement_coverage   │  0.05  │ Code addresses ticket requirements       │
│  test_validation        │  0.05  │ Heuristic: assert count in tests        │
├─────────────────────────────────────────────────────────────────────────────┤
│  TOTAL                  │  1.00  │ Threshold: 0.7                           │
└─────────────────────────────────────────────────────────────────────────────┘

test_quality sub-checks (must score ≥ 0.5 to avoid penalty):
  • Function actually called (not just typeof check)     +0.5
  • Return type asserted (expect typeof === 'string')    +0.5  
  • Output format/length checked                         +0.5
  • Uniqueness checked (Set, multiple calls)             +0.5
  • ≥3 it() blocks                                       +0.5
  Max: 2.5 → normalized to 0-1 range
```

## Routing Logic (Conditional Edge)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  After generate_code_tests node:                                            │
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │ eval_passed?    │     │ recovery_attempt│     │ Max retries     │        │
│  │                 │     │ < 3?            │     │ exhausted       │        │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘        │
│           │                       │                       │                 │
│  ┌────────▼────────┐     ┌───────▼────────┐     ┌───────▼────────┐        │
│  │ YES → "test"    │     │ YES → retry    │     │ NO → "output"  │        │
│  │ (continue to    │     │ "generate_code  │     │ (stop workflow, │        │
│  │  post-integration│    │  _tests" again  │     │  success=False) │        │
│  │  tests)         │     │ + increment     │     │                 │        │
│  └─────────────────┘     │   counter       │     └─────────────────┘        │
│                          └─────────────────┘                                │
│                                                                             │
│  Key: After 3 failed retries, workflow STOPS. Does NOT run tests on        │
│  broken code. Does NOT integrate. Output node reports success=False.       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Integration Process (When All Gates Pass)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTEGRATION SEQUENCE (atomic — all or nothing)                             │
│                                                                             │
│  Step 1: Write generated code                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ src/generated/<slug>.ts                                              │    │
│  │ • export function generateUuidV7(): string { ... }                   │    │
│  │ • Saved with backup of previous version                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  Step 2: Update main.ts                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ • Add import after existing imports:                                 │    │
│  │   import { generateUuidV7 } from './generated/<slug>';               │    │
│  │                                                                      │    │
│  │ • Add addCommand inside onload() method:                             │    │
│  │   this.addCommand({                                                  │    │
│  │       id: '<command_id>',                                            │    │
│  │       name: '<title>',                                               │    │
│  │       editorCallback: (editor, _ctx) => {                            │    │
│  │           editor.replaceSelection(generateUuidV7());                 │    │
│  │       },                                                             │    │
│  │   });                                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  Step 3: Write generated tests (separate file)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ src/__tests__/generated/<slug>.test.ts                               │    │
│  │ • Tests the raw function in isolation                                │    │
│  │ • import { generateUuidV7 } from '../../generated/<slug>';           │    │
│  │ • describe('generateUuidV7', () => { ... })                          │    │
│  │ • NOT appended to main.test.ts                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  Step 4: Append integration tests to main.test.ts                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Appended before final '});' of main describe block:                 │    │
│  │                                                                      │    │
│  │ describe('Integration: <command_id> command', () => {                │    │
│  │     let plugin: any;                                                 │    │
│  │     let mockEditor: any;                                             │    │
│  │     beforeEach(() => {                                               │    │
│  │         plugin = { commands: [{                                      │    │
│  │             id: '<command_id>',                                      │    │
│  │             name: '<title>',                                         │    │
│  │             editorCallback: jest.fn()                                │    │
│  │         }]};                                                          │    │
│  │         mockEditor = { replaceSelection: jest.fn() };                │    │
│  │     });                                                              │    │
│  │     it('should register the <command_id> command', ...);             │    │
│  │     it('should have the correct command name', ...);                 │    │
│  │     it('should have an editorCallback', ...);                        │    │
│  │     it('should call the editorCallback and replace selection', ...); │    │
│  │     it('should import <export_name> from generated module', ...);    │    │
│  │ });                                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  Step 5: Save regression baseline                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ RegressionTracker.save_baseline(eval_scores)                         │    │
│  │ RubricStore.record(eval_result)                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## File Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   AGENTIC CODE (generates)          RESULTS (created/updated)               │
│                                                                             │
│   ┌─────────────────────┐           ┌─────────────────────┐                 │
│   │ LLM reasoning model │           │ src/generated/      │                 │
│   │                     │──────────▶│   <slug>.ts         │                 │
│   │ • Generates code    │           │   (export function)  │                 │
│   │ • Generates tests   │           └─────────┬───────────┘                 │
│   │ • Naming prompt     │                     │                             │
│   └─────────────────────┘                     │ imported by                 │
│                                               │                             │
│   ┌─────────────────────┐           ┌─────────▼───────────┐                 │
│   │ Eval gate scoring   │           │ src/main.ts         │                 │
│   │                     │           │                     │                 │
│   │ • 2 hard gates      │──────────▶│ • import { func }   │                 │
│   │ • 7 weighted criteria│          │ • addCommand({...}) │                 │
│   │ • compiles_success  │           │                     │                 │
│   │ • test_quality      │           └─────────┬───────────┘                 │
│   └─────────────────────┘                     │                             │
│                                               │ tested by                   │
│   ┌─────────────────────┐           ┌─────────▼───────────┐                 │
│   │ LLM code model      │           │ src/__tests__/      │                 │
│   │                     │           │   main.test.ts      │                 │
│   │ • Generates tests   │──────────▶│                     │                 │
│   │ • Self-correction   │           │ • Integration tests │                 │
│   │ • Retry on failure  │           │   (appended)        │                 │
│   └─────────────────────┘           │                     │                 │
│                                     └─────────┬───────────┘                 │
│                                               │                             │
│                                               │ also tests                  │
│                                     ┌─────────▼───────────┐                 │
│                                     │ src/__tests__/      │                 │
│                                     │   generated/        │                 │
│                                     │     <slug>.test.ts  │                 │
│                                     │                     │                 │
│                                     │ • Function tests    │                 │
│                                     │ • Raw unit tests    │                 │
│                                     │ • (separate file)   │                 │
│                                     └─────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Anti-Slop Protection Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER                  │ PROTECTS AGAINST           │ HOW                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 1: Tests pass     │ Code that crashes at runtime│ npx jest returncode  │
│                         │ (HARD GATE: total=0 on fail)│                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 2: Consistency    │ Test imports wrong function│ Import/export matching│
│                         │ (HARD GATE: total=0 on fail)│                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 3: Syntax         │ Const reassignment         │ Pattern matching     │
│                         │ Unbalanced braces/parens   │ Depth counting       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 4: Compilation    │ TypeScript type errors     │ tsc --noEmit         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 5: Test quality   │ Trivial tests (typeof only)│ Pattern analysis     │
│                         │ Tests that always pass     │ Multi-criteria check │
├─────────────────────────────────────────────────────────────────────────────┤
│  Gate 6: Score threshold│ Mediocre code              │ 7 criteria weighted  │
│                         │                            │ Must be ≥ 0.7        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Routing fix            │ Broken code reaching tests │ Stop after 3 retries │
├─────────────────────────────────────────────────────────────────────────────┤
│  Output node fix        │ False success reporting    │ success=integrated   │
└─────────────────────────────────────────────────────────────────────────────┘

Result: Code that compiles but produces wrong results (like UUID v7 without
version bits) is caught by test_quality gate because the generated tests
don't check the right things. The code is NOT integrated.
```
