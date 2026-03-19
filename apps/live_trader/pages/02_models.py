"""
Models Page - Browse and load trained models
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import streamlit as st

# Password protection
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from utils.auth import require_auth, show_logout_button
require_auth()

# Import components
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from components.model_selector import (
    render_model_selector,
    render_loaded_model_status,
    load_model_to_session,
)
from components.model_upload import (
    render_model_uploader,
    get_uploaded_models,
)

st.set_page_config(
    page_title="Models",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 Model Management")

# Check if we have any models
import glob
artifacts_exist = len(glob.glob("artifacts/*")) > 0
uploaded_models = get_uploaded_models()

if not artifacts_exist and not uploaded_models:
    st.warning("""
    ⚠️ **No Models Found**
    
    It looks like the `artifacts/` folder isn't available in this deployment.
    
    **You have 3 options:**
    
    1️⃣ **Upload a Model** (Recommended for demo)
       - Use the upload section below
       - Zip your local model folder and upload it
       
    2️⃣ **Commit artifacts to Git** (Not recommended - large files)
       - Add model files to your repo
       - Re-deploy
       
    3️⃣ **Train a new model** (Takes time)
       - Run training locally
       - Then upload the model
    """)

# Create tabs for different model sources
tab_local, tab_upload = st.tabs(["📁 Local Models", "📤 Upload Model"])

with tab_local:
    st.header("Select a Model")
    st.write("Choose a trained model from your artifacts folder.")
    
    # Render selector
    selected_model = render_model_selector()
    
    # Handle load
    if selected_model:
        success = load_model_to_session(selected_model)
        if success:
            st.rerun()
    
    if not artifacts_exist:
        st.info("💡 No local models found. Switch to 'Upload Model' tab to upload a model.")

with tab_upload:
    st.header("Upload a Model")
    st.write("Upload a trained model from your local machine.")
    
    # Show upload interface
    uploaded_model = render_model_uploader()
    
    # Show previously uploaded models
    if uploaded_models:
        st.divider()
        st.subheader("📦 Previously Uploaded Models")
        
        for model in uploaded_models:
            col1, col2 = st.columns([3, 1])
            with col1:
                meta = model['metadata']
                st.write(f"**{model['name']}**")
                st.caption(f"Symbol: {meta.get('symbol', 'N/A')} | Timeframe: {meta.get('timeframe', 'N/A')}")
            with col2:
                if st.button("Load", key=f"load_uploaded_{model['name']}"):
                    success = load_model_to_session(model)
                    if success:
                        st.rerun()

# Current model status
st.divider()
st.header("Current Model")
render_loaded_model_status()

# Instructions
with st.expander("💡 How to package your model for upload"):
    st.write("""
    **Step 1: Find your model locally**
    ```bash
    cd fox_of_wallstreet/artifacts/
    ls -la
    # You'll see folders like:
    # 20260318_143000_AAPL_1h_discrete_5/
    ```
    
    **Step 2: Verify it has the required files**
    ```bash
    cd 20260318_143000_AAPL_1h_discrete_5/
    ls -la
    # Should contain:
    # - metadata.json
    # - best_model.zip (or best_model/ folder)
    ```
    
    **Step 3: Zip the entire folder**
    ```bash
    cd ..
    zip -r my_model.zip 20260318_143000_AAPL_1h_discrete_5/
    ```
    
    **Step 4: Upload the ZIP file**
    - Switch to the "Upload Model" tab
    - Select your ZIP file
    - Click "Load" to use the model
    
    **Note:** Uploaded models are stored temporarily and may be lost when the app restarts.
    For permanent deployment, consider committing the artifacts folder or using persistent storage.
    """)

show_logout_button()
