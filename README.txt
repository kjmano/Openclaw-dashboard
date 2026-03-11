Dashboard LLM Usage - V3

Files:
- index.html
- usage-data.json
- generate_usage_data.py

Open locally in a browser, or publish on GitHub Pages.

This V3 includes:
- automatic collection from local OpenClaw session files
- main session usage
- sub-agent view (auto-populates when sub-agents exist)
- separate input/output token cards
- cache hit visibility
- models and providers breakdown
- provider-reported cost aggregation when present in transcript usage
- APIs inventory
- charts for agent usage, input/output split, models, providers, timeline, and API status

Refresh data:
- cd /root/.openclaw/workspace/dashboard-llm-usage
- python3 generate_usage_data.py

Next improvement path:
- add filtering by date / session / provider in the UI
- add automatic publish pipeline to GitHub Pages
- optionally upload backup copy to Google Drive via gog drive upload
