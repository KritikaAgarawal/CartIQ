import os
import sys
import re
import pandas as pd
from pathlib import Path
import ollama

# Ensure we can import from src.agents.budget_calculator
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.agents.budget_calculator import calculate_channel_performance, recommend_budget_changes

def extract_numbers(text):
    """
    Extracts all numeric values from text and returns their absolute values.
    Handles commas in numbers (e.g., 1,234.56 -> 1234.56).
    """
    text_no_commas = text.replace(',', '')
    # regex for floats and integers, including negative numbers
    matches = re.findall(r'-?\d+\.?\d*', text_no_commas)
    
    numbers = []
    for m in matches:
        if m not in ('.', '-'):
            try:
                numbers.append(abs(float(m)))
            except ValueError:
                pass
    return numbers

def validate_hallucinations(response_text, prompt_text):
    """
    VALIDATION STEP:
    Even with a strict prompt, a local LLM can still occasionally invent a number 
    (hallucination). We verify programmatically rather than trusting the prompt alone 
    by extracting all numbers from the LLM's response and checking them against 
    the numbers provided in the prompt.
    """
    prompt_numbers = extract_numbers(prompt_text)
    response_numbers = extract_numbers(response_text)
    
    for num in response_numbers:
        valid = False
        for p_num in prompt_numbers:
            # Check absolute difference for small values/decimals
            if abs(num - p_num) <= 0.1:
                valid = True
                break
            # Check relative difference (within 1% tolerance, giving 1.5% for safety)
            if p_num != 0 and abs(num - p_num) / p_num <= 0.015:
                valid = True
                break
        
        if not valid:
            return False, num
            
    return True, None

def generate_recommendation_brief(df):
    """
    Generates a brief LLM explanation for each channel's deterministic recommendation.
    Validates that the LLM does not hallucinate new numbers.
    """
    results = []
    
    for _, row in df.iterrows():
        # 1. Build the strict prompt string
        prompt = f"""You are a marketing budget analyst assistant. You must ONLY use the exact numbers provided below. Do NOT invent, estimate, or round differently than shown. Do NOT add any information not given here.

Channel: {row['channel_name']}
Current Monthly Spend: ${row['total_spend']}
Revenue (linear attribution): ${row['attributed_revenue_linear']}
ROAS: {row['roas']}
CAC: ${row['cac']}
Data limitation: {row['data_limitation']}
Rule-based recommendation: {row['recommend_direction']} spend by {row['suggested_change_pct']}%

Write a 2-3 sentence business explanation of why this recommendation makes sense, using ONLY the numbers above. End by restating the exact recommended percentage change."""

        # 2. Send prompt to local LLM
        try:
            response = ollama.chat(
                model='llama3.2:3b',
                messages=[{'role': 'user', 'content': prompt}]
            )
            response_text = response.get('message', {}).get('content', '')
        except Exception as e:
            response_text = f"Error calling Ollama: {e}"
            
        # 3. Validation Step
        is_valid, bad_num = validate_hallucinations(response_text, prompt)
        
        if is_valid:
            validation_status = 'PASSED'
        else:
            validation_status = 'FLAGGED - contains unverified number'
            print(f"WARNING: Channel '{row['channel_name']}' flagged for unverified number: {bad_num}")
            
        # 4. Append to results
        results.append({
            'channel_name': row['channel_name'],
            'recommend_direction': row['recommend_direction'],
            'suggested_change_pct': row['suggested_change_pct'],
            'llm_explanation': response_text,
            'validation_status': validation_status
        })
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    print("Calculating channel performance...")
    df_perf = calculate_channel_performance()
    
    print("Generating deterministic budget recommendations...")
    df_recs = recommend_budget_changes(df_perf)
    
    print("Generating LLM explanations with hallucination validation...")
    df_final = generate_recommendation_brief(df_recs)
    
    print("\n" + "="*70)
    print("FINAL RECOMMENDATIONS & EXPLANATIONS")
    print("="*70)
    
    for _, row in df_final.iterrows():
        print(f"\nChannel: {row['channel_name']}")
        print(f"Recommendation: {row['recommend_direction']} by {row['suggested_change_pct']}%")
        print(f"Validation Status: {row['validation_status']}")
        print(f"Explanation:\n{row['llm_explanation']}")
        print("-" * 70)
