import random
import time
import uuid
from langchain_ollama.chat_models import ChatOllama

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import AnyMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langserve import add_routes
from langchain_core.runnables import RunnableLambda
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from paho.mqtt import client as mqtt_client

MQTT_SERVER = "test.mosquitto.org"
PORT = 1883
CLIENTID = f'solomon_client_{random.randint(0, 100)}'

SUBTOPIC_LED_CTL = "esp32-solomon/LED_CTL" # used to control the light
SUBTOPIC_DOOR_CTL = "esp32-solomon/DOOR_CTL" # used to control the door
SUBTOPIC_LED = "esp32-solomon/LED" # used to get the state of the light
SUBTOPIC_DOOR = "esp32-solomon/DOOR" # used to get the state of the door

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

BASE_URL = "http://localhost:11434"
MODEL = "llama3.1:8b"

deviceValues = {
    "light": -1,
    "door": -1
}

def on_disconnect(client, userdata, rc):
    print("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        print("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            print("Reconnected successfully!")
            return
        except Exception as err:
            print("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    print("Reconnect failed after %s attempts. Exiting...", reconnect_count)

def on_message(client, userdata, msg):
    print(f'Received `{msg.payload.decode()}` from `{msg.topic}` topic')
    if msg.topic == SUBTOPIC_LED:
        deviceValues["light"] = int(msg.payload.decode())
    elif msg.topic == SUBTOPIC_DOOR:
        deviceValues["door"] = int(msg.payload.decode())
        

def connect_mqtt():
    # For paho-mqtt 2.0.0, you need to add the properties parameter.
    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            print("Connected to MQTT Broker!")
            time.sleep(1)
            client.subscribe(SUBTOPIC_LED, qos=2)
            time.sleep(1)
            client.subscribe(SUBTOPIC_DOOR, qos=2)
            time.sleep(1)
            client.publish(SUBTOPIC_LED_CTL, "-1")
            time.sleep(1)
            client.publish(SUBTOPIC_DOOR_CTL, "-1")
        else:
            print("Failed to connect, return code %d\n", rc)

    # For paho-mqtt 2.0.0, you need to set callback_api_version.
    client = mqtt_client.Client(client_id=CLIENTID, callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2)

    # client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_SERVER, PORT, 60)
    client.on_disconnect = on_disconnect
    
    return client


client = connect_mqtt()
client.loop_start()

MAX_RETRY = 3 # number of times to retry if the device state is unknown
WAIT_PUBLISH = 2 # time to wait publishing

@tool
def deviceState(device: Literal["light", "door"], retry_count: int = 0) -> str:
    """
    Get the current state of the light or door in the room. If the state is unknown, retry a few times.

    Args:
        device (str): 'light' or 'door'.
        retry_count (int): Current retry attempt, default is 0.

    Returns:
        str: The final state of the device after the action.
    """
    print(f"Query device state: {device}, Retry count: {retry_count}")
    
    if not client.is_connected():
        return "Not connected to the server"
    
    if device not in deviceValues:
        return "Invalid device"
    
    if device == "light":
        state = deviceValues.get("light")
        if state == 1:
            return "light is on"
        elif state == 0:
            return "light is off"
        else:
            if retry_count < MAX_RETRY:
                if retry_count != -1:
                    client.publish(SUBTOPIC_LED_CTL, "-1")
                    time.sleep(WAIT_PUBLISH)
                return deviceState(device, retry_count + 1)
            return "Unknown light state after multiple retries, please check manually."
    
    elif device == "door":
        state = deviceValues.get("door")
        if state > 45:
            return "door is open"
        elif state == -1:
            if retry_count < MAX_RETRY:
                if retry_count != -1:
                    client.publish(SUBTOPIC_DOOR_CTL, "-1")
                    time.sleep(WAIT_PUBLISH)
                return deviceState(device, retry_count + 1)
            return "Unknown door state after multiple retries, please check manually."
        else:
            return "door is closed"
        
    return "Unknown error"

@tool
def deviceControl(device: Literal["light", "door"], action: Literal["on", "off", "open", "close"]) -> str:
    """
    Control the light or door in the room, then check the state.

    Args:
        device (str): 'light' or 'door'.
        action (str): 'on/off' for light, 'open/close' for door.

    Returns:
        str: The final state of the device after the action.
    """
    print(f"Control device: {device}, Action: {action}")
    
    if not client.is_connected():
        return "Not connected to the server"
    
    # Control the device
    if device == "light" and action in {"on", "off"}:
        deviceValues["light"] = -1
        if action == "on":
            client.publish(SUBTOPIC_LED_CTL, "1")
        elif action == "off":
            client.publish(SUBTOPIC_LED_CTL, "0")
        else:
            return f"Invalid action '{action}' for device '{device}'"
    elif device == "door" and action in {"open", "close"}:
        deviceValues["door"] = -1
        if action == "open":
            client.publish(SUBTOPIC_DOOR_CTL, "80")
        elif action == "close":
            client.publish(SUBTOPIC_DOOR_CTL, "2")
        else:
            return f"Invalid action '{action}' for device '{device}'"
    else:
        return f"Invalid action '{action}' for device '{device}'"
    
    # Wait briefly to ensure the command has been processed
    time.sleep(WAIT_PUBLISH)
    
    # Check and return the final state of the device
    return deviceState(device)


tools = [deviceState, deviceControl]
tool_node = ToolNode(tools)
model = ChatOllama(model=MODEL, temperature=0, base_url=BASE_URL).bind_tools(tools)

# Define the function that determines whether to continue or not
def should_continue(state: MessagesState) -> Literal["tools", END]:
    messages = state['messages']
    last_message = messages[-1]
    # If the LLM makes a tool call, then we route to the "tools" node
    if last_message.tool_calls:
        return "tools"
    # Otherwise, we stop (reply to the user)
    return END


# Define the function that calls the model
def call_model(state: MessagesState):
    messages = state['messages']
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


# Define a new graph
workflow = StateGraph(MessagesState)

# Define the two nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# Set the entrypoint as `agent`
# This means that this node is the first one called
workflow.add_edge(START, "agent")

# We now add a conditional edge
workflow.add_conditional_edges(
    # First, we define the start node. We use `agent`.
    # This means these are the edges taken after the `agent` node is called.
    "agent",
    # Next, we pass in the function that will determine which node is called next.
    should_continue,
)

# We now add a normal edge from `tools` to `agent`.
# This means that after `tools` is called, `agent` node is called next.
workflow.add_edge("tools", 'agent')

# Initialize memory to persist state between graph runs
# checkpointer = MemorySaver()

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable.
# Note that we're (optionally) passing the memory when compiling the graph
# flow = workflow.compile(checkpointer=checkpointer)
flow = workflow.compile()

# Initialize FastAPI app
app = FastAPI(
    title="Home Automation",
    version="0.1",
    description="LangGraph + LangServe",
)

def inp(input: str) -> dict:
    return {"messages": [HumanMessage(content=input)]}

def out(state: dict):
    return state["agent"]["messages"][-1].content

final_chain = RunnableLambda(inp) | flow | RunnableLambda(out)

add_routes(app, final_chain, path="/home")

@app.get("/")
async def read_root():
    return RedirectResponse(url="/home/playground")

thread_id = uuid.uuid4()
config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
    # while True:
    #     # Use the Runnable
    #     str = input("Enter a command: ")
    #     if str == "exit":
    #         break
    #     if len(str) == 0:
    #         continue
    #     final_state = flow.invoke(
    #         {"messages": [HumanMessage(content=str)]},
    #         config=config
    #     )
    #     print(final_state["messages"][-1].content)
    
# ---------------------------------------------
# final_state = flow.invoke(
#     {"messages": [HumanMessage(content="turn on the light and close the door in the room")]},
#     config=config
# )
# print(final_state["messages"][-1].content)
# time.sleep(10)
# final_state = flow.invoke(
#     {"messages": [HumanMessage(content="turn off the light and open the door in the room")]},
#     config=config
# )
# print(final_state["messages"][-1].content)
