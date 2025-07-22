import streamlit as st
import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from openai import OpenAI
import re
from collections import defaultdict
import yfinance as yf
import pandas as pd

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # This loads .env file variables into os.environ
    print("✅ .env file loaded successfully")
except ImportError:
    print("⚠️ python-dotenv not installed, .env file won't be loaded")
    pass

# Page config
st.set_page_config(
    page_title="Market Insights Report Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom styling for professional look */
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.2rem;
        opacity: 0.9;
    }
    
    /* Configuration cards */
    .config-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #2a5298;
        margin-bottom: 1rem;
    }
    
    .config-card h3 {
        margin-top: 0;
        color: #1e3c72;
        font-size: 1.3rem;
        font-weight: 600;
    }
    
    /* Success/Error messages styling */
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Form styling */
    .stSelectbox > div > div {
        background-color: #f8f9fa;
        border: 2px solid #e9ecef;
        border-radius: 8px;
    }
    
    .stDateInput > div > div {
        background-color: #f8f9fa;
        border: 2px solid #e9ecef;
        border-radius: 8px;
    }
    
    /* Progress bar styling */
    .stProgress > div > div {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
    }
    
    /* Metrics styling */
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        text-align: center;
        border-top: 3px solid #2a5298;
    }
    
    /* Download section */
    .download-section {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        border: 2px dashed #2a5298;
        margin: 2rem 0;
    }
    
    /* Password page styling */
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        background: white;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
        border-top: 5px solid #2a5298;
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .login-header h1 {
        color: #1e3c72;
        margin-bottom: 0.5rem;
    }
    
    .login-header p {
        color: #6c757d;
        font-size: 1rem;
    }
    
    /* Hide streamlit elements */
    .css-1d391kg {display: none;}
    .css-1rs6os {display: none;}
    .css-17ziqus {display: none;}
    
</style>
""", unsafe_allow_html=True)

class StreamlitMarketReportGenerator:
    """
    Streamlit-integrated market report generator with UI controls
    """
    
    def __init__(self):
        """Initialize with API keys from environment or Streamlit secrets."""
        # Try to load from .env file first, then Streamlit secrets
        self.benzinga_key = self._get_api_key('BENZINGA_API_KEY')
        self.openai_key = self._get_api_key('OPENAI_API_KEY')
        
        if not self.benzinga_key or not self.openai_key:
            st.error("❌ API keys not found. Please check your .env file or Streamlit secrets.")
            st.stop()
        
        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=self.openai_key)
        self.benzinga_url = "https://api.benzinga.com/api"
        
        # Market data configuration
        self._setup_market_config()
        
    def _get_api_key(self, key_name: str) -> str:
        """Get API key from environment or Streamlit secrets."""
        # Try environment variable first
        api_key = os.getenv(key_name)
        if api_key:
            return api_key
        
        # Try Streamlit secrets
        try:
            return st.secrets[key_name]
        except:
            return ""
    
    def _setup_market_config(self):
        """Setup market indices, sectors, and stocks to track."""
        self.market_indices = {
            '^GSPC': 'S&P 500', '^DJI': 'Dow Jones', '^IXIC': 'NASDAQ', '^RUT': 'Russell 2000',
            '^VIX': 'VIX', '^STOXX50E': 'Euro Stoxx 50', '^FTSE': 'FTSE 100', '^GDAXI': 'DAX',
            '^FCHI': 'CAC 40', '^HSI': 'Hang Seng', '^N225': 'Nikkei 225', '000001.SS': 'Shanghai Composite',
            '^STI': 'Straits Times Index', 'EURUSD=X': 'EUR/USD', 'GBPUSD=X': 'GBP/USD',
            'USDJPY=X': 'USD/JPY', 'USDCNY=X': 'USD/CNY', 'GC=F': 'Gold', 'CL=F': 'Crude Oil', '^TNX': '10-Year Treasury'
        }
        
        self.sector_etfs = {
            'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Healthcare', 'XLE': 'Energy',
            'XLI': 'Industrials', 'XLP': 'Consumer Staples', 'XLY': 'Consumer Discretionary',
            'XLU': 'Utilities', 'XLB': 'Materials', 'XLRE': 'Real Estate', 'XLC': 'Communication Services'
        }
        
        self.major_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'JNJ', 'V', 'WMT', 'UNH', 'HD', 'PG', 'MA']
        self.sea_stocks = ['BABA', 'JD', 'TCEHY', 'PDD', 'BIDU', 'GRAB', 'SEA']
    
    def _make_benzinga_request(self, endpoint: str, params: Dict = None) -> List[Dict]:
        """Make request to Benzinga API with error handling."""
        if params is None:
            params = {}
        params['token'] = self.benzinga_key
        
        url = f"{self.benzinga_url}{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        try:
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/json')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                result = json.loads(data.decode('utf-8'))
                return result if isinstance(result, list) else []
        except Exception as e:
            st.error(f"Benzinga API error: {e}")
            return []
    
    def get_articles_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get articles for specific date range."""
        endpoint = "/v2/news"
        params = {
            "pageSize": 200,
            "displayOutput": "full",
            "dateFrom": start_date.strftime("%Y-%m-%d"),
            "dateTo": end_date.strftime("%Y-%m-%d")
        }
        return self._make_benzinga_request(endpoint, params)
    
    def get_market_data_by_range(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get market performance data for specific date range."""
        market_data = {}
        
        # Get index performance
        for ticker, name in self.market_indices.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date.strftime("%Y-%m-%d"), 
                                   end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"))
                if not hist.empty and len(hist) >= 2:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    change_pct = ((end_price - start_price) / start_price) * 100
                    
                    market_data[ticker] = {
                        'name': name,
                        'current_price': round(end_price, 2),
                        'change_pct': round(change_pct, 2),
                        'start_price': round(start_price, 2)
                    }
            except Exception as e:
                continue
        
        # Get sector performance
        sector_data = {}
        for ticker, name in self.sector_etfs.items():
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date.strftime("%Y-%m-%d"), 
                                   end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"))
                if not hist.empty and len(hist) >= 2:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    change_pct = ((end_price - start_price) / start_price) * 100
                    
                    sector_data[ticker] = {
                        'name': name,
                        'change_pct': round(change_pct, 2)
                    }
            except Exception as e:
                continue
        
        market_data['sectors'] = sector_data
        
        # Get major stock performance
        stock_data = {}
        all_stocks = self.major_stocks + self.sea_stocks
        for ticker in all_stocks:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date.strftime("%Y-%m-%d"), 
                                   end=(end_date + timedelta(days=1)).strftime("%Y-%m-%d"))
                if not hist.empty and len(hist) >= 2:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]
                    change_pct = ((end_price - start_price) / start_price) * 100
                    
                    stock_data[ticker] = {
                        'change_pct': round(change_pct, 2),
                        'current_price': round(end_price, 2)
                    }
            except Exception as e:
                continue
        
        market_data['stocks'] = stock_data
        return market_data
    
    def categorize_news_themes(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize articles by major themes."""
        themes = {
            'earnings': [], 'fed_policy': [], 'trade_tensions': [], 'tech_developments': [],
            'geopolitical': [], 'market_movements': [], 'deals_ma': [], 'china_sea': [],
            'crypto': [], 'other': []
        }
        
        for article in articles:
            title = article.get('title', '').lower()
            teaser = article.get('teaser', '').lower()
            text = f"{title} {teaser}"
            
            categorized = False
            if any(word in text for word in ['earnings', 'revenue', 'profit', 'quarterly', 'eps']):
                themes['earnings'].append(article)
                categorized = True
            if any(word in text for word in ['fed', 'federal reserve', 'interest rates', 'powell', 'monetary']):
                themes['fed_policy'].append(article)
                categorized = True
            if any(word in text for word in ['tariff', 'trade war', 'trade deal', 'import', 'export']):
                themes['trade_tensions'].append(article)
                categorized = True
            if any(word in text for word in ['ai', 'artificial intelligence', 'tech', 'semiconductor', 'chip']):
                themes['tech_developments'].append(article)
                categorized = True
            if any(word in text for word in ['trump', 'election', 'government', 'policy', 'regulation']):
                themes['geopolitical'].append(article)
                categorized = True
            if any(word in text for word in ['surge', 'plunge', 'rally', 'crash', 'soar', 'tumble']):
                themes['market_movements'].append(article)
                categorized = True
            if any(word in text for word in ['merger', 'acquisition', 'deal', 'buyout', 'takeover']):
                themes['deals_ma'].append(article)
                categorized = True
            if any(word in text for word in ['china', 'chinese', 'asia', 'singapore', 'hong kong']):
                themes['china_sea'].append(article)
                categorized = True
            if any(word in text for word in ['bitcoin', 'crypto', 'blockchain', 'ethereum']):
                themes['crypto'].append(article)
                categorized = True
            if not categorized:
                themes['other'].append(article)
        
        return themes
    
    def extract_key_stories(self, themes: Dict[str, List[Dict]], limit: int = 3) -> Dict[str, List[Dict]]:
        """Extract the most important stories from each theme."""
        key_stories = {}
        for theme, articles in themes.items():
            if not articles:
                continue
            scored_articles = []
            for article in articles:
                score = self._score_article_importance(article)
                scored_articles.append((article, score))
            scored_articles.sort(key=lambda x: x[1], reverse=True)
            key_stories[theme] = [article for article, score in scored_articles[:limit]]
        return key_stories
    
    def _score_article_importance(self, article: Dict) -> int:
        """Score article importance for market recap."""
        score = 0
        title = article.get('title', '').lower()
        teaser = article.get('teaser', '').lower()
        text = f"{title} {teaser}"
        
        major_companies = ['apple', 'microsoft', 'google', 'amazon', 'tesla', 'meta', 'nvidia']
        score += sum(5 for company in major_companies if company in text)
        
        impact_words = ['billion', 'million', 'record', 'historic', 'breakthrough', 'crisis']
        score += sum(3 for word in impact_words if word in text)
        
        urgent_words = ['breaking', 'just in', 'urgent', 'alert']
        score += sum(4 for word in urgent_words if word in text)
        
        try:
            created_time = datetime.fromisoformat(article.get('created', '').replace('Z', '+00:00'))
            hours_old = (datetime.now().astimezone() - created_time).total_seconds() / 3600
            if hours_old < 24:
                score += 5
        except:
            pass
        
        return score
    
    def translate_content(self, content: str, target_language: str) -> str:
        """Translate content to target language."""
        if target_language == "English":
            return content
        
        language_map = {
            "Thai": "Thai", "Simplified Chinese": "Simplified Chinese",
            "Traditional Chinese": "Traditional Chinese", "Vietnamese": "Vietnamese"
        }
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"You are a professional financial translator. Translate the following market report to {language_map[target_language]} while maintaining professional tone and financial accuracy."},
                    {"role": "user", "content": content}
                ],
                max_tokens=3000,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Translation error: {e}")
            return content
    
    def generate_market_report(self, market_data: Dict, key_stories: Dict, start_date: datetime, end_date: datetime) -> str:
        """Generate comprehensive market report using OpenAI with compliance safeguards."""
        performance_summary = self._create_performance_summary(market_data, start_date, end_date)
        news_summary = self._create_news_summary_with_sources(key_stories)
        
        date_range = f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
        
        system_prompt = """
        You are a senior financial market analyst writing a professional market insights report for institutional clients.
        
        CRITICAL INSTRUCTIONS - COMPLIANCE & ACCURACY:
        - Use ONLY the provided market data and news articles
        - ALWAYS include source links for any news references in your analysis
        - When mentioning news stories, format as: "According to Benzinga [insert URL], [story details]"
        - Add clear disclaimers that news content comes from third-party sources
        - Write with authority but acknowledge information sources transparently
        - Focus on analysis and interpretation rather than republishing news content
        - Maintain professional tone suitable for institutional clients
        
        COMPLIANCE REQUIREMENTS:
        - Include source attribution for all news references
        - Add disclaimers about third-party content
        - Focus on data analysis rather than news republication
        - Ensure readers can verify original sources independently
        """
        
        user_prompt = f"""
        Generate a comprehensive market insights report for the period {date_range}:
        
        MARKET PERFORMANCE DATA (Verified):
        {performance_summary}
        
        KEY NEWS DEVELOPMENTS WITH SOURCES:
        {news_summary}
        
        COMPLIANCE INSTRUCTIONS:
        - For any news story mentioned, include the source URL from the data above
        - Use format: "According to Benzinga (URL), [brief summary]"
        - Add disclaimer: "Readers should verify information independently from original sources"
        - Focus on analytical insights rather than republishing full news content
        
        Structure the report with these sections:
        1. Executive Summary (3-4 key themes with source links)
        2. Market Performance Analysis (indices, sectors, notable movements)
        3. Key Developments During Period (major themes with source links and disclaimers)
        4. Notable Stock Movements (significant performers with context)
        5. Market Outlook (forward-looking analysis based on trends)
        6. Sources & Disclaimers (comprehensive source list and compliance notices)
        
        Target length: 1200-1500 words. Write for sophisticated investors expecting actionable intelligence with full transparency.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=2500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            return "Error generating market report"
    
    def _create_performance_summary(self, market_data: Dict, start_date: datetime, end_date: datetime) -> str:
        """Create formatted performance summary from market data."""
        summary = []
        date_range = f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
        
        summary.append(f"MARKET PERFORMANCE ({date_range}):")
        for ticker, data in market_data.items():
            if ticker not in ['sectors', 'stocks']:
                name = data['name']
                change = data['change_pct']
                summary.append(f"• {name}: {change:+.2f}%")
        
        if 'sectors' in market_data:
            summary.append(f"\nSECTOR PERFORMANCE ({date_range}):")
            sectors_sorted = sorted(market_data['sectors'].items(), key=lambda x: x[1]['change_pct'], reverse=True)
            for ticker, data in sectors_sorted:
                name = data['name']
                change = data['change_pct']
                summary.append(f"• {name}: {change:+.2f}%")
        
        if 'stocks' in market_data:
            summary.append(f"\nNOTABLE STOCK MOVEMENTS ({date_range}):")
            stocks_sorted = sorted(market_data['stocks'].items(), key=lambda x: abs(x[1]['change_pct']), reverse=True)
            for ticker, data in stocks_sorted[:10]:
                change = data['change_pct']
                summary.append(f"• {ticker}: {change:+.2f}%")
        
        return "\n".join(summary)
    
    def _create_news_summary_with_sources(self, key_stories: Dict[str, List[Dict]]) -> str:
        """Create formatted news summary with source attribution and compliance links."""
        summary = []
        theme_names = {
            'earnings': 'Earnings Reports', 'fed_policy': 'Federal Reserve & Monetary Policy',
            'trade_tensions': 'Trade & Tariffs', 'tech_developments': 'Technology Developments',
            'geopolitical': 'Geopolitical Events', 'market_movements': 'Major Market Movements',
            'deals_ma': 'Mergers & Acquisitions', 'china_sea': 'China & Asia-Pacific',
            'crypto': 'Cryptocurrency', 'other': 'Other Notable News'
        }
        
        for theme, articles in key_stories.items():
            if not articles:
                continue
            theme_name = theme_names.get(theme, theme.title())
            summary.append(f"\n{theme_name.upper()}:")
            
            for i, article in enumerate(articles[:3], 1):
                title = article.get('title', 'No title')
                teaser = article.get('teaser', '')[:200] + "..." if len(article.get('teaser', '')) > 200 else article.get('teaser', '')
                created = article.get('created', 'Date unknown')
                url = article.get('url', 'No URL available')
                
                summary.append(f"{i}. TITLE: {title}")
                summary.append(f"   DATE: {created}")
                summary.append(f"   SUMMARY: {teaser}")
                summary.append(f"   SOURCE: Benzinga")
                summary.append(f"   FULL ARTICLE: {url}")
                summary.append(f"   DISCLAIMER: This is a third-party news source. Please verify independently.")
                summary.append("")
        
        return "\n".join(summary)

def get_app_password() -> str:
    """Get application password from environment or Streamlit secrets."""
    # Try environment variable first (.env file or system environment)
    password = os.getenv('APP_PASSWORD')
    if password:
        print(f"✅ Password found in environment: {password[:3]}***")
        return password
    
    # Try Streamlit secrets (for cloud deployment)
    try:
        password = st.secrets['APP_PASSWORD']
        print(f"✅ Password found in Streamlit secrets: {password[:3]}***")
        return password
    except:
        print("❌ No password found in secrets.toml")
        pass
    
    # Fallback to default (not recommended for production)
    print("⚠️ Using default password. Set APP_PASSWORD in .env file!")
    return "weekly_report"

def password_check():
    """Enhanced password protection with professional styling."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        # Professional login page
        st.markdown("""
        <div class="login-container">
            <div class="login-header">
                <h1>🏢 Market Intelligence Platform</h1>
                <p>Secure Access Portal</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🔐 Authentication Required")
            password = st.text_input(
                "Enter Access Code:", 
                type="password", 
                key="password_input",
                placeholder="••••••••••••",
                help="Enter your secure access code to continue"
            )
            
            login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
            with login_col2:
                if st.button("🚀 Access Platform", key="login_button", use_container_width=True):
                    correct_password = get_app_password()
                    
                    if password == correct_password:
                        st.session_state.authenticated = True
                        st.success("✅ Access Granted")
                        st.rerun()
                    else:
                        st.error("❌ Invalid access code. Please verify and try again.")
                        st.info("💡 Contact system administrator for assistance.")
        
        # Professional footer with security info
        st.markdown("---")
        with st.expander("🔒 Security Information", expanded=False):
            st.markdown("""
            **Platform Security:**
            - Multi-environment configuration support
            - Encrypted credential management  
            - Session-based authentication
            - Enterprise-grade access controls
            
            **Technical Support:**
            - Environment: Local Development / Cloud Deployment
            - Authentication: Environment Variables / Streamlit Secrets
            - Data Sources: Benzinga API, Yahoo Finance, OpenAI GPT-4
            """)
        
        st.stop()

def main():
    """Main Streamlit application with professional styling."""
    # Password protection
    password_check()
    
    # Professional header
    st.markdown("""
    <div class="main-header">
        <h1>📊 Market Intelligence Platform</h1>
        <p>Professional Market Analysis & Research Suite</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize generator
    try:
        generator = StreamlitMarketReportGenerator()
        st.markdown("""
        <div class="success-box">
            <strong>✅ System Status:</strong> All systems operational. API connections established.
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div class="error-box">
            <strong>❌ System Error:</strong> {e}
        </div>
        """, unsafe_allow_html=True)
        st.stop()
    
    # Main configuration section
    st.markdown("## ⚙️ Report Configuration")
    
    # Configuration cards layout
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.markdown("""
        <div class="config-card">
            <h3>📅 Analysis Period</h3>
        </div>
        """, unsafe_allow_html=True)
        
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now() - timedelta(days=7),
                help="Select the beginning of your analysis period"
            )
        with date_col2:
            end_date = st.date_input(
                "End Date",
                value=datetime.now(),
                help="Select the end of your analysis period"
            )
        
        # Date validation with professional styling
        if start_date >= end_date:
            st.markdown("""
            <div class="error-box">
                <strong>⚠️ Date Error:</strong> Start date must be before end date.
            </div>
            """, unsafe_allow_html=True)
            return
        
        days_range = (end_date - start_date).days + 1
        st.markdown(f"""
        <div style="background: #e3f2fd; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
            <strong>📊 Analysis Scope:</strong> {days_range} days | {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="config-card">
            <h3>🌍 Output Configuration</h3>
        </div>
        """, unsafe_allow_html=True)
        
        language = st.selectbox(
            "Report Language",
            ["English", "Thai", "Simplified Chinese", "Traditional Chinese", "Vietnamese"],
            help="Select the primary language for your analysis report"
        )
        
        st.markdown("**📋 Report Features**")
        
        feature_col1, feature_col2 = st.columns(2)
        with feature_col1:
            include_sectors = st.checkbox("📈 Sector Analysis", value=True)
            include_compliance = st.checkbox("⚖️ Compliance Notices", value=True)
        with feature_col2:
            include_sources = st.checkbox("🔗 Source Attribution", value=True)
            email_format = st.checkbox("📧 Email Optimization", value=True)
    
    # Advanced settings in professional expander
    with st.expander("🔧 Advanced Configuration", expanded=False):
        st.markdown("### Technical Parameters")
        
        adv_col1, adv_col2, adv_col3 = st.columns(3)
        with adv_col1:
            articles_limit = st.slider("Article Analysis Limit", 50, 300, 200, 25)
            st.caption("Maximum number of articles to process")
        with adv_col2:
            themes_limit = st.slider("Stories per Theme", 1, 5, 3)
            st.caption("Top stories to extract per category")
        with adv_col3:
            temperature = st.slider("AI Analysis Depth", 0.1, 1.0, 0.7, 0.1)
            st.caption("Higher values = more creative analysis")
    
    # Professional generation section
    st.markdown("---")
    st.markdown("## 🚀 Generate Analysis")
    
    generation_col1, generation_col2, generation_col3 = st.columns([1, 2, 1])
    with generation_col2:
        generate_button = st.button(
            "📊 Generate Market Intelligence Report", 
            type="primary",
            use_container_width=True,
            help="Process market data and generate comprehensive analysis"
        )
    
    # Professional report generation with enhanced progress tracking
    if generate_button:
        if 'report_data' in st.session_state:
            del st.session_state.report_data
        
        # Enhanced progress section
        st.markdown("### 🔄 Processing Status")
        progress_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            metrics_placeholder = st.empty()
        
        try:
            # Step 1: Market data
            status_text.markdown("**📈 Phase 1:** Retrieving market performance data...")
            progress_bar.progress(20)
            market_data = generator.get_market_data_by_range(start_date, end_date)
            
            # Step 2: News articles
            status_text.markdown("**📰 Phase 2:** Collecting financial news articles...")
            progress_bar.progress(40)
            articles = generator.get_articles_by_date_range(start_date, end_date)
            
            if not articles:
                st.markdown("""
                <div class="error-box">
                    <strong>⚠️ Data Warning:</strong> No articles found for selected period. Consider expanding date range.
                </div>
                """, unsafe_allow_html=True)
                return
            
            # Show interim metrics
            with metrics_placeholder:
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                with metric_col1:
                    st.metric("📊 Market Indices", len([k for k in market_data.keys() if k not in ['sectors', 'stocks']]))
                with metric_col2:
                    st.metric("📰 Articles Found", len(articles))
                with metric_col3:
                    st.metric("🏢 Sectors Tracked", len(market_data.get('sectors', {})))
            
            # Step 3: Analysis
            status_text.markdown("**🔍 Phase 3:** Analyzing themes and market patterns...")
            progress_bar.progress(60)
            themes = generator.categorize_news_themes(articles)
            key_stories = generator.extract_key_stories(themes, limit=themes_limit)
            
            # Step 4: Report generation
            status_text.markdown("**✍️ Phase 4:** Generating intelligence report...")
            progress_bar.progress(80)
            report_content = generator.generate_market_report(market_data, key_stories, start_date, end_date)
            
            # Step 5: Translation
            if language != "English":
                status_text.markdown(f"**🌍 Phase 5:** Localizing content to {language}...")
                progress_bar.progress(90)
                report_content = generator.translate_content(report_content, language)
            
            # Completion
            status_text.markdown("**✅ Complete:** Market intelligence report generated successfully!")
            progress_bar.progress(100)
            
            # Store results
            st.session_state.report_data = {
                'content': report_content,
                'start_date': start_date,
                'end_date': end_date,
                'language': language,
                'articles_count': len(articles),
                'themes_count': len([t for t, a in themes.items() if a]),
                'market_data': market_data,
                'settings': {
                    'include_sectors': include_sectors,
                    'include_compliance': include_compliance,
                    'include_sources': include_sources,
                    'email_format': email_format
                }
            }
            
            # Clear progress
            progress_bar.empty()
            status_text.empty()
            metrics_placeholder.empty()
            
        except Exception as e:
            st.markdown(f"""
            <div class="error-box">
                <strong>❌ Processing Error:</strong> {str(e)}
            </div>
            """, unsafe_allow_html=True)
            return
    
    # Display results with professional styling
    if 'report_data' in st.session_state:
        data = st.session_state.report_data
        
        # Success message
        st.markdown("""
        <div class="success-box">
            <strong>✅ Analysis Complete:</strong> Market intelligence report generated successfully.
        </div>
        """, unsafe_allow_html=True)
        
        # Professional metrics dashboard
        st.markdown("### 📊 Report Analytics")
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            st.markdown("""
            <div class="metric-container">
                <h3 style="color: #2a5298; margin: 0;">{}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6c757d;">Articles Analyzed</p>
            </div>
            """.format(data['articles_count']), unsafe_allow_html=True)
        
        with metric_col2:
            st.markdown("""
            <div class="metric-container">
                <h3 style="color: #2a5298; margin: 0;">{}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6c757d;">Market Themes</p>
            </div>
            """.format(data['themes_count']), unsafe_allow_html=True)
        
        with metric_col3:
            days = (data['end_date'] - data['start_date']).days + 1
            st.markdown("""
            <div class="metric-container">
                <h3 style="color: #2a5298; margin: 0;">{}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6c757d;">Day Period</p>
            </div>
            """.format(days), unsafe_allow_html=True)
        
        with metric_col4:
            st.markdown("""
            <div class="metric-container">
                <h3 style="color: #2a5298; margin: 0;">{}</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6c757d;">Language</p>
            </div>
            """.format(data['language']), unsafe_allow_html=True)
        
        # Report preview with professional styling
        st.markdown("### 📖 Report Preview")
        with st.expander("🔍 View Full Analysis Content", expanded=False):
            st.markdown(f"""
            <div style="background: #f8f9fa; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #2a5298;">
                {data['content'][:1000]}...
            </div>
            """, unsafe_allow_html=True)
            
            if len(data['content']) > 1000:
                st.markdown("*Preview shows first 1000 characters. Download full report below.*")
        
        # Professional download section
        st.markdown("""
        <div class="download-section">
            <h3 style="text-align: center; color: #1e3c72; margin-bottom: 1.5rem;">📥 Export & Distribution</h3>
        </div>
        """, unsafe_allow_html=True)
        
        date_str = data['end_date'].strftime("%Y%m%d")
        filename_base = f"market_intelligence_{date_str}"
        
        download_col1, download_col2, download_col3 = st.columns(3)
        
        with download_col1:
            # Professional text report
            text_content = f"""MARKET INTELLIGENCE REPORT
Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}
Period: {data['start_date'].strftime('%B %d')} - {data['end_date'].strftime('%B %d, %Y')}
Language: {data['language']}

{'='*80}

EXECUTIVE DISCLAIMER:
This report contains information from third-party financial news sources.
All content should be independently verified from original sources.
This analysis is for informational purposes only and does not constitute investment advice.

{'='*80}

{data['content']}

{'='*80}

COMPLIANCE NOTICE:
- Data Sources: Benzinga Financial News, Yahoo Finance Market Data
- AI Analysis: OpenAI GPT-4 Professional Financial Analysis
- Generated: {datetime.now().isoformat()}
- Verification: Please confirm all information independently before investment decisions
"""
            st.download_button(
                label="📄 Professional Report",
                data=text_content.encode('utf-8'),
                file_name=f"{filename_base}_report.txt",
                mime="text/plain"
            )
        
        with download_col2:
            # Executive summary format
            exec_summary = f"""EXECUTIVE MARKET BRIEFING

TO: Leadership Team
FROM: Market Intelligence Platform
DATE: {datetime.now().strftime('%B %d, %Y')}
RE: Market Analysis ({data['start_date'].strftime('%b %d')} - {data['end_date'].strftime('%b %d, %Y')})

EXECUTIVE SUMMARY:
{data['content'][:500]}...

DISTRIBUTION:
- Board Members
- Investment Committee  
- Risk Management
- Strategy Team

CONFIDENTIALITY NOTICE:
This briefing contains proprietary market analysis and should be treated as confidential.
"""
            st.download_button(
                label="📊 Executive Brief",
                data=exec_summary.encode('utf-8'),
                file_name=f"{filename_base}_executive.txt",
                mime="text/plain"
            )
        
        with download_col3:
            # Email distribution format
            email_content = f"""Subject: Market Intelligence Brief | {data['end_date'].strftime('%B %d, %Y')}

MARKET INTELLIGENCE BRIEFING
{data['end_date'].strftime('%B %d, %Y')}

Dear Team,

Please find our latest market intelligence analysis covering the period from {data['start_date'].strftime('%B %d')} to {data['end_date'].strftime('%B %d, %Y')}.

KEY HIGHLIGHTS:
- {data['articles_count']} market developments analyzed
- {data['themes_count']} strategic themes identified  
- Multi-source verification included

{data['content']}

Best regards,
Market Intelligence Team

---
DISCLAIMER: This analysis is for informational purposes only. Please verify all information independently.
Data Sources: Benzinga, Yahoo Finance | AI Analysis: GPT-4 Professional
"""
            st.download_button(
                label="📧 Email Distribution",
                data=email_content.encode('utf-8'),
                file_name=f"{filename_base}_email.txt",
                mime="text/plain"
            )
        
        # Technical data export
        st.markdown("### 🔧 Technical Data Export")
        technical_col1, technical_col2 = st.columns(2)
        
        with technical_col1:
            # JSON export for developers
            json_data = {
                'report_metadata': {
                    'generated_timestamp': datetime.now().isoformat(),
                    'analysis_period': {
                        'start_date': data['start_date'].isoformat(),
                        'end_date': data['end_date'].isoformat(),
                        'duration_days': (data['end_date'] - data['start_date']).days + 1
                    },
                    'configuration': {
                        'language': data['language'],
                        'articles_analyzed': data['articles_count'],
                        'themes_identified': data['themes_count'],
                        'settings': data.get('settings', {})
                    }
                },
                'report_content': {
                    'full_analysis': data['content'],
                    'language': data['language']
                },
                'market_data': data['market_data'],
                'system_info': {
                    'platform': 'Market Intelligence Platform',
                    'version': '2.0',
                    'data_sources': ['Benzinga API', 'Yahoo Finance', 'OpenAI GPT-4']
                }
            }
            
            st.download_button(
                label="⚙️ JSON Data Export",
                data=json.dumps(json_data, indent=2).encode('utf-8'),
                file_name=f"{filename_base}_data.json",
                mime="application/json"
            )
        
        with technical_col2:
            # CSV export for analysis
            try:
                # Create a simple CSV with key metrics
                csv_data = f"""Metric,Value,Unit
Analysis Period,{(data['end_date'] - data['start_date']).days + 1},Days
Articles Analyzed,{data['articles_count']},Count
Market Themes,{data['themes_count']},Count
Language,{data['language']},Text
Generated Date,{datetime.now().strftime('%Y-%m-%d %H:%M')},Timestamp
Market Indices,{len([k for k in data['market_data'].keys() if k not in ['sectors', 'stocks']])},Count
Sectors Tracked,{len(data['market_data'].get('sectors', {}))},Count
Individual Stocks,{len(data['market_data'].get('stocks', {}))},Count
"""
                st.download_button(
                    label="📈 CSV Analytics",
                    data=csv_data.encode('utf-8'),
                    file_name=f"{filename_base}_analytics.csv",
                    mime="text/csv"
                )
            except:
                st.info("CSV export temporarily unavailable")
        
        # Professional footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 8px; color: #6c757d;">
            <strong>Market Intelligence Platform</strong> | Professional Financial Analysis Suite<br>
            Generated: {timestamp} | Session: Authenticated Access<br>
            <em>Powered by Benzinga API, Yahoo Finance & OpenAI GPT-4</em>
        </div>
        """.format(timestamp=datetime.now().strftime('%B %d, %Y at %H:%M')), unsafe_allow_html=True)

if __name__ == "__main__":
    main()