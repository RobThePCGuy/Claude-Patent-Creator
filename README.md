# Claude Patent Creator

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10-3.13](https://img.shields.io/badge/python-3.10--3.13-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Python%20SDK%202.x-purple.svg)](https://github.com/modelcontextprotocol/python-sdk)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-red.svg)](https://pytorch.org/)
[![Status](https://img.shields.io/badge/status-beta%20(WIP)-orange.svg)](#project-status)

**An AI-powered patent creation and analysis system for Claude Code.**

I built this because I needed to file a patent myself. I used AI to build the system, used the system to file the patent, and it worked. Now it's open source so anyone can use it. You do not need to be a lawyer or a programmer. If you can describe your idea in a chat window, you can use this.

In plain terms, this tool lets you:

- **Ask patent-rule questions in plain English.** "Do my claims have to be numbered?" "How long can the abstract be?" You get the actual rule, with a citation, in about a second. (Under the hood it searches the MPEP, the examiner's rulebook, plus the patent statutes and regulations.)
- **Find out whether your idea is actually new.** Search more than 100 million existing patents worldwide for anything close to your invention. This is called a *prior art* search, and it is the single most important step: it is how you learn whether a patent is even worth pursuing.
- **Get your draft checked before a human ever bills you an hour.** The tool reads your claims and application the way an examiner would and flags the mechanical problems: unclear wording, missing sections, an abstract that is too long. It also tells you which checks it *did not* run, so a clean report means what it says.
- **Make the drawings.** Patent-style diagrams and flowcharts from a description, no design software.
- **Go from "here is my idea" to a reviewable draft application.** A guided workflow takes your description (or even your source code), hunts for prior art, drafts claims and a specification, checks everything, and hands you a package a patent professional can review quickly, for US or European filing.

New to the vocabulary? Every term this page uses is explained in the [Glossary](#glossary) in plain English.

---

## Read this first: what this tool will and will not do

This tool is built for people who cannot afford a mistake, so it is honest to a fault. Know what you are getting:

- **It will tell you "no."** If the search finds your idea already exists, the tool's job is to show you the evidence and save you the filing fee, not to flatter you into spending money. A well-reasoned "this is not new, and here is why" is the tool working, not failing.
- **It never says "verified" loosely.** Every automated check reports what it ran *and what it skipped*. If a report looks clean, you can trust that the words mean exactly what they say.
- **It does not file anything for you.** You review, you decide, you file. The tool prepares; you commit.
- **It is not a lawyer and does not give legal advice.** What it produces is a well-prepared draft plus organized evidence, built so that a patent professional's review is fast and cheap instead of slow and expensive. For anything you intend to file, have a registered patent practitioner look at it. The point of this tool is to make that look-over affordable, not to skip it.
- **Some judgments are human-only.** Whether your invention is "non-obvious" and whether it is the kind of thing patent law protects at all are legal judgments no software makes reliably. The tool arms you for those conversations; it does not have them for you.

---

## Table of Contents

- [What this tool will and will not do](#read-this-first-what-this-tool-will-and-will-not-do)
- [Quick Start](#quick-start)
- [What Can I Actually Do With This?](#what-can-i-actually-do-with-this)
- [How It Works](#how-it-works)
- [What Setup Does](#what-setup-does)
- [CLI Commands](#cli-commands)
- [MCP Tools Reference](#mcp-tools-reference)
- [Skills, Agents, and Slash Commands](#skills-agents-and-slash-commands)
- [Configuration](#configuration)
- [Requirements](#requirements)
- [Architecture](#architecture)
- [Performance](#performance)
- [Known Issues](#known-issues)
- [Glossary](#glossary)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Credits](#credits)
- [License](#license)

---

## Quick Start

This takes about an hour, most of it waiting while the tool downloads the patent rulebook and builds its search index. You type a handful of lines; nothing here needs programming.

### What you need first

| You need | How to check or get it |
|---|---|
| **Claude Code** with a paid Claude plan | Anthropic's AI assistant. [Install it](https://claude.com/claude-code), sign in, and open it once. |
| **A terminal** | The window where you type commands. Mac: press Cmd+Space, type `Terminal`, press Enter. Windows: press Start, type `PowerShell`, press Enter. |
| **Python 3.10 to 3.13** | In the terminal, type `python3 --version` (Mac/Linux) or `py --version` (Windows). If it says 3.9 or older, or "not found", install Python 3.13 from [python.org/downloads](https://www.python.org/downloads/) and open a new terminal. On Windows, tick "Add python.exe to PATH" in the installer. |
| **git** | Type `git --version`. On a Mac that has never used it, a box offers to install "command line developer tools": click Install. Windows: install [Git for Windows](https://git-scm.com/download/win) (Claude Code needs it on Windows anyway). |
| **About 4 GB of free disk space** | The tool itself is about 2 GB; the rulebook and index add about 1 GB. |

### Step 1: Install the tool

Copy these lines into the terminal one at a time, pressing Enter after each. They make a private folder for the tool (a "virtual environment"), so it can't disturb anything else on your computer.

**Mac or Linux:**

```bash
cd ~
python3 -m venv patent-creator-venv
patent-creator-venv/bin/pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git
patent-creator-venv/bin/patent-creator setup
```

**Windows (PowerShell):**

```powershell
cd ~
py -m venv patent-creator-venv
.\patent-creator-venv\Scripts\pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git
.\patent-creator-venv\Scripts\patent-creator setup
```

The install line takes about a minute. `setup` then runs for 5 to 45 minutes (45 on a laptop without an NVIDIA graphics card, including Apple Silicon Macs). It asks three questions:

- **Delete the PDF files?** Either answer is fine. The search runs on the index it built; the PDFs are only needed to rebuild it.
- **Install Graphviz?** Say yes if you want patent drawings. It's a free program the diagram tools need.
- **Set up BigQuery?** Say no for now. It's an optional patent search that needs a Google Cloud account; Step 3 covers the easier option.

It finishes by connecting itself to Claude Code and testing that connection. If you see **Setup Complete!**, go on. If it says Claude Code is **not connected**, the lines above that message say why.

### Step 2: Add the guided workflows to Claude Code

Step 1 gives Claude the tools. This step adds the guided workflows, like `/create-patent`. Open Claude Code and type these two lines into Claude (not the terminal):

```
/plugin marketplace add RobThePCGuy/Claude-Patent-Creator
/plugin install claude-patent-creator-standalone@claude-patent-creator
```

Quit Claude Code completely and open it again. Then ask it:

> Search MPEP for claim definiteness requirements

You should get rule excerpts, each labeled with the MPEP chapter, the PDF file and the page it came from. That means everything is connected.

### Step 3: Turn on patent search (free key)

Rule search, claim checks, drawings and research-paper search work now with no keys. Searching existing **patents** needs one free key:

1. Sign up at [serpapi.com](https://serpapi.com/users/sign_up) (250 free searches a month).
2. Copy your key from [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key).
3. In the terminal, save it (replace `YOUR_KEY`):
   - Mac/Linux: `~/patent-creator-venv/bin/patent-creator config set SERPAPI_API_KEY "YOUR_KEY"`
   - Windows: `.\patent-creator-venv\Scripts\patent-creator config set SERPAPI_API_KEY "YOUR_KEY"` (run `cd ~` first)
4. Restart Claude Code.

Now ask: *"Is my idea of a self-heating coffee mug new?"*

### What it costs

| Part | Cost |
|---|---|
| Claude Code | Your paid Claude plan. This is the only required cost. |
| Rule search, claim and formality checks, drawings | Free, runs on your computer |
| Research-paper search (OpenAlex, arXiv, Semantic Scholar) | Free, no key needed |
| Patent search through SerpApi (Google Patents) | Free for 250 searches a month |
| Patent search through BigQuery (optional) | Free for the first 1 TB of searching each month; Google charges after that only if you add billing |

### If something goes wrong

Run the health check. It says what's working and what to fix:

- Mac/Linux: `~/patent-creator-venv/bin/patent-creator health`
- Windows: `.\patent-creator-venv\Scripts\patent-creator health` (from `cd ~`)

To test the connection to Claude Code, starting the tool exactly the way Claude does:

- Mac/Linux: `~/patent-creator-venv/bin/patent-creator verify-config`
- Windows: `.\patent-creator-venv\Scripts\patent-creator verify-config` (from `cd ~`)

<details>
<summary><strong>Other ways to install</strong></summary>

**Let Claude do the install.** After Step 2, type `/claude-patent-creator-standalone:setup-patent-system` in Claude Code. Claude makes the private folder, installs and runs setup for you. Skip this if you already did Step 1.

**From a copy of the code** (for people changing the code):

```bash
git clone https://github.com/RobThePCGuy/Claude-Patent-Creator.git
cd Claude-Patent-Creator
python3 -m venv venv
venv/bin/pip install -e .
venv/bin/patent-creator setup
```

On a Mac, a bare `pip install ...` outside a private folder fails with `externally-managed-environment`. That's macOS protecting its own Python. Use the steps above; don't use `--break-system-packages`.

</details>

---

## What Can I Actually Do With This?

Here are some real examples. You can type these directly in Claude Code and the right skill or tool kicks in automatically. Say it in your own words; the "what to say" column is a starting point, not a required incantation.

| What you want to do | What to say | What happens |
|---|---|---|
| Find out if a rule applies to you | "Search MPEP for claim definiteness requirements", or just "do my claims have to be written a certain way?" | The tool searches the examiner's rulebook and returns the relevant sections, with citations you can read yourself |
| See if your idea already exists | "Search for patents about [your idea]", e.g. "self-heating coffee mug" | Searches 100M+ existing patents and shows you the closest matches, so you know what you're up against (needs the free key from Quick Start Step 3) |
| Get your draft claims checked | "Review these claims" (paste them in) | Flags unclear wording, subjective terms and structural problems, the mechanical mistakes an examiner rejects first, and says which checks it skipped |
| Check a whole application | `/full-review` | Runs the claims, description, and formatting checks together and reports everything at once |
| Go from idea to draft application | `/create-patent` | A guided workflow: describe the invention, the tool searches prior art, drafts, checks, and assembles a reviewable package. Plan on 2.5 to 4.5 hours of back-and-forth; the result is Markdown and SVG files you convert to DOCX/PDF before filing |
| Make a drawing | "Create a block diagram showing [your system]" | Produces a patent-style figure, no design software needed |
| Dig deep on whether your idea is new | "Conduct a prior art search for [your invention]" | A thorough multi-angle hunt through existing patents, with an honest verdict on what it found |

---

## How It Works

*Everything from here down gets progressively more technical. You do not need any of it to use the tool: the sections above plus the [Glossary](#glossary) are enough. This part is for developers, patent professionals, and the curious.*

The system has two modes that can work independently or together:

**MCP Server** is the engine. It exposes 20+ tools that any MCP-compatible client (Claude Code, Claude Desktop, etc.) can call programmatically. These tools handle search, analysis, and diagram generation.

**Claude Code Plugin** adds the interactive layer. Skills activate automatically based on what you're doing. Agents handle long-running tasks in the background. Slash commands give you quick access to common workflows.

Under the hood, patent regulation search uses a hybrid approach: FAISS vector search finds semantically similar content, BM25 lexical search catches exact terminology matches, and a cross-encoder reranker sorts the combined results by relevance. Patent search goes through Google BigQuery's public patent dataset.

```
You (Claude Code) ──> MCP Server ──> Search / Analysis / Diagrams
                           │
            ┌──────────────┼──────────────┐
            v              v              v
     MPEP/USC/CFR     BigQuery        Graphviz
     (hybrid RAG)    (100M+ patents)   (diagrams)
```

---

## What Setup Does

`patent-creator setup` runs these steps. Running it again is safe: it skips anything already done.

1. Checks your hardware. On an NVIDIA graphics card it installs the GPU version of PyTorch and restarts itself. Apple Silicon and other computers build on the CPU, which is faster than Apple's GPU for this job.
2. Downloads the MPEP, 35 USC and 37 CFR from the USPTO, and the EPO and PCT rules (about 500 MB).
3. Builds the search index (FAISS + BM25). This is the long step.
4. Offers to delete the downloaded PDFs. The index keeps working either way.
5. Asks before installing Graphviz for the diagram tools. It never installs it without a yes.
6. Looks for existing Google Cloud sign-in for the optional BigQuery search.
7. Registers the tool with Claude Code, then starts it the way Claude will and checks it answers. It only reports success after that check passes.

Data lives in `~/.local/share/claude-patent-creator/data` (Mac/Linux) or `%APPDATA%\claude-patent-creator\data` (Windows); `PATENT_DATA_DIR` moves it. To load the plugin from a local copy of the code instead of the marketplace: `claude --plugin-dir ./Claude-Patent-Creator`.

---

## CLI Commands

Run these in a terminal. If you followed the Quick Start, put `~/patent-creator-venv/bin/` (Mac/Linux) or `.\patent-creator-venv\Scripts\` (Windows, from `cd ~`) in front of `patent-creator`.

```bash
patent-creator setup             # Full setup: downloads, builds index, connects to Claude Code
patent-creator setup --rebuild   # Same, but rebuilds the search index from scratch
patent-creator health            # What's working and what isn't
patent-creator status            # Same as health
patent-creator verify-config     # Starts the tool the way Claude Code does and checks it answers
patent-creator serve             # Run the MCP server by hand
patent-creator config list       # Show every setting and where its value comes from
patent-creator config set KEY VALUE   # Save a setting or key (e.g. SERPAPI_API_KEY)
patent-creator config unset KEY  # Remove a saved setting
patent-creator config path       # Where saved settings live
patent-creator config --gui      # Settings window (needs Python's Tkinter)
patent-creator rebuild-index     # Rebuild the MPEP search index
patent-creator download-mpep     # Download MPEP PDFs only
patent-creator download-all      # Download all sources (MPEP + 35 USC + 37 CFR)
patent-creator check-bigquery    # Test BigQuery connection
```

---

## MCP Tools Reference

### Search

| Tool | What it does |
|---|---|
| `search_mpep` | Hybrid RAG search across MPEP, 35 USC, and 37 CFR with filters |
| `get_mpep_section` | Pull full content of a specific MPEP section |
| `search_patents_google` | Full-text keyword search worldwide, claims included (recommended; free SerpApi key, 250 searches/month) |
| `search_patents_bigquery` | Keyword search fallback when no SerpApi key is set (~$2 a search past the free monthly TiB) |
| `search_non_patent_literature` | Papers and preprints as prior art (OpenAlex, arXiv, Semantic Scholar), free with no key, filter by priority date |
| `get_patent_bigquery` | Get details on a specific patent (claims by default; abstract/description opt-in) |
| `get_patents_bigquery` | Get details on up to 50 patents in one query, same cost as one |
| `search_patents_by_cpc_bigquery` | Search by CPC classification code |
| `search_uspto_api` | Search via the USPTO API |
| `get_uspto_patent` | Get patent details from USPTO |
| `get_recent_uspto_patents` | Pull recent filings |
| `search_patent_law` | Law search across US (MPEP/USC/CFR), EPO (EPC/Guidelines) and PCT sources |
| `search_patents_by_ipc_bigquery` | Search by IPC classification code |
| `search_patent_family_bigquery` | Every publication in a patent family, across countries |
| `search_epo_patents` | European patent search through EPO OPS (free EPO key) |
| `get_epo_patent` | EP patent details, claims and description through EPO OPS |
| `get_epo_patent_family` | Patent family members through EPO OPS |

### Analysis

| Tool | What it does |
|---|---|
| `review_patent_claims` | 35 USC 112(b) compliance check (definiteness, antecedent basis, structure) |
| `review_specification` | 35 USC 112(a) adequacy check (written description, enablement, best mode) |
| `check_formalities` | MPEP 608 compliance (abstract, title, drawings, required sections) |
| `review_epo_claims` | Art. 84 EPC claim check (clarity, support, two-part form) |
| `review_epo_specification` | Art. 83 EPC sufficiency and Rule 42 sections |
| `check_epo_formalities` | EPO formalities, Rules 42-49 EPC |
| `check_pct_formalities` | PCT formalities, Rules 5-12 |
| `check_package` | Whole-package consistency: stale verification stamps, claim-count disagreements, status contradictions, commentary inside filing copies, date errors |

### Generation

| Tool | What it does |
|---|---|
| `render_diagram` | Generate patent-style diagrams from Graphviz DOT code |
| `create_flowchart` | Build a flowchart from a list of steps and connections |
| `create_block_diagram` | Build a block diagram from components and relationships |
| `add_diagram_references` | Add patent reference numbers to an existing SVG diagram |
| `get_diagram_templates` | List available diagram templates |

### System

| Tool | What it does |
|---|---|
| `check_bigquery_status` | BigQuery configuration status |
| `check_google_patents_status` | Whether SerpApi patent search is set up and how many searches are left |
| `check_diagram_tools_status` | Graphviz availability |
| `check_uspto_api_status` | USPTO API connectivity |
| `check_epo_api_status` | EPO OPS credentials and quota |

Search index statistics are available as the MCP resource `mpep://index/stats`.

---

## Skills, Agents, and Slash Commands

### Skills (activate automatically)

You don't need to call these directly. Just describe what you want to do and the right skill kicks in.

| Skill | When it activates | What it brings |
|---|---|---|
| **setup-assistant** | Installing, configuring, or troubleshooting | Full setup lifecycle guidance |
| **patent-reviewer** | Reviewing a complete application for compliance | Comprehensive review (claims + spec + formalities) |
| **patent-claims-analyzer** | Reviewing claims specifically for 35 USC 112(b) | Deep-dive claims analysis (definiteness, antecedent basis, structure) |
| **patent-search** | Searching patents or prior art | BigQuery search workflows via the MCP tools |
| **bigquery-patent-search** | Quick BigQuery-only patent search | Keyword, CPC, and patent detail retrieval across 100M+ patents |
| **mpep-search** | Finding MPEP sections or regulations | Hybrid RAG search |
| **patent-diagram-generator** | Creating technical diagrams | Flowcharts, block diagrams, system architectures via Graphviz |
| **patent-application-creator** | Drafting a patent application interactively | Guided end-to-end workflow (prior art, claims, spec, diagrams, compliance) |
| **prior-art-search** | Novelty or freedom-to-operate analysis | 7-step prior art discovery methodology |
| **index-manager** | Building or rebuilding the search index | MPEP index lifecycle management |
| **development-assistant** | Adding features or creating tools | Development workflows and patterns |
| **troubleshooting-assistant** | Something's broken | Systematic 6-step diagnostics |
| **testing-assistant** | Running tests or validation | Test suite execution |
| **epc-search** | European or PCT law questions | Search of the EPC, EPO Guidelines and PCT rules |
| **epo-patent-analyzer** | Checking an application for EPO filing | Art. 84 and Art. 83 EPC checks |
| **epo-patent-search** | Searching European patents | EPO OPS and BigQuery search with an EP filter |
| **pct-application** | Preparing an international (PCT) application | PCT Rules 5-12, unity of invention, national phase deadlines |

### Agents (long-running, work independently)

These run in the background while you keep working on other things. There are 13 in `agents/`; these two are the ones you'll start yourself.

| Agent | What it does | How long | Output |
|---|---|---|---|
| **patent-creator** | Drafts a complete USPTO-ready application | 55-80 min | Specification, claims, abstract, diagrams, validation report |
| **prior-art-searcher** | Comprehensive prior art search | 15-30 min | Patentability report, top 10 prior art, claim strategy, IDS list |

To use them: "Create a patent for [your invention], use the patent-creator agent"

### Slash Commands

```
/create-patent          # Guided US application, idea to draft (2.5-4.5 hours)
/create-epo-patent      # Guided European application
/search-prior-art       # Prior art search with novelty analysis
/search-epo             # European patent search
/full-review            # Parallel review (claims + spec + formalities)
/review-claims          # Claims-only 35 USC 112(b) analysis
/review-specification   # Specification-only 35 USC 112(a) analysis
/review-formalities     # MPEP 608 formalities check
/review-epo-claims      # Art. 84 EPC claims check
/review-epo-formalities # EPO formalities (Rules 42-49 EPC)
/check-pct-formalities  # PCT formalities (Rules 5-12)
/configure-bigquery     # Set up the optional BigQuery search
/rebuild-index          # Rebuild the rulebook search index
/test-system            # Run the system checks
```

Installed from the marketplace, each command is also available with the plugin prefix, for example `/claude-patent-creator-standalone:create-patent`.

---

## Configuration

Save settings and keys with the `config` command. They go in one file, `~/.config/claude-patent-creator/config.json` (Mac/Linux) or `%APPDATA%\claude-patent-creator\config.json` (Windows), stored as plain text and readable only by you on Mac/Linux. Restart Claude Code after changing one.

```bash
patent-creator config set SERPAPI_API_KEY "your-key"
patent-creator config list
```

| Setting | What it's for | Where to get it |
|---|---|---|
| `SERPAPI_API_KEY` | Google Patents search (recommended) | Free, 250 searches a month: [serpapi.com](https://serpapi.com/users/sign_up) |
| `GOOGLE_CLOUD_PROJECT` | BigQuery patent search (optional) | Your Google Cloud project ID, see below |
| `OPENALEX_API_KEY` | More daily paper searches (works without it) | Free: [openalex.org](https://openalex.org/settings/api-key) |
| `SEMANTIC_SCHOLAR_API_KEY` | Steadier Semantic Scholar paper search (works without it) | Free, by request: [semanticscholar.org](https://www.semanticscholar.org/product/api#api-key-form) |
| `EPO_OPS_KEY`, `EPO_OPS_SECRET` | European patent full text | Free registration: [developers.epo.org](https://developers.epo.org) |
| `USPTO_API_KEY` | USPTO Open Data Portal search | [data.uspto.gov](https://data.uspto.gov/myodp) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Only for HyDE query expansion with `HYDE_BACKEND=api`. HyDE is off by default and has local backends that need no key | Your API account |
| `PATENT_LOG_LEVEL`, `PATENT_LOG_FORMAT` | Server logging detail and format | `INFO` and `json` by default; the `patent-creator` command always prints readable lines |
| `PATENT_MPEP_DEVICE` | Force `cpu` or `gpu` for the index build | Detected automatically |
| `PATENT_DATA_DIR` | Move the downloaded data and index | Default shown in [What Setup Does](#what-setup-does) |

`patent-creator config list` shows every setting. If you work from a copy of the code, a `.env` file in that folder works too (see `.env.example`); saved settings fill in anything `.env` and your environment leave unset.

<details>
<summary><strong>Setting up BigQuery (optional, for patent search)</strong></summary>

BigQuery searches Google's public patent dataset directly. It needs a Google Cloud project, but not a credit card: the [BigQuery sandbox](https://cloud.google.com/bigquery/docs/sandbox) works without a billing account and includes 1 TB of searching a month. If you add billing, searches past that are charged; the tool refuses any single search that would scan more than its cap (350 GiB by default), so one search can't run up a large bill.

```bash
# 1. Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# 2. Authenticate
gcloud auth application-default login

# 3. Set quota project (replace with your project ID)
gcloud auth application-default set-quota-project your-project-id

# 4. Save your project ID
patent-creator config set GOOGLE_CLOUD_PROJECT your-project-id

# 5. Test it
patent-creator check-bigquery
```

</details>

<details>
<summary><strong>Windows-specific setup notes</strong></summary>

**Git Bash is required** for the `claude mcp add` command on Windows. Install [Git for Windows](https://git-scm.com/download/win) and set the path:

```bash
# PowerShell, if setup can't find Git Bash on its own
$env:CLAUDE_CODE_GIT_BASH_PATH="C:\Program Files\Git\bin\bash.exe"
```

**Use forward slashes in MCP config paths.** The setup wizard handles this, but if you're configuring manually:

```bash
# Correct
claude mcp add ... -- "C:/Users/YourName/venv/Scripts/python.exe"

# Wrong (will fail)
claude mcp add ... -- "C:\Users\YourName\venv\Scripts\python.exe"
```

</details>

---

## Requirements

- **Python:** 3.10 to 3.13. CI tests 3.11; the full install has been walked end to end on 3.13 (macOS, Apple Silicon). 3.14 is untested.
- **RAM:** 8 GB (16 GB makes the index build more comfortable)
- **Disk:** about 4 GB free: about 2 GB for the tool and its libraries, 0.5 GB for the language models it downloads, about 1 GB for the rulebook and index
- **Claude Code** with a paid Claude plan

Optional:

- **NVIDIA GPU** with CUDA 12.8: builds the index several times faster. Apple Silicon builds on the CPU.
- **Graphviz:** a free program the diagram tools need (`brew install graphviz`, `winget install graphviz`, or `sudo apt-get install graphviz`). Setup offers to install it.
- **Google Cloud project:** for the optional BigQuery search.

<details>
<summary><strong>Full dependency list</strong></summary>

| Package | Version | Purpose |
|---|---|---|
| mcp | >=2.0.0, <3.0.0 | MCP Python SDK (MCPServer) |
| sentence-transformers | >=5.1.2, <7.0.0 | Text embeddings |
| faiss-cpu | >=1.13.2 | Vector similarity search |
| numpy | >=1.26.0, <3.0.0 | Array operations |
| rank-bm25 | >=0.2.2 | Lexical search |
| transformers | >=4.57.6, <6.0.0 | HuggingFace models |
| google-cloud-bigquery | >=3.41.0 | Patent search |
| pydantic | >=2.12.5 | Data validation |
| graphviz | >=0.21 | Diagram generation |
| PyMuPDF | >=1.26.0 | PDF processing |

See `pyproject.toml` for the complete list.

</details>

---

## Architecture

```
claude-patent-creator/
├── .claude-plugin/          # Plugin manifest and marketplace config
├── mcp_server/              # Core MCP server
│   ├── server.py            # MCPServer entry point
│   ├── mpep_search.py       # Hybrid RAG search engine
│   ├── bigquery_search.py   # BigQuery patent search
│   ├── claims_analyzer.py   # 35 USC 112(b) analyzer
│   ├── specification_analyzer.py  # 112(a) analyzer
│   ├── formalities_checker.py     # MPEP 608 checker
│   ├── diagram_generator.py       # Graphviz diagrams
│   ├── tools/               # MCP tool definitions
│   └── index/               # FAISS + BM25 index (git-ignored)
├── skills/                  # Claude Code skills (17)
├── agents/                  # Autonomous agents (13)
├── commands/                # Slash commands (16)
├── hooks/                   # Event-driven automation
├── scripts/                 # Testing and utilities
├── docs/                    # Additional documentation
├── pdfs/                    # Downloaded MPEP PDFs (git-ignored)
└── CLAUDE.md                # Full project documentation
```

For the complete architecture documentation, development workflows, and troubleshooting guides, see [CLAUDE.md](CLAUDE.md).

---

## Performance

| Operation | Time | Notes |
|---|---|---|
| **MPEP Search** | 50-200ms | Hybrid FAISS + BM25. The first search after starting takes about 2 s |
| **BigQuery Patent Search** | 1-3 sec | 100M+ patents |
| **USPTO API** | 500ms - 2s | Rate-limited by USPTO |
| **Index Build (NVIDIA GPU)** | 3-5 min | CUDA 12.8 |
| **Index Build (CPU, including Apple Silicon)** | 25-40 min | Measured 37 min on an Apple Silicon Mac; full setup took 38 min |

Resource usage: the loaded search index takes about 2-4GB of RAM and the index files are 500MB-1GB on disk. If you have a GPU, it'll use 1-2GB of VRAM for acceleration.

---

## Known Issues

> **This project is a work in progress.** Most features work, but expect some rough edges. Contributions, issues, and PRs are welcome.

Things to be aware of:

- **NVIDIA users: PyTorch install order matters.** Setup handles it. On a hand-made install, install the CUDA build of PyTorch before `sentence-transformers`, or you get the CPU-only build.
- **Patent search needs one setup step.** A free SerpApi key (Quick Start, Step 3) or a Google Cloud project for BigQuery. Everything else works with no keys.
- **Diagrams need Graphviz**, a free program outside Python. Setup offers to install it.
- **The claims check skips the antecedent-basis check by default** (terms like "the controller" used before "a controller"). Its pattern matcher flags too many correct claims. Every claims report names this skipped check; turn it on with `patent-creator config set PATENT_ENABLE_ANTECEDENT_CHECK 1` and review its findings by hand.
- **Windows users need Git Bash** for Claude Code's `claude mcp add`. See [Windows setup notes](#configuration).
- **Claude Code 2.1.280 handshake error `-32022`:** see the [optional stdio workaround](CLAUDE.md#claude-code-handshake-error--32022) for the reported client negotiation bug. Reported by [DanielTillett](https://github.com/RobThePCGuy/Claude-Patent-Creator/issues/102).

See [CLAUDE.md](CLAUDE.md) for the full troubleshooting guide.

---

## Glossary

If you're coming from the development side and patent terminology is new (or vice versa), here's a quick reference:

| Term | What it means |
|---|---|
| **MPEP** | Manual of Patent Examining Procedure. The handbook patent examiners use at the USPTO. Think of it as the rulebook. |
| **35 USC** | Title 35 of the United States Code. The federal patent statutes. |
| **37 CFR** | Title 37 of the Code of Federal Regulations. The rules that implement the patent statutes. |
| **USPTO** | United States Patent and Trademark Office. The agency that grants patents. |
| **CPC** | Cooperative Patent Classification. A system for categorizing patents by technology area. |
| **Prior Art** | Anything publicly available before your filing date that's relevant to your invention. Finding it is how you figure out if your idea is actually new. |
| **112(a)** | The section of patent law requiring your application to fully describe and enable the invention. |
| **112(b)** | The section requiring your claims to be definite and clear. |
| **MPEP 608** | The section covering formalities like abstract length, title format, and drawing requirements. |
| **RAG** | Retrieval Augmented Generation. Instead of relying only on what the AI was trained on, it searches a database first and uses those results to give a better answer. |
| **FAISS** | Facebook AI Similarity Search. A fast way to find similar text by comparing mathematical representations of meaning. |
| **BM25** | A text search algorithm that matches exact words and phrases. Works alongside FAISS to catch things vector search might miss. |
| **MCP** | Model Context Protocol. A standard for connecting AI tools to AI models. It's how this system talks to Claude. |
| **MCP server** | The part of this tool that runs quietly in the background and answers Claude's requests. Claude Code starts it for you. |
| **Plugin** | An add-on for Claude Code. This one adds the guided workflows and slash commands. |
| **Terminal** | The window where you type commands: Terminal on a Mac, PowerShell on Windows. |
| **Python** | The programming language this tool is written in. You install it once; you never write any. |
| **Virtual environment (venv)** | A private folder holding this tool and its libraries, so it can't disturb other programs. The Quick Start makes one called `patent-creator-venv`. |
| **pip** | Python's installer. It downloads the tool and its libraries into the virtual environment. |
| **git** | A program for downloading code. pip uses it to fetch this tool from GitHub. |
| **API key** | A password-like code a service gives you so the tool can use it on your behalf. Keep it private. |
| **Homebrew** | The common installer for extra programs on a Mac (`brew install ...`). |
| **IDS** | Information Disclosure Statement. A form listing prior art references you need to disclose to the USPTO. |

---

## Roadmap

- [x] Support for international patent offices (EPO, WIPO/PCT)
- [ ] Web interface for non-Claude Code users
- [ ] Claim dependency graph visualization
- [ ] Automated obviousness analysis (35 USC 103)
- [ ] Patent portfolio analysis tools
- [ ] Integration with patent drafting software

---

## Contributing

This project is open to contributions. Since it's a work in progress, expect breaking changes and incomplete documentation. Issues and PRs are welcome.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, branch naming, commit conventions, and code style guide.

---

## Credits

### Open Source Dependencies

This project builds on excellent open source work: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [FAISS](https://github.com/facebookresearch/faiss) (Meta AI Research), [Sentence Transformers](https://www.sbert.net/) (UKP Lab), [HuggingFace Transformers](https://huggingface.co/transformers/), [PyTorch](https://pytorch.org/), [rank-bm25](https://github.com/dorianbrown/rank_bm25), [PyMuPDF](https://pymupdf.readthedocs.io/), [Graphviz](https://graphviz.org/), [Pydantic](https://docs.pydantic.dev/), and [Google Cloud BigQuery](https://cloud.google.com/bigquery).

### Data Sources

MPEP, 35 USC, and 37 CFR are published by the USPTO. Patent data comes from Google BigQuery's `patents-public-data` dataset (100M+ patents). Embedding models are [BGE-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5) (BAAI) and [MS-MARCO MiniLM-L-6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2) (Microsoft).

### Trademark Notice

"USPTO" is a registered trademark of the United States Patent and Trademark Office. This project isn't affiliated with, endorsed by, or sponsored by the USPTO.

---

## Project Status

This project is in **beta**. I'm actively working on it, but not everything is polished and some features may not work as described. If you run into issues, [open one on GitHub](https://github.com/RobThePCGuy/Claude-Patent-Creator/issues) and I'll take a look.

For detailed documentation: [CLAUDE.md](CLAUDE.md) | For security issues: [SECURITY.md](SECURITY.md)

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Built with Claude Code.** The code is the output, but the real work is deciding what needs to exist and how the pieces fit together.
