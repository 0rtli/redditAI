# redditAI

Small Python CLI and local web app that researches Reddit posts and top comments for any topic. For broad business prompts, it can also switch into monetizable browser extension or lightweight SaaS opportunity analysis.

It includes a local browser UI where you can paste your OpenAI key, ask a question, choose an output language, and get a clean Reddit-backed report.

## Run the GUI

```bash
cd "/Users/tsardarov/Documents/New project/кк"
python3 app.py
```

Then open:

```text
http://127.0.0.1:8000
```

Notes:

- Your API key is sent only with the request you make from the page.
- The app does not save the key to disk.
- If you leave the key blank or turn off AI summary, the app uses the built-in fallback summary.
- Custom report language works through OpenAI analysis. The local fallback report stays in English.

## What it does

- Accepts a topic or niche you want researched.
- Searches Reddit globally or inside one subreddit.
- Pulls top posts plus top comments for extra context.
- Extracts pains, complaints, workarounds, and demand signals.
- Supports Discovery Mode for broad prompts like finding monetizable browser extension ideas.
- Scores each opportunity for pain severity, repeat usage, willingness to pay, ROI, extension fit, and competition risk.
- Ranks the strongest product opportunities for browser extensions and lightweight SaaS ideas.
- Uses OpenAI for a sharper founder-style report if `OPENAI_API_KEY` is available.
- Falls back to a local opportunity report if AI is disabled or unavailable.

## Quick start

```bash
cd "/Users/tsardarov/Documents/New project/кк"
export OPENAI_API_KEY="your_api_key_here"
python3 reddit_research_agent.py "linkedin lead generation workflow"
```

## Useful examples

Search all of Reddit:

```bash
python3 reddit_research_agent.py "chrome tab overload for researchers"
```

Search only one subreddit:

```bash
python3 reddit_research_agent.py "ecommerce price monitoring" --subreddit ecommerce
```

Skip OpenAI and use the built-in fallback summary:

```bash
python3 reddit_research_agent.py "freelancer invoice follow-up workflow" --no-ai
```

Save the collected research as JSON:

```bash
python3 reddit_research_agent.py "recruiter sourcing workflow" --save-json research.json
```

## Options

```bash
python3 reddit_research_agent.py --help
```

Main flags:

- `--subreddit`: limit research to one subreddit
- `--limit`: number of posts to inspect
- `--comments-per-post`: number of top comments per post
- `--time`: `hour`, `day`, `week`, `month`, `year`, or `all`
- `--sort`: `relevance`, `hot`, `top`, `new`, or `comments`
- `--model`: OpenAI model for summarization
- `--language`: desired output language for the AI-written report
- `--no-ai`: use local summarization only
- `--discovery`: force Discovery Mode for broad opportunity hunting
- `--save-json`: save raw research output

## Notes

- Reddit can rate-limit or block requests if hit too aggressively.
- The opportunity report is only as good as the sample of posts pulled in.
- Reddit is useful for pain discovery, but willingness to pay still needs validation outside Reddit.
