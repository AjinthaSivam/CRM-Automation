# Model Selection Guide

This guide explains how to use the model selection feature in the smart query system, which now supports both Meta-Llama-3.1-70B-Instruct and Meta-Llama-3.1-405B-Instruct models.

## Available Models

- **70b**: `meta-llama/Meta-Llama-3.1-70B-Instruct` (default)
- **405b**: `meta-llama/Meta-Llama-3.1-405B-Instruct`

## API Usage

### 1. Smart Query Endpoint (`/smart-query/`)

The main endpoint that automatically classifies queries and routes them to the appropriate workflow.

#### Request Format
```json
{
    "query": "Your query here",
    "model": "70b",  // or "405b"
    "metadata": {    // Optional, required for NED queries
        "contact_id": "003Ws000004Fo3qIAC",
        "today's_date": "2024-01-15"
    },
    "query_type": "KQA"  // Optional, auto-detected if not provided
}
```

#### Response Format
```json
{
    "query_type": "KQA",
    "result": "Answer or result",
    "error": null,
    "model_used": "70b",
    "node_outputs": [...]
}
```

#### Example Requests

**Knowledge Query with 70B model:**
```bash
curl -X POST http://localhost:8000/smart-query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What technology features do golf shoes have?",
    "model": "70b"
  }'
```

**Named Entity Disambiguation with 405B model:**
```bash
curl -X POST http://localhost:8000/smart-query/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Can you display the women'\''s trail jacket I purchased a fortnight ago?",
    "model": "405b",
    "metadata": {
      "contact_id": "003Ws000004Fo3qIAC",
      "today'\''s_date": "2024-01-15"
    }
  }'
```

### 2. Individual Workflow Endpoints

#### Knowledge Q&A (`/kqa/`)
```json
{
    "query": "What is the return policy?",
    "model": "405b"
}
```

#### Named Entity Disambiguation (`/ned/`)
```json
{
    "query": "Show me the running shoes I bought last week",
    "model": "70b",
    "metadata": {
        "contact_id": "003Ws000004Fo3qIAC",
        "today's_date": "2024-01-15"
    }
}
```

#### Policy Violation Identification (`/pvi/`)
```json
{
    "case_id": "500Ws000004Fo3qIAC",
    "model": "405b"
}
```

## Model Selection Guidelines

### When to Use 70B Model
- **Faster responses**: Generally faster processing time
- **Lower resource usage**: More efficient for high-volume requests
- **Good performance**: Sufficient for most standard queries
- **Cost-effective**: Lower computational requirements

### When to Use 405B Model
- **Complex reasoning**: Better for nuanced or complex queries
- **Higher accuracy**: Generally more accurate for sophisticated tasks
- **Better understanding**: Superior comprehension of context and subtleties
- **Research/analysis**: When maximum quality is needed

## Error Handling

### Invalid Model Selection
If you specify an invalid model, you'll receive a 400 error:

```json
{
    "error": "Invalid model 'invalid_model'. Available models: ['70b', '405b']"
}
```

### Missing Required Fields
- **NED queries**: Require `contact_id` and `today's_date` in metadata
- **PVI queries**: Require `case_id`
- **All queries**: Require `query` field

## Testing the Integration

### 1. Run the Unit Test
```bash
cd backend
python test_model_integration.py
```

### 2. Run the API Test
```bash
# Make sure the server is running first
python manage.py runserver

# In another terminal
python test_api_models.py
```

### 3. Manual Testing with curl

Test both models with the same query:

```bash
# Test with 70B model
curl -X POST http://localhost:8000/smart-query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What technology features do golf shoes have?", "model": "70b"}'

# Test with 405B model  
curl -X POST http://localhost:8000/smart-query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "What technology features do golf shoes have?", "model": "405b"}'
```

## Implementation Details

### Model Configuration
Models are configured in `backend/core/llm.py`:

```python
AVAILABLE_MODELS = {
    "70b": "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "405b": "meta-llama/Meta-Llama-3.1-405B-Instruct"
}
```

### Workflow Integration
All workflows (KQA, NED, PVI) now accept a `model_name` parameter that gets passed through to the LLM calls.

### State Management
Each workflow state includes a `model_name` field that tracks which model is being used throughout the execution.

## Performance Considerations

- **405B model**: Higher latency but better quality
- **70B model**: Lower latency but good quality
- **Memory usage**: 405B requires more memory
- **API limits**: Consider rate limits for each model

## Troubleshooting

### Common Issues

1. **Model not found**: Ensure the model name is exactly "70b" or "405b"
2. **Timeout errors**: 405B model may take longer to respond
3. **Memory errors**: 405B model requires more system resources
4. **API key issues**: Ensure `DEEPINFRA_API_KEY` is set correctly

### Debug Information

All responses include `model_used` field to confirm which model was actually used. Check the `node_outputs` for detailed execution information.

## Migration from Single Model

If you were previously using the system with only the 70B model:

1. **No breaking changes**: Default behavior remains the same (70B model)
2. **Optional upgrade**: Add `"model": "405b"` to requests for better quality
3. **Gradual migration**: Test 405B model with critical queries first
4. **A/B testing**: Compare results between models for your use cases
