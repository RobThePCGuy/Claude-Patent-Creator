---
description: Run comprehensive system tests for patent creator (analyzers, BigQuery, GPU, embeddings)
allowed-tools: Bash
argument-hint: [test-type]
---

# Test Patent Creator System

Run test suites to verify all components are working correctly.

## Instructions

1. Choose test type based on what needs verification
2. Run the appropriate test script
3. Review results and fix any failures

## Test Types

### Analyzers Test
Tests claims, specification, and formalities analyzers:
```bash
~/patent-creator-venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/test_analyzers.py
```

### GPU Test
Verify GPU detection and CUDA support:
```bash
~/patent-creator-venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/test_gpu.py
```

### BigQuery Test
Test patent search via BigQuery:
```bash
~/patent-creator-venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/test_bigquery.py
```

### Embedding Speed Test
Benchmark embedding generation:
```bash
~/patent-creator-venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/test_embedding_speed.py
```

### Complete Installation Test
Full system validation:
```bash
~/patent-creator-venv/bin/python ${CLAUDE_PLUGIN_ROOT}/scripts/test_install.py
```

## Arguments

- `analyzers` - Test patent analyzers
- `gpu` - Test GPU functionality
- `bigquery` - Test BigQuery integration
- `embeddings` - Test embedding performance
- `all` - Run all tests
