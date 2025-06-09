# Multi-Agent Interaction Platform

## Overview

The Multi-Agent Interaction Platform is a Python-based web application built with Streamlit, designed to simulate interactions between AI agents representing real-world entities (e.g., nations, individuals). Agents are powered by persona-driven configurations and a knowledge base updated via NewsAPI, enabling realistic single-agent chats and multi-agent discussions. The platform supports strategic simulations, such as geopolitical or economic debates, with agents like Donald Trump and Elon Musk, reflecting their public and private stances as of June 2025.

Key features:
- **Single-Agent Chat**: Engage in conversations with individual agents, leveraging their personas and recent news.
- **Multi-Agent Discussion**: Observe simulated discussions among multiple agents on user-defined topics.
- **Dynamic Knowledge Updates**: Fetch and integrate news articles from NewsAPI to keep agent knowledge current.
- **Persona-Driven Behavior**: Agents respond with internal reasoning (`<suy_nghĩ>`) and official statements, parsed for nuanced interactions.
- **Streamlit Interface**: User-friendly UI with a single-tab design for mode selection and configuration.

## Commands
- source venv/Scripts/activate
- streamlit run app/streamlit_app.py 
- python main.py
