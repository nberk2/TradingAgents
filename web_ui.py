import gradio as gr
import os
from datetime import datetime
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

def analyze_stock(ticker, analysis_date):
    """
    Run TradingAgents analysis on a stock ticker
    """
    try:
        # Initialize the trading graph
        config = DEFAULT_CONFIG.copy()
        ta = TradingAgentsGraph(debug=True, config=config)
        
        # Run the analysis
        graph_output, decision = ta.propagate(ticker.upper(), analysis_date)
        
        # Format the output
        result = f"""
# Trading Analysis for {ticker.upper()}
**Date:** {analysis_date}

## Final Decision
{decision}

## Analysis Details
{graph_output}
"""
        return result
        
    except Exception as e:
        return f"Error analyzing {ticker}: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="TradingAgents Dashboard") as demo:
    gr.Markdown("""
    # 📈 TradingAgents Dashboard
    ### Multi-Agent LLM Financial Trading Framework
    
    Enter a stock ticker symbol and date to get AI-powered trading analysis from multiple specialized agents.
    """)
    
    with gr.Row():
        with gr.Column():
            ticker_input = gr.Textbox(
                label="Stock Ticker Symbol",
                placeholder="SPY, AAPL, NVDA, etc.",
                value="SPY"
            )
            date_input = gr.Textbox(
                label="Analysis Date",
                placeholder="YYYY-MM-DD",
                value=datetime.now().strftime("%Y-%m-%d")
            )
            analyze_btn = gr.Button("🔍 Analyze Stock", variant="primary")
        
        with gr.Column():
            output = gr.Markdown(
                label="Analysis Results",
                value="Results will appear here..."
            )
    
    # Connect the button to the analysis function
    analyze_btn.click(
        fn=analyze_stock,
        inputs=[ticker_input, date_input],
        outputs=output
    )
    
    gr.Markdown("""
    ---
    **Powered by:** TradingAgents Framework | Built with [Gradio](https://gradio.app)
    """)

if __name__ == "__main__":
    # Run the web interface
    demo.launch(
        server_name="0.0.0.0",
        server_port=5000,
        share=False
    )
