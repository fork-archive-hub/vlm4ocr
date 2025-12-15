import abc
import importlib.util
from typing import Any, List, Dict, Union, Generator
import warnings
import os
import re
from PIL import Image
from vlm4ocr.utils import image_to_base64
from vlm4ocr.data_types import FewShotExample


class VLMConfig(abc.ABC):
    def __init__(self, **kwargs):
        """
        This is an abstract class to provide interfaces for VLM configuration. 
        Children classes that inherts this class can be used in extrators and prompt editor.
        Common VLM parameters: max_new_tokens, temperature, top_p, top_k, min_p.
        """
        self.params = kwargs.copy()

    @abc.abstractmethod
    def preprocess_messages(self, messages:List[Dict[str,str]]) -> List[Dict[str,str]]:
        """
        This method preprocesses the input messages before passing them to the VLM.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        
        Returns:
        -------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        """
        return NotImplemented

    @abc.abstractmethod
    def postprocess_response(self, response:Union[str, Dict[str, str], Generator[str, None, None]]) -> Union[str, Generator[str, None, None]]:
        """
        This method postprocesses the VLM response after it is generated.

        Parameters:
        ----------
        response : Union[str, Generator[str, None, None]]
            the VLM response. Can be a string or a generator.
        
        Returns:
        -------
        response : str
            the postprocessed VLM response
        """
        return NotImplemented


class BasicVLMConfig(VLMConfig):
    def __init__(self, max_new_tokens:int=2048, temperature:float=0.0, **kwargs):
        """
        The basic VLM configuration for most non-reasoning models.
        """
        super().__init__(**kwargs)
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.params["max_new_tokens"] = self.max_new_tokens
        self.params["temperature"] = self.temperature

    def preprocess_messages(self, messages:List[Dict[str,str]]) -> List[Dict[str,str]]:
        """
        This method preprocesses the input messages before passing them to the VLM.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        
        Returns:
        -------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        """
        return messages

    def postprocess_response(self, response:Union[str, Dict[str, str], Generator[str, None, None]]) -> Union[Dict[str, str], Generator[Dict[str, str], None, None]]:
        """
        This method postprocesses the VLM response after it is generated.

        Parameters:
        ----------
        response : Union[str, Generator[str, None, None]]
            the VLM response. Can be a string or a generator.
        
        Returns: Union[str, Generator[Dict[str, str], None, None]]
            the postprocessed VLM response. 
            if input is a generator, the output will be a generator {"type": "response", "data": <content>}.
        """
        if isinstance(response, str):
            return {"response": response}
        
        elif isinstance(response, dict):
            if "response" in response:
                return response
            else:
                warnings.warn(f"Invalid response dict keys: {response.keys()}. Returning default empty dict.", UserWarning)
                return {"response": ""}

        def _process_stream():
            for chunk in response:
                if isinstance(chunk, dict):
                    yield chunk
                elif isinstance(chunk, str):
                    yield {"type": "response", "data": chunk}

        return _process_stream()
    
class ReasoningVLMConfig(VLMConfig):
    def __init__(self, thinking_token_start="<think>", thinking_token_end="</think>", **kwargs):
        """
        The general configuration for reasoning vision models.
        """
        super().__init__(**kwargs)
        self.thinking_token_start = thinking_token_start
        self.thinking_token_end = thinking_token_end

    def preprocess_messages(self, messages:List[Dict[str,str]]) -> List[Dict[str,str]]:
        """
        This method preprocesses the input messages before passing them to the VLM.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        
        Returns:
        -------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        """
        return messages.copy()

    def postprocess_response(self, response:Union[str, Dict[str, str], Generator[str, None, None]]) -> Union[Dict[str,str], Generator[Dict[str,str], None, None]]:
        """
        This method postprocesses the VLM response after it is generated.
        1. If input is a string, it will extract the reasoning and response based on the thinking tokens.
        2. If input is a dict, it should contain keys "reasoning" and "response". This is for inference engines that already parse reasoning and response.
        3. If input is a generator, 
            a. if the chunk is a dict, it should contain keys "type" and "data". This is for inference engines that already parse reasoning and response.
            b. if the chunk is a string, it will yield dicts with keys "type" and "data" based on the thinking tokens.

        Parameters:
        ----------
        response : Union[str, Generator[str, None, None]]
            the VLM response. Can be a string or a generator.
        
        Returns:
        -------
        response : Union[str, Generator[str, None, None]]
            the postprocessed LLM response as a dict {"reasoning": <reasoning>, "response": <content>}
            if input is a generator, the output will be a generator {"type": <reasoning or response>, "data": <content>}.
        """
        if isinstance(response, str):
            # get contents between thinking_token_start and thinking_token_end
            pattern = f"{re.escape(self.thinking_token_start)}(.*?){re.escape(self.thinking_token_end)}"
            match = re.search(pattern, response, re.DOTALL)
            reasoning = match.group(1) if match else ""
            # get response AFTER thinking_token_end
            response = re.sub(f".*?{self.thinking_token_end}", "", response, flags=re.DOTALL).strip()
            return {"reasoning": reasoning, "response": response}

        elif isinstance(response, dict):
            if "reasoning" in response and "response" in response:
                return response
            else:
                warnings.warn(f"Invalid response dict keys: {response.keys()}. Returning default empty dict.", UserWarning)
                return {"reasoning": "", "response": ""}

        elif isinstance(response, Generator):
            def _process_stream():
                think_flag = False
                buffer = ""
                for chunk in response:
                    if isinstance(chunk, dict):
                        yield chunk

                    elif isinstance(chunk, str):
                        buffer += chunk
                        # switch between reasoning and response
                        if self.thinking_token_start in buffer:
                            think_flag = True
                            buffer = buffer.replace(self.thinking_token_start, "")
                        elif self.thinking_token_end in buffer:
                            think_flag = False
                            buffer = buffer.replace(self.thinking_token_end, "")
                        
                        # if chunk is in thinking block, tag it as reasoning; else tag it as response
                        if chunk not in [self.thinking_token_start, self.thinking_token_end]:
                            if think_flag:
                                yield {"type": "reasoning", "data": chunk}
                            else:
                                yield {"type": "response", "data": chunk}

            return _process_stream()
        
        else:
            warnings.warn(f"Invalid response type: {type(response)}. Returning default empty dict.", UserWarning)
            return {"reasoning": "", "response": ""}


class OpenAIReasoningVLMConfig(ReasoningVLMConfig):
    def __init__(self, reasoning_effort:str="low", **kwargs):
        """
        The OpenAI "o" series configuration.
        1. The reasoning effort is set to "low" by default.
        2. The temperature parameter is not supported and will be ignored.
        3. The system prompt is not supported and will be concatenated to the next user prompt.

        Parameters:
        ----------
        reasoning_effort : str, Optional
            the reasoning effort. Must be one of {"low", "medium", "high"}. Default is "low".
        """
        super().__init__(**kwargs)
        if reasoning_effort not in ["low", "medium", "high"]:
            raise ValueError("reasoning_effort must be one of {'low', 'medium', 'high'}.")

        self.reasoning_effort = reasoning_effort
        self.params["reasoning_effort"] = self.reasoning_effort

        if "temperature" in self.params:
            warnings.warn("Reasoning models do not support temperature parameter. Will be ignored.", UserWarning)
            self.params.pop("temperature")

    def preprocess_messages(self, messages:List[Dict[str,str]]) -> List[Dict[str,str]]:
        """
        Concatenate system prompts to the next user prompt.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        
        Returns:
        -------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        """
        system_prompt_holder = ""
        new_messages = []
        for i, message in enumerate(messages):
            # if system prompt, store it in system_prompt_holder
            if message['role'] == 'system':
                system_prompt_holder = message['content']
            # if user prompt, concatenate it with system_prompt_holder
            elif message['role'] == 'user':
                if system_prompt_holder:
                    new_message = {'role': message['role'], 'content': f"{system_prompt_holder} {message['content']}"}
                    system_prompt_holder = ""
                else:
                    new_message = {'role': message['role'], 'content': message['content']}

                new_messages.append(new_message)
            # if assistant/other prompt, do nothing
            else:
                new_message = {'role': message['role'], 'content': message['content']}
                new_messages.append(new_message)

        return new_messages


class MessagesLogger:
    def __init__(self):
        """
        This class is used to log the messages for InferenceEngine.chat().
        """
        self.messages_log = []

    def log_messages(self, messages : List[Dict[str,str]]):
        """
        This method logs the messages to a list.
        """
        self.messages_log.append(messages)

    def get_messages_log(self) -> List[List[Dict[str,str]]]:
        """
        This method returns a copy of the current messages log
        """
        return self.messages_log.copy()
    
    def clear_messages_log(self):
        """
        This method clears the current messages log
        """
        self.messages_log.clear()


class VLMEngine:
    @abc.abstractmethod
    def __init__(self, config:VLMConfig, **kwrs):
        """
        This is an abstract class to provide interfaces for VLM inference engines. 
        Children classes that inherts this class can be used in extrators. Must implement chat() method.

        Parameters:
        ----------
        config : VLMConfig
            the VLM configuration. Must be a child class of VLMConfig.
        """
        return NotImplemented

    @abc.abstractmethod
    def chat(self, messages:List[Dict[str,str]], verbose:bool=False, stream:bool=False, 
             messages_logger:MessagesLogger=None) -> Union[Dict[str, str], Generator[Dict[str, str], None, None]]:
        """
        This method inputs chat messages and outputs VLM generated text.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        verbose : bool, Optional
            if True, VLM generated text will be printed in terminal in real-time.
        stream : bool, Optional
            if True, returns a generator that yields the output in real-time.
        Messages_logger : MessagesLogger, Optional
            the message logger that logs the chat messages.
        """
        return NotImplemented
    
    @abc.abstractmethod
    def chat_async(self, messages:List[Dict[str,str]], messages_logger:MessagesLogger=None) -> Dict[str, str]:
        """
        The async version of chat method. Streaming is not supported.
        """
        return NotImplemented

    @abc.abstractmethod
    def get_ocr_messages(self, system_prompt:str, user_prompt:str, image:Image.Image, few_shot_examples:List[FewShotExample]=None) -> List[Dict[str,str]]:
        """
        This method inputs an image and returns the correesponding chat messages for the inference engine.

        Parameters:
        ----------
        system_prompt : str
            the system prompt.
        user_prompt : str
            the user prompt.
        image : Image.Image
            the image for OCR.
        few_shot_examples : List[FewShotExample], Optional
            list of few-shot examples. 
        """
        return NotImplemented
    
    def _format_config(self) -> Dict[str, Any]:
        """
        This method format the VLM configuration with the correct key for the inference engine. 

        Return : Dict[str, Any]
            the config parameters.
        """
        return NotImplemented


class OllamaVLMEngine(VLMEngine):
    def __init__(self, model_name:str, num_ctx:int=8192, keep_alive:int=300, config:VLMConfig=None, **kwrs):
        """
        The Ollama inference engine.

        Parameters:
        ----------
        model_name : str
            the model name exactly as shown in >> ollama ls
        num_ctx : int, Optional
            context length that LLM will evaluate.
        keep_alive : int, Optional
            seconds to hold the LLM after the last API call.
        config : LLMConfig
            the LLM configuration. 
        """
        if importlib.util.find_spec("ollama") is None:
            raise ImportError("ollama-python not found. Please install ollama-python (```pip install ollama```).")
        
        from ollama import Client, AsyncClient
        self.client = Client(**kwrs)
        self.async_client = AsyncClient(**kwrs)
        self.model_name = model_name
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.config = config if config else BasicVLMConfig()
        self.formatted_params = self._format_config()
    
    def _format_config(self) -> Dict[str, Any]:
        """
        This method format the LLM configuration with the correct key for the inference engine. 
        """
        formatted_params = self.config.params.copy()
        if "max_new_tokens" in formatted_params:
            formatted_params["num_predict"] = formatted_params["max_new_tokens"]
            formatted_params.pop("max_new_tokens")

        return formatted_params

    def chat(self, messages:List[Dict[str,str]], verbose:bool=False, stream:bool=False, 
             messages_logger:MessagesLogger=None) -> Union[Dict[str,str], Generator[Dict[str, str], None, None]]:
        """
        This method inputs chat messages and outputs VLM generated text.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        verbose : bool, Optional
            if True, VLM generated text will be printed in terminal in real-time.
        stream : bool, Optional
            if True, returns a generator that yields the output in real-time.
        Messages_logger : MessagesLogger, Optional
            the message logger that logs the chat messages.

        Returns:
        -------
        response : Union[Dict[str,str], Generator[Dict[str, str], None, None]]
            a dict {"reasoning": <reasoning>, "response": <response>} or Generator {"type": <reasoning or response>, "data": <content>}
        """
        processed_messages = self.config.preprocess_messages(messages)

        options={'num_ctx': self.num_ctx, **self.formatted_params}
        if stream:
            def _stream_generator():
                response_stream = self.client.chat(
                    model=self.model_name, 
                    messages=processed_messages, 
                    options=options,
                    stream=True, 
                    keep_alive=self.keep_alive
                )
                res = {"reasoning": "", "response": ""}
                for chunk in response_stream:
                    if hasattr(chunk.message, 'thinking') and chunk.message.thinking:
                        content_chunk = getattr(getattr(chunk, 'message', {}), 'thinking', '')
                        res["reasoning"] += content_chunk
                        yield {"type": "reasoning", "data": content_chunk}
                    else:
                        content_chunk = getattr(getattr(chunk, 'message', {}), 'content', '')
                        res["response"] += content_chunk
                        yield {"type": "response", "data": content_chunk}

                    if chunk.done_reason == "length":
                        warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)
                
                # Postprocess response
                res_dict = self.config.postprocess_response(res)
                # Write to messages log
                if messages_logger:
                    # replace images content with a placeholder "[image]" to save space
                    for messages in processed_messages:
                        if "images" in messages:
                            messages["images"] = ["[image]" for _ in messages["images"]]

                    processed_messages.append({"role": "assistant",
                                                "content": res_dict.get("response", ""),
                                                "reasoning": res_dict.get("reasoning", "")})
                    messages_logger.log_messages(processed_messages)

            return self.config.postprocess_response(_stream_generator())

        elif verbose:
            response = self.client.chat(
                            model=self.model_name, 
                            messages=processed_messages, 
                            options=options,
                            stream=True,
                            keep_alive=self.keep_alive
                        )
            
            res = {"reasoning": "", "response": ""}
            phase = ""
            for chunk in response:
                if hasattr(chunk.message, 'thinking') and chunk.message.thinking:
                    if phase != "reasoning":
                        print("\n--- Reasoning ---")
                        phase = "reasoning"

                    content_chunk = getattr(getattr(chunk, 'message', {}), 'thinking', '')
                    res["reasoning"] += content_chunk
                else:
                    if phase != "response":
                        print("\n--- Response ---")
                        phase = "response"
                    content_chunk = getattr(getattr(chunk, 'message', {}), 'content', '')
                    res["response"] += content_chunk

                print(content_chunk, end='', flush=True)

                if chunk.done_reason == "length":
                    warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)
            print('\n')

        else:
            response = self.client.chat(
                                model=self.model_name, 
                                messages=processed_messages, 
                                options=options,
                                stream=False,
                                keep_alive=self.keep_alive
                            )
            res = {"reasoning": getattr(getattr(response, 'message', {}), 'thinking', ''),
                   "response": getattr(getattr(response, 'message', {}), 'content', '')}
        
            if response.done_reason == "length":
                warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "images" in messages:
                    messages["images"] = ["[image]" for _ in messages["images"]]

            processed_messages.append({"role": "assistant", 
                                    "content": res_dict.get("response", ""), 
                                    "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
        

    async def chat_async(self, messages:List[Dict[str,str]], messages_logger:MessagesLogger=None) -> Dict[str,str]:
        """
        Async version of chat method. Streaming is not supported.
        """
        processed_messages = self.config.preprocess_messages(messages)

        response = await self.async_client.chat(
                            model=self.model_name, 
                            messages=processed_messages, 
                            options={'num_ctx': self.num_ctx, **self.formatted_params},
                            stream=False,
                            keep_alive=self.keep_alive
                        )
        
        res = {"reasoning": getattr(getattr(response, 'message', {}), 'thinking', ''),
               "response": getattr(getattr(response, 'message', {}), 'content', '')}
        
        if response.done_reason == "length":
            warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)
        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "images" in messages:
                    messages["images"] = ["[image]" for _ in messages["images"]]

            processed_messages.append({"role": "assistant", 
                                        "content": res_dict.get("response", ""), 
                                        "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
    
    def get_ocr_messages(self, system_prompt:str, user_prompt:str, image:Image.Image, few_shot_examples:List[FewShotExample]=None) -> List[Dict[str,str]]:
        """
        This method inputs an image and returns the correesponding chat messages for the inference engine.

        Parameters:
        ----------
        system_prompt : str
            the system prompt.
        user_prompt : str
            the user prompt.
        image : Image.Image
            the image for OCR.
        few_shot_examples : List[FewShotExample], Optional
            list of few-shot examples. 
        """
        base64_str = image_to_base64(image)
        output_messages = []
        # system message
        system_message = {"role": "system", "content": system_prompt}
        output_messages.append(system_message)

        # few-shot examples
        if few_shot_examples is not None:
            for example in few_shot_examples:
                if not isinstance(example, FewShotExample):
                    raise ValueError("Few-shot example must be a FewShotExample object.")
                
                example_image_b64 = image_to_base64(example.image)
                example_user_message = {"role": "user", "content": user_prompt, "images": [example_image_b64]}
                example_agent_message = {"role": "assistant", "content": example.text}
                output_messages.append(example_user_message)
                output_messages.append(example_agent_message)

        # user message
        user_message = {"role": "user", "content": user_prompt, "images": [base64_str]}
        output_messages.append(user_message)

        return output_messages


class OpenAICompatibleVLMEngine(VLMEngine):
    def __init__(self, model:str, api_key:str, base_url:str, config:VLMConfig=None, **kwrs):
        """
        General OpenAI-compatible server inference engine.
        https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

        For parameters and documentation, refer to https://platform.openai.com/docs/api-reference/introduction

        Parameters:
        ----------
        model_name : str
            model name as shown in the vLLM server
        api_key : str
            the API key for the vLLM server.
        base_url : str
            the base url for the vLLM server. 
        config : LLMConfig
            the LLM configuration.
        """
        if importlib.util.find_spec("openai") is None:
            raise ImportError("OpenAI Python API library not found. Please install OpanAI (```pip install openai```).")
        
        from openai import OpenAI, AsyncOpenAI
        from openai.types.chat import ChatCompletionChunk
        self.ChatCompletionChunk = ChatCompletionChunk
        super().__init__(config)
        self.client = OpenAI(api_key=api_key, base_url=base_url, **kwrs)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url, **kwrs)
        self.model = model
        self.config = config if config else BasicVLMConfig()
        self.formatted_params = self._format_config()

    def _format_config(self) -> Dict[str, Any]:
        """
        This method format the VLM configuration with the correct key for the inference engine. 
        """
        formatted_params = self.config.params.copy()
        if "max_new_tokens" in formatted_params:
            formatted_params["max_completion_tokens"] = formatted_params["max_new_tokens"]
            formatted_params.pop("max_new_tokens")

        return formatted_params
    

    def _format_response(self, response: Any) -> Dict[str, str]:
        """
        This method format the response from OpenAI API to a dict with keys "type" and "data".

        Parameters:
        ----------
        response : Any
            the response from OpenAI-compatible API. Could be a dict, generator, or object.
        """
        if isinstance(response, self.ChatCompletionChunk):
            chunk_text = getattr(response.choices[0].delta, "content", "")
            if chunk_text is None:
                chunk_text = ""
            return {"type": "response", "data": chunk_text}

        return {"response": getattr(response.choices[0].message, "content", "")}

    def chat(self, messages:List[Dict[str,str]], verbose:bool=False, stream:bool=False, 
             messages_logger:MessagesLogger=None) -> Union[Dict[str, str], Generator[Dict[str, str], None, None]]:
        """
        This method inputs chat messages and outputs LLM generated text.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        verbose : bool, Optional
            if True, VLM generated text will be printed in terminal in real-time.
        stream : bool, Optional
            if True, returns a generator that yields the output in real-time.
        messages_logger : MessagesLogger, Optional
            the message logger that logs the chat messages.

        Returns:
        -------
        response : Union[Dict[str,str], Generator[Dict[str, str], None, None]]
            a dict {"reasoning": <reasoning>, "response": <response>} or Generator {"type": <reasoning or response>, "data": <content>}
        """
        processed_messages = self.config.preprocess_messages(messages)

        if stream:
            def _stream_generator():
                response_stream = self.client.chat.completions.create(
                                        model=self.model,
                                        messages=processed_messages,
                                        stream=True,
                                        **self.formatted_params
                                    )
                res_text = ""
                for chunk in response_stream:
                    if len(chunk.choices) > 0:
                        chunk_dict = self._format_response(chunk)
                        yield chunk_dict

                        res_text += chunk_dict["data"]
                        if chunk.choices[0].finish_reason == "length":
                            warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

                # Postprocess response
                res_dict = self.config.postprocess_response(res_text)
                # Write to messages log
                if messages_logger:
                    # replace images content with a placeholder "[image]" to save space
                    for messages in processed_messages:
                        if "content" in messages and isinstance(messages["content"], list):
                            for content in messages["content"]:
                                if isinstance(content, dict) and content.get("type") == "image_url":
                                    content["image_url"]["url"] = "[image]"

                    processed_messages.append({"role": "assistant",
                                                "content": res_dict.get("response", ""),
                                                "reasoning": res_dict.get("reasoning", "")})
                    messages_logger.log_messages(processed_messages)

            return self.config.postprocess_response(_stream_generator())

        elif verbose:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                stream=True,
                **self.formatted_params
            )
            res = {"reasoning": "", "response": ""}
            phase = ""
            for chunk in response:
                if len(chunk.choices) > 0:
                    chunk_dict = self._format_response(chunk)
                    chunk_text = chunk_dict["data"]
                    res[chunk_dict["type"]] += chunk_text
                    if phase != chunk_dict["type"] and chunk_text != "":
                        print(f"\n--- {chunk_dict['type'].capitalize()} ---")
                        phase = chunk_dict["type"]

                    print(chunk_text, end="", flush=True)
                    if chunk.choices[0].finish_reason == "length":
                        warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

            print('\n')

        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                stream=False,
                **self.formatted_params
            )
            res = self._format_response(response)

            if response.choices[0].finish_reason == "length":
                warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)
            
        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "content" in messages and isinstance(messages["content"], list):
                    for content in messages["content"]:
                        if isinstance(content, dict) and content.get("type") == "image_url":
                            content["image_url"]["url"] = "[image]"

            processed_messages.append({"role": "assistant", 
                                    "content": res_dict.get("response", ""), 
                                    "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
    

    async def chat_async(self, messages:List[Dict[str,str]], messages_logger:MessagesLogger=None) -> Dict[str,str]:
        """
        Async version of chat method. Streaming is not supported.
        """
        processed_messages = self.config.preprocess_messages(messages)

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=processed_messages,
            stream=False,
            **self.formatted_params
        )
        
        if response.choices[0].finish_reason == "length":
            warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

        res = self._format_response(response)

        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "content" in messages and isinstance(messages["content"], list):
                    for content in messages["content"]:
                        if isinstance(content, dict) and content.get("type") == "image_url":
                            content["image_url"]["url"] = "[image]"

            processed_messages.append({"role": "assistant", 
                                        "content": res_dict.get("response", ""), 
                                        "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
    
    def get_ocr_messages(self, system_prompt:str, user_prompt:str, image:Image.Image, format:str='png', 
                         detail:str="high", few_shot_examples:List[FewShotExample]=None) -> List[Dict[str,str]]:
        """
        This method inputs an image and returns the correesponding chat messages for the inference engine.

        Parameters:
        ----------
        system_prompt : str
            the system prompt.
        user_prompt : str
            the user prompt.
        image : Image.Image
            the image for OCR.
        format : str, Optional
            the image format. 
        detail : str, Optional
            the detail level of the image. Default is "high". 
        few_shot_examples : List[FewShotExample], Optional
            list of few-shot examples.
        """
        base64_str = image_to_base64(image)
        output_messages = []
        # system message
        system_message = {"role": "system", "content": system_prompt}
        output_messages.append(system_message)

        # few-shot examples
        if few_shot_examples is not None:
            for example in few_shot_examples:
                if not isinstance(example, FewShotExample):
                    raise ValueError("Few-shot example must be a FewShotExample object.")
                
                example_image_b64 = image_to_base64(example.image)
                example_user_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{format};base64,{example_image_b64}",
                                "detail": detail
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                }
                example_agent_message = {"role": "assistant", "content": example.text}
                output_messages.append(example_user_message)
                output_messages.append(example_agent_message)

        # user message
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{format};base64,{base64_str}",
                        "detail": detail
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }
        output_messages.append(user_message)
        return output_messages


class VLLMVLMEngine(OpenAICompatibleVLMEngine):
    def __init__(self, model:str, api_key:str="", base_url:str="http://localhost:8000/v1", config:VLMConfig=None, **kwrs):
        """
        vLLM OpenAI compatible server inference engine.
        https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

        For parameters and documentation, refer to https://platform.openai.com/docs/api-reference/introduction

        Parameters:
        ----------
        model_name : str
            model name as shown in the vLLM server
        api_key : str, Optional
            the API key for the vLLM server.
        base_url : str, Optional
            the base url for the vLLM server. 
        config : LLMConfig
            the LLM configuration.
        """
        super().__init__(model, api_key, base_url, config, **kwrs)


    def _format_response(self, response: Any) -> Dict[str, str]:
        """
        This method format the response from OpenAI API to a dict with keys "type" and "data".

        Parameters:
        ----------
        response : Any
            the response from OpenAI-compatible API. Could be a dict, generator, or object.
        """
        if isinstance(response, self.ChatCompletionChunk):
            if hasattr(response.choices[0].delta, "reasoning_content") and getattr(response.choices[0].delta, "reasoning_content") is not None:
                chunk_text = getattr(response.choices[0].delta, "reasoning_content", "")
                if chunk_text is None:
                    chunk_text = ""
                return {"type": "reasoning", "data": chunk_text}
            else:
                chunk_text = getattr(response.choices[0].delta, "content", "")
                if chunk_text is None:
                    chunk_text = ""
                return {"type": "response", "data": chunk_text}

        return {"reasoning": getattr(response.choices[0].message, "reasoning_content", ""),
                "response": getattr(response.choices[0].message, "content", "")}
        

class OpenRouterVLMEngine(OpenAICompatibleVLMEngine):
    def __init__(self, model:str, api_key:str=None, base_url:str="https://openrouter.ai/api/v1", config:VLMConfig=None, **kwrs):
        """
        OpenRouter OpenAI-compatible server inference engine.

        Parameters:
        ----------
        model_name : str
            model name as shown in the vLLM server
        api_key : str, Optional
            the API key for the vLLM server. If None, will use the key in os.environ['OPENROUTER_API_KEY'].
        base_url : str, Optional
            the base url for the vLLM server. 
        config : LLMConfig
            the LLM configuration.
        """
        self.api_key = api_key
        if self.api_key is None:
            self.api_key = os.getenv("OPENROUTER_API_KEY")
        super().__init__(model, self.api_key, base_url, config, **kwrs)

    def _format_response(self, response: Any) -> Dict[str, str]:
        """
        This method format the response from OpenAI API to a dict with keys "type" and "data".

        Parameters:
        ----------
        response : Any
            the response from OpenAI-compatible API. Could be a dict, generator, or object.
        """
        if isinstance(response, self.ChatCompletionChunk):
            if hasattr(response.choices[0].delta, "reasoning") and getattr(response.choices[0].delta, "reasoning") is not None:
                chunk_text = getattr(response.choices[0].delta, "reasoning", "")
                if chunk_text is None:
                    chunk_text = ""
                return {"type": "reasoning", "data": chunk_text}
            else:
                chunk_text = getattr(response.choices[0].delta, "content", "")
                if chunk_text is None:
                    chunk_text = ""
                return {"type": "response", "data": chunk_text}

        return {"reasoning": getattr(response.choices[0].message, "reasoning", ""),
                "response": getattr(response.choices[0].message, "content", "")}


class OpenAIVLMEngine(VLMEngine):
    def __init__(self, model:str, config:VLMConfig=None, **kwrs):
        """
        The OpenAI API inference engine. Supports OpenAI models and OpenAI compatible servers:
        - vLLM OpenAI compatible server (https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)

        For parameters and documentation, refer to https://platform.openai.com/docs/api-reference/introduction

        Parameters:
        ----------
        model_name : str
            model name as described in https://platform.openai.com/docs/models
        config : VLMConfig, Optional
            the VLM configuration. Must be a child class of VLMConfig.
        """
        if importlib.util.find_spec("openai") is None:
            raise ImportError("OpenAI Python API library not found. Please install OpanAI (```pip install openai```).")
        
        from openai import OpenAI, AsyncOpenAI
        self.client = OpenAI(**kwrs)
        self.async_client = AsyncOpenAI(**kwrs)
        self.model = model
        self.config = config if config else BasicVLMConfig()
        self.formatted_params = self._format_config()

    def _format_config(self) -> Dict[str, Any]:
        """
        This method format the LLM configuration with the correct key for the inference engine. 
        """
        formatted_params = self.config.params.copy()
        if "max_new_tokens" in formatted_params:
            formatted_params["max_completion_tokens"] = formatted_params["max_new_tokens"]
            formatted_params.pop("max_new_tokens")

        return formatted_params

    def chat(self, messages:List[Dict[str,str]], verbose:bool=False, stream:bool=False, messages_logger:MessagesLogger=None) -> Union[Dict[str, str], Generator[Dict[str, str], None, None]]:
        """
        This method inputs chat messages and outputs LLM generated text.

        Parameters:
        ----------
        messages : List[Dict[str,str]]
            a list of dict with role and content. role must be one of {"system", "user", "assistant"}
        verbose : bool, Optional
            if True, VLM generated text will be printed in terminal in real-time.
        stream : bool, Optional
            if True, returns a generator that yields the output in real-time.
        messages_logger : MessagesLogger, Optional
            the message logger that logs the chat messages.

        Returns:
        -------
        response : Union[Dict[str,str], Generator[Dict[str, str], None, None]]
            a dict {"reasoning": <reasoning>, "response": <response>} or Generator {"type": <reasoning or response>, "data": <content>}
        """
        processed_messages = self.config.preprocess_messages(messages)

        if stream:
            def _stream_generator():
                response_stream = self.client.chat.completions.create(
                                        model=self.model,
                                        messages=processed_messages,
                                        stream=True,
                                        **self.formatted_params
                                    )
                res_text = ""
                for chunk in response_stream:
                    if len(chunk.choices) > 0:
                        chunk_text = chunk.choices[0].delta.content
                        if chunk_text is not None:
                            res_text += chunk_text
                            yield chunk_text
                        if chunk.choices[0].finish_reason == "length":
                            warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

                # Postprocess response
                res_dict = self.config.postprocess_response(res_text)
                # Write to messages log
                if messages_logger:
                    # replace images content with a placeholder "[image]" to save space
                    for messages in processed_messages:
                        if "content" in messages and isinstance(messages["content"], list):
                            for content in messages["content"]:
                                if isinstance(content, dict) and content.get("type") == "image_url":
                                    content["image_url"]["url"] = "[image]"

                    processed_messages.append({"role": "assistant",
                                                "content": res_dict.get("response", ""),
                                                "reasoning": res_dict.get("reasoning", "")})
                    messages_logger.log_messages(processed_messages)

            return self.config.postprocess_response(_stream_generator())

        elif verbose:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                stream=True,
                **self.formatted_params
            )
            res = ''
            for chunk in response:
                if len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content is not None:
                        res += chunk.choices[0].delta.content
                        print(chunk.choices[0].delta.content, end="", flush=True)
                    if chunk.choices[0].finish_reason == "length":
                        warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

            print('\n')

        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                stream=False,
                **self.formatted_params
            )
            res = response.choices[0].message.content
            
        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "content" in messages and isinstance(messages["content"], list):
                    for content in messages["content"]:
                        if isinstance(content, dict) and content.get("type") == "image_url":
                            content["image_url"]["url"] = "[image]"

            processed_messages.append({"role": "assistant", 
                                    "content": res_dict.get("response", ""), 
                                    "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
    

    async def chat_async(self, messages:List[Dict[str,str]], messages_logger:MessagesLogger=None) -> Dict[str,str]:
        """
        Async version of chat method. Streaming is not supported.
        """
        processed_messages = self.config.preprocess_messages(messages)

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=processed_messages,
            stream=False,
            **self.formatted_params
        )
        
        if response.choices[0].finish_reason == "length":
            warnings.warn("Model stopped generating due to context length limit.", RuntimeWarning)

        res = response.choices[0].message.content
        # Postprocess response
        res_dict = self.config.postprocess_response(res)
        # Write to messages log
        if messages_logger:
            # replace images content with a placeholder "[image]" to save space
            for messages in processed_messages:
                if "content" in messages and isinstance(messages["content"], list):
                    for content in messages["content"]:
                        if isinstance(content, dict) and content.get("type") == "image_url":
                            content["image_url"]["url"] = "[image]"
                            
            processed_messages.append({"role": "assistant", 
                                    "content": res_dict.get("response", ""), 
                                    "reasoning": res_dict.get("reasoning", "")})
            messages_logger.log_messages(processed_messages)

        return res_dict
    
    def get_ocr_messages(self, system_prompt:str, user_prompt:str, image:Image.Image, format:str='png', 
                         detail:str="high", few_shot_examples:List[FewShotExample]=None) -> List[Dict[str,str]]:
        """
        This method inputs an image and returns the correesponding chat messages for the inference engine.

        Parameters:
        ----------
        system_prompt : str
            the system prompt.
        user_prompt : str
            the user prompt.
        image : Image.Image
            the image for OCR.
        format : str, Optional
            the image format. 
        detail : str, Optional
            the detail level of the image. Default is "high". 
        few_shot_examples : List[FewShotExample], Optional
            list of few-shot examples. Each example is a dict with keys "image" (PIL.Image.Image) and "text" (str).
        """
        base64_str = image_to_base64(image)
        output_messages = []
        # system message
        system_message = {"role": "system", "content": system_prompt}
        output_messages.append(system_message)

        # few-shot examples
        if few_shot_examples is not None:
            for example in few_shot_examples:
                if not isinstance(example, FewShotExample):
                    raise ValueError("Few-shot example must be a FewShotExample object.")
                
                example_image_b64 = image_to_base64(example.image)
                example_user_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{format};base64,{example_image_b64}",
                                "detail": detail
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                }
                example_agent_message = {"role": "assistant", "content": example.text}
                output_messages.append(example_user_message)
                output_messages.append(example_agent_message)

        # user message
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{format};base64,{base64_str}",
                        "detail": detail
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }
        output_messages.append(user_message)
        return output_messages


class AzureOpenAIVLMEngine(OpenAIVLMEngine):
    def __init__(self, model:str, api_version:str, config:VLMConfig=None, **kwrs):
        """
        The Azure OpenAI API inference engine.
        For parameters and documentation, refer to 
        - https://azure.microsoft.com/en-us/products/ai-services/openai-service
        - https://learn.microsoft.com/en-us/azure/ai-services/openai/quickstart
        
        Parameters:
        ----------
        model : str
            model name as described in https://platform.openai.com/docs/models
        api_version : str
            the Azure OpenAI API version
        config : LLMConfig
            the LLM configuration.
        """
        if importlib.util.find_spec("openai") is None:
            raise ImportError("OpenAI Python API library not found. Please install OpanAI (```pip install openai```).")
        
        from openai import AzureOpenAI, AsyncAzureOpenAI
        self.model = model
        self.api_version = api_version
        self.client = AzureOpenAI(api_version=self.api_version, 
                                  **kwrs)
        self.async_client = AsyncAzureOpenAI(api_version=self.api_version, 
                                             **kwrs)
        self.config = config if config else BasicVLMConfig()
        self.formatted_params = self._format_config()
