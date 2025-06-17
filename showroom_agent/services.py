import openai
import json
import re
import logging
from django.conf import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from products.models import Product, ProductCategory
from .models import UserSession, ChatInteraction

# Set up logging
logger = logging.getLogger(__name__)

openai.api_key = settings.OPENAI_API_KEY

class ShowroomAIService:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.product_vectors = None
        self.products = None
        self._initialize_product_vectors()
    
    def _initialize_product_vectors(self):
        """Initialize product vectors for similarity search"""
        try:
            self.products = list(Product.objects.filter(is_available=True))
            if self.products:
                # Make sure products have search_text attribute
                product_texts = []
                for product in self.products:
                    if hasattr(product, 'search_text') and product.search_text:
                        product_texts.append(product.search_text)
                    else:
                        # Fallback to product name and description
                        text = f"{product.name} {getattr(product, 'description', '')} {getattr(product, 'style', '')}"
                        product_texts.append(text.strip())
                
                if product_texts:
                    self.product_vectors = self.vectorizer.fit_transform(product_texts)
                    logger.info(f"Initialized vectors for {len(product_texts)} products")
                else:
                    logger.warning("No product texts found for vectorization")
            else:
                logger.warning("No available products found")
        except Exception as e:
            logger.error(f"Error initializing product vectors: {str(e)}")
            self.products = []
            self.product_vectors = None
    
    def process_user_message(self, message, session_id):
        """Process user message and generate AI response with preference extraction"""
        try:
            # Get session with proper error handling
            try:
                session = UserSession.objects.get(id=session_id)
                logger.info(f"Processing message for session: {session_id}")
            except UserSession.DoesNotExist:
                logger.error(f"Session not found: {session_id}")
                raise UserSession.DoesNotExist("Session not found")
            
            # Create system prompt with context
            system_prompt = self._create_system_prompt(session)
            
            # Generate AI response
            try:
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                ai_response = response.choices[0].message.content
                logger.info("OpenAI response generated successfully")
                
            except Exception as openai_error:
                logger.error(f"OpenAI API error: {str(openai_error)}")
                ai_response = "I'm having trouble connecting to my language model. Please try again in a moment."
            
            # Extract preferences from the conversation
            preferences = self._extract_preferences(message, ai_response)
            
            # Update session preferences
            self._update_session_preferences(session, preferences)
            
            # Get product recommendations if relevant
            product_recommendations = self._get_relevant_products(message, session.preferences)
            
            # Save interaction
            try:
                interaction = ChatInteraction.objects.create(
                    session=session,
                    user_message=message,
                    ai_response=ai_response,
                    extracted_preferences=preferences,
                    intent=self._classify_intent(message)
                )
                logger.info(f"Interaction saved: {interaction.id}")
            except Exception as db_error:
                logger.error(f"Error saving interaction: {str(db_error)}")
                # Continue even if saving fails
            
            return {
                'response': ai_response,
                'preferences': preferences,
                'product_suggestions': product_recommendations,
                'session_updated': True
            }
            
        except UserSession.DoesNotExist:
            # Re-raise this specific exception
            raise
        except Exception as e:
            logger.error(f"Error processing user message: {str(e)}")
            return {
                'response': "I apologize, but I'm having trouble processing your request. Could you please try again?",
                'error': str(e),
                'session_updated': False
            }
    
    def _create_system_prompt(self, session):
        """Create contextual system prompt"""
        try:
            current_preferences = session.preferences if session.preferences else {}
            
            return f"""You are an expert interior design assistant helping users explore our virtual showroom. 

Current user preferences: {json.dumps(current_preferences)}

Your role:
1. Have natural, friendly conversations about interior design
2. Ask thoughtful questions to understand user preferences
3. Provide helpful information about design styles, materials, and concepts
4. Suggest products when relevant
5. Guide users toward making design decisions

Available styles: Modern, Traditional, Contemporary, Rustic, Minimalist, Industrial
Room types: Living Room, Bedroom, Kitchen, Dining Room, Bathroom, Office

Be conversational, helpful, and focus on understanding what the user wants for their space. Don't be overly salesy - focus on education and preference discovery."""

        except Exception as e:
            logger.error(f"Error creating system prompt: {str(e)}")
            return "You are a helpful interior design assistant. Help users with their design questions."

    def _extract_preferences(self, user_message, ai_response):
        """Extract design preferences from conversation using GPT"""
        try:
            extraction_prompt = f"""
Extract design preferences from this conversation. Return ONLY a JSON object with these keys (use null for unknown):

User: {user_message}
AI: {ai_response}

Extract:
{{
    "room_type": "living_room|bedroom|kitchen|dining_room|bathroom|office|null",
    "style": "modern|traditional|contemporary|rustic|minimalist|industrial|null", 
    "budget_range": "low|medium|high|null",
    "color_preference": "warm|cool|neutral|bold|null",
    "materials": ["wood", "metal", "fabric", "etc"],
    "specific_items": ["sofa", "table", "chair", "etc"]
}}
"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parse JSON response
            preferences_text = response.choices[0].message.content.strip()
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', preferences_text, re.DOTALL)
            if json_match:
                extracted_prefs = json.loads(json_match.group())
                logger.info(f"Extracted preferences: {extracted_prefs}")
                return extracted_prefs
            
        except Exception as e:
            logger.error(f"Preference extraction error: {str(e)}")
        
        return {}
    
    def _update_session_preferences(self, session, new_preferences):
        """Update session preferences with new information"""
        try:
            current_prefs = session.preferences if session.preferences else {}
            
            for key, value in new_preferences.items():
                if value and value != "null":
                    if key == "materials" or key == "specific_items":
                        # Merge lists
                        current_list = current_prefs.get(key, [])
                        if isinstance(value, list):
                            current_prefs[key] = list(set(current_list + value))
                    else:
                        current_prefs[key] = value
            
            session.preferences = current_prefs
            session.save()
            logger.info(f"Session preferences updated: {session.id}")
            
        except Exception as e:
            logger.error(f"Error updating session preferences: {str(e)}")
    
    def _classify_intent(self, message):
        """Classify user message intent"""
        try:
            message_lower = message.lower()
            
            if any(word in message_lower for word in ['price', 'cost', 'budget', 'expensive']):
                return 'pricing_inquiry'
            elif any(word in message_lower for word in ['recommend', 'suggest', 'show me', 'what do you think']):
                return 'product_recommendation'
            elif any(word in message_lower for word in ['style', 'design', 'look', 'aesthetic']):
                return 'style_discussion' 
            elif any(word in message_lower for word in ['room', 'space', 'area']):
                return 'room_planning'
            else:
                return 'general_conversation'
        except Exception as e:
            logger.error(f"Error classifying intent: {str(e)}")
            return 'general_conversation'
    
    def _get_relevant_products(self, message, preferences):
        """Get relevant products based on message and preferences"""
        if not self.products or self.product_vectors is None:
            logger.warning("No products or vectors available for recommendations")
            return []
        
        try:
            # Create search query from message and preferences
            search_terms = [message]
            if preferences and isinstance(preferences, dict):
                if preferences.get('style'):
                    search_terms.append(preferences['style'])
                if preferences.get('room_type'):
                    search_terms.append(preferences['room_type'].replace('_', ' '))
            
            search_query = ' '.join(search_terms)
            query_vector = self.vectorizer.transform([search_query])
            
            # Calculate similarities
            similarities = cosine_similarity(query_vector, self.product_vectors).flatten()
            
            # Get top 3 most similar products
            top_indices = similarities.argsort()[-3:][::-1]
            
            recommendations = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Minimum similarity threshold
                    product = self.products[idx]
                    recommendations.append({
                        'id': str(product.id),
                        'name': product.name,
                        'style': getattr(product, 'style', 'Unknown'),
                        'price': float(product.price) if hasattr(product, 'price') else 0.0,
                        'similarity': float(similarities[idx])
                    })
            
            logger.info(f"Generated {len(recommendations)} product recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Product recommendation error: {str(e)}")
            return []