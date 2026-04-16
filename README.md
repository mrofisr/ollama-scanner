# Ollama Scanner

> [!IMPORTANT]  
> **Disclaimer:** This tool is for **educational purposes only**. The author is not responsible for any misuse. Always ensure you have permission and are following ethical guidelines and terms of service when scanning or accessing network resources.

A fully autonomous tool for discovering and benchmarking Ollama instances across specific regions. It leverages the Shodan API with parallel search patterns and multi-threaded testing to automatically identify accessible hosts, verify available models, and evaluate performance using random test prompts—all without user interaction.

## Usage as GitHub Action

You can call this scanner from any other repository using this composite action:

```yaml
- name: Run Ollama Scanner
  uses: mrofisr/ollama-scanner@main
  with:
    shodan-api-key: ${{ secrets.SHODAN_API_KEY }}
    countries: "ID,MY,SG" # Optional: Comma-separated country codes (default: SEA region)
```

### Alerting Channels
The scanner supports automatic reporting to Telegram, Discord, and Slack. Simply provide the following inputs in your workflow:

```yaml
- name: Run Ollama Scanner
  uses: mrofisr/ollama-scanner@main
  with:
    shodan-api-key: ${{ secrets.SHODAN_API_KEY }}
    countries: "ID,MY,SG"
    telegram-bot-token: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    telegram-chat-id: ${{ secrets.TELEGRAM_CHAT_ID }}
    discord-webhook-url: ${{ secrets.DISCORD_WEBHOOK_URL }}
    slack-webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Local Development

If you'd like to run the scanner on your local machine:

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended)

### Installation
```bash
git clone https://github.com/mrofisr/ollama-scanner.git
cd ollama-scanner
uv sync
```

### Running the Scanner
You can run the script directly. It will look for environment variables for configuration.

```bash
export SHODAN_API_KEY='your_key'
export COUNTRIES='ID,MY,SG' # Optional: Comma-separated country codes

# Optional: Notification settings
# export TELEGRAM_BOT_TOKEN='...'
# export TELEGRAM_CHAT_ID='...'
# export DISCORD_WEBHOOK_URL='...'
# export SLACK_WEBHOOK_URL='...'

uv run python main.py
```

## Data Persistence (SQLite)
The scanner now uses a SQLite database (`ollama_nodes.db`) to track discovered hosts. To avoid redundant testing, it will skip hosts that have already been successfully scanned in the last 24 hours.

- **Storage**: The database is persisted across GitHub runs using `actions/cache`.
- **Artifacts**: At the end of every run, the updated database is uploaded as a GitHub Artifact (`ollama-scanner-db`) for easy inspection.

---
[License](LICENSE) | [Project Config](pyproject.toml) | [GitHub Action](action.yml)