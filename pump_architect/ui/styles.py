import streamlit as st


def inject_compact_css():
    """Forces Streamlit to use ultra-tight spacing and smaller fonts like Colab."""
    st.markdown("""
        <style>
            /* Base font size */
            html, body, [class*="st-"] { font-size: 14px !important; }
            
            /* Squeeze the main container padding */
            .block-container {
                padding-top: 1.5rem !important;
                padding-bottom: 1.5rem !important;
                max-width: 98% !important; /* Use almost full screen width */
            }
            
            /* Shrink headers and eliminate huge gaps below them */
            h1 { font-size: 1.6rem !important; padding-bottom: 0.2rem !important; margin-bottom: 0 !important;}
            h2 { font-size: 1.4rem !important; padding-bottom: 0.2rem !important; margin-bottom: 0 !important;}
            h3 { font-size: 1.1rem !important; padding-bottom: 0.1rem !important; margin-bottom: 0 !important;}
            
            /* Squeeze gaps between standard elements */
            .st-emotion-cache-1wivap2 { gap: 0.5rem !important; }
            
            /* Tighten up dividers */
            hr { margin-top: 0.5em !important; margin-bottom: 0.5em !important; }
            
            /* Make alert boxes (Remarks) more compact */
            .stAlert { padding: 0.5rem !important; }
        </style>
    """, unsafe_allow_html=True)
