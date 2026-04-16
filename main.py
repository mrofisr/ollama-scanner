import time
import ollama
import os
import shodan
import threading
import random
import requests
import sqlite3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Lock for synchronized printing in parallel mode
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def get_random_prompt() -> str:
    prompts = [
        "Explain quantum entanglement like I'm five.",
        "Write a short poem about a cat in space.",
        "What are the benefits of open-source software?",
        "Tell me a joke about robots.",
        "How do I make a perfect cup of coffee?",
        "Translate 'Hello, how are you?' into French, Spanish, and German.",
        "Summarize the history of the internet in three sentences.",
        "What is the best way to learn a new programming language?",
        "Explain the importance of cybersecurity in one paragraph.",
        "Write a one-sentence horror story."
    ]
    return random.choice(prompts)

# DB Logic
DB_PATH = "ollama_nodes.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                host TEXT PRIMARY KEY,
                last_seen TIMESTAMP,
                models_count INTEGER,
                models_list TEXT
            )
        """)

def filter_new_hosts(hosts: list) -> list:
    """Filter out hosts seen in the last 24 hours."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor = conn.execute("SELECT host FROM nodes WHERE last_seen > ?", (yesterday,))
        seen_hosts = {row[0] for row in cursor.fetchall()}
    
    new_hosts = [h for h in hosts if h not in seen_hosts]
    safe_print(f"🧹 Filtered {len(hosts) - len(new_hosts)} recently scanned hosts.")
    return new_hosts

def save_node_result(host: str, models: list):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO nodes (host, last_seen, models_count, models_list)
            VALUES (?, ?, ?, ?)
        """, (host, datetime.now().isoformat(), len(models), ",".join(models)))

def send_notifications(summary_text: str):
    """Send summary to Telegram, Discord, and Slack if configured."""
    # Telegram
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        try:
            requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", 
                          json={"chat_id": tg_chat_id, "text": f"🚀 *Ollama Scanned*\n\n{summary_text}", "parse_mode": "Markdown"})
            safe_print("📡 Notification sent to Telegram.")
        except Exception as e:
            safe_print(f"❌ Failed to send Telegram: {e}")

    # Discord
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_url:
        try:
            requests.post(discord_url, json={"content": f"🚀 **Ollama Scanned**\n\n{summary_text}"})
            safe_print("📡 Notification sent to Discord.")
        except Exception as e:
            safe_print(f"❌ Failed to send Discord: {e}")

    # Slack
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_url:
        try:
            requests.post(slack_url, json={"text": f"🚀 *Ollama Scanned*\n\n{summary_text}"})
            safe_print("📡 Notification sent to Slack.")
        except Exception as e:
            safe_print(f"❌ Failed to send Slack: {e}")

def get_ollama_hosts(api_key: str) -> list[str]:
    """
    Search Shodan for Ollama instances and return a list of host URLs.
    Uses 'map' to execute multiple queries as requested.
    """
    if not api_key:
        print("❌ Shodan API key is missing.")
        return []

    try:
        api = shodan.Shodan(api_key)
        countries_env = os.getenv("COUNTRIES", "").strip()
        base_queries = ["product:ollama", "port:11434"]
        
        if countries_env:
            countries = [c.strip() for c in countries_env.split(",") if c.strip()]
            queries = [f"{q} country:{c}" for q in base_queries for c in countries]
            safe_print(f"🔍 Searching Shodan for Ollama instances in: {', '.join(countries)}...")
        else:
            queries = base_queries
            safe_print("🔍 Searching Shodan globally for Ollama instances...")

        # Use ThreadPoolExecutor to run searches in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            search_results = list(executor.map(api.search, queries))
        
        hosts = set()
        for result in search_results:
            for match in result.get('matches', []):
                ip = match.get('ip_str')
                port = match.get('port')
                if ip and port:
                    hosts.add(f"http://{ip}:{port}")
        
        return list(hosts)
    except shodan.APIError as e:
        print(f"❌ Shodan API Error: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return []

def get_all_models(client: ollama.Client) -> list[str]:
    models = client.list()
    return [model.model for model in models.models]

def test_model(client: ollama.Client, model: str, prompt: str) -> dict:
    try:
        start = time.perf_counter()
        response = client.generate(model=model, prompt=prompt)
        elapsed = time.perf_counter() - start

        result = response.response.strip()
        is_gibberish = len(result.split()) > 5 and all(
            any(c.isdigit() for c in word) for word in result.split()[:5]
        )
        status = "⚠️  GIBBERISH" if is_gibberish else "✅ OK"
        return {"status": status, "response": result[:200], "elapsed": elapsed}
    except Exception as e:
        return {"status": "❌ ERROR", "response": str(e), "elapsed": 0.0}

def process_host(host: str, prompt: str):
    safe_print(f"\n" + "=" * 60)
    safe_print(f"🌐 Testing Host: {host}")
    safe_print("=" * 60)
    
    client = ollama.Client(host=host)
    try:
        models = get_all_models(client)
    except Exception as e:
        safe_print(f"❌ [{host}] Failed to connect: {e}")
        return

    if not models:
        safe_print(f"❌ [{host}] No models found.")
        return

    safe_print(f"✅ [{host}] Found {len(models)} model(s): {', '.join(models)}\n")
    save_node_result(host, models)
    
    timings: dict[str, float] = {}
    for model in models:
        result = test_model(client, model, prompt)
        timings[model] = result["elapsed"]
        out = [
            f"\n🤖 [{host}] Model : {model}",
            f"   Status          : {result['status']}",
            f"   Response        : {result['response']}",
            f"   Time taken      : {result['elapsed']:.2f}s",
            "-" * 60
        ]
        safe_print("\n".join(out))

    if timings:
        summary = [f"\n📊 [{host}] Response Time Summary"]
        sorted_timings = sorted(timings.items(), key=lambda x: x[1])
        for rank, (model, elapsed) in enumerate(sorted_timings, start=1):
            bar = "█" * int(elapsed * 5)
            summary.append(f"  {rank}. {model:<40} {elapsed:>6.2f}s  {bar}")
        safe_print("\n".join(summary))
        return {"host": host, "models": len(models), "model_names": models[:5], "status": "✅ Success"}
    
    return {"host": host, "models": 0, "model_names": [], "status": "❌ No Models"}

def generate_report(results: list, prompt: str) -> str:
    """Generate a beautiful Markdown report for notifications."""
    header = [
        "🔍 *Ollama Discovery Report*",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📝 *Test Prompt:* `{prompt}`",
        ""
    ]
    
    body = ["*Discovered Hosts:*"]
    success_count = 0
    total_models = 0
    
    # Filter for successful results
    valid_results = [r for r in results if r and r.get("models", 0) > 0]
    
    if not valid_results:
        body.append("∅ No accessible Ollama hosts found in this scan.")
    else:
        for r in valid_results:
            success_count += 1
            total_models += r['models']
            
            # Host line
            host_line = f"🌐 `{r['host']}`"
            body.append(host_line)
            
            # Model details line
            models_str = ", ".join(r['model_names'])
            if r['models'] > 5:
                models_str += "..."
            body.append(f"   └─ ✅ {r['models']} models (_{models_str}_)")

    footer = [
        "",
        "📈 *Scan Performance*",
        f"• *Successful Hosts:* {success_count}",
        f"• *Total Models:* {total_models}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "✨ _Automated by rofiabdur/ollama-scanner_"
    ]
    
    return "\n".join(header + body + footer)

if __name__ == "__main__":
    safe_print("--- Ollama Access Scanner & Tester (Automatic Mode) ---")
    
    api_key = os.getenv("SHODAN_API_KEY")
    hosts = []

    if api_key:
        hosts = get_ollama_hosts(api_key)
    else:
        safe_print("⚠️  SHODAN_API_KEY not found in environment. Defaulting to localhost.")
        hosts = ["http://localhost:11434"]

    if not hosts:
        safe_print("No hosts found or accessible.")
        exit()

    # Filter out recently seen hosts to prevent duplicates
    hosts = filter_new_hosts(hosts)
    
    if not hosts:
        safe_print("All found hosts were recently scanned. Nothing to do.")
        exit()

    safe_print(f"\nFound {len(hosts)} new host(s) to scan.")
    
    prompt = get_random_prompt()
    safe_print(f"🚀 Using random prompt: \"{prompt}\"")

    # Parallelize host testing
    run_results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        run_results = list(executor.map(lambda h: process_host(h, prompt), hosts))

    # Send notifications
    report_text = generate_report(run_results, prompt)
    send_notifications(report_text)

    safe_print("\n" + "=" * 60)
    safe_print("Automatic scan, test, and notification complete.")
