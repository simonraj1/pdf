#!/usr/bin/env python3
"""
PDF to Questions

A streamlined script that takes a PDF and directly produces an Excel file with improved questions.
This script:
1. Converts PDF pages to images
2. Uses Gemini's vision capabilities to extract text from each page
3. Processes the extracted text to identify multiple-choice questions
4. Improves the extracted questions for clarity and formatting
5. Saves the questions to an Excel file
"""

import os
import re
import time
import json
import logging
import argparse
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

# PDF and image processing
from PIL import Image
from pdf2image import convert_from_path

# Gemini API
from dotenv import load_dotenv
import google.generativeai as genai

# Data handling
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Load environment variables
load_dotenv()

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.warning("GEMINI_API_KEY not found in environment variables. Please provide it as an argument.")

# Hardcoded DPI value
DPI = 300

def convert_pdf_to_images(pdf_path: str, start_page: int = 1, max_pages: Optional[int] = None, 
                          temp_dir: str = "temp_images") -> List[str]:
    """
    Convert PDF pages to images.
    
    Args:
        pdf_path: Path to the PDF file
        start_page: Page to start from (1-indexed)
        max_pages: Maximum number of pages to process
        temp_dir: Directory to save temporary images
    
    Returns:
        List of paths to the generated images
    """
    try:
        # Create temp directory if it doesn't exist
        os.makedirs(temp_dir, exist_ok=True)
        
        # Adjust start_page for pdf2image (0-indexed)
        pdf_start_page = start_page - 1
        
        # Calculate end page
        if max_pages is not None:
            pdf_end_page = pdf_start_page + max_pages - 1
        else:
            pdf_end_page = None
        
        logging.info(f"Converting PDF to images with DPI={DPI}")
        logging.info(f"Processing pages {start_page} to {pdf_end_page + 1 if pdf_end_page is not None else 'end'}")
        
        # Open the PDF file to check if it exists and is valid
        try:
            images = convert_from_path(
                pdf_path,
                dpi=DPI,
                first_page=pdf_start_page + 1,  # pdf2image uses 1-indexed pages
                last_page=pdf_end_page + 1 if pdf_end_page is not None else None,
                fmt="jpeg",
                output_folder=temp_dir,
                paths_only=True,
                output_file=f"page_{start_page}"
            )
            logging.info(f"Successfully opened PDF and converted {len(images)} pages to images")
        except Exception as e:
            logging.error(f"Failed to open PDF file: {str(e)}")
            return []
        
        # Rename files to include page numbers
        image_paths = []
        for i, img_path in enumerate(images):
            page_num = start_page + i
            new_path = os.path.join(temp_dir, f"page_{page_num}.jpg")
            
            # If the file already exists with the correct name, no need to rename
            if img_path != new_path and os.path.exists(img_path):
                try:
                    os.rename(img_path, new_path)
                    image_paths.append(new_path)
                except Exception as e:
                    logging.error(f"Failed to rename {img_path} to {new_path}: {str(e)}")
                    image_paths.append(img_path)  # Use original path if rename fails
            else:
                image_paths.append(img_path)
        
        logging.info(f"Converted {len(image_paths)} pages to images")
        return image_paths
    except Exception as e:
        logging.error(f"Error converting PDF to images: {str(e)}")
        return []

def extract_text_with_gemini(image_path: str, api_key: str, retry_count: int = 3, delay: int = 5) -> str:
    """
    Extract text from an image using Gemini's vision capabilities.
    """
    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    # Set up the model with very low temperature for exact extraction
    generation_config = {
        "temperature": 0.01,
        "top_p": 1.0,
        "top_k": 32,
        "max_output_tokens": 8192,
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config
    )
    
    # Enhanced system prompt for better text extraction
    system_prompt = """
    You are an expert OCR system. Extract ALL text from the image with perfect accuracy, maintaining the exact original formatting.
    
    CRITICAL REQUIREMENTS:
    1. Extract EVERY SINGLE QUESTION completely:
       - Never skip any question, even if it seems incomplete
       - Extract ALL question numbers (1, 2, 3, etc.)
       - Look for questions that might be split across columns or sections
       - Pay attention to questions that might start at the bottom of one column and continue in another
       
    2. For match-type questions:
       - Extract the complete question text with both lists
       - Extract ALL items in List I and List II exactly as shown
       - Extract all code combinations (a, b, c, d) completely
       - Maintain the exact table structure and alignment
       - Look for lists that might continue on next columns
       
    3. For regular questions:
       - Extract the complete question text
       - Extract ALL options (A, B, C, D) completely
       - Look for options that might be in different columns
       - Check for options that might continue on next lines
       
    4. Preserve ALL formatting:
       - Keep exact question numbering
       - Maintain all whitespace and indentation
       - Keep table structures intact
       - Preserve list formatting
       - Keep any special characters or symbols
       
    5. Special attention to:
       - Questions split across columns
       - Questions continuing on next pages
       - Questions with complex formatting
       - Questions with tables or diagrams
       - Questions with special characters
       - Questions with multiple parts
       
    6. If you see:
       - Partial or cut-off text: Mark with [...] and add comment
       - Unclear numbering: Note the uncertainty
       - Split questions: Add marker [CONTINUES] or [CONTINUED FROM ABOVE]
       - Missing content: Mark with [CONTENT MISSING]
    
    FORMAT THE OUTPUT EXACTLY AS IT APPEARS IN THE IMAGE.
    Double-check that ALL question numbers are accounted for in sequence.
    """
    
    try:
        logging.info(f"Extracting text from image {image_path}")
        
        # Try multiple times with different prompts if needed
        for attempt in range(retry_count):
            try:
                response = model.generate_content([system_prompt, Image.open(image_path)])
                
                if response.text:
                    # Clean up the extracted text while preserving structure
                    text = response.text.strip()
                    
                    # Preserve table structures and alignments
                    text = re.sub(r'(\s*\|\s*)', ' | ', text)
                    
                    # Ensure proper spacing for options and lists
                    text = re.sub(r'(?m)^([A-D]\.|\d+\.|\([a-d]\))\s*', r'\1 ', text)
                    
                    # Preserve list structure
                    text = re.sub(r'List\s+(I+|[1-9])', r'\nList \1', text)
                    
                    # Check for potentially missed questions
                    question_numbers = re.findall(r'(?m)^(\d+)\.\s', text)
                    if question_numbers:
                        numbers = [int(n) for n in question_numbers]
                        expected = list(range(min(numbers), max(numbers) + 1))
                        missing = set(expected) - set(numbers)
                        
                        if missing:
                            logging.warning(f"Potentially missed questions: {missing}")
                            continue  # Try another attempt if questions are missing
                    
                    return text
                    
            except Exception as e:
                logging.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(delay)
                    continue
                break
    
    except Exception as e:
        logging.error(f"Error in text extraction: {str(e)}")
    
    return ""

def preprocess_text(text: str) -> str:
    """
    Preprocess text to better identify and structure questions.
    """
    # Remove excessive whitespace while preserving formatting
    text = re.sub(r'\s+', ' ', text)
    
    # Fix common OCR issues
    text = text.replace('|', 'I')  # Common OCR mistake
    text = re.sub(r'(?<=[0-9])\.(?=[A-Z])', '. ', text)  # Fix missing space after numbers
    
    # Ensure proper spacing for question numbers
    text = re.sub(r'(?m)^(\d+)\.(?=[^\s])', r'\1. ', text)
    
    # Fix list formatting
    text = re.sub(r'List\s+(I+|[1-9])', r'\nList \1', text)
    text = re.sub(r'([A-D])\.(?=[^\s])', r'\1. ', text)  # Fix option spacing
    
    # Handle split questions
    text = text.replace('[CONTINUES]', '')
    text = text.replace('[CONTINUED FROM ABOVE]', '')
    
    return text

def extract_questions_with_gemini(text: str, api_key: str, retry_count: int = 3, delay: int = 5) -> List[Dict[str, str]]:
    """
    Extract multiple-choice questions from text using Gemini AI.
    """
    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    # Set up the model with very low temperature for consistent extraction
    generation_config = {
        "temperature": 0.01,
        "top_p": 0.99,
        "top_k": 64,
        "max_output_tokens": 8192,
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config
    )
    
    # Preprocess the text
    text = preprocess_text(text)
    
    # Find all potential question numbers in the text
    question_numbers = re.findall(r'(?m)^(\d+)\.\s', text)
    expected_questions = []
    if question_numbers:
        numbers = [int(n) for n in question_numbers]
        min_num = min(numbers)
        max_num = max(numbers)
        expected_questions = list(range(min_num, max_num + 1))
    
    # Create the expected questions string for the prompt
    expected_str = str(expected_questions) if expected_questions else 'Unknown'
    
    # Enhanced system prompt for better question extraction
    system_prompt = """
    Extract ALL questions from the provided text with perfect accuracy. Pay special attention to match-type questions, formatting, and explanations.
    
    Expected question numbers: """ + expected_str + """
    
    For match-type questions:
    1. The question field MUST include:
       - The complete matching instruction
       - List I with ALL items and their labels
       - List II with ALL items and their labels
       - The complete table structure if present
    2. The options field MUST include:
       - Complete code combinations (e.g., "A-3, B-1, C-4, D-2")
       - Each option should be a SINGLE code combination
       - Do NOT include multiple combinations in one option
    
    For ALL questions:
    1. Never skip any question, even if it seems incomplete
    2. Preserve ALL formatting, tables, and special characters
    3. Keep question numbers exactly as shown
    4. Include ALL context and additional information
    5. Extract ANY explanations provided in the PDF exactly as they appear
    6. Look for explanations that follow the answer key or appear after the options
    7. Check for questions that might be split across sections
    8. Look for questions that might have been marked as [CONTINUES] or [CONTINUED FROM ABOVE]
    9. Pay attention to question numbering sequence
    10. Handle questions with multiple parts or sub-questions
    11. ENSURE ALL QUESTIONS ARE EXTRACTED
    
    Format requirements:
    1. For match-type questions:
       - question: Include BOTH lists with proper formatting
       - option_a: First code combination ONLY
       - option_b: Second code combination ONLY
       - option_c: Third code combination ONLY
       - option_d: Fourth code combination ONLY
       - explanation: Extract explanation EXACTLY as shown in PDF
    2. For regular questions:
       - Include complete question text
       - Include all options A through D
       - Extract any provided explanation exactly as shown
    
    JSON format example:
    {
        "question_number": "1",
        "question": "The complete question text including lists/tables",
        "option_a": "First option or code combination",
        "option_b": "Second option or code combination",
        "option_c": "Third option or code combination",
        "option_d": "Fourth option or code combination",
        "correct_answer": "A",
        "answer_text": "Text of the correct answer",
        "explanation": "The complete explanation from PDF",
        "explanation_source": "pdf",
        "is_match_type": false,
        "is_complete": true
    }
    
    CRITICAL: 
    1. Never combine multiple code combinations into a single option
    2. Each option should contain exactly ONE code combination
    3. Extract EVERYTHING exactly as shown
    4. Preserve the exact format of code combinations
    5. Extract explanations EXACTLY as they appear in the PDF
    6. If no explanation is found, set explanation_source to "generated"
    7. Set is_complete to false if any part of the question seems missing
    8. Check question numbers for sequence gaps
    9. Look for split questions across sections
    10. Handle multi-part questions properly
    11. DO NOT SKIP ANY QUESTIONS - Extract all questions from the text
    """
    
    try:
        logging.info("Sending text to Gemini for question extraction")
        
        # Split text into smaller chunks if it's too long
        max_chunk_size = 12000  # Adjust based on model's context window
        text_chunks = []
        
        if len(text) > max_chunk_size:
            # Split on question boundaries
            chunks = re.split(r'(?m)(?=^\d+\.\s)', text)
            current_chunk = ""
            
            for chunk in chunks:
                if len(current_chunk) + len(chunk) < max_chunk_size:
                    current_chunk += chunk
                else:
                    if current_chunk:
                        text_chunks.append(current_chunk)
                    current_chunk = chunk
            
            if current_chunk:
                text_chunks.append(current_chunk)
        else:
            text_chunks = [text]
        
        all_questions = []
        processed_numbers = set()
        
        # Process each chunk
        for chunk_idx, chunk in enumerate(text_chunks):
            logging.info(f"Processing chunk {chunk_idx + 1} of {len(text_chunks)}")
            
            # Try multiple attempts if needed
            for attempt in range(retry_count):
                try:
                    response = model.generate_content([system_prompt, chunk])
                    
                    if response.text:
                        # Parse JSON response
                        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.text)
                        json_content = json_match.group(1) if json_match else response.text
                        json_content = json_content.strip()
                        
                        if json_content.startswith('```') and json_content.endswith('```'):
                            json_content = json_content[3:-3].strip()
                        
                        questions = json.loads(json_content)
                        
                        # Ensure we have a list of questions
                        if not isinstance(questions, list):
                            questions = [questions] if isinstance(questions, dict) else []
                        
                        # Enhanced validation and cleanup
                        validated_questions = []
                        chunk_numbers = set()
                        
                        for q in questions:
                            # Skip if no question text
                            if not q.get('question', '').strip():
                                continue
                            
                            # Track question numbers
                            if q.get('question_number'):
                                q_num = int(re.sub(r'\D', '', q['question_number']))
                                if q_num in processed_numbers:
                                    continue  # Skip duplicates
                                processed_numbers.add(q_num)
                                chunk_numbers.add(q_num)
                            
                            # Detect match-type questions
                            is_match = bool(
                                re.search(r'match.*list|list.*match', q['question'].lower(), re.IGNORECASE) or
                                (('List I' in q['question'] or 'List 1' in q['question']) and 
                                 ('List II' in q['question'] or 'List 2' in q['question']))
                            )
                            
                            q['is_match_type'] = is_match
                            
                            # Special handling for match-type questions
                            if is_match:
                                # Clean up the question formatting
                                q['question'] = re.sub(r'\s+', ' ', q['question'])
                                q['question'] = q['question'].replace(' List ', '\nList ')
                                
                                # Extract and format code combinations
                                code_pattern = r'([A-D]-\d+(?:\s*,\s*[A-D]-\d+)*)'
                                codes = re.findall(code_pattern, chunk)
                                
                                # Assign code combinations to options
                                for i, opt in enumerate(['a', 'b', 'c', 'd']):
                                    key = f'option_{opt}'
                                    if i < len(codes):
                                        code = codes[i]
                                        code = re.sub(r'\s+', ' ', code)
                                        code = re.sub(r'\s*,\s*', ', ', code)
                                        q[key] = code
                                    else:
                                        q[key] = ''
                            
                            # Clean up fields
                            q['question_number'] = q.get('question_number', '').strip()
                            q['question'] = q['question'].strip()
                            q['correct_answer'] = q.get('correct_answer', '').strip().upper()
                            q['answer_text'] = q.get('answer_text', '').strip()
                            
                            # Handle explanation
                            explanation = q.get('explanation', '').strip()
                            if explanation:
                                # Clean up explanation formatting while preserving content
                                explanation = re.sub(r'\s+', ' ', explanation)
                                explanation = explanation.replace(' . ', '. ')
                                q['explanation'] = explanation
                                q['explanation_source'] = q.get('explanation_source', 'pdf')
                            else:
                                q['explanation'] = ''
                                q['explanation_source'] = 'generated'
                            
                            # Check if question is complete
                            q['is_complete'] = bool(
                                q.get('question', '').strip() and
                                q.get('option_a', '').strip() and
                                q.get('option_b', '').strip() and
                                q.get('option_c', '').strip() and
                                q.get('option_d', '').strip()
                            )
                            
                            validated_questions.append(q)
                        
                        # Check for missing questions in this chunk
                        if chunk_numbers and expected_questions:
                            chunk_expected = set(n for n in expected_questions if any(
                                str(n) in chunk for chunk in text_chunks[chunk_idx:chunk_idx+1]
                            ))
                            missing = chunk_expected - chunk_numbers
                            if missing:
                                logging.warning(f"Missing questions in chunk {chunk_idx + 1}: {missing}")
                                if attempt < retry_count - 1:
                                    continue  # Try another attempt if questions are missing
                        
                        all_questions.extend(validated_questions)
                        break  # Success, move to next chunk
                        
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed for chunk {chunk_idx + 1}: {str(e)}")
                    if attempt < retry_count - 1:
                        time.sleep(delay)
                        continue
                    break
        
        # Final validation of all extracted questions
        if expected_questions:
            extracted_numbers = {int(re.sub(r'\D', '', q['question_number'])) for q in all_questions if q.get('question_number')}
            missing_final = set(expected_questions) - extracted_numbers
            if missing_final:
                logging.error(f"Failed to extract questions: {missing_final}")
        
        logging.info(f"Extracted and validated {len(all_questions)} questions")
        return all_questions
        
    except Exception as e:
        logging.error(f"Error in question extraction: {str(e)}")
        return []

def improve_questions(questions: List[Dict[str, str]], api_key: str) -> List[Dict[str, str]]:
    """
    Improve the extracted questions using Gemini AI.
    """
    if not questions:
        logging.warning("No questions to improve")
        return []
        
    # Configure the Gemini API
    genai.configure(api_key=api_key)
    
    # Set up the model with moderate temperature for improvements
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config
    )
    
    # Create a system prompt for question improvement
    system_prompt = """
    Improve the following questions while maintaining their original structure and meaning.
    
    For ALL questions:
    1. Fix any formatting or grammatical issues
    2. Ensure the question is clear and complete
    3. Make sure all options are properly formatted
    4. Verify the correct answer is clearly indicated
    5. If explanation exists in PDF (explanation_source = "pdf"):
       - Keep the original explanation
       - Fix only formatting and grammar issues
       - DO NOT add or remove content
       - Preserve the original structure and points
    6. If no explanation exists (explanation_source = "generated"):
       - Generate a comprehensive explanation
    
    For match-type questions:
    1. Keep both lists complete and properly formatted
    2. Ensure code combinations are correctly formatted
    3. Maintain the exact structure of lists and codes
    
    For NEW explanations (only if explanation_source = "generated"):
    
    For DRUG-related questions:
    1. Provide a comprehensive explanation that includes:
       CORRECT ANSWER:
       - Drug classification and mechanism
       - Main therapeutic uses
       - Common adverse effects
       - Important contraindications
       
       INCORRECT OPTIONS:
       For each incorrect option:
       - Why this option is incorrect
       - Key differences from correct answer
       - Clinical implications
    
    For SURGICAL questions:
    1. Provide a comprehensive explanation that includes:
       CORRECT ANSWER:
       - Procedure overview
       - Main indications
       - Key surgical steps
       - Important complications
       
       INCORRECT OPTIONS:
       For each incorrect option:
       - Why this approach is incorrect
       - Clinical implications
       - When it might be considered
    
    For OTHER questions:
    1. Provide a clear explanation that includes:
       CORRECT ANSWER:
       - Main concept explanation
       - Clinical relevance
       - Supporting evidence
       
       INCORRECT OPTIONS:
       For each incorrect option:
       - Why it is incorrect
       - Common misconceptions
       - Clinical implications
    
    Return the improved questions in the same JSON format, preserving all fields including explanation_source.
    
    IMPORTANT:
    1. Preserve original explanations from PDF
    2. Only generate new explanations when none exist
    3. Keep technical terms and specific details intact
    4. Use clear paragraph breaks between sections
    5. Format sections with clear headers
    6. Number incorrect options clearly
    """
    
    try:
        # Convert questions to JSON string
        questions_json = json.dumps(questions, indent=2)
        
        # Send to Gemini for improvement
        logging.info("Improving questions with Gemini")
        response = model.generate_content([system_prompt, questions_json])
        
        if response.text:
            try:
                # Parse JSON response
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.text)
                json_content = json_match.group(1) if json_match else response.text
                json_content = json_content.strip()
                
                if json_content.startswith('```') and json_content.endswith('```'):
                    json_content = json_content[3:-3].strip()
                
                improved_questions = json.loads(json_content)
                
                # Ensure we have a list of questions
                if not isinstance(improved_questions, list):
                    improved_questions = [improved_questions] if isinstance(improved_questions, dict) else []
                
                # Validate and clean up improved questions
                validated_questions = []
                for q in improved_questions:
                    if not q.get('question', '').strip():
                        continue
                        
                    # Clean up fields
                    q['question_number'] = q.get('question_number', '').strip()
                    q['question'] = q['question'].strip()
                    
                    # Ensure proper option formatting
                    for opt in ['a', 'b', 'c', 'd']:
                        key = f'option_{opt}'
                        q[key] = q.get(key, '').strip()
                    
                    q['correct_answer'] = q.get('correct_answer', '').strip().upper()
                    q['answer_text'] = q.get('answer_text', '').strip()
                    
                    # Format explanation with proper line breaks and sections
                    explanation = q.get('explanation', '').strip()
                    if explanation:
                        if q.get('explanation_source') == 'pdf':
                            # Minimal formatting for PDF explanations
                            explanation = re.sub(r'\s+', ' ', explanation)
                            explanation = explanation.replace(' . ', '. ')
                            explanation = explanation.replace(' , ', ', ')
                        else:
                            # Full formatting for generated explanations
                            explanation = re.sub(r'([.!?])\s+(?=[A-Z])', r'\1\n\n', explanation)
                            explanation = re.sub(r'(?m)^(CORRECT ANSWER|INCORRECT OPTIONS|Incorrect Option \d+):', r'\n\1:\n', explanation)
                        
                        q['explanation'] = explanation
                    
                    validated_questions.append(q)
                
                logging.info(f"Successfully improved {len(validated_questions)} questions")
                return validated_questions
                
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse improved questions: {str(e)}")
                return questions
        else:
            logging.warning("Empty response from Gemini")
            return questions
            
    except Exception as e:
        logging.error(f"Error improving questions: {str(e)}")
        return questions

def process_pdf_page(pdf_path: str, page_num: int, api_key: str, 
                    retry_count: int = 3, delay: int = 5, temp_dir: str = "temp_images") -> List[Dict[str, str]]:
    """
    Process a single page of a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        page_num: Page number to process (1-indexed)
        api_key: Gemini API key
        retry_count: Number of retry attempts
        delay: Delay between retries in seconds
        temp_dir: Directory to save temporary images
    
    Returns:
        List of extracted questions
    """
    try:
        # Convert the specific page to an image
        image_paths = convert_pdf_to_images(
            pdf_path=pdf_path,
            start_page=page_num,
            max_pages=1,
            temp_dir=temp_dir
        )
        
        if not image_paths:
            logging.error(f"Failed to convert page {page_num} to image")
            return []
        
        image_path = image_paths[0]
        
        # Extract text from the image
        extracted_text = extract_text_with_gemini(
            image_path=image_path,
            api_key=api_key,
            retry_count=retry_count,
            delay=delay
        )
        
        if not extracted_text:
            logging.error(f"Failed to extract text from page {page_num}")
            return []
        
        # Extract questions from the text
        questions = extract_questions_with_gemini(
            text=extracted_text,
            api_key=api_key,
            retry_count=retry_count,
            delay=delay
        )
        
        # Add page number to each question
        for q in questions:
            q['page_number'] = page_num
        
        logging.info(f"Extracted {len(questions)} questions from page {page_num}")
        return questions
    except Exception as e:
        logging.error(f"Error processing page {page_num}: {str(e)}")
        return []

def main():
    """Main function to process the PDF and extract questions."""
    parser = argparse.ArgumentParser(description="Extract multiple-choice questions from a PDF file")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output", default="extracted_questions.xlsx", help="Output Excel file")
    parser.add_argument("--start", type=int, default=1, help="First page to process (1-indexed)")
    parser.add_argument("--max-pages", type=int, help="Maximum number of pages to process")
    parser.add_argument("--api-key", help="Gemini API key (optional, will use .env if provided)")
    parser.add_argument("--retry-count", type=int, default=3, help="Number of retries for API calls")
    parser.add_argument("--delay", type=int, default=10, help="Delay between API calls in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files")
    
    args = parser.parse_args()
    
    # Set up logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug mode enabled")
    
    # Use API key from arguments or environment
    api_key = args.api_key or GEMINI_API_KEY
    if not api_key:
        logging.error("No Gemini API key provided. Please set GEMINI_API_KEY in .env or provide --api-key")
        return
    
    # Create a temporary directory for images
    temp_dir = tempfile.mkdtemp(prefix="pdf_questions_")
    logging.info(f"Created temporary directory: {temp_dir}")
    
    try:
        # Convert PDF to images
        image_paths = convert_pdf_to_images(
            pdf_path=args.pdf_path,
            start_page=args.start,
            max_pages=args.max_pages,
            temp_dir=temp_dir
        )
        
        if not image_paths:
            logging.error("Failed to convert PDF to images")
            return
        
        # Process each page
        all_questions = []
        for i, image_path in enumerate(image_paths):
            page_num = args.start + i
            logging.info(f"Processing page {page_num}")
            
            # Extract questions from the page
            questions = process_pdf_page(
                pdf_path=args.pdf_path,
                page_num=page_num,
                api_key=api_key,
                retry_count=args.retry_count,
                delay=args.delay,
                temp_dir=temp_dir
            )
            
            all_questions.extend(questions)
            
            # Add a delay between pages to avoid rate limits
            if i < len(image_paths) - 1:
                logging.info(f"Waiting {args.delay} seconds before processing next page")
                time.sleep(args.delay)
        
        # Improve questions
        if all_questions:
            logging.info(f"Improving {len(all_questions)} extracted questions")
            improved_questions = improve_questions(all_questions, api_key)
            
            # Create a DataFrame from the questions
            df = pd.DataFrame(improved_questions)
            
            # Save to Excel
            df.to_excel(args.output, index=False)
            logging.info(f"Saved {len(improved_questions)} questions to {args.output}")
        else:
            logging.warning("No questions extracted from the PDF")
    
    finally:
        # Clean up temporary files
        if not args.keep_temp:
            try:
                import shutil
                shutil.rmtree(temp_dir)
                logging.info(f"Removed temporary directory: {temp_dir}")
            except Exception as e:
                logging.error(f"Failed to remove temporary directory: {str(e)}")

if __name__ == "__main__":
    main() 