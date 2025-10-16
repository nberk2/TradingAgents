import gradio as gr
import os
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import chromadb
import traceback

# Get version from environment variable (set by Docker build)
APP_VERSION = os.getenv('APP_VERSION', 'dev')

DATA_DIR = Path(os.getenv('DATA_DIR', '/tmp'))
ANALYSIS_DIR = DATA_DIR / 'analyses'
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR = DATA_DIR / 'status'
STATUS_DIR.mkdir(parents=True, exist_ok=True)

def clear_chromadb_collections():
    try:
        import shutil
        import chromadb
        import gc
        
        # Force garbage collection to release any ChromaDB clients
        gc.collect()
        
        # Clear the directory
        chromadb_path = Path('/tmp/chromadb')
        if chromadb_path.exists():
            shutil.rmtree(chromadb_path, ignore_errors=True)
        
        chromadb_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ ChromaDB cleared: {chromadb_path}")
        
    except Exception as e:
        print(f"⚠️ Could not clear ChromaDB: {str(e)}")

def save_analysis(ticker, analysis_date, result_text):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ticker}_{analysis_date}_{timestamp}"
        json_file = ANALYSIS_DIR / f"{filename}.json"
        with open(json_file, 'w') as f:
            json.dump({'ticker': ticker, 'analysis_date': analysis_date, 'timestamp': datetime.now().isoformat(), 'result': result_text}, f, indent=2)
        md_file = ANALYSIS_DIR / f"{filename}.md"
        with open(md_file, 'w') as f:
            f.write(result_text)
        print(f"✓ Analysis saved to {md_file}")
        return True
    except Exception as e:
        print(f"✗ Error saving analysis: {str(e)}")
        return False

def analyze_stock_async(ticker, analysis_date, session_id):
    """Run analysis in background thread"""
    status_file = STATUS_DIR / f"{session_id}.json"
    
    try:
        ticker = ticker.strip().upper()
        print(f"[INFO] Starting ASYNC analysis for {ticker} on {analysis_date}")
        
        with open(status_file, 'w') as f:
            json.dump({'status': 'running', 'ticker': ticker, 'progress': 10, 'message': 'Starting analysis...'}, f)
        
        with open(status_file, 'w') as f:
            json.dump({'status': 'running', 'ticker': ticker, 'progress': 20, 'message': 'Clearing ChromaDB collections...'}, f)
        clear_chromadb_collections()
        
        with open(status_file, 'w') as f:
            json.dump({'status': 'running', 'ticker': ticker, 'progress': 30, 'message': 'Initializing trading agents...'}, f)
        config = DEFAULT_CONFIG.copy()
        ta = TradingAgentsGraph(debug=True, config=config)
        
        print(f"[INFO] Running propagate for {ticker}")
        with open(status_file, 'w') as f:
            json.dump({'status': 'running', 'ticker': ticker, 'progress': 40, 'message': f'Running multi-agent analysis for {ticker}...'}, f)
        
        graph_output, decision = ta.propagate(ticker, analysis_date)
        
        print(f"[INFO] Analysis complete for {ticker}")
        with open(status_file, 'w') as f:
            json.dump({'status': 'running', 'ticker': ticker, 'progress': 90, 'message': 'Formatting results...'}, f)
        
        analysis_text = ""
        if isinstance(graph_output, dict) and 'messages' in graph_output:
            messages = graph_output['messages']
            for msg in messages:
                if hasattr(msg, 'content') and msg.content:
                    if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                        content = str(msg.content)
                        if len(content) > 100 and 'HumanMessage' not in content:
                            analysis_text += f"\n\n{content}\n\n---\n"
        else:
            analysis_text = str(graph_output)
        
        display_result = f"""# 📈 Trading Analysis: {ticker}

**Analysis Date:** {analysis_date}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 🎯 Final Trading Decision

### **{decision}**

---

## 📊 Multi-Agent Analysis

{analysis_text}

---

## 💾 Storage

✓ Analysis saved to persistent storage

---

*Powered by TradingAgents Multi-Agent LLM Framework*
"""
        
        save_result = f"""# 📈 Trading Analysis: {ticker}

**Analysis Date:** {analysis_date}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 🎯 Final Trading Decision

### **{decision}**

---

## 📊 Multi-Agent Analysis

{analysis_text}
"""
        
        save_analysis(ticker, analysis_date, save_result)
        
        temp_file = Path('/tmp') / f"{ticker}_{analysis_date}_latest.md"
        with open(temp_file, 'w') as f:
            f.write(display_result)
        
        print(f"[INFO] Returning result to Gradio (via status file)")
        
        with open(status_file, 'w') as f:
            json.dump({
                'status': 'complete',
                'ticker': ticker,
                'result': display_result,
                'download_path': str(temp_file),
                'progress': 100,
                'message': 'Analysis complete!'
            }, f)
        
        print(f"[INFO] ASYNC analysis complete - status file updated")
        
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = str(e)
        
        print("="*80)
        print(f"[ERROR] Failed analyzing {ticker}:")
        print(error_details)
        print("="*80)
        
        error_report = f"""# ⚠️ Analysis Failed for {ticker}

## Error Summary
**{error_message}**

---

## Detailed Error Trace
{error_details}

---

## Debug Information

**Ticker:** {ticker}  
**Date:** {analysis_date}  
**Timestamp:** {datetime.now().isoformat()}  
**Storage Path:** {DATA_DIR}
"""
     
        with open(status_file, 'w') as f:
            json.dump({
                'status': 'error',
                'ticker': ticker,
                'result': error_report,
                'error': str(e)
            }, f)

def check_analysis_status(session_id):
    """Check status file for completion"""
    if not session_id:
        return (
            "### 🚀 Ready to Analyze!\n\nEnter a stock ticker and click **Analyze Stock**.",
            gr.update(visible=False),
            session_id
        )
    
    status_file = STATUS_DIR / f"{session_id}.json"
    
    if not status_file.exists():
        return (
            "### ⏳ Initializing analysis...\n\nClick **Check Status** in 10 seconds.",
            gr.update(visible=False),
            session_id
        )
    
    try:
        with open(status_file, 'r') as f:
            status = json.load(f)
    except:
        return (
            "### ⏳ Loading status...\n\nClick **Check Status** again.",
            gr.update(visible=False),
            session_id
        )
    
    if status['status'] == 'running':
        progress = status.get('progress', 0)
        ticker = status.get('ticker', '...')
        message = status.get('message', 'Processing...')
        return (
            f"### ⏳ Analysis in Progress: {ticker}\n\n**Progress:** {progress}%\n\n**Status:** {message}\n\n*Click **Check Status** in 10-20 seconds to see results*",
            gr.update(visible=False),
            session_id
        )
    
    elif status['status'] == 'complete':
        result = status.get('result', 'Analysis complete but result missing')
        download_path = status.get('download_path')
        return (
            result,
            gr.update(visible=True, value=download_path),
            None
        )
    
    elif status['status'] == 'error':
        result = status.get('result', 'Unknown error occurred')
        return (
            result,
            gr.update(visible=False),
            None
        )
    
    return (
        "### Unknown status",
        gr.update(visible=False),
        session_id
    )

def start_analysis(ticker, date):
    """Start analysis in background thread - returns immediately"""
    if not ticker or ticker.strip() == "":
        return (
            "# ⚠️ Error: Invalid Input\n\nPlease enter a valid stock ticker symbol.",
            gr.update(visible=False),
            None
        )
    
    session_id = str(uuid.uuid4())
    thread = threading.Thread(target=analyze_stock_async, args=(ticker, date, session_id), daemon=True)
    thread.start()
    
    return (
        f"### ⏳ Analysis Started: {ticker.upper()}\n\n**Analysis running in background...**\n\nClick **Check Status** in 30-60 seconds to see results.",
        gr.update(visible=False),
        session_id
    )

def load_past_analyses():
    try:
        analyses = []
        for json_file in sorted(ANALYSIS_DIR.glob("*.json"), reverse=True):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    analyses.append({'filename': json_file.stem, 'ticker': data.get('ticker', 'Unknown'), 'date': data.get('analysis_date', 'Unknown'), 'timestamp': data.get('timestamp', 'Unknown')})
            except:
                continue
        return analyses
    except:
        return []

def load_analysis_content(filename):
    if not filename:
        return "### Select an analysis from the dropdown to view it."
    try:
        json_file = ANALYSIS_DIR / f"{filename}.json"
        if json_file.exists():
            with open(json_file, 'r') as f:
                data = json.load(f)
                return data.get('result', 'No content found')
        return "### Analysis file not found"
    except Exception as e:
        return f"### Error Loading Analysis\n\n{str(e)}"

def refresh_analysis_list():
    analyses = load_past_analyses()
    if not analyses:
        return gr.Dropdown(choices=["No analyses found"])
    analysis_options = [f"{a['ticker']} - {a['date']} ({a['timestamp'][:10]})" for a in analyses]
    analysis_filenames = [a['filename'] for a in analyses]
    return gr.Dropdown(choices=list(zip(analysis_options, analysis_filenames)))

# Gradio UI
with gr.Blocks(title="TradingAgents Dashboard", theme=gr.themes.Soft(), css="""
    .output-markdown {height: 70vh !important; overflow-y: auto !important; overflow-x: hidden !important;}
    .gradio-container {max-width: 1600px !important;}
    .input-column {max-width: 350px;}
""") as demo:
    gr.Markdown("# 📈 TradingAgents Dashboard\n### Multi-Agent LLM Financial Trading Framework\n\nGet AI-powered trading analysis from specialized agents")
    
    with gr.Tabs():
        with gr.Tab("🔍 New Analysis"):
            with gr.Row():
                with gr.Column(scale=1, elem_classes="input-column"):
                    ticker_input = gr.Textbox(label="Stock Ticker Symbol", placeholder="SPY", value="SPY", lines=1)
                    date_input = gr.Textbox(label="Analysis Date (YYYY-MM-DD)", placeholder="2025-10-15", value=datetime.now().strftime("%Y-%m-%d"), lines=1)
                    
                    with gr.Row():
                        analyze_btn = gr.Button("🔍 Analyze Stock", variant="primary", size="lg", scale=2)
                        check_btn = gr.Button("🔄 Check Status", variant="secondary", size="lg", scale=1)
                    
                    download_btn = gr.DownloadButton("📥 Download Report", visible=False)
                    gr.Markdown("### 📌 Popular Tickers\n**Indices:** SPY, QQQ, DIA, IWM\n**Tech:** AAPL, NVDA, MSFT, GOOGL\n**Growth:** TSLA, ASTS, PLTR, COIN\n\n### ⏱️ Analysis Time\n**30-60 seconds** - Click **Check Status** when ready")
                with gr.Column(scale=4):
                    output = gr.Markdown(value="### 🚀 Ready to Analyze!\n\nEnter a stock ticker and click **Analyze Stock**.", elem_classes="output-markdown")
            
            # Hidden session state
            session_state = gr.State()
            
            # Start analysis (non-blocking)
            analyze_btn.click(
                fn=start_analysis,
                inputs=[ticker_input, date_input],
                outputs=[output, download_btn, session_state]
            )
            
            # Manual status check
            check_btn.click(
                fn=check_analysis_status,
                inputs=[session_state],
                outputs=[output, download_btn, session_state]
            )
        
        with gr.Tab("📂 Past Analyses"):
            gr.Markdown("## 📚 Analysis History\nReview all previously completed stock analyses.")
            with gr.Row():
                with gr.Column(scale=1, elem_classes="input-column"):
                    refresh_btn = gr.Button("🔄 Refresh List", size="sm")
                    analyses = load_past_analyses()
                    if analyses:
                        analysis_options = [f"{a['ticker']} - {a['date']} ({a['timestamp'][:10]})" for a in analyses]
                        analysis_filenames = [a['filename'] for a in analyses]
                        choices = list(zip(analysis_options, analysis_filenames))
                    else:
                        choices = ["No analyses found"]
                    analysis_dropdown = gr.Dropdown(label="Select Analysis", choices=choices, value=None)
                    load_btn = gr.Button("📄 Load Analysis", variant="primary")
                    gr.Markdown(f"### 💾 Storage\n**Path:** `{ANALYSIS_DIR}`\n**Count:** {len(analyses)} analyses")
                with gr.Column(scale=4):
                    past_output = gr.Markdown(value="### Select an analysis to view it.", elem_classes="output-markdown")
            refresh_btn.click(fn=refresh_analysis_list, outputs=analysis_dropdown)
            load_btn.click(fn=load_analysis_content, inputs=analysis_dropdown, outputs=past_output)
            analysis_dropdown.change(fn=load_analysis_content, inputs=analysis_dropdown, outputs=past_output)
    
    gr.Markdown(f"---\n**Version:** {APP_VERSION} | **Framework:** [TradingAgents](https://github.com/TauricResearch/TradingAgents)")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=5000, share=False, show_error=True)