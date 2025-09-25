import streamlit as st
# from dotenv import load_dotenv
from model_use import get_responses_from_models, proprietary_models, open_source_models
from supabase import create_client, Client
import time

# load_dotenv()

st.set_page_config(
    page_title="Model Response Comparator",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Model Response Comparator")
st.write("Compare responses from different AI models side by side")

api_key = st.secrets["OPENROUTER_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_ANON_KEY"]

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
            
            # Store each model response in database and collect response IDs
            response_records = {}
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
                
                result = supabase.table("model_responses").insert(response_data).execute()
                response_records[model_name] = {
                    'id': result.data[0]['id'],
                    'content': content if not isinstance(response, str) or not response.startswith("Error:") else None,
                    'error': response if isinstance(response, str) and response.startswith("Error:") else None
                }
            
            # Store response_records in session state for feedback forms
            st.session_state.current_responses = response_records
            st.session_state.current_prompt_id = prompt_id
            
            # Update prompt status to completed
            supabase.table("prompts").update({"status": "completed"}).eq("id", prompt_id).execute()
            
            st.success(f"✅ Got responses from {len(responses)} models and saved to database!")
            
        except Exception as e:
            # Update prompt status to failed if something went wrong
            if 'prompt_id' in locals():
                supabase.table("prompts").update({"status": "failed"}).eq("id", prompt_id).execute()
            st.error(f"An error occurred: {str(e)}")

# Display responses with feedback forms
if 'current_responses' in st.session_state and st.session_state.current_responses:
    st.markdown("---")
    st.subheader("📝 Model Responses & Feedback")
    
    response_records = st.session_state.current_responses
    prompt_id = st.session_state.current_prompt_id
    
    # Create columns for responses
    num_responses = len(response_records)
    cols = st.columns(min(num_responses, 3))
    
    feedback_data = {}
    
    for i, (model_name, record) in enumerate(response_records.items()):
        col_index = i % len(cols)
        
        with cols[col_index]:
            st.subheader(f"🔹 {model_name}")
            
            # Display response content
            if record['error']:
                st.error(record['error'])
            else:
                st.write(record['content'])
            
            st.markdown("---")
            
            # Feedback form
            st.markdown(f"**Rate {model_name}:**")
            
            # Star rating
            rating = st.selectbox(
                "⭐ Rating (1-5 stars)",
                options=[None, 1, 2, 3, 4, 5],
                format_func=lambda x: "Select rating..." if x is None else f"{'⭐' * x} ({x}/5)",
                key=f"rating_{model_name}_{i}"
            )
            
            # Text feedback
            feedback_text = st.text_area(
                "💬 Feedback (optional)",
                placeholder="Enter your thoughts about this response...",
                key=f"feedback_{model_name}_{i}",
                height=100
            )
            
            # Ranking
            rank = st.selectbox(
                "🏆 Rank this response",
                options=[None] + list(range(1, num_responses + 1)),
                format_func=lambda x: "Select rank..." if x is None else f"#{x} {'🥇' if x == 1 else '🥈' if x == 2 else '🥉' if x == 3 else ''}",
                key=f"rank_{model_name}_{i}"
            )
            
            # Store feedback data for submission
            feedback_data[model_name] = {
                'response_id': record['id'],
                'rating': rating,
                'feedback_text': feedback_text.strip() if feedback_text.strip() else None,
                'rank': rank
            }
            
            st.divider()
    
    # Submit feedback button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Submit All Feedback", type="primary", use_container_width=True):
            try:
                feedback_submitted = False
                
                for model_name, feedback in feedback_data.items():
                    # Only submit if user provided any feedback
                    if feedback['rating'] or feedback['feedback_text'] or feedback['rank']:
                        feedback_record = {
                            "response_id": feedback['response_id'],
                            "prompt_id": prompt_id,
                            "username": username.strip() if username.strip() else None,
                            "rating": feedback['rating'],
                            "feedback_text": feedback['feedback_text'],
                            "rank_position": feedback['rank']
                        }
                        
                        # Check if feedback already exists for this response and user
                        existing = supabase.table("response_feedback")\
                            .select("id")\
                            .eq("response_id", feedback['response_id'])\
                            .eq("username", username.strip() if username.strip() else None)\
                            .execute()
                        
                        if existing.data:
                            # Update existing feedback
                            supabase.table("response_feedback")\
                                .update(feedback_record)\
                                .eq("id", existing.data[0]["id"])\
                                .execute()
                        else:
                            # Insert new feedback
                            supabase.table("response_feedback").insert(feedback_record).execute()
                        
                        feedback_submitted = True
                
                if feedback_submitted:
                    st.success("✅ Feedback submitted successfully!")
                    st.balloons()
                else:
                    st.warning("⚠️ No feedback provided. Please rate, comment, or rank at least one response.")
                    
            except Exception as e:
                st.error(f"Error submitting feedback: {str(e)}")
    
    # Analytics section
    st.markdown("---")
    with st.expander("📊 Model Performance Analytics", expanded=False):
        try:
            analytics = supabase.table("response_ratings_summary").select("*").execute()
            if analytics.data:
                import pandas as pd
                df = pd.DataFrame(analytics.data)
                df = df.sort_values('avg_rating', ascending=False)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No ratings data available yet.")
        except Exception as e:
            st.error(f"Error loading analytics: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.markdown("**Instructions:**")
st.sidebar.markdown("1. Enter username (optional)")
st.sidebar.markdown("2. Select one or more models")
st.sidebar.markdown("3. Enter your prompt")
st.sidebar.markdown("4. Click 'Get Responses'")
st.sidebar.markdown("5. Rate and provide feedback")
st.sidebar.markdown("6. Rank responses and submit feedback")
st.sidebar.markdown("7. View analytics in expandable section")