"""
Prompt Inspector - Retrieve and display prompt information
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import json
from datetime import datetime

load_dotenv()

class PromptInspector:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
    
    def get_prompt_info(self, prompt_id=None, prompt_text=None):
        """Retrieve complete prompt information"""
        
        if prompt_id:
            # Get by prompt ID
            prompt_result = self.supabase.table("prompts").select("*").eq("id", prompt_id).execute()
            if not prompt_result.data:
                print(f"❌ No prompt found with ID: {prompt_id}")
                return None
            prompt_data = prompt_result.data[0]
            
        elif prompt_text:
            # Get most recent prompt matching the text
            prompt_result = self.supabase.table("prompts")\
                .select("*")\
                .eq("prompt_text", prompt_text)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            if not prompt_result.data:
                print(f"❌ No prompt found with text: {prompt_text}")
                return None
            prompt_data = prompt_result.data[0]
            prompt_id = prompt_data["id"]
        else:
            print("❌ Please provide either prompt_id or prompt_text")
            return None
        
        # Get all responses for this prompt
        responses_result = self.supabase.table("model_responses")\
            .select("*")\
            .eq("prompt_id", prompt_id)\
            .order("created_at")\
            .execute()
        
        # Get feedback for this prompt
        feedback_result = self.supabase.table("response_feedback")\
            .select("*")\
            .eq("prompt_id", prompt_id)\
            .execute()
        
        # Get LLM evaluations if they exist
        evaluations_result = self.supabase.table("llm_evaluations")\
            .select("*")\
            .eq("prompt_id", prompt_id)\
            .execute()
        
        return {
            'prompt': prompt_data,
            'responses': responses_result.data,
            'feedback': feedback_result.data,
            'evaluations': evaluations_result.data
        }
    
    def display_prompt_info(self, info):
        """Display prompt information in a formatted way"""
        if not info:
            return
        
        prompt = info['prompt']
        responses = info['responses']
        feedback = info['feedback']
        evaluations = info['evaluations']
        
        print("=" * 80)
        print("📋 PROMPT INFORMATION")
        print("=" * 80)
        
        # Prompt details
        print(f"🆔 ID: {prompt['id']}")
        print(f"👤 Username: {prompt.get('username', 'Anonymous')}")
        print(f"📅 Created: {self._format_datetime(prompt['created_at'])}")
        print(f"📊 Status: {prompt['status']}")
        print(f"🔢 Total Models: {prompt['total_models']}")
        print(f"🎯 Selected Models: {', '.join(prompt['selected_models'])}")
        print()
        print(f"💬 Prompt Text:")
        print("-" * 40)
        print(prompt['prompt_text'])
        print("-" * 40)
        print()
        
        # Responses
        print("🤖 MODEL RESPONSES")
        print("=" * 50)
        
        for i, response in enumerate(responses, 1):
            print(f"\n{i}. {response['model_name']}")
            print(f"   ⏱️ Response Time: {response.get('response_time_ms', 'N/A')} ms")
            print(f"   📅 Created: {self._format_datetime(response['created_at'])}")
            
            if response['response_error']:
                print(f"   ❌ Error: {response['response_error']}")
            else:
                content = response['response_content']
                if len(content) > 200:
                    print(f"   📝 Content (first 200 chars): {content[:200]}...")
                else:
                    print(f"   📝 Content: {content}")
            print()
        
        # Feedback
        if feedback:
            print("💭 USER FEEDBACK")
            print("=" * 50)
            
            feedback_by_response = {}
            for fb in feedback:
                response_id = fb['response_id']
                if response_id not in feedback_by_response:
                    feedback_by_response[response_id] = []
                feedback_by_response[response_id].append(fb)
            
            for response in responses:
                response_id = response['id']
                model_name = response['model_name']
                
                if response_id in feedback_by_response:
                    print(f"\n🤖 {model_name}")
                    for fb in feedback_by_response[response_id]:
                        print(f"   👤 User: {fb.get('username', 'Anonymous')}")
                        if fb['rating']:
                            stars = "⭐" * fb['rating']
                            print(f"   ⭐ Rating: {stars} ({fb['rating']}/5)")
                        if fb['rank_position']:
                            rank_emoji = "🥇" if fb['rank_position'] == 1 else "🥈" if fb['rank_position'] == 2 else "🥉" if fb['rank_position'] == 3 else "🏅"
                            print(f"   🏆 Rank: #{fb['rank_position']} {rank_emoji}")
                        if fb['feedback_text']:
                            print(f"   💬 Comment: {fb['feedback_text']}")
                        print(f"   📅 Given: {self._format_datetime(fb['created_at'])}")
                        print()
        else:
            print("\n💭 USER FEEDBACK: None")
        
        # LLM Evaluations
        if evaluations:
            print("\n🧠 LLM EVALUATIONS")
            print("=" * 50)
            
            for eval_data in evaluations:
                print(f"\n🤖 {eval_data['model_name']}")
                print(f"   🧑‍⚖️ Judge: {eval_data['judge_model']}")
                print(f"   📅 Evaluated: {self._format_datetime(eval_data['created_at'])}")
                
                if eval_data['scores']:
                    scores = json.loads(eval_data['scores']) if isinstance(eval_data['scores'], str) else eval_data['scores']
                    print(f"   📊 Scores:")
                    if 'overall' in scores:
                        print(f"      Overall: {scores['overall']}/10")
                    if 'confusion_recognition' in scores:
                        print(f"      Confusion Recognition: {scores['confusion_recognition']}/10")
                    if 'adaptive_response' in scores:
                        print(f"      Adaptive Response: {scores['adaptive_response']}/10")
                    if 'learning_facilitation' in scores:
                        print(f"      Learning Facilitation: {scores['learning_facilitation']}/10")
                    if 'strategic_decision' in scores:
                        print(f"      Strategic Decision: {scores['strategic_decision']}/10")
                    if 'engagement_eq' in scores:
                        print(f"      Engagement & EQ: {scores['engagement_eq']}/10")
                
                # Show first 300 chars of evaluation
                eval_text = eval_data['evaluation_text']
                if len(eval_text) > 300:
                    print(f"   📝 Evaluation (first 300 chars): {eval_text[:300]}...")
                else:
                    print(f"   📝 Evaluation: {eval_text}")
                print()
        else:
            print("\n🧠 LLM EVALUATIONS: None")
        
        print("=" * 80)
    
    def _format_datetime(self, dt_string):
        """Format datetime string for display"""
        try:
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return dt_string
    
    def list_recent_prompts(self, limit=10):
        """List recent prompts"""
        result = self.supabase.table("prompts")\
            .select("id, username, prompt_text, created_at, total_models")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        
        print("🕒 RECENT PROMPTS")
        print("=" * 60)
        
        for i, prompt in enumerate(result.data, 1):
            prompt_preview = prompt['prompt_text'][:60] + "..." if len(prompt['prompt_text']) > 60 else prompt['prompt_text']
            print(f"{i}. ID: {prompt['id']}")
            print(f"   👤 {prompt.get('username', 'Anonymous')} | 🤖 {prompt['total_models']} models | 📅 {self._format_datetime(prompt['created_at'])}")
            print(f"   💬 {prompt_preview}")
            print()


def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Inspect prompt information")
    parser.add_argument("--prompt-id", type=str, help="UUID of the prompt to inspect")
    parser.add_argument("--prompt-text", type=str, help="Text of the prompt to inspect")
    parser.add_argument("--list-recent", type=int, metavar="N", help="List N recent prompts (default: 10)")
    
    args = parser.parse_args()
    
    try:
        inspector = PromptInspector()
        
        if args.list_recent is not None:
            limit = args.list_recent if args.list_recent > 0 else 10
            inspector.list_recent_prompts(limit)
        elif args.prompt_id or args.prompt_text:
            info = inspector.get_prompt_info(prompt_id=args.prompt_id, prompt_text=args.prompt_text)
            inspector.display_prompt_info(info)
        else:
            print("❌ Please provide --prompt-id, --prompt-text, or --list-recent")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()