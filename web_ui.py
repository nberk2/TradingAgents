import gradio as gr
import os
import json
import sys
from io import StringIO
from datetime import datetime
from pathlib import Path
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
import chromadb
import traceback

DATA_DIR = Path(os.getenv('DATA_DIR', '/tmp'))
ANALYSIS_DIR = DATA_DIR / 'analyses'
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

def clear_chromadb_collections():
    try:
        import shutil
        chromadb_path = Path('/tmp/chromadb')
        if chromadb_path.exists():
            shutil.rmtree(chromadb_path)
        chromadb_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ ChromaDB cleared: {chromadb_path}")
    except Exception as e:
        print(f"Note: Could not clear ChromaDB: {str(e)}")

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

def analyze_stock(ticker, analysis_date, progress=gr.Progress()):
    progress(0, desc="Starting analysis...")
    try:
        if not ticker or ticker.strip() == "":
            return "# ⚠️ Error: Invalid Input\n\nPlease enter a valid stock ticker symbol."
        
        ticker = ticker.strip().upper()
        print(f"[INFO] Starting analysis for {ticker} on {analysis_date}")

        progress(0.1, desc="Clearing ChromaDB collections...")
        clear_chromadb_collections()
        
        progress(0.2, desc="Initializing trading agents...")
        config = DEFAULT_CONFIG.copy()
        ta = TradingAgentsGraph(debug=True, config=config)
        
        print(f"[INFO] Running propagate for {ticker}")
        progress(0.3, desc=f"Running multi-agent analysis for {ticker}...")
        
        # Run the analysis
        graph_output, decision = ta.propagate(ticker, analysis_date)
        
        print(f"[INFO] Analysis complete for {ticker}")
        progress(0.9, desc="Formatting results...")
        
        # Parse the graph_output to extract clean content
        # graph_output is a dict with 'messages' key containing the conversation
        analysis_text = ""
        if isinstance(graph_output, dict) and 'messages' in graph_output:
            messages = graph_output['messages']
            for msg in messages:
                if hasattr(msg, 'content') and msg.content:
                    # Skip tool calls and system messages
                    if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                        content = str(msg.content)
                        # Clean up the content
                        if len(content) > 100 and 'HumanMessage' not in content:
                            analysis_text += f"\n\n{content}\n\n---\n"
        else:
            # Fallback: convert to string
            analysis_text = str(graph_output)
        
        # Format the final output
        result = f"""# 📈 Trading Analysis: {ticker}

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

✓ Analysis saved to persistent storage at `{ANALYSIS_DIR}`

---

*Powered by TradingAgents Multi-Agent LLM Framework*
"""
        
        progress(1.0, desc="Complete!")
        save_analysis(ticker, analysis_date, result)
        
        print(f"[INFO] Returning result to Gradio")
        return result
        
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

## Troubleshooting Steps

1. **Verify Ticker Symbol**
   - Ensure "{ticker}" is a valid stock ticker

2. **Check Logs**
   - kubectl logs -n tradingagents -l app=tradingagents --tail=200

3. **API Rate Limits**
   - Alpha Vantage free tier: 25 calls/day

---

## Debug Information

**Ticker:** {ticker}  
**Date:** {analysis_date}  
**Timestamp:** {datetime.now().isoformat()}  
**Storage Path:** {DATA_DIR}
"""
        return error_report
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
                    analyze_btn = gr.Button("🔍 Analyze Stock", variant="primary", size="lg")
                    gr.Markdown("### 📌 Popular Tickers\n**Indices:** SPY, QQQ, DIA, IWM\n**Tech:** AAPL, NVDA, MSFT, GOOGL\n**Growth:** TSLA, ASTS, PLTR, COIN\n\n### ⏱️ Analysis Time\n**30-60 seconds** for complete analysis")
                with gr.Column(scale=4):
                    output = gr.Markdown(value="### 🚀 Ready to Analyze!\n\nEnter a stock ticker and click **Analyze Stock**.", elem_classes="output-markdown")
            analyze_btn.click(fn=analyze_stock, inputs=[ticker_input, date_input], outputs=output, show_progress=True)
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
    gr.Markdown("---\n**Version:** 1.0.5 | **Framework:** [TradingAgents](https://github.com/TauricResearch/TradingAgents)")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=5000, share=False, show_error=True)
