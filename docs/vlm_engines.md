The `VLMEngine` class is responsible for configuring VLM for OCR. Children of this abstract class implements `chat` and `chat_async` methods for prompting VLMs with input messages. It also has `get_ocr_messages` method that unifies messages template for image input. Below are the built-in VLMEngines. Use `BasicVLMConfig` to set sampling parameters. For reasoning models, use `ReasoningVLMConfig` to handle reasoning tokens. For OpenAI reasoning models ("o" series), use `OpenAIReasoningVLMConfig` to automatically handle system prompt and reasoning tokens. 

### OpenAI Compatible
The OpenAI compatible VLM engine works with a wide variety of VLM inferencing services. In general, the parent class `OpenAICompatibleVLMEngine` can be used to create custom engines for services that follow the OpenAI chat-completion API format. Below are some built-in engines that inherit from `OpenAICompatibleVLMEngine`.

#### Locally hosted vLLM server
Inference engines like [vLLM OpenAI compatible server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) is supported. To start a server:

##### Qwen3-VL-30B-A3B-Instruct
```bash
vllm serve Qwen/Qwen3-VL-30B-A3B-Instruct \
    --max-model-len 16000 \ 
    --limit-mm-per-prompt '{"images": 1, "videos": 0}'
```

Define a VLM engine to work with the vLLM server. 

```python
from vlm4ocr import BasicVLMConfig, VLLMVLMEngine

vlm_engine = VLLMVLMEngine(model="Qwen/Qwen3-VL-30B-A3B-Instruct", 
                           config=BasicVLMConfig(max_new_tokens=4096, temperature=0.0)    
                          )
```

##### Qwen3-VL-30B-A3B-Thinking
```bash
vllm serve Qwen/Qwen3-VL-30B-A3B-Thinking \
    --max-model-len 64000 \ 
    --limit-mm-per-prompt '{"images": 1, "videos": 0}' \
    --reasoning-parser deepseek-r1
```

Define a VLM engine to work with the vLLM server. 

```python
from vlm4ocr import ReasoningVLMConfig, VLLMVLMEngine

vlm_engine = VLLMVLMEngine(model="Qwen/Qwen3-VL-30B-A3B-Thinking", 
                           config=ReasoningVLMConfig(temperature=0.6, top_p=0.95, max_new_tokens=8192)    
                          )
```

#### VLM inference with API servers
Remote VLM inference servers are supported. We use OpenRouter as an example:

```python
from vlm4ocr import BasicVLMConfig, OpenRouterVLMEngine

vlm_engine = OpenRouterVLMEngine(model="Qwen/Qwen2.5-VL-7B-Instruct", 
                                 api_key="<OPENROUTER_API_KEY>",
                                 config=BasicVLMConfig(max_tokens=4096, temperature=0.0)  
                                )
```

### Ollama
Ollama to run VLM inference:

```python
from vlm4ocr import BasicVLMConfig, OllamaVLMEngine

vlm_engine = OllamaVLMEngine(model_name="llama3.2-vision:11b-instruct-fp16", 
                             num_ctx:int=4096, 
                             keep_alive:int=300,
                             config=BasicVLMConfig(max_tokens=4096, temperature=0.0)  
                            )
```

### OpenAI API
Follow the [Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) to set up API key.

```bash
export OPENAI_API_KEY=<your_API_key>
```
For non-reasoning models (e.g., *gpt-4o-mini*), use `BasicVLMConfig` to set sampling parameters.
```python
from vlm4ocr import BasicVLMConfig, OpenAIVLMEngine

vlm_engine = OpenAIVLMEngine(model="gpt-4o-mini", config=BasicVLMConfig(max_tokens=4096, temperature=0.0) )
```

For reasoning models (e.g., *o3-mini*), use `OpenAIReasoningVLMConfig` to set reasoning effort.

```python
from vlm4ocr import OpenAIReasoningVLMConfig, OpenAIVLMEngine

vlm_engine = OpenAIVLMEngine(model="o3-mini", config=OpenAIReasoningVLMConfig(reasoning_effort="low") )
```

### Azure OpenAI API
Follow the [Azure AI Services Quickstart](https://learn.microsoft.com/en-us/azure/ai-services/openai/quickstart?tabs=command-line%2Ckeyless%2Ctypescript-keyless%2Cpython-new&pivots=programming-language-python) to set up Endpoint and API key.

```bash
export AZURE_OPENAI_API_KEY="<your_API_key>"
export AZURE_OPENAI_ENDPOINT="<your_endpoint>"
```

For non-reasoning models (e.g., *gpt-4o-mini*), use `BasicVLMConfig` to set sampling parameters.

```python
from llm_ie.engines import AzureOpenAIVLMEngine

vlm_engine = AzureOpenAIVLMEngine(model="gpt-4o-mini", 
                                  api_version="<your api version>",
                                  config=BasicVLMConfig(max_tokens=4096, temperature=0.0)  
                                )
```

For reasoning models (e.g., *o3-mini*), use `OpenAIReasoningVLMConfig` to set reasoning effort.

```python
from vlm4ocr import OpenAIReasoningVLMConfig, OpenAIVLMEngine

vlm_engine = AzureOpenAIVLMEngine(model="o3-mini", 
                                  api_version="<your api version>",
                                  config=OpenAIReasoningVLMConfig(reasoning_effort="low") )
```