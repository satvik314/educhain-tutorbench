from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

proprietary_models = ['openai/gpt-5', 'anthropic/claude-sonnet-4', 'google/gemini-2.5-pro' ]

open_source_models = ['deepseek/deepseek-v3.1-terminus', 'moonshotai/kimi-k2-0905']

model_list = proprietary_models + open_source_models

api_key = os.getenv("OPENROUTER_API_KEY")

import asyncio
from concurrent.futures import ThreadPoolExecutor

def get_responses_from_models(model_list, prompt, api_key = api_key):
    """
    Get responses from multiple models for a given prompt concurrently.
    
    Args:
        model_list: List of model names to query
        prompt: The prompt to send to all models
        api_key: API key for OpenRouter
    
    Returns:
        Dictionary with model names as keys and responses as values
    """
    def query_single_model(model_name):
        try:
            model = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                # headers={
                #     "HTTP-Referer": "https://github.com/satvik314/educhain-tutorbench",  # Optional: for rankings
                #     "X-Title": "Educhain TutorBench"  # Optional: show in rankings
                # }
            )
            
            response = model.invoke(prompt)
            return model_name, response
            
        except Exception as e:
            return model_name, f"Error: {str(e)}"
    
    responses = {}
    
    # Use ThreadPoolExecutor to make all API calls concurrently
    with ThreadPoolExecutor(max_workers=len(model_list)) as executor:
        future_to_model = {executor.submit(query_single_model, model_name): model_name 
                          for model_name in model_list}
        
        for future in future_to_model:
            model_name, response = future.result()
            responses[model_name] = response
    
    return responses



