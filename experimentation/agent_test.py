from strands import Agent
from strands_tools import calculator
from strands.models import BedrockModel

# def custom_callback_handler(**kwargs):
#     # Process stream data
#     if "data" in kwargs:
#         print(f"MODEL OUTPUT: {kwargs['data']}")
#     elif "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
#         print(f"\nUSING TOOL: {kwargs['current_tool_use']['name']}")

# # Create an agent with custom callback handler
# agent = Agent(
#     model=BedrockModel(
#         model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
#         region_name="us-east-1",
#     ),
#     tools=[calculator],
#     callback_handler=custom_callback_handler
# )

# agent("Calculate 2+2")

# def debugger_callback_handler(**kwargs):
#     # Print the values in kwargs so that we can see everything
#     print(kwargs)

# agent = Agent(
#     model=BedrockModel(
#         model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
#         region_name="us-east-1",
#     ),
#     tools=[calculator],
#     callback_handler=debugger_callback_handler
# )

# agent("What is 922 + 5321")

def event_loop_tracker(**kwargs):
    # Track event loop lifecycle
    if kwargs.get("init_event_loop", False):
        print("🔄 Event loop initialized")
    elif kwargs.get("start_event_loop", False):
        print("▶️ Event loop cycle starting")
    elif kwargs.get("start", False):
        print("📝 New cycle started")
    elif "message" in kwargs:
        print(f"📬 New message created: {kwargs['message']['role']}")
    elif kwargs.get("complete", False):
        print("✅ Cycle completed")
    elif kwargs.get("force_stop", False):
        print(f"🛑 Event loop force-stopped: {kwargs.get('force_stop_reason', 'unknown reason')}")

    # Track tool usage
    if "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
        tool_name = kwargs["current_tool_use"]["name"]
        print(f"🔧 Using tool: {tool_name}")

    # Show only a snippet of text to keep output clean
    if "data" in kwargs:
        # Only show first 20 chars of each chunk for demo purposes
        data_snippet = kwargs["data"][:20] + ("..." if len(kwargs["data"]) > 20 else "")
        print(f"📟 Text: {data_snippet}")

# Create agent with event loop tracker
agent = Agent(
    model=BedrockModel(
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-1",
    ), 
    tools=[calculator],
    callback_handler=event_loop_tracker
)

# This will show the full event lifecycle in the console
agent("What is the capital of France and what is 42+7?")