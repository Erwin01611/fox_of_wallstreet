"""
Model upload component for cloud deployments.
Allows users to upload model files directly when artifacts folder isn't committed.
"""

import os
import json
import zipfile
import streamlit as st
from typing import Optional, Dict
import shutil


def extract_model_from_zip(uploaded_file, extract_dir: str) -> Optional[Dict]:
    """
    Extract and validate a model from uploaded zip file.
    
    Expected zip structure:
    model_name/
      ├── best_model.zip (or best_model/ folder)
      └── metadata.json
    """
    try:
        # Save uploaded file temporarily
        temp_zip = os.path.join(extract_dir, "temp_upload.zip")
        with open(temp_zip, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        # Extract
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        os.remove(temp_zip)
        
        # Find model folder (should be only one folder)
        items = [d for d in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, d))]
        if not items:
            return None
        
        model_name = items[0]
        model_path = os.path.join(extract_dir, model_name)
        
        # Check for metadata
        metadata_path = os.path.join(model_path, "metadata.json")
        if not os.path.exists(metadata_path):
            return None
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Validate required fields
        required = ['symbol', 'timeframe', 'action_space']
        if not all(k in metadata for k in required):
            return None
        
        return {
            'name': model_name,
            'path': model_path,
            'metadata': metadata,
        }
        
    except Exception as e:
        st.error(f"Error extracting model: {e}")
        return None


def save_uploaded_model(uploaded_file, target_dir: str = "uploaded_models") -> Optional[Dict]:
    """
    Save uploaded model to disk and return model info.
    """
    # Create upload directory
    upload_dir = os.path.join(os.getcwd(), target_dir)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Create temp extraction dir
    temp_dir = os.path.join(upload_dir, "_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract and validate
        model_info = extract_model_from_zip(uploaded_file, temp_dir)
        
        if model_info is None:
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None
        
        # Move to final location
        final_path = os.path.join(upload_dir, model_info['name'])
        if os.path.exists(final_path):
            shutil.rmtree(final_path)
        
        shutil.move(model_info['path'], final_path)
        model_info['path'] = final_path
        
        # Clean up temp
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return model_info
        
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        st.error(f"Error saving model: {e}")
        return None


def render_model_uploader():
    """
    Render model upload section for cloud deployments.
    """
    st.subheader("📤 Upload Model")
    
    st.info("""
    **For cloud deployments:** Upload your trained model as a ZIP file.
    
    **ZIP structure should be:**
    ```
    your_model_name/
      ├── best_model.zip (or best_model/ folder with model files)
      └── metadata.json
    ```
    
    **To create a model ZIP:**
    1. Go to your local `artifacts/` folder
    2. Find your model folder (e.g., `20260318_143000_AAPL_1h_discrete_5/`)
    3. Zip the entire folder
    4. Upload here
    """)
    
    uploaded_file = st.file_uploader(
        "Upload model ZIP file",
        type=['zip'],
        help="Upload a zipped model folder containing metadata.json and best_model",
    )
    
    if uploaded_file is not None:
        with st.spinner("Processing uploaded model..."):
            model_info = save_uploaded_model(uploaded_file)
            
            if model_info:
                st.success(f"✅ Model uploaded successfully!")
                
                # Show model info
                meta = model_info['metadata']
                st.write(f"**Model:** {model_info['name']}")
                st.write(f"**Symbol:** {meta.get('symbol', 'N/A')}")
                st.write(f"**Timeframe:** {meta.get('timeframe', 'N/A')}")
                st.write(f"**Action Space:** {meta.get('action_space', 'N/A')}")
                
                return model_info
            else:
                st.error("❌ Invalid model file. Please check the ZIP structure.")
                return None
    
    return None


def get_uploaded_models(upload_dir: str = "uploaded_models") -> list:
    """
    Get list of uploaded models.
    """
    upload_path = os.path.join(os.getcwd(), upload_dir)
    
    if not os.path.exists(upload_path):
        return []
    
    models = []
    for item in os.listdir(upload_path):
        item_path = os.path.join(upload_path, item)
        if os.path.isdir(item_path) and not item.startswith('_'):
            metadata_path = os.path.join(item_path, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    models.append({
                        'name': item,
                        'path': item_path,
                        'metadata': metadata,
                    })
                except:
                    pass
    
    return models
