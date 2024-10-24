# LLM Device Control with LangChain, LangGraph, LangServe, and Ollama using MQTT

This repository provides tools to control and query the state of devices (lights and doors) in a room using MQTT. These tools are integrated with LangChain, LangGraph, LangServe, and Ollama to facilitate more complex workflows, natural language processing, and distributed task management.

## Installation

Ensure that you have the necessary dependencies to run this system.

```bash
pip install -qU langgraph langchain-community langchain_ollama "langserve[server]" paho-mqtt
```

Make sure you have an MQTT broker set up and connected to the devices you want to control or query.

## Start the Server

You can start the server by running the following command:

```bash
python app.py
```

## License

This project is licensed under the MIT License.

## References

This project was inspired and built upon the following resources:

* [LangChain](https://www.langchain.com/)
* [Ollama](https://ollama.com/)
* [MQTT - The Standard for IoT Messaging](https://mqtt.org/)
* [Arduino](https://www.arduino.cc/)
* [Wokwi ESP32, STM32, Arduino Simulator](https://wokwi.com/)
