import streamlit as st
import os
from dotenv import load_dotenv
from model_use import get_responses_from_models, proprietary_models, open_source_models
from supabase import create_client, Client
import time

load_dotenv()

st.set_page_config(
    page_title="Model Response Comparator",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Model Response Comparator")
st.write("Compare responses from different AI models side by side")

api_key = os.getenv("OPENROUTER_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")

if not api_key:
    st.error("❌ OPENROUTER_API_KEY not found in environment variables. Please set it in your .env file.")
    st.stop()

if not supabase_url or not supabase_key:
    st.error("❌ SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables.")
    st.stop()

supabase: Client = create_client(supabase_url, supabase_key)

st.sidebar.header("User Info")
username = st.sidebar.text_input("👤 Username (optional)", placeholder="Enter your name")

st.sidebar.header("Model Selection")

proprietary_selected = st.sidebar.multiselect(
    "🏢 Proprietary Models",
    proprietary_models,
    default=[]
)

open_source_selected = st.sidebar.multiselect(
    "🌟 Open Source Models", 
    open_source_models,
    default=[]
)

selected_models = proprietary_selected + open_source_selected

if not selected_models:
    st.warning("⚠️ Please select at least one model from the sidebar.")
    st.stop()

st.sidebar.write(f"**Selected Models:** {len(selected_models)}")
for model in selected_models:
    st.sidebar.write(f"• {model}")

prompt = st.text_area(
    "✏️ Enter your prompt:",
    height=150,
    placeholder="Type your question or prompt here..."
)

if st.button("🚀 Get Responses", type="primary"):
    if not prompt.strip():
        st.error("Please enter a prompt.")
        st.stop()
    
    with st.spinner("Getting responses from selected models..."):
        try:
            # Create prompt record in database
            prompt_data = {
                "username": username.strip() if username.strip() else None,
                "prompt_text": prompt,
                "selected_models": selected_models,
                "total_models": len(selected_models),
                "status": "pending"
            }
            
            prompt_result = supabase.table("prompts").insert(prompt_data).execute()
            prompt_id = prompt_result.data[0]["id"]
            
            # Get responses from models with timing
            start_time = time.time()
            responses = get_responses_from_models(selected_models, prompt, api_key)
            
            # Store each model response in database
            for model_name, response in responses.items():
                response_time = int((time.time() - start_time) * 1000 / len(responses))
                
                if isinstance(response, str) and response.startswith("Error:"):
                    response_data = {
                        "prompt_id": prompt_id,
                        "model_name": model_name,
                        "response_content": None,
                        "response_error": response,
                        "response_time_ms": response_time
                    }
                else:
                    content = response.content if hasattr(response, 'content') else str(response)
                    response_data = {
                        "prompt_id": prompt_id,
                        "model_name": model_name,
                        "response_content": content,
                        "response_error": None,
                        "response_time_ms": response_time
                    }
                
                supabase.table("model_responses").insert(response_data).execute()
            
            # Update prompt status to completed
            supabase.table("prompts").update({"status": "completed"}).eq("id", prompt_id).execute()
            
            st.success(f"✅ Got responses from {len(responses)} models and saved to database!")
            
            cols = st.columns(min(len(responses), 3))
            
            for i, (model_name, response) in enumerate(responses.items()):
                col_index = i % len(cols)
                
                with cols[col_index]:
                    st.subheader(f"🔹 {model_name}")
                    
                    if isinstance(response, str) and response.startswith("Error:"):
                        st.error(response)
                    else:
                        if hasattr(response, 'content'):
                            st.write(response.content)
                        else:
                            st.write(str(response))
                    
                    st.divider()
                    
        except Exception as e:
            # Update prompt status to failed if something went wrong
            if 'prompt_id' in locals():
                supabase.table("prompts").update({"status": "failed"}).eq("id", prompt_id).execute()
            st.error(f"An error occurred: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.markdown("**Instructions:**")
st.sidebar.markdown("1. Enter username (optional)")
st.sidebar.markdown("2. Select one or more models")
st.sidebar.markdown("3. Enter your prompt")
st.sidebar.markdown("4. Click 'Get Responses'")
st.sidebar.markdown("5. Compare responses side by side")
st.sidebar.markdown("6. All responses are saved to database")