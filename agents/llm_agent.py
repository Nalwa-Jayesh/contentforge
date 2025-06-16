import asyncio
from typing import Tuple, Optional, Dict, Any
from google import genai
from google.genai import types
from utils.logger import logger
from config import Config

class LLMAgent:
    """Handles AI writing and reviewing using Google's Gemini"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Gemini API key is required")
        
        # Configure Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Generation config
        self.generation_config = types.GenerateContentConfig(
            max_output_tokens=Config.MAX_TOKENS,
            temperature=Config.TEMPERATURE,
            top_p=0.8,
            top_k=40
        )
        
        logger.info(f"LLM Agent initialized with model: gemini-2.0-flash")
    
    async def generate_content(self, title: str, research_content: str, target_length: int, 
                             description: str = "") -> str:
        """
        Generate content based on research and parameters
        
        Args:
            title: Title of the chapter
            research_content: Research content to base generation on
            target_length: Target length in words
            description: Optional description of the chapter
            
        Returns:
            Generated content
        """
        logger.info(f"Generating content for chapter: {title}")
        
        # Build the prompt
        prompt = f"""
        You are an expert AI Writer tasked with creating engaging content based on research.
        
        Chapter Title: {title}
        Target Length: {target_length} words
        Description: {description}
        
        Research Content:
        {research_content[:2000]}...
        
        Requirements:
        1. Create engaging, well-structured content
        2. Maintain accuracy with the research
        3. Use clear, professional language
        4. Include relevant details and examples
        5. Target approximately {target_length} words
        
        Please provide your generated content:
        """
        
        try:
            # Generate content using the client
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.0-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    max_output_tokens=target_length * 4,  # Approximate tokens per word
                    temperature=self.generation_config.temperature,
                    top_p=0.8,
                    top_k=40
                )
            )
            
            if not response.text:
                logger.warning("Empty response from AI writer")
                return ""
            
            generated_content = response.text.strip()
            logger.info(f"Content generation completed: {len(generated_content)} characters")
            return generated_content
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return ""
    
    async def spin_content(self, original_content: str, instructions: str = "", 
                          style_preferences: Optional[Dict[str, Any]] = None) -> str:
        """
        AI Writer: Transform original content with creative spin
        
        Args:
            original_content: The source content to transform
            instructions: Specific instructions for the transformation
            style_preferences: Style and tone preferences
            
        Returns:
            Transformed content
        """
        logger.info("Starting AI content spinning")
        
        # Build the prompt
        prompt = self._build_writer_prompt(original_content, instructions, style_preferences)
        
        try:
            # Generate content using the client
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.0-flash",
                contents=[prompt],
                config=self.generation_config
            )
            
            if not response.text:
                logger.warning("Empty response from AI writer")
                return original_content
            
            transformed_content = response.text.strip()
            logger.info(f"AI writing completed: {len(transformed_content)} characters generated")
            return transformed_content
            
        except Exception as e:
            logger.error(f"Error in AI writing: {str(e)}")
            # Return original content as fallback
            return original_content
    
    async def review_content(self, content: str, original_content: str, 
                           review_focus: Optional[str] = None) -> Dict[str, Any]:
        """
        AI Reviewer: Review and suggest improvements
        
        Args:
            content: The content to review
            original_content: Original source content for reference
            review_focus: Specific aspects to focus on during review
            
        Returns:
            Dictionary containing review results
        """
        logger.info("Starting AI content review")
        
        # Build the review prompt
        prompt = self._build_reviewer_prompt(content, original_content, review_focus)
        
        try:
            # Generate content using the client
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model="gemini-2.0-flash",
                contents=[prompt],
                config=self.generation_config
            )
            
            if not response.text:
                logger.warning("Empty response from AI reviewer")
                return {
                    'improved_content': content,
                    'score': 0,
                    'suggestions': ["Review failed: No response from AI"],
                    'improvements_made': []
                }
            
            # Parse the response to extract revised content and feedback
            review_result = self._parse_review_response(response.text)
            
            logger.info(f"AI review completed with score: {review_result.get('score', 0)}")
            return review_result
            
        except Exception as e:
            logger.error(f"Error in AI review: {str(e)}")
            return {
                'improved_content': content,
                'score': 0,
                'suggestions': [f"Review failed due to technical error: {str(e)}"],
                'improvements_made': []
            }
    
    def _parse_review_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the AI reviewer's response"""
        try:
            improved_content = ""
            suggestions = []
            improvements_made = []
            score = 0

            # Look for revised content between markers
            begin_marker = "---BEGIN REVISED CONTENT---"
            end_marker = "---END REVISED CONTENT---"

            begin_index = response_text.find(begin_marker)
            end_index = response_text.find(end_marker)

            if begin_index != -1 and end_index != -1 and begin_index < end_index:
                # Extract content between markers
                improved_content = response_text[begin_index + len(begin_marker):end_index].strip()
                # Remove the marked section from the response_text for further parsing
                response_text = response_text[:begin_index] + response_text[end_index + len(end_marker):]
            else:
                # Fallback to original logic if markers are not found or malformed
                sections = response_text.split('\n\n')
                if sections:
                    improved_content = sections[0].strip()
                    response_text = '\n\n'.join(sections[1:])

            # Parse the rest of the response for review details
            sections = response_text.split('\n\n')
            
            for section in sections:
                if section.startswith('Score:'):
                    try:
                        score = int(section.split(':')[1].strip())
                    except:
                        score = 0
                elif section.startswith('Suggestions:'):
                    suggestions = [s.strip() for s in section.split('\n')[1:] if s.strip()]
                elif section.startswith('Improvements:'):
                    improvements_made = [i.strip() for i in section.split('\n')[1:] if i.strip()]
            
            return {
                'improved_content': improved_content,
                'score': score,
                'suggestions': suggestions,
                'improvements_made': improvements_made
            }
            
        except Exception as e:
            logger.error(f"Error parsing review response: {str(e)}")
            return {
                'improved_content': response_text,
                'score': 0,
                'suggestions': ["Failed to parse review response"],
                'improvements_made': []
            }
    
    async def generate_summary(self, content: str, max_length: int = 200) -> str:
        """Generate a summary of the content"""
        prompt = f"""
        Please provide a concise summary of the following content in no more than {max_length} words:
        
        Content:
        {content[:2000]}...
        
        Summary:
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=Config.AI_MODEL,
                contents=prompt,
                generation_config={
                    "max_output_tokens": max_length * 2,  # Account for token vs word difference
                    "temperature": 0.3
                }
            )
            
            return response.text.strip() if response.text else "Summary generation failed"
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Summary generation failed"
    
    async def analyze_content_quality(self, content: str) -> Dict[str, Any]:
        """Analyze content quality and provide metrics"""
        prompt = f"""
        Analyze the following content and provide a quality assessment with scores (1-10):
        
        Content:
        {content[:1500]}...
        
        Please rate and provide brief comments on:
        1. Readability (1-10)
        2. Engagement (1-10)
        3. Coherence (1-10)
        4. Style (1-10)
        5. Overall Quality (1-10)
        
        Format your response as:
        Readability: [score] - [brief comment]
        Engagement: [score] - [brief comment]
        Coherence: [score] - [brief comment]
        Style: [score] - [brief comment]
        Overall: [score] - [brief comment]
        """
        
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=Config.AI_MODEL,
                contents=prompt,
                generation_config={
                    "max_output_tokens": 500,
                    "temperature": 0.2
                }
            )
            
            if response.text:
                return self._parse_quality_analysis(response.text)
            else:
                return self._default_quality_analysis()
                
        except Exception as e:
            logger.error(f"Error analyzing content quality: {str(e)}")
            return self._default_quality_analysis()
    
    def _build_writer_prompt(self, original_content: str, instructions: str, 
                           style_preferences: Optional[Dict[str, Any]]) -> str:
        """Build the prompt for the AI writer"""
        base_instructions = """
        You are an expert AI Writer tasked with creating a creative adaptation of literary content.
        Your goal is to transform the source material while preserving its essence and improving its engagement.
        """
        
        style_guide = ""
        if style_preferences:
            style_guide = f"""
        Style Preferences:
        - Tone: {style_preferences.get('tone', 'engaging and literary')}
        - Perspective: {style_preferences.get('perspective', 'maintain original')}
        - Length: {style_preferences.get('length', 'similar to original')}
        - Target Audience: {style_preferences.get('audience', 'general readers')}
        """
        
        custom_instructions = f"\nSpecific Instructions: {instructions}" if instructions else ""
        
        prompt = f"""
        {base_instructions}
        {style_guide}
        {custom_instructions}
        
        Original Content to Transform:
        {original_content}
        
        Instructions for Creative Adaptation:
        1.  **COMPLETELY REWRITE** the original content. Do not merely rephrase or make minor edits. Aim for a substantial transformation while preserving the core narrative, themes, and character development.
        2.  Use fresh, imaginative, and highly engaging language. Elevate the prose to a more literary and captivating style.
        3.  Maintain the original structure and logical flow of the narrative.
        4.  Ensure the adaptation is original and truly transformative, offering a new perspective or enhanced readability.
        5.  Keep the approximate length similar to the original, but prioritize quality and transformation over exact word count.
        
        **OUTPUT ONLY THE CREATIVELY ADAPTED CONTENT. DO NOT INCLUDE ANY INTRODUCTORY PHRASES, EXPLANATIONS, OR CONVERSATIONAL TEXT.**
        
        Please provide your creative adaptation:
        """
        
        return prompt
    
    def _build_reviewer_prompt(self, content: str, original_content: str, 
                             review_focus: Optional[str]) -> str:
        """Build the prompt for the AI reviewer"""
        focus_area = review_focus or "overall quality, narrative flow, and engagement"
        
        prompt = f"""
        You are an expert AI Reviewer and Editor. Your task is to review and improve the following adapted content.
        
        Focus Areas: {focus_area}
        
        Original Source Content (for reference):
        {original_content[:1000]}...
        
        Adapted Content to Review:
        {content}
        
        Please provide:
        1. A detailed review of the content
        2. Specific suggestions for improvement
        3. A revised version incorporating your suggestions
        
        Your review should focus on:
        - Content accuracy and faithfulness to the original
        - Writing style and engagement
        - Structure and flow
        - Grammar and mechanics
        - Overall effectiveness
        
        ---BEGIN REVISED CONTENT---
        
        ---END REVISED CONTENT---
        
        Please provide:
        1. A detailed review of the content
        2. Specific suggestions for improvement
        3. A revised version incorporating your suggestions (THIS SHOULD BE PLACED BETWEEN ---BEGIN REVISED CONTENT--- AND ---END REVISED CONTENT--- MARKERS ABOVE)
        """
        
        return prompt