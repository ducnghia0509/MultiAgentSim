import requests
from bs4 import BeautifulSoup
import os
import datetime
from core.utils import clean_text 
import time
from newsapi import NewsApiClient
from dotenv import load_dotenv
import asyncio

# Load API key from .env
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

if not NEWS_API_KEY:
    print("Warning: NEWS_API_KEY not found. NewsAPI functionality will be limited.")

# Cập nhật cấu hình NewsAPI với các truy vấn mới
AGENT_NEWSAPI_CONFIG = {
    "general_knowledge": [
        {"query": "global economy OR geopolitics OR major world events", "language": "en", "page_size": 50},
        {"query": "Donald Trump OR US president OR 2024 US election", "language": "en", "page_size": 20},
        {"query": "Hamas-Israel conflict OR Ukraine war OR Sudan war", "language": "en", "page_size": 20},
        {"query": "Paris Olympics 2024 OR space race OR AI summit 2025", "language": "en", "page_size": 20},
        {"query": "Type 5 diabetes OR climate change OR COP30", "language": "en", "page_size": 20},
        {"query": "Donald Trump AND Elon Musk OR government efficiency", "language": "en", "page_size": 20},
        {"category": "technology", "country": "us", "page_size": 10},
    ],
    "usa_nation": [
        {"country": "us", "category": "general", "page_size": 10},
        {"query": "US politics OR White House OR US economy", "language": "en", "page_size": 10},
    ],
    "china_nation": [
        {"country": "cn", "category": "general", "page_size": 10},
        {"query": "China economy OR Beijing policy OR Xi Jinping", "language": "en", "page_size": 10},
    ],
    "germany_nation": [
        {"country": "de", "category": "general", "page_size": 10},
        {"query": "Germany politics OR Olaf Scholz", "language": "en", "page_size": 10},
    ],
    "russia_nation": [
        {"country": "ru", "category": "general", "page_size": 10},
        {"query": "Russia foreign policy OR Kremlin OR Putin", "language": "en", "page_size": 10},
    ],
    "india_nation": [
        {"country": "in", "category": "general", "page_size": 10},
        {"query": "India economy OR Narendra Modi", "language": "en", "page_size": 10},
    ],
    "donald_trump_persona": [
        {"query": "\"Donald Trump\" OR Trump campaign OR Mar-a-Lago", "language": "en", "page_size": 10},
        {"query": "Donald Trump AND Elon Musk OR DOGE OR government efficiency", "language": "en", "page_size": 10},
    ],
    "vladimir_putin_persona": [
        {"query": "\"Vladimir Putin\" OR Kremlin policy", "language": "en", "page_size": 10},
    ]
}

async def fetch_news_from_newsapi(query: str = None, sources: str = None, category: str = None, language: str = 'en', country: str = None, page_size: int = 20):
    if not NEWS_API_KEY:
        print("NEWS_API_KEY is not configured. Cannot fetch news from NewsAPI.")
        return []
    newsapi = NewsApiClient(api_key=NEWS_API_KEY)
    articles_data = []
    try:
        print(f"Fetching news from NewsAPI with query='{query}', sources='{sources}', category='{category}', country='{country}', page_size={page_size}")
        if query:
            api_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: newsapi.get_everything(q=query, sources=sources, language=language, sort_by='publishedAt', page_size=page_size, from_param="2025-01-01")
            )
        elif sources or category or country:
            api_response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: newsapi.get_top_headlines(q=query, sources=sources, category=category, language=language, country=country, page_size=page_size)
            )
        else:
            print("NewsAPI: Must provide query, sources, category, or country.")
            return []

        if api_response['status'] == 'ok':
            for article_newsapi in api_response['articles']:
                content_for_rag = article_newsapi.get('content', '') or article_newsapi.get('description', '')
                if content_for_rag and "[+" in content_for_rag and " chars]" in content_for_rag:
                    content_for_rag = content_for_rag.split("[+")[0].strip()
                articles_data.append({
                    "title": clean_text(article_newsapi['title'] or ""),
                    "link": article_newsapi['url'],
                    "content": clean_text(content_for_rag or ""),
                    "source": article_newsapi['source']['name'] if article_newsapi.get('source') else "NewsAPI",
                    "published_at": article_newsapi.get('publishedAt'),
                    "fetch_date": datetime.date.today().strftime("%Y-%m-%d")
                })
            print(f"NewsAPI fetched {len(articles_data)} articles.")
        else:
            print(f"Error from NewsAPI: {api_response.get('code')} - {api_response.get('message')}")
    except Exception as e:
        print(f"An error occurred while fetching from NewsAPI: {e}")
        import traceback
        traceback.print_exc()
    return articles_data

def save_crawled_data(articles_data: list, raw_data_dir_base: str, agent_id_context: str = None):
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    for i, article in enumerate(articles_data):
        content_to_save = f"Title: {article['title']}\nSource: {article['source']}\nLink: {article['link']}\nPublished At: {article.get('published_at', 'N/A')}\nFetch Date: {article.get('fetch_date', today_str)}\n\n{article['content']}\n\n--- FETCHED VIA NEWSAPI ON {today_str} ---"
        target_dir = os.path.join(raw_data_dir_base, agent_id_context if agent_id_context else "general_newsapi_feed")
        os.makedirs(target_dir, exist_ok=True)
        safe_title = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in article['title'][:50]).rstrip()
        filename = os.path.join(target_dir, f"{today_str}_{safe_title.replace(' ', '_')}_{i+1}.txt")
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            print(f"Saved news to: {filename}")
        except Exception as e:
            print(f"Error saving file {filename}: {e}")

def update_agents_knowledge_from_raw_data(agent_manager_instance, raw_data_dir_base: str):
    print("\n=== Updating agents' knowledge from crawled & saved data ===")
    if not os.path.exists(raw_data_dir_base):
        print(f"Raw data base directory not found: {raw_data_dir_base}. Skipping knowledge update.")
        return {"status": "failed", "articles_processed": 0, "last_updated": None}

    articles_processed = 0
    last_updated = None
    for agent_id_folder_name in os.listdir(raw_data_dir_base):
        agent_specific_raw_data_dir = os.path.join(raw_data_dir_base, agent_id_folder_name)
        if os.path.isdir(agent_specific_raw_data_dir):
            agent_instance = agent_manager_instance.get_agent(agent_id_folder_name)
            if agent_instance:
                print(f"Processing data for agent '{agent_instance.persona.get('full_name', agent_id_folder_name)}' from {agent_specific_raw_data_dir}")
                files_processed_count = 0
                for news_file_name in os.listdir(agent_specific_raw_data_dir):
                    if news_file_name.endswith(".txt"):
                        file_path = os.path.join(agent_specific_raw_data_dir, news_file_name)
                        print(f"  Adding knowledge from: {news_file_name}")
                        try:
                            agent_instance.add_knowledge_from_file(file_path)
                            files_processed_count += 1
                            articles_processed += 1
                            last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            print(f"    Error processing file {file_path} for agent {agent_id_folder_name}: {e}")
                if files_processed_count == 0:
                    print(f"  No new .txt files found to process for {agent_id_folder_name} in this run.")
            else:
                print(f"Warning: Found data folder '{agent_id_folder_name}' but no corresponding agent loaded in AgentManager.")
    print("=== Knowledge update process finished. ===")
    return {"status": "success", "articles_processed": articles_processed, "last_updated": last_updated}

async def _perform_data_update_logic(manager_instance, raw_data_dir_base_path, agent_news_config_dict):
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Performing data update logic...")
    any_new_articles_fetched_overall = False
    update_status = {"status": "failed", "articles_processed": 0, "last_updated": None}

    for agent_id_config, search_configs_list in agent_news_config_dict.items():
        if agent_id_config not in manager_instance.agents:
            print(f"Skipping news fetch for agent_id '{agent_id_config}' from config as it's not loaded in AgentManager.")
            continue

        agent_display_name = manager_instance.agents[agent_id_config].persona.get('full_name', agent_id_config)
        print(f"\nFetching news for agent: {agent_display_name} ({agent_id_config})")
        
        agent_specific_articles_this_run = []
        for config_item in search_configs_list:
            query = config_item.get('query')
            sources = config_item.get('sources')
            category = config_item.get('category')
            country = config_item.get('country')
            page_size = config_item.get('page_size', 10)
            language = config_item.get('language', 'en')

            if not (query or sources or category or country):
                print(f"Skipping invalid NewsAPI config for {agent_id_config}: {config_item}")
                continue
            
            fetched_articles_for_this_config = await fetch_news_from_newsapi(
                query=query, sources=sources, category=category, language=language, country=country, page_size=page_size
            )
            if fetched_articles_for_this_config:
                agent_specific_articles_this_run.extend(fetched_articles_for_this_config)
                print(f"Fetched {len(fetched_articles_for_this_config)} articles for {agent_id_config} with config: {config_item}")
            await asyncio.sleep(0.5)

        if agent_specific_articles_this_run:
            print(f"Saving {len(agent_specific_articles_this_run)} articles for {agent_id_config}...")
            save_crawled_data(agent_specific_articles_this_run, raw_data_dir_base_path, agent_id_context=agent_id_config)
            any_new_articles_fetched_overall = True
        else:
            print(f"No new articles fetched for {agent_id_config} in this run.")

    if any_new_articles_fetched_overall:
        print("\nUpdating all agent knowledge bases from newly saved files...")
        update_status = update_agents_knowledge_from_raw_data(manager_instance, raw_data_dir_base_path)
        print("Knowledge bases updated.")
    else:
        print("No new articles were fetched overall in this run to update knowledge bases.")
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Data update logic finished.\n")
    return update_status

def trigger_data_update(manager_instance, raw_data_dir_base_path, agent_news_config_dict_param):
    print(f"Triggering data update with manager: {type(manager_instance)}, raw_dir: {raw_data_dir_base_path}")
    return asyncio.run(_perform_data_update_logic(manager_instance, raw_data_dir_base_path, agent_news_config_dict_param))