import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from modules.memory_tools import Mem0ServiceClient


def main():
    memory_config = {
        "embedder": {
            "provider": "aws_bedrock",
            "config": {
                "model": "amazon.titan-embed-text-v2:0",
                "aws_region": 'eu-central-1'
            }
        },
        "llm": {
            "provider": "aws_bedrock",
            "config": {
                "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "temperature": 0.1,
                "max_tokens": 2000,
                "aws_region": 'eu-central-1'
            }
        },
        "vector_store": {
            "config": {
                "path": "/Users/konradsemsch/Projects/private/Cyber-AutoAgent/memory"
            }
        }
    }    
    
    client = Mem0ServiceClient(memory_config)
    print(f"Client initialized: {client}")
    
    # Try to list memories
    try:
        memories = client.list_memories(user_id="cyber_agent")
        print(f"Found {len(memories)} memories")
        print(memories)
        # for i, memory in enumerate(memories, 1):
        #     print(f"\n{i}. Memory ID: {memory.get('id', 'Unknown')}")
        #     print(f"   Content: {memory.get('memory', 'No content')[:100]}...")
        #     print(f"   Created: {memory.get('created_at', 'Unknown')}")
        #     if memory.get('metadata'):
        #         print(f"   Metadata: {memory['metadata']}")
    except Exception as e:
        print(f"Error listing memories: {e}")


if __name__ == '__main__':
    main()