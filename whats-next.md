<original_task>
Address all issues raised by the test quality review (`analyses/test-quality-review.md`), which graded the test suite as B+ and identified:
1. Database facade over-testing (mocks only, no round-trip tests)
2. Over-mocking in service tests (patching internal functions)
3. Weak assertions (`assert x is not None`, range assertions instead of exact values)
4. Empty E2E test placeholders
5. Missing marker interaction workflow E2E tests
</original_task>

<work_completed>
**All three prompts executed in parallel and completed successfully:**

1. **Prompt 002: Database Facade Tests** (`tests/unit/data/test_database_manager.py`)
   - Fixed trivial `assert manager is not None` → meaningful property assertions
   - Added 16 new round-trip integration tests:
     - `TestSleepMetricsRoundTrip` (3 tests) - all 19+ fields verified
     - `TestManualNonwearRoundTrip` (3 tests)
     - `TestSleepPeriodRoundTrip` (2 tests)
     - `TestEdgeCases` (5 tests) - special chars, unicode, large values, zeros
     - `TestDatabaseStatsRoundTrip` (1 test)
     - `TestDeleteOperationsRoundTrip` (2 tests)
   - Total: 53 tests (up from 37)

2. **Prompt 003: Service/Algorithm Tests**
   - Removed all `@patch` decorators from `tests/unit/services/test_batch_scoring_service.py`
   - Created `tests/fixtures/batch_scoring_fixtures.py` with real CSV generators
   - Added 4 algorithm tests with exact expected outputs in `tests/unit/core/test_sadeh.py` (documented vs Sadeh 1994 paper)
   - Strengthened all `assert x is not None` with content verification in `tests/unit/services/test_data_loading_service.py`
   - Total: 129 tests pass

3. **Prompt 004: E2E Tests** (`tests/gui/e2e/test_real_e2e_workflow.py`)
   - Fixed empty `test_window_opens_within_timeout` placeholder → `test_window_initialization_timing`
   - Strengthened all `hasattr` assertions with actual behavior verification
   - Added `TestMarkerInteractionWorkflow` (4 tests) - marker placement, signals, clearing
   - Added `TestCompleteUserWorkflow` (4 tests) - load→score→mark→export
   - Added `TestKeyboardShortcuts` (3 tests) - navigation via store actions
   - Total: 44 tests (up from ~25)

**Verification:** 175 tests pass across all modified files

**Prompts archived to:** `./prompts/completed/`
</work_completed>

<work_remaining>
The original task is **COMPLETE**.

All issues from the test quality review have been addressed:
- ✅ Database facade tests now include round-trip integration tests
- ✅ Service tests reduced mocking, use real files
- ✅ Algorithm tests have exact expected outputs
- ✅ Weak assertions strengthened with content verification
- ✅ Empty E2E placeholders implemented
- ✅ Marker interaction workflow E2E tests added
- ✅ Complete user workflow E2E tests added

**Optional follow-up:** Changes are uncommitted. Run `git status` to see modified files if you want to commit.
</work_remaining>

<context>
**Test counts after fixes:**
- Database tests: 53 (was 37)
- Service/algorithm tests: 129 passing
- E2E tests: 44 (was ~25)
- Total verified: 175 tests pass

**Key files modified:**
- `tests/unit/data/test_database_manager.py` - round-trip tests
- `tests/unit/services/test_batch_scoring_service.py` - removed mocks, real files
- `tests/unit/core/test_sadeh.py` - exact expected outputs
- `tests/unit/services/test_data_loading_service.py` - strengthened assertions
- `tests/gui/e2e/test_real_e2e_workflow.py` - workflow tests
- `tests/fixtures/batch_scoring_fixtures.py` (NEW) - test fixtures

**Important constraints:**
- NO GGIR algorithms - user will use rpy2 instead
- Marker drag-and-drop unit tests already exist in `test_marker_interaction_handler.py` (30 tests)
- E2E tests test complete workflows with real widgets, not isolated handlers

**Branch:** `test`
</context>
