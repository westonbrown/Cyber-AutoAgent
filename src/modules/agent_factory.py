#!/usr/bin/env python3

import os
import logging
import warnings
from datetime import datetime
from typing import Optional, List

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands_tools import shell, file_write, editor, load_tool
from mem0 import Memory

from . import memory_tools
from .memory_tools import memory_store, memory_retrieve, memory_list
from .system_prompts import get_system_prompt
from .agent_handlers import ReasoningHandler
from .utils import Colors

warnings.filterwarnings('ignore', category=DeprecationWarning)

def create_agent(target: str, objective: str, max_steps: int = 100, available_tools: Optional[List[str]] = None, 
                op_id: Optional[str] = None, model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
                region_name: str = "us-east-1"):
    """Create autonomous agent"""
    
    logger = logging.getLogger('CyberAutoAgent')
    logger.debug("Creating agent for target: %s, objective: %s", target, objective)
    
    # Use provided operation_id or generate new one
    if not op_id:
        operation_id = f"OP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    else:
        operation_id = op_id
    
    # Set AWS region
    os.environ["AWS_REGION"] = region_name
    
    config = {
        "llm": {
            "provider": "aws_bedrock",
            "config": {
                "model": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "temperature": 0.1,
                "max_tokens": 1024,
                "top_p": 0.9
            }
        },
        "embedder": {
            "provider": "aws_bedrock",
            "config": {
                "model": "amazon.titan-embed-text-v2:0"
            }
        },
        "vector_store": {
            "provider": "faiss",
            "config": {
                "embedding_model_dims": 1024,
                "path": f"./evidence_{operation_id}"
            }
        },
        "version": "v1.1"
    }
    
    # Initialize mem0 with configuration and set it in the memory_tools module
    memory_tools.mem0_instance = Memory.from_config(config)
    memory_tools.operation_id = operation_id
        
    print("%s[+] Memory system initialized with AWS Bedrock & FAISS %s" % (Colors.GREEN, Colors.RESET))
    
    tools_context = ""
    if available_tools:
        tools_context = f"""
## ENVIRONMENTAL CONTEXT

Professional tools discovered in your environment:
{', '.join(available_tools)}

Leverage these tools directly via shell. 
"""
    
    # Get system prompt
    system_prompt = get_system_prompt(target, objective, max_steps, operation_id, tools_context)
    
    # Create callback handler
    callback_handler = ReasoningHandler(max_steps=max_steps)
    
    # Configure model
    logger.debug("Configuring BedrockModel")
    model = BedrockModel(
        model_id=model_id,
        region_name=region_name,
        temperature=0.95, 
        max_tokens=4096,
        top_p=0.95
    )
    
    logger.debug("Creating autonomous agent")
    agent = Agent(
        model=model,
        tools=[shell, file_write, editor, load_tool, memory_store, memory_retrieve, memory_list],
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=120),
        load_tools_from_directory=True,  
        max_parallel_tools=8  
    )
    
    logger.debug("Agent initialized successfully")
    return agent, callback_handler
