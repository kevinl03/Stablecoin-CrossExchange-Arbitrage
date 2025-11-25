# Timeout and Error Code System

## Overview

The live integration tests now include comprehensive timeout handling and error codes to properly handle API failures, network issues, and timeouts.

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | `SUCCESS` | Test completed successfully |
| 1 | `TIMEOUT` | Operation exceeded timeout limit |
| 2 | `API_ERROR` | General API error |
| 3 | `NETWORK_ERROR` | Network/connection error |
| 4 | `RATE_LIMIT` | API rate limit exceeded |
| 5 | `UNKNOWN_ERROR` | Unexpected error |
| 6 | `NO_DATA` | No data available (e.g., empty graph) |

## Timeout Configuration

Each test function has a timeout decorator with appropriate limits:

| Test Function | Timeout | Reason |
|--------------|---------|--------|
| `test_live_sparse_vs_dense` | 60s | Graph construction can be slow |
| `test_live_weighted_astar` | 45s | Algorithm execution |
| `test_live_volatility_tracking` | 30s | Simple API calls |
| `test_live_metrics_output` | 60s | Graph + algorithm + file I/O |

## Usage

### Timeout Decorator

```python
@with_timeout(timeout_seconds=30)
def my_test_function():
    # This function will timeout after 30 seconds
    ...
```

### Error Code Handling

```python
try:
    result = test_function()
    if result == ErrorCodes.SUCCESS:
        print("Test passed")
    elif result == ErrorCodes.TIMEOUT:
        print("Test timed out")
except TimeoutError as e:
    print(f"Timeout: {e.message}, Code: {e.error_code}")
```

## Implementation Details

### Unix/MacOS (Signal-based)
- Uses `signal.SIGALRM` for precise timeout
- More efficient, lower overhead
- Works on Unix-like systems

### Windows/Fallback (Threading-based)
- Uses `threading.Thread` with `join(timeout)`
- Cross-platform compatible
- Slightly higher overhead

## Test Output

The test suite now provides detailed error information:

```
LIVE TEST SUMMARY
============================================================
✓ Passed: 2/4
⚠ Skipped: 1/4
⏱ Timeouts: 1/4
✗ Failed: 1/4

Error Code Summary:
  test_live_sparse_vs_dense: TIMEOUT (1)
  test_live_volatility_tracking: RATE_LIMIT (4)
============================================================
```

## Exit Codes

The script returns appropriate exit codes:
- `0` (SUCCESS): All tests passed
- `1` (TIMEOUT): One or more tests timed out
- `2` (API_ERROR): API-related failures
- Other codes: See ErrorCodes class

## Benefits

1. **Prevents Hanging**: Tests won't hang indefinitely on slow APIs
2. **Clear Diagnostics**: Error codes identify specific failure types
3. **Better CI/CD**: Exit codes enable automated test reporting
4. **User-Friendly**: Clear error messages with codes

## Example Output

```
============================================================
LIVE TEST: Sparse vs Dense Graph Construction
============================================================
Timeout: 60 seconds

1. Building DENSE graph...
   ✓ Nodes: 6
   ✓ Edges: 30
   ✓ Build time: 2.3456s

✗ TIMEOUT: Operation exceeded timeout limit
  Error Code: 1
```

## Future Enhancements

- Configurable timeout per test via command-line arguments
- Retry logic for transient failures
- Exponential backoff for rate limits
- Timeout adjustment based on network conditions

