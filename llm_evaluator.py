"""
LLM Evaluator for Model Responses
Uses Grok-4-Fast as a judge model to evaluate tutoring responses
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from supabase import create_client, Client
import json
import re

load_dotenv()

class LLMEvaluator:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not all([self.api_key, self.supabase_url, self.supabase_key]):
            raise ValueError("Missing required environment variables")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Initialize Grok-4-Fast as judge model
        self.judge_model = ChatOpenAI(
            model="x-ai/grok-4-fast:free",
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            headers={
                "HTTP-Referer": "https://github.com/satvik314/educhain-tutorbench",
                "X-Title": "Educhain TutorBench Evaluator"
            }
        )
        
        # Load evaluation system prompt
        self.system_prompt = self._load_evaluation_prompt()
    
    def _load_evaluation_prompt(self):
        """Load the evaluation system prompt from file"""
        try:
            with open('/Users/satvikp/Desktop/mygit/educhain-tutorbench/prompts/evaluation_prompt.md', 'r') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError("evaluation_prompt.md not found. Please ensure the file exists.")
    
    def get_prompt_responses(self, prompt_id=None, prompt_text=None):
        """Retrieve prompt and responses from database"""
        if prompt_id:
            # Get by prompt ID
            prompt_result = self.supabase.table("prompts").select("*").eq("id", prompt_id).execute()
            if not prompt_result.data:
                raise ValueError(f"No prompt found with ID: {prompt_id}")
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
                raise ValueError(f"No prompt found with text: {prompt_text}")
            prompt_data = prompt_result.data[0]
            prompt_id = prompt_data["id"]
        else:
            raise ValueError("Either prompt_id or prompt_text must be provided")
        
        # Get all responses for this prompt
        responses_result = self.supabase.table("model_responses")\
            .select("*")\
            .eq("prompt_id", prompt_id)\
            .execute()
        
        if not responses_result.data:
            raise ValueError(f"No responses found for prompt ID: {prompt_id}")
        
        return prompt_data, responses_result.data
    
    def evaluate_single_response(self, prompt_text, model_name, response_content):
        """Evaluate a single model response"""
        evaluation_prompt = f"""
{self.system_prompt}

## Evaluation Task

**Teaching Scenario/Student Question:**
{prompt_text}

**AI Model Response ({model_name}):**
{response_content}

Please evaluate this response using the framework provided. Provide scores for all 5 dimensions and follow the exact output format specified in the system prompt.
"""
        
        try:
            response = self.judge_model.invoke(evaluation_prompt)
            return response.content
        except Exception as e:
            return f"Error during evaluation: {str(e)}"
    
    def evaluate_multiple_responses(self, prompt_text, responses):
        """Evaluate multiple responses comparatively"""
        response_text = ""
        for i, resp in enumerate(responses, 1):
            response_text += f"\n**Response {chr(64+i)} ({resp['model_name']}):**\n{resp['response_content']}\n"
        
        evaluation_prompt = f"""
{self.system_prompt}

## Comparative Evaluation Task

**Teaching Scenario/Student Question:**
{prompt_text}

**AI Model Responses:**
{response_text}

Please evaluate these responses using the comparative evaluation framework. Provide head-to-head scores and determine the winner.
"""
        
        try:
            response = self.judge_model.invoke(evaluation_prompt)
            return response.content
        except Exception as e:
            return f"Error during comparative evaluation: {str(e)}"
    
    def parse_evaluation_scores(self, evaluation_text):
        """Parse numerical scores from evaluation text"""
        scores = {}
        
        # Multiple patterns to catch different formats
        patterns = {
            'confusion_recognition': [
                r'Confusion Recognition:\s*(\d+)/10',
                r'Confusion Recognition.*?(\d+)\s*/\s*10',
                r'(?:^|\n)\s*-\s*Confusion Recognition:\s*(\d+)/10'
            ],
            'adaptive_response': [
                r'Adaptive Response:\s*(\d+)/10',
                r'Adaptive Response.*?(\d+)\s*/\s*10',
                r'(?:^|\n)\s*-\s*Adaptive Response:\s*(\d+)/10'
            ],
            'learning_facilitation': [
                r'Learning Facilitation:\s*(\d+)/10',
                r'Learning Facilitation.*?(\d+)\s*/\s*10',
                r'(?:^|\n)\s*-\s*Learning Facilitation:\s*(\d+)/10'
            ],
            'strategic_decision': [
                r'Strategic Decision(?:-Making)?:\s*(\d+)/10',
                r'Strategic Decision.*?(\d+)\s*/\s*10',
                r'(?:^|\n)\s*-\s*Strategic Decision(?:-Making)?:\s*(\d+)/10'
            ],
            'engagement_eq': [
                r'Engagement.*?(?:EQ|Intelligence):\s*(\d+)/10',
                r'Engagement.*?(?:EQ|Intelligence).*?(\d+)\s*/\s*10',
                r'(?:^|\n)\s*-\s*Engagement.*?(?:EQ|Intelligence):\s*(\d+)/10'
            ]
        }
        
        for dimension, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, evaluation_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    scores[dimension] = int(match.group(1))
                    break
        
        # Try to extract overall score with multiple patterns
        overall_patterns = [
            r'Overall.*?(?:Effectiveness\s+)?Score.*?(\d+(?:\.\d+)?)/10',
            r'Overall.*?Score.*?(\d+(?:\.\d+)?)\s*/\s*10',
            r'\*\*Overall.*?Score\*\*:\s*(\d+(?:\.\d+)?)/10'
        ]
        
        for pattern in overall_patterns:
            match = re.search(pattern, evaluation_text, re.IGNORECASE | re.MULTILINE)
            if match:
                scores['overall'] = float(match.group(1))
                break
        
        return scores
    
    def store_evaluation_result(self, prompt_id, model_name, evaluation_text, scores):
        """Store evaluation results in database"""
        evaluation_data = {
            "prompt_id": prompt_id,
            "model_name": model_name,
            "evaluation_text": evaluation_text,
            "scores": json.dumps(scores) if scores else None,
            "judge_model": "x-ai/grok-4-fast:free"
        }
        
        try:
            result = self.supabase.table("llm_evaluations").insert(evaluation_data).execute()
            return result.data[0]["id"]
        except Exception as e:
            print(f"Error storing evaluation: {e}")
            return None
    
    def run_evaluation(self, prompt_id=None, prompt_text=None, comparative=True):
        """Main evaluation function"""
        print("🔍 Starting LLM Evaluation...")
        
        # Get prompt and responses
        prompt_data, responses = self.get_prompt_responses(prompt_id, prompt_text)
        prompt_id = prompt_data["id"]
        prompt_text = prompt_data["prompt_text"]
        
        print(f"📝 Evaluating prompt: {prompt_text[:100]}...")
        print(f"🤖 Found {len(responses)} model responses")
        
        # Filter out error responses
        valid_responses = [r for r in responses if r['response_content'] and not r['response_error']]
        
        if not valid_responses:
            print("❌ No valid responses found to evaluate")
            return
        
        results = {}
        
        if comparative and len(valid_responses) > 1:
            print("🔄 Running comparative evaluation...")
            comparative_eval = self.evaluate_multiple_responses(prompt_text, valid_responses)
            results['comparative'] = comparative_eval
            print("✅ Comparative evaluation completed")
        
        # Individual evaluations
        print("🔍 Running individual evaluations...")
        for response in valid_responses:
            model_name = response['model_name']
            response_content = response['response_content']
            
            print(f"  📊 Evaluating {model_name}...")
            evaluation = self.evaluate_single_response(prompt_text, model_name, response_content)
            scores = self.parse_evaluation_scores(evaluation)
            
            # Store in database
            eval_id = self.store_evaluation_result(prompt_id, model_name, evaluation, scores)
            
            results[model_name] = {
                'evaluation': evaluation,
                'scores': scores,
                'eval_id': eval_id
            }
            
            # Debug info for score parsing
            if not scores:
                print(f"    ⚠️ No scores parsed for {model_name}")
                print(f"    📄 First 200 chars of evaluation: {evaluation[:200]}...")
            
            print(f"    ✅ {model_name} evaluated (ID: {eval_id})")
        
        print("🎉 Evaluation completed!")
        return results


def main():
    """Command line interface for the evaluator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate model responses using LLM judge")
    parser.add_argument("--prompt-id", type=str, help="UUID of the prompt to evaluate")
    parser.add_argument("--prompt-text", type=str, help="Text of the prompt to evaluate (uses most recent)")
    parser.add_argument("--no-comparative", action="store_true", help="Skip comparative evaluation")
    parser.add_argument("--debug", action="store_true", help="Show full evaluation text for debugging")
    
    args = parser.parse_args()
    
    if not args.prompt_id and not args.prompt_text:
        print("❌ Please provide either --prompt-id or --prompt-text")
        return
    
    try:
        evaluator = LLMEvaluator()
        results = evaluator.run_evaluation(
            prompt_id=args.prompt_id,
            prompt_text=args.prompt_text,
            comparative=not args.no_comparative
        )
        
        print("\n" + "="*50)
        print("📋 EVALUATION SUMMARY")
        print("="*50)
        
        for model_name, result in results.items():
            if model_name == 'comparative':
                continue
            print(f"\n🤖 {model_name}")
            if result['scores']:
                print(f"   Overall Score: {result['scores'].get('overall', 'N/A')}/10")
                print(f"   Confusion Recognition: {result['scores'].get('confusion_recognition', 'N/A')}/10")
                print(f"   Adaptive Response: {result['scores'].get('adaptive_response', 'N/A')}/10")
                print(f"   Learning Facilitation: {result['scores'].get('learning_facilitation', 'N/A')}/10")
                print(f"   Strategic Decision: {result['scores'].get('strategic_decision', 'N/A')}/10")
                print(f"   Engagement & EQ: {result['scores'].get('engagement_eq', 'N/A')}/10")
            else:
                print("   ⚠️ Could not parse scores")
                
            if args.debug:
                print(f"\n📄 Full Evaluation Text for {model_name}:")
                print("-" * 60)
                print(result['evaluation'])
                print("-" * 60)
        
        if 'comparative' in results:
            print(f"\n🏆 Comparative Analysis Available")
            print("   Check the database for full comparative evaluation")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()