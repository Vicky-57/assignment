import openai
import json
import re
import logging
from django.conf import settings
from django.core.cache import cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from products.models import Product, ProductCategory
from .models import UserSession, ChatInteraction

logger = logging.getLogger(__name__)
openai.api_key = settings.OPENAI_API_KEY

class ShowroomAIService:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.product_vectors = None
        self.products = None
        self._initialize_product_vectors()
        
        # Budget categories for context
        self.budget_categories = {
            'kitchen': {
                'low': {'min': 5000, 'max': 15000, 'features': 'Cosmetic upgrades, DIY work, repainting, refacing cabinets, basic appliances'},
                'medium': {'min': 15000, 'max': 30000, 'features': 'Semi-custom cabinets, new countertops, mid-range appliances and finishes'},
                'high': {'min': 30000, 'max': 150000, 'features': 'Custom cabinets, structural changes, high-end materials & appliances, full redesign'}
            },
            'bathroom': {
                'low': {'min': 2500, 'max': 6500, 'features': 'Cosmetic changes, painting, basic fixtures, DIY upgrades'},
                'medium': {'min': 7000, 'max': 25000, 'features': 'New fixtures, cabinets, moderate tile/finish upgrades, professional installation'},
                'high': {'min': 30000, 'max': 80000, 'features': 'Complete overhaul, luxury finishes, expansions, custom work'}
            }
        }
        
        # Essential questions only - keep it focused
        self.essential_questions = {
            'bathroom': ['room_type', 'style', 'room_size', 'budget_range'],
            'kitchen': ['room_type', 'style', 'room_size', 'budget_range']
        }
    
    def _initialize_product_vectors(self):
        """Initialize product vectors with caching"""
        cache_key = 'product_vectors_cache'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            self.products, self.product_vectors, self.vectorizer = cached_data
            logger.info(f"Loaded {len(self.products)} products from cache")
            return
            
        try:
            self.products = list(Product.objects.filter(
                is_available=True,
                category__name__in=['Bathroom', 'Kitchen', 'bathroom', 'kitchen']
            ))
            
            if self.products:
                product_texts = []
                for product in self.products:
                    text_parts = [product.name]
                    
                    for attr in ['description', 'style', 'material', 'color', 'category']:
                        value = getattr(product, attr, None)
                        if value:
                            text_parts.append(str(value))
                    
                    product_texts.append(' '.join(text_parts))
                
                if product_texts:
                    self.product_vectors = self.vectorizer.fit_transform(product_texts)
                    cache.set(cache_key, (self.products, self.product_vectors, self.vectorizer), 3600)
                    logger.info(f"Initialized vectors for {len(product_texts)} products")
                    
        except Exception as e:
            logger.error(f"Error initializing product vectors: {str(e)}")
            self.products = []
            self.product_vectors = None
    
    def process_user_message(self, message, session_id):
        """Enhanced message processing with budget awareness"""
        try:
            session = UserSession.objects.get(id=session_id)
            
            # Get conversation context
            conversation_context = self._get_conversation_context(session)
            
            # Determine conversation strategy
            should_ask_questions = self._should_continue_questioning(session, message)
            
            if should_ask_questions:
                ai_response = self._generate_targeted_question(session, message, conversation_context)
            else:
                ai_response = self._generate_final_response(session, message, conversation_context)
            
            # Extract preferences with budget awareness
            preferences = self._extract_preferences_enhanced(message, ai_response, session.preferences)
            
            # Update session
            self._update_session_preferences(session, preferences)
            
            # Get recommendations when appropriate
            product_recommendations = []
            if self._should_provide_recommendations(session, message):
                product_recommendations = self._get_budget_aware_products(message, session.preferences)
            
            # Save interaction selectively
            if self._should_save_interaction(session):
                self._save_interaction(session, message, ai_response, preferences)
            
            return {
                'response': ai_response,
                'preferences': preferences,
                'product_suggestions': product_recommendations,
                'session_phase': self._get_session_phase(session),
                'progress': self._calculate_progress(session)
            }
            
        except UserSession.DoesNotExist:
            raise
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return self._error_response(str(e))
    
    def _get_conversation_context(self, session):
        """Get conversation context efficiently"""
        cache_key = f'conversation_context_{session.id}'
        context = cache.get(cache_key)
        
        if not context:
            recent_interactions = ChatInteraction.objects.filter(
                session=session
            ).order_by('-timestamp')[:2]  # Reduced to 2 for simplicity
            
            context = {
                'message_count': ChatInteraction.objects.filter(session=session).count(),
                'recent_messages': [
                    {'user': i.user_message, 'ai': i.ai_response} 
                    for i in reversed(recent_interactions)
                ],
                'has_budget_amount': bool(session.budget_amount),
                'budget_info': self._get_budget_context(session)
            }
            
            cache.set(cache_key, context, 300)
        
        return context
    
    def _get_budget_context(self, session):
        """Get budget context for AI prompts"""
        if not session.budget_amount or not session.room_type:
            return ""
        
        room_type = session.room_type
        budget_range = session.budget_range
        amount = float(session.budget_amount)
        
        if room_type in self.budget_categories and budget_range in self.budget_categories[room_type]:
            category_info = self.budget_categories[room_type][budget_range]
            return f"Budget: ${amount:,.0f} ({budget_range} range for {room_type}). Features: {category_info['features']}"
        
        return f"Budget: ${amount:,.0f}"
    
    def _should_continue_questioning(self, session, message):
        """Simplified questioning logic - only ask essential questions"""
        prefs = session.preferences or {}
        room_type = prefs.get('room_type')
        
        if room_type not in ['bathroom', 'kitchen']:
            return True  # Still identifying room
        
        # Check essential questions only
        essential = self.essential_questions.get(room_type, [])
        missing_essential = [key for key in essential if not prefs.get(key)]
        
        message_count = ChatInteraction.objects.filter(session=session).count()
        
        # Stop questioning after 6 messages or when essentials are complete
        return len(missing_essential) > 0 and message_count < 6
    
    def _generate_targeted_question(self, session, message, context):
        """Generate targeted questions with budget awareness"""
        room_type = session.preferences.get('room_type', 'unknown')
        
        if room_type not in ['bathroom', 'kitchen']:
            return self._identify_room_type(message)
        
        # Get missing essential info
        essential = self.essential_questions.get(room_type, [])
        missing = [key for key in essential if not session.preferences.get(key)]
        
        if not missing:
            return self._generate_design_offer(session)
        
        # Create budget-aware system prompt
        budget_context = context.get('budget_info', '')
        system_prompt = self._create_budget_aware_prompt(room_type, missing[0], budget_context, session.preferences)
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.5,
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            return self._fallback_question(missing[0], room_type)
    
    def _generate_design_offer(self, session):
        """Offer to create design or continue chatting"""
        room_type = session.room_type or 'space'
        budget_info = ""
        
        if session.budget_amount:
            budget_info = f" with your ${session.budget_amount:,.0f} budget"
        
        return f"Perfect! I have all the details I need for your {room_type}{budget_info}. Would you like me to create a design recommendation now, or do you have any specific questions about materials, layouts, or features?"
    
    def _generate_final_response(self, session, message, context):
        """Generate final responses with budget context"""
        budget_context = context.get('budget_info', '')
        
        system_prompt = f"""You are a helpful interior design assistant specializing in bathrooms and kitchens.

Current user info: Room: {session.room_type}, Style: {session.style_preference}, Size: {session.room_size}
{budget_context}

Provide helpful, concise advice. Keep responses under 150 words and be conversational.
If discussing products or recommendations, always consider the user's budget range."""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI error: {str(e)}")
            return "I'd love to help you with your design project! What specific aspect would you like to discuss?"
    
    def _identify_room_type(self, message):
        """Identify room type from message"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['bathroom', 'bath', 'shower', 'toilet', 'vanity']):
            return "Great! I specialize in bathroom design. What's your budget range for this bathroom project?"
        elif any(word in message_lower for word in ['kitchen', 'cook', 'cabinet', 'countertop', 'appliance']):
            return "Perfect! I love working on kitchen projects. What's your budget for this kitchen renovation?"
        else:
            return "I specialize in bathroom and kitchen design! Which space are you looking to renovate, and what's your budget range?"
    
    def _create_budget_aware_prompt(self, room_type, missing_key, budget_context, current_prefs):
        """Create prompts that consider budget context"""
        base_prompt = f"""You are a {room_type} design specialist.

Current info: {json.dumps(current_prefs)}
{budget_context}

Focus on asking about: {missing_key}

Question guides:
- room_size: Ask about space dimensions (small/medium/large)
- style: Ask about preferred design style considering their budget
- budget_range: Ask for specific budget amount in dollars
- Any other: Ask relevant question about {missing_key}

Ask ONE focused question (1-2 sentences). Consider budget constraints if known."""
        
        return base_prompt
    
    def _fallback_question(self, missing_key, room_type):
        """Budget-aware fallback questions"""
        fallbacks = {
            'room_size': f"What size {room_type} are you working with - small, medium, or large?",
            'style': f"What design style do you prefer for your {room_type}?",
            'budget_range': f"What's your budget range for this {room_type} project?",
        }
        return fallbacks.get(missing_key, f"Tell me more about your {room_type} project!")
    
    def _extract_preferences_enhanced(self, user_message, ai_response, current_prefs):
        """Enhanced preference extraction with budget amount detection"""
        extracted = {}
        message_lower = user_message.lower()
        
        # Room type detection
        if 'bathroom' in message_lower or any(word in message_lower for word in ['bath', 'shower', 'toilet']):
            extracted['room_type'] = 'bathroom'
        elif 'kitchen' in message_lower or any(word in message_lower for word in ['cook', 'cabinet', 'counter']):
            extracted['room_type'] = 'kitchen'
        
        # Budget amount extraction (priority)
        budget_amount = self._extract_budget_amount(user_message)
        if budget_amount:
            extracted['budget_amount'] = budget_amount
        
        # Style detection
        styles = ['modern', 'traditional', 'contemporary', 'rustic', 'minimalist', 'industrial']
        for style in styles:
            if style in message_lower:
                extracted['style'] = style
                break
        
        # Size detection
        if any(word in message_lower for word in ['small', 'tiny', 'compact']):
            extracted['room_size'] = 'small'
        elif any(word in message_lower for word in ['large', 'big', 'spacious']):
            extracted['room_size'] = 'large'
        elif any(word in message_lower for word in ['medium', 'average']):
            extracted['room_size'] = 'medium'
        
        return extracted
    
    def _extract_budget_amount(self, message):
        """Extract specific budget amounts from message"""
        # Look for patterns like $50000, $50,000, 50000, 50k, etc.
        patterns = [
            r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $50,000 or 50,000
            r'\$?(\d+)k',  # 50k
            r'\$?(\d+)K',  # 50K
            r'(\d+)\s*(?:thousand|k)',  # 50 thousand
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                try:
                    if 'k' in message.lower() or 'thousand' in message.lower():
                        amount = float(match.replace(',', '')) * 1000
                    else:
                        amount = float(match.replace(',', ''))
                    
                    # Reasonable budget range check
                    if 1000 <= amount <= 500000:
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def _get_budget_aware_products(self, message, preferences):
        """Get products filtered by budget range"""
        if not self.products or self.product_vectors is None:
            return []
        
        try:
            # Build search with budget context
            search_terms = []
            room_type = preferences.get('room_type')
            style = preferences.get('style')
            budget_range = preferences.get('budget_range')
            
            if room_type:
                search_terms.append(room_type)
            if style:
                search_terms.append(style)
            if budget_range:
                search_terms.append(f"{budget_range} range")
            
            search_terms.append(message)
            search_query = ' '.join(search_terms)
            
            # Find similar products
            query_vector = self.vectorizer.transform([search_query])
            similarities = cosine_similarity(query_vector, self.product_vectors).flatten()
            
            # Get top products
            top_indices = similarities.argsort()[-3:][::-1]
            recommendations = []
            
            for idx in top_indices:
                if similarities[idx] > 0.1:
                    product = self.products[idx]
                    
                    # Filter by budget if available
                    if self._is_product_in_budget(product, preferences):
                        recommendations.append({
                            'id': str(product.id),
                            'name': product.name,
                            'style': getattr(product, 'style', ''),
                            'price': float(getattr(product, 'price', 0)),
                            'category': str(getattr(product, 'category', '')),
                            'relevance_score': round(float(similarities[idx]), 2)
                        })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Budget-aware product error: {str(e)}")
            return []
    
    def _is_product_in_budget(self, product, preferences):
        """Check if product fits within user's budget"""
        budget_amount = preferences.get('budget_amount')
        if not budget_amount:
            return True  # No budget constraint
        
        product_price = getattr(product, 'price', 0)
        if not product_price:
            return True  # No price info
        
        # Allow products up to 20% of total budget
        max_item_budget = float(budget_amount) * 0.2
        return float(product_price) <= max_item_budget
    
    # Keep other methods unchanged
    def _should_provide_recommendations(self, session, message):
        message_lower = message.lower()
        prefs = session.preferences or {}
        
        if any(word in message_lower for word in ['recommend', 'suggest', 'show', 'options', 'design']):
            return True
        
        if prefs.get('room_type') and prefs.get('style'):
            return True
        
        interaction_count = ChatInteraction.objects.filter(session=session).count()
        return interaction_count >= 4
    
    def _should_save_interaction(self, session):
        count = ChatInteraction.objects.filter(session=session).count()
        return count % 2 == 0
    
    def _save_interaction(self, session, user_message, ai_response, preferences):
        try:
            ChatInteraction.objects.create(
                session=session,
                user_message=user_message,
                ai_response=ai_response,
                extracted_preferences=preferences,
                intent=self._classify_intent(user_message)
            )
        except Exception as e:
            logger.error(f"Error saving interaction: {str(e)}")
    
    def _get_session_phase(self, session):
        prefs = session.preferences or {}
        room_type = prefs.get('room_type')
        
        if not room_type:
            return 'room_identification'
        elif room_type not in ['bathroom', 'kitchen']:
            return 'general'
        else:
            essential = self.essential_questions.get(room_type, [])
            missing = [key for key in essential if not prefs.get(key)]
            
            if len(missing) > 2:
                return 'basic_info'
            elif missing:
                return 'detailed_info'
            else:
                return 'design_ready'
    
    def _calculate_progress(self, session):
        prefs = session.preferences or {}
        room_type = prefs.get('room_type')
        
        if room_type not in ['bathroom', 'kitchen']:
            return 10 if room_type else 0
        
        essential = self.essential_questions.get(room_type, [])
        completed = sum(1 for key in essential if prefs.get(key))
        
        return min(90, (completed / len(essential)) * 100)
    
    def _update_session_preferences(self, session, new_preferences):
        if not new_preferences:
            return
            
        try:
            current_prefs = session.preferences or {}
            updated = False
            
            for key, value in new_preferences.items():
                if value and value != "null" and current_prefs.get(key) != value:
                    current_prefs[key] = value
                    updated = True
            
            if updated:
                session.preferences = current_prefs
                session.save()
                cache.delete(f'conversation_context_{session.id}')
                
        except Exception as e:
            logger.error(f"Error updating preferences: {str(e)}")
    
    def _classify_intent(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['price', 'cost', 'budget']):
            return 'pricing_inquiry'
        elif any(word in message_lower for word in ['recommend', 'suggest', 'show']):
            return 'product_recommendation'
        elif any(word in message_lower for word in ['style', 'design', 'look']):
            return 'style_discussion'
        else:
            return 'general_conversation'
    
    def _error_response(self, error_msg):
        return {
            'response': "I apologize, but I'm having some technical difficulties. Could you please try again?",
            'error': error_msg,
            'session_updated': False,
            'preferences': {},
            'product_suggestions': []
        }