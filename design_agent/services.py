import openai
import json
import random
from django.conf import settings
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from io import BytesIO
import pandas as pd
from products.models import Product
from showroom_agent.models import UserSession
from .models import LayoutTemplate, DesignRecommendation, ProductRecommendation
from datetime import datetime

openai.api_key = settings.OPENAI_API_KEY


def parse_room_dimensions(raw):
    if isinstance(raw, dict):
        return raw
    try:
        parts = raw.lower().replace(' ', '').split('x')
        if len(parts) == 3:
            return {
                'width': parts[0],
                'length': parts[1],
                'height': parts[2],
                'area_sqft': str(int(parts[0]) * int(parts[1]))
            }
    except:
        pass
    return {}

class DesignAIService:
    def __init__(self):
        self.layout_templates = self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize kitchen and bathroom templates only"""
        templates = {
            'kitchen_modern': {
                'name': 'Modern Kitchen',
                'room_type': 'kitchen',
                'style': 'modern',
                'dimensions': {'width': 12, 'height': 10, 'area_sqft': 120},
                'product_slots': [
                    {'name': 'kitchen_cabinet', 'category': 'Storage', 'required': True, 'quantity': 1, 'budget_percentage': 40},
                    {'name': 'kitchen_island', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 25},
                    {'name': 'bar_stools', 'category': 'Seating', 'required': False, 'quantity': 3, 'budget_percentage': 15},
                    {'name': 'pendant_lights', 'category': 'Lighting', 'required': True, 'quantity': 3, 'budget_percentage': 12},
                    {'name': 'kitchen_appliances', 'category': 'Appliances', 'required': True, 'quantity': 1, 'budget_percentage': 8},
                ],
                'color_palette': ['#FFFFFF', '#2C3E50', '#3498DB', '#ECF0F1'],
                'estimated_budget': 8000
            },
            'kitchen_traditional': {
                'name': 'Traditional Kitchen',
                'room_type': 'kitchen',
                'style': 'traditional',
                'dimensions': {'width': 14, 'height': 11, 'area_sqft': 154},
                'product_slots': [
                    {'name': 'wooden_cabinets', 'category': 'Storage', 'required': True, 'quantity': 1, 'budget_percentage': 45},
                    {'name': 'dining_table', 'category': 'Tables', 'required': False, 'quantity': 1, 'budget_percentage': 20},
                    {'name': 'dining_chairs', 'category': 'Seating', 'required': False, 'quantity': 4, 'budget_percentage': 15},
                    {'name': 'chandelier', 'category': 'Lighting', 'required': True, 'quantity': 1, 'budget_percentage': 12},
                    {'name': 'kitchen_appliances', 'category': 'Appliances', 'required': True, 'quantity': 1, 'budget_percentage': 8},
                ],
                'color_palette': ['#8B4513', '#F5DEB3', '#CD853F', '#FFFFFF'],
                'estimated_budget': 9500
            },
            
            'bathroom_modern': {
                'name': 'Modern Bathroom',
                'room_type': 'bathroom',
                'style': 'modern',
                'dimensions': {'width': 8, 'height': 6, 'area_sqft': 48},
                'product_slots': [
                    {'name': 'vanity_cabinet', 'category': 'Storage', 'required': True, 'quantity': 1, 'budget_percentage': 35},
                    {'name': 'mirror', 'category': 'Accessories', 'required': True, 'quantity': 1, 'budget_percentage': 15},
                    {'name': 'shower_fixtures', 'category': 'Fixtures', 'required': True, 'quantity': 1, 'budget_percentage': 25},
                    {'name': 'bathroom_lighting', 'category': 'Lighting', 'required': True, 'quantity': 2, 'budget_percentage': 15},
                    {'name': 'storage_shelves', 'category': 'Storage', 'required': False, 'quantity': 2, 'budget_percentage': 10},
                ],
                'color_palette': ['#FFFFFF', '#E8E8E8', '#4A90E2', '#2C3E50'],
                'estimated_budget': 4500
            },
            'bathroom_luxury': {
                'name': 'Luxury Bathroom',
                'room_type': 'bathroom',
                'style': 'luxury',
                'dimensions': {'width': 10, 'height': 8, 'area_sqft': 80},
                'product_slots': [
                    {'name': 'double_vanity', 'category': 'Storage', 'required': True, 'quantity': 1, 'budget_percentage': 30},
                    {'name': 'luxury_mirror', 'category': 'Accessories', 'required': True, 'quantity': 1, 'budget_percentage': 12},
                    {'name': 'premium_fixtures', 'category': 'Fixtures', 'required': True, 'quantity': 1, 'budget_percentage': 35},
                    {'name': 'luxury_lighting', 'category': 'Lighting', 'required': True, 'quantity': 3, 'budget_percentage': 15},
                    {'name': 'towel_warmer', 'category': 'Accessories', 'required': False, 'quantity': 1, 'budget_percentage': 8},
                ],
                'color_palette': ['#F8F8FF', '#DAA520', '#2F4F4F', '#FFFFFF'],
                'estimated_budget': 12000
            }
        }
        
        # Create templates in database if they don't exist
        for key, template_data in templates.items():
            template, created = LayoutTemplate.objects.get_or_create(
                name=template_data['name'],
                room_type=template_data['room_type'],
                style=template_data['style'],
                defaults={
                    'dimensions': template_data['dimensions'],
                    'product_slots': template_data['product_slots'],
                    'template_description': f"A {template_data['style']} {template_data['room_type']} design with carefully selected fixtures and fittings.",
                    'color_palette': template_data.get('color_palette', []),
                    'estimated_budget': template_data.get('estimated_budget', {})
                }
            )
        
        return LayoutTemplate.objects.filter(room_type__in=['kitchen', 'bathroom'])
    
    def generate_design_recommendation(self, session_id, room_dimensions=None, budget=None, layout_template_id=None):
        """Generate design recommendation maximizing the budget utilization."""
        try:
            print(f"DEBUG: Service layer - Looking for session_id: {session_id}")
            
            # Enhanced session validation
            try:
                session = UserSession.objects.select_for_update().get(id=session_id)
                print(f"DEBUG: Service layer - Found session: {session.id}, active: {session.is_active}")
            except UserSession.DoesNotExist:
                print(f"DEBUG: Service layer - Session {session_id} not found")
                available_sessions = UserSession.objects.values_list('id', flat=True)
                print(f"DEBUG: Service layer - Available sessions: {list(available_sessions)}")
                return {'error': f'Session with ID {session_id} does not exist in database'}
            
            # Validate session is active
            if not session.is_active:
                return {'error': 'Session is inactive'}
            
            # Check if session is expired
            if hasattr(session, 'is_expired') and session.is_expired():
                session.is_active = False
                session.save()
                return {'error': 'Session has expired'}
            
            preferences = session.preferences
            
            # Handle budget - use single value and ensure full utilization
            if budget is not None:
                total_budget = float(budget)
            else:
                # Use default based on room type
                room_type = preferences.get('room_type', 'kitchen')
                total_budget = 8000 if room_type == 'kitchen' else 4500

            # Select appropriate template
            if layout_template_id:
                try:
                    template = LayoutTemplate.objects.get(id=layout_template_id)
                except LayoutTemplate.DoesNotExist:
                    return {'error': f'Layout template with ID {layout_template_id} does not exist'}
            else:
                template = self._select_template(preferences)
                
            if not template:
                return {'error': 'No suitable template found for your preferences'}
                
            # Handle product_slots format
            if isinstance(template.product_slots, list):
                product_slots_dict = {}
                for i, slot in enumerate(template.product_slots):
                    if isinstance(slot, dict):
                        slot_name = slot.get('name', f'slot_{i}')
                        product_slots_dict[slot_name] = slot
                    else:
                        product_slots_dict[f'slot_{i}'] = {'type': slot, 'quantity': 1}
            elif isinstance(template.product_slots, dict):
                product_slots_dict = template.product_slots
            else:
                return {'error': 'Invalid product_slots format in template'}
                
            # Use provided dimensions or template defaults
            dimensions = room_dimensions or template.dimensions
            
            # Calculate labor cost (15% of material cost)
            material_budget = total_budget * 0.85  # 85% for materials
            labor_cost = total_budget * 0.15       # 15% for labor
            
            # Generate AI reasoning for the design
            ai_reasoning = self._generate_design_reasoning(preferences, template, dimensions, total_budget)
            
            print(f"DEBUG: Creating DesignRecommendation for session {session.id}")
            
            # Create design recommendation with transaction
            from django.db import transaction
            
            with transaction.atomic():
                # Double-check session still exists and is active
                session.refresh_from_db()
                if not session.is_active:
                    return {'error': 'Session became inactive during processing'}
                    
                design = DesignRecommendation.objects.create(
                    session=session,
                    layout_template=template,
                    room_dimensions=dimensions,
                    user_preferences=preferences,
                    ai_reasoning=ai_reasoning,
                    status='generated'
                )
                
                print(f"DEBUG: Created DesignRecommendation with ID: {design.id}")
            
            # Generate product recommendations for each slot with full budget utilization
            product_recommendations = self._generate_optimized_products(
                design, product_slots_dict, preferences, material_budget
            )
            
            # Calculate totals
            material_cost = sum(float(prod.total_price) for prod in product_recommendations)
            total_project_cost = material_cost + labor_cost
            
            # Update design with costs
            design.total_cost = total_project_cost
            design.save()
            
            return {
                'design_id': str(design.id),
                'template': template.name,
                'room_type': template.room_type,
                'style': template.style,
                'dimensions': dimensions,
                'material_cost': float(material_cost),
                'labor_cost': float(labor_cost),
                'total_cost': float(total_project_cost),
                'budget_used': float(total_budget),
                'budget_utilization': round((total_project_cost / total_budget) * 100, 1),
                'color_palette': getattr(template, 'color_palette', []),
                'ai_reasoning': ai_reasoning,
                'product_count': len(product_recommendations),
                'cost_breakdown': self._generate_enhanced_cost_breakdown(product_recommendations, labor_cost),
                'design_features': self._generate_design_features(template, preferences),
                'status': 'success'
            }
            
        except Exception as e:
            print(f"DEBUG: Design generation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'error': f'Design generation failed: {str(e)}'}
    def _generate_optimized_products(self, design, product_slots_dict, preferences, material_budget):
        """Generate products that fully utilize the material budget to match user expectations"""
        product_recommendations = []
        
        slot_budgets = {}
        total_percentage = sum(slot_info.get('budget_percentage', 10) for slot_info in product_slots_dict.values())
        
        # Normalize percentages if they don't add up to 100
        if total_percentage != 100:
            for slot_name, slot_info in product_slots_dict.items():
                slot_budgets[slot_name] = material_budget * (slot_info.get('budget_percentage', 10) / total_percentage)
        else:
            for slot_name, slot_info in product_slots_dict.items():
                slot_budgets[slot_name] = material_budget * slot_info.get('budget_percentage', 10) / 100
        
        total_allocated = 0.0
        
        # First pass: Create products for each slot
        for slot_name, slot_info in product_slots_dict.items():
            slot_budget = slot_budgets[slot_name]
            quantity = slot_info.get('quantity', 1)
            
            # Try to find real products first
            products = self._recommend_products_for_slot({
                'name': slot_name,
                'category': slot_info.get('category'),
                'quantity': quantity,
                'max_budget': slot_budget
            }, preferences, slot_budget)
            
            product_created = False
            
            # Use real product if available and within budget range
            if products:
                for product_data in products:
                    try:
                        product = Product.objects.get(id=product_data['product_id'])
                        unit_price = float(product.price)
                        total_price = unit_price * quantity
                        
                        # Accept products that use 50-150% of slot budget for better utilization
                        if total_price <= slot_budget * 1.5:
                            product_rec = ProductRecommendation.objects.create(
                                design=design,
                                product=product,
                                quantity=quantity,
                                slot_name=slot_name,
                                reasoning=product_data['reasoning'],
                                unit_price=unit_price,
                                total_price=total_price
                            )
                            product_recommendations.append(product_rec)
                            total_allocated += total_price
                            product_created = True
                            break
                    except Product.DoesNotExist:
                        continue
            
            # If no suitable real product found, create AI-generated product that uses the full slot budget
            if not product_created:
                ai_product = self._create_budget_maximizing_product(
                    slot_name, slot_info, slot_budget, material_budget
                )
                
                product_rec = ProductRecommendation.objects.create(
                    design=design,
                    product=None,
                    quantity=ai_product['quantity'],
                    slot_name=slot_name,
                    reasoning=ai_product['reasoning'],
                    unit_price=ai_product['unit_price'],
                    total_price=ai_product['total_price']
                )
                product_recommendations.append(product_rec)
                total_allocated += ai_product['total_price']
        
        # Second pass: Ensure we're close to the material budget
        remaining_budget = material_budget - total_allocated
        
        # If we're significantly under budget, upgrade products proportionally
        if remaining_budget > material_budget * 0.05:  # If more than 5% remains
            self._redistribute_remaining_budget(product_recommendations, remaining_budget)
        
        # If we're over budget, scale down proportionally
        elif total_allocated > material_budget * 1.02:  # If more than 2% over
            self._scale_down_to_budget(product_recommendations, material_budget)
        
        return product_recommendations
    
    def _create_budget_maximizing_product(self, slot_name, slot_info, slot_budget, total_material_budget):
        """Create AI product that utilizes 90-95% of the allocated slot budget"""
        
        # Enhanced product database with realistic premium pricing
        premium_products = {
            # Kitchen products
            'kitchen_cabinet': {
                'name': 'Premium Modular Kitchen Cabinet System',
                'base_price': 2000,
                'scaling_factor': 1.5
            },
            'modular_cabinets': {
                'name': 'Custom Modular Kitchen Cabinets',
                'base_price': 2000,
                'scaling_factor': 1.5
            },
            'kitchen_island': {
                'name': 'Designer Kitchen Island with Storage',
                'base_price': 1500,
                'scaling_factor': 1.8
            },
            'bar_stools': {
                'name': 'Premium Bar Stool',
                'base_price': 300,
                'scaling_factor': 2.0
            },
            'pendant_lights': {
                'name': 'Designer Pendant Light Fixture',
                'base_price': 250,
                'scaling_factor': 2.5
            },
            'kitchen_appliances': {
                'name': 'Premium Kitchen Appliance Package',
                'base_price': 1200,
                'scaling_factor': 1.8
            },
            'hob': {
                'name': 'Premium Gas Hob with Auto-Ignition',
                'base_price': 500,
                'scaling_factor': 2.0
            },
            'sink': {
                'name': 'Premium Stainless Steel Kitchen Sink',
                'base_price': 400,
                'scaling_factor': 2.5
            },
            'chimney': {
                'name': 'High-Performance Kitchen Chimney',
                'base_price': 600,
                'scaling_factor': 2.0
            },
            'lighting': {
                'name': 'LED Kitchen Lighting System',
                'base_price': 400,
                'scaling_factor': 1.8
            },
            'countertop': {
                'name': 'Premium Granite/Quartz Countertop',
                'base_price': 800,
                'scaling_factor': 2.2
            },
            
            # Bathroom products
            'vanity_cabinet': {
                'name': 'Premium Bathroom Vanity with Sink',
                'base_price': 1000,
                'scaling_factor': 1.8
            },
            'double_vanity': {
                'name': 'Luxury Double Sink Vanity Unit',
                'base_price': 2000,
                'scaling_factor': 1.6
            },
            'mirror': {
                'name': 'Smart LED Bathroom Mirror',
                'base_price': 400,
                'scaling_factor': 2.0
            },
            'luxury_mirror': {
                'name': 'Premium Smart Mirror with Touch Controls',
                'base_price': 800,
                'scaling_factor': 1.8
            },
            'shower_fixtures': {
                'name': 'Premium Shower System with Fixtures',
                'base_price': 800,
                'scaling_factor': 2.0
            },
            'premium_fixtures': {
                'name': 'Luxury Rain Shower System',
                'base_price': 1500,
                'scaling_factor': 1.8
            },
            'bathroom_lighting': {
                'name': 'Premium LED Bathroom Lighting',
                'base_price': 200,
                'scaling_factor': 2.5
            },
            'luxury_lighting': {
                'name': 'Designer Bathroom Light Collection',
                'base_price': 400,
                'scaling_factor': 2.0
            },
            'storage_shelves': {
                'name': 'Premium Bathroom Storage System',
                'base_price': 300,
                'scaling_factor': 1.8
            },
            'towel_warmer': {
                'name': 'Electric Heated Towel Warmer Rack',
                'base_price': 400,
                'scaling_factor': 2.0
            },
        }
        
        quantity = slot_info.get('quantity', 1)
        
        # Target 90-95% of slot budget utilization
        target_total = slot_budget * 0.92  # Use 92% of allocated budget
        target_unit_price = target_total / quantity
        
        # Get product info or create generic
        if slot_name in premium_products:
            product_info = premium_products[slot_name]
            base_price = product_info['base_price']
            scaling_factor = product_info['scaling_factor']
            
            # Scale price based on available budget
            if target_unit_price > base_price:
                unit_price = min(target_unit_price, base_price * scaling_factor)
            else:
                unit_price = max(target_unit_price, base_price * 0.7)  # Minimum 70% of base
            
            name = product_info['name']
        else:
            # Generic premium product
            unit_price = target_unit_price
            name = f'Premium {slot_name.replace("_", " ").title()}'
        
        total_price = unit_price * quantity
        
        return {
            'name': name,
            'quantity': quantity,
            'unit_price': round(unit_price, 2),
            'total_price': round(total_price, 2),
            'reasoning': f"Selected {name} with premium materials and finishes to maximize your investment while ensuring exceptional quality and durability. This selection utilizes your allocated budget effectively for optimal value."
        }
    
    def _redistribute_remaining_budget(self, product_recommendations, remaining_budget):
        """Redistribute remaining budget proportionally across all products"""
        if not product_recommendations or remaining_budget <= 0:
            return
        
        total_current_cost = sum(prod.total_price for prod in product_recommendations)
        
        for prod_rec in product_recommendations:
            # Calculate proportional upgrade
            proportion = prod_rec.total_price / total_current_cost if total_current_cost > 0 else 0
            upgrade_amount = remaining_budget * proportion
            
            # Apply upgrade
            new_unit_price = prod_rec.unit_price + (upgrade_amount / prod_rec.quantity)
            new_total_price = new_unit_price * prod_rec.quantity
            
            prod_rec.unit_price = round(new_unit_price, 2)
            prod_rec.total_price = round(new_total_price, 2)
            prod_rec.reasoning += " Enhanced with premium upgrades to fully utilize your budget allocation."
            prod_rec.save()
    
    def _scale_down_to_budget(self, product_recommendations, target_budget):
        """Scale down all products proportionally to fit within budget"""
        if not product_recommendations:
            return
            
        total_current_cost = sum(prod.total_price for prod in product_recommendations)
        scale_factor = target_budget / total_current_cost if total_current_cost > 0 else 1
        
        for prod_rec in product_recommendations:
            new_total_price = prod_rec.total_price * scale_factor
            new_unit_price = new_total_price / prod_rec.quantity
            
            prod_rec.unit_price = round(new_unit_price, 2)
            prod_rec.total_price = round(new_total_price, 2)
            prod_rec.save()

    def _create_smart_fallback_product(self, slot_name, slot_info, slot_budget, total_budget):
        """Create intelligent fallback products with realistic pricing"""
        
        # Enhanced product database with realistic pricing
        enhanced_products = {
            # Kitchen products with premium options
            'kitchen_cabinet': {
                'name': 'Premium Modular Kitchen Cabinets',
                'base_price': 1500,
                'price_multiplier': lambda budget: min(3.5, max(1.0, budget / 2000))
            },
            'modular_cabinets': {
                'name': 'Premium Modular Kitchen Cabinets',
                'base_price': 1500,
                'price_multiplier': lambda budget: min(3.5, max(1.0, budget / 2000))
            },
            'kitchen_island': {
                'name': 'Kitchen Island with Premium Countertop',
                'base_price': 800,
                'price_multiplier': lambda budget: min(4.0, max(1.0, budget / 1500))
            },
            'bar_stools': {
                'name': 'Designer Bar Stool',
                'base_price': 150,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 200))
            },
            'pendant_lights': {
                'name': 'Designer Pendant Light',
                'base_price': 120,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 180))
            },
            'kitchen_appliances': {
                'name': 'Premium Kitchen Appliance Package',
                'base_price': 800,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 1000))
            },
            'hob': {
                'name': 'Premium Gas Hob with Auto Ignition',
                'base_price': 300,
                'price_multiplier': lambda budget: min(4.0, max(1.0, budget / 500))
            },
            'sink': {
                'name': 'Premium Stainless Steel Kitchen Sink',
                'base_price': 200,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 400))
            },
            'chimney': {
                'name': 'High-Efficiency Kitchen Chimney',
                'base_price': 400,
                'price_multiplier': lambda budget: min(3.5, max(1.0, budget / 600))
            },
            'lighting': {
                'name': 'LED Kitchen Lighting System',
                'base_price': 250,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 400))
            },
            'countertop': {
                'name': 'Premium Granite/Quartz Countertop',
                'base_price': 400,
                'price_multiplier': lambda budget: min(4.0, max(1.0, budget / 800))
            },
            
            # Bathroom products with premium options
            'vanity_cabinet': {
                'name': 'Premium Bathroom Vanity Cabinet',
                'base_price': 600,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 1000))
            },
            'double_vanity': {
                'name': 'Premium Double Sink Vanity',
                'base_price': 1200,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 2000))
            },
            'mirror': {
                'name': 'Premium LED Bathroom Mirror',
                'base_price': 200,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 350))
            },
            'luxury_mirror': {
                'name': 'Smart LED Mirror with Touch Controls',
                'base_price': 400,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 600))
            },
            'shower_fixtures': {
                'name': 'Premium Shower Fixture Set',
                'base_price': 500,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 800))
            },
            'premium_fixtures': {
                'name': 'Luxury Rain Shower System',
                'base_price': 1200,
                'price_multiplier': lambda budget: min(3.5, max(1.0, budget / 2000))
            },
            'bathroom_lighting': {
                'name': 'LED Bathroom Light Fixture',
                'base_price': 100,
                'price_multiplier': lambda budget: min(2.5, max(1.0, budget / 200))
            },
            'luxury_lighting': {
                'name': 'Designer Bathroom Lighting',
                'base_price': 200,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 400))
            },
            'storage_shelves': {
                'name': 'Premium Bathroom Storage Shelf',
                'base_price': 150,
                'price_multiplier': lambda budget: min(2.0, max(1.0, budget / 250))
            },
            'towel_warmer': {
                'name': 'Electric Heated Towel Warmer',
                'base_price': 250,
                'price_multiplier': lambda budget: min(3.0, max(1.0, budget / 500))
            },
        }
        
        quantity = slot_info.get('quantity', 1)
        
        # Get product info or create generic
        if slot_name in enhanced_products:
            product_info = enhanced_products[slot_name]
            base_price = product_info['base_price']
            multiplier = product_info['price_multiplier'](slot_budget)
            unit_price = base_price * multiplier
            name = product_info['name']
        else:
            # Generic product
            unit_price = slot_budget / quantity * 0.9  # Use 90% of budget for buffer
            name = f'Premium {slot_name.replace("_", " ").title()}'
        
        # Ensure we use most of the allocated budget
        target_total = slot_budget * 0.95  # Use 95% of allocated budget
        unit_price = max(unit_price, target_total / quantity)
        total_price = unit_price * quantity
        
        return {
            'name': name,
            'quantity': quantity,
            'unit_price': round(unit_price, 2),
            'total_price': round(total_price, 2),
            'reasoning': f"Selected {name} with premium features and quality materials to maximize your budget allocation while ensuring excellent value and durability."
        }

    def _generate_enhanced_cost_breakdown(self, product_recommendations, labor_cost):
        """Generate enhanced cost breakdown including labor"""
        breakdown = {}
        material_total = 0
        
        # Group by category
        for prod_rec in product_recommendations:
            if prod_rec.product and hasattr(prod_rec.product, 'category'):
                category_name = prod_rec.product.category.name
            else:
                # Categorize based on slot name
                slot_name = prod_rec.slot_name.lower()
                if 'cabinet' in slot_name or 'storage' in slot_name or 'vanity' in slot_name:
                    category_name = 'Storage & Cabinetry'
                elif 'light' in slot_name or 'chandelier' in slot_name:
                    category_name = 'Lighting'
                elif 'fixture' in slot_name or 'shower' in slot_name or 'faucet' in slot_name:
                    category_name = 'Fixtures'
                elif 'appliance' in slot_name or 'hob' in slot_name or 'chimney' in slot_name:
                    category_name = 'Appliances'
                elif 'stool' in slot_name or 'chair' in slot_name:
                    category_name = 'Seating'
                elif 'countertop' in slot_name or 'surface' in slot_name:
                    category_name = 'Surfaces'
                else:
                    category_name = 'Accessories'
            
            if category_name not in breakdown:
                breakdown[category_name] = {'items': [], 'subtotal': 0}
            
            item_name = prod_rec.product.name if prod_rec.product else f"{prod_rec.slot_name.replace('_', ' ').title()}"
            
            item_info = {
                'name': item_name,
                'quantity': prod_rec.quantity,
                'unit_price': float(prod_rec.unit_price),
                'total_price': float(prod_rec.total_price)
            }
            
            breakdown[category_name]['items'].append(item_info)
            breakdown[category_name]['subtotal'] += float(prod_rec.total_price)
            material_total += float(prod_rec.total_price)
        
        # Add labor cost as separate category
        breakdown['Labor & Installation'] = {
            'items': [
                {
                    'name': 'Professional Installation & Labor',
                    'quantity': 1,
                    'unit_price': float(labor_cost),
                    'total_price': float(labor_cost)
                }
            ],
            'subtotal': float(labor_cost)
        }
        
        return {
            'categories': breakdown,
            'material_total': material_total,
            'labor_total': float(labor_cost),
            'grand_total': material_total + float(labor_cost)
        }

    def _recommend_products_for_slot(self, slot, preferences, slot_budget):
        """Recommend products for kitchen and bathroom slots"""
        try:
            products = Product.objects.filter(is_available=True)
            
            # Apply category filter for kitchen and bathroom
            category_keywords = slot['category'].lower() if slot.get('category') else ''
            if 'storage' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(cabinet|storage|vanity|shelf)'
                )
            elif 'seating' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(chair|stool|bench)'
                )
            elif 'table' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(table|island)'
                )
            elif 'lighting' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(light|lamp|chandelier|pendant)'
                )
            elif 'fixtures' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(fixture|faucet|shower|tap)'
                )
            elif 'appliances' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(appliance|refrigerator|stove|dishwasher)'
                )
            elif 'accessories' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(mirror|accessory|towel|hardware)'
                )
            
            # Apply budget filter with higher tolerance for budget utilization
            max_unit_price = slot_budget / slot.get('quantity', 1)
            products = products.filter(price__lte=max_unit_price * 1.5)  # 50% tolerance for better products
            
            # Apply style and room type preferences
            if preferences.get('style') and products.filter(style=preferences['style']).exists():
                products = products.filter(style=preferences['style'])
            
            if preferences.get('room_type') and products.filter(room_type=preferences['room_type']).exists():
                products = products.filter(room_type=preferences['room_type'])
            
            # Select products for this slot
            selected_products = []
            quantity = slot.get('quantity', 1)
            
            if products.exists():
                product = self._ai_select_best_product(products, slot, preferences, slot_budget)
                if product:
                    reasoning = self._generate_product_reasoning(product, slot, preferences)
                    selected_products.append({
                        'product_id': product.id,
                        'quantity': quantity,
                        'reasoning': reasoning
                    })
            
            return selected_products
            
        except Exception as e:
            print(f"Product recommendation error for slot {slot['name']}: {e}")
            return []
    
    def _generate_product_reasoning(self, product, slot, preferences):
        """Generate reasoning for product selection"""
        reasons = []
        
        if preferences.get('style') == product.style:
            reasons.append(f"matches your preferred {product.style} style")
        
        slot_name = slot['name'].replace('_', ' ')
        reasons.append(f"ideal for {slot_name} in your {preferences.get('room_type', 'space')}")
        
        if hasattr(product, 'material') and product.material:
            reasons.append(f"quality {product.material} construction")
        
        reasons.append("selected to optimize your budget while ensuring quality")
        
        return f"This {product.name} was selected because it " + ", ".join(reasons) + "."
    
    def _generate_design_features(self, template, preferences):
        """Generate design features for kitchen and bathroom"""
        features = []
        
        style = template.style.lower()
        room_type = template.room_type
        
        if room_type == 'kitchen':
            if 'modern' in style:
                features.extend(['Clean contemporary lines', 'Efficient workflow design', 'Smart storage solutions', 'Modern appliance integration'])
            elif 'traditional' in style:
                features.extend(['Classic design elements', 'Warm wood finishes', 'Timeless appeal', 'Functional layout'])
            features.extend(['Optimal counter space', 'Strategic lighting placement', 'Durable materials'])
        
        elif room_type == 'bathroom':
            if 'modern' in style:
                features.extend(['Sleek minimalist design', 'Water-efficient fixtures', 'Contemporary finishes', 'Smart storage'])
            elif 'luxury' in style:
                features.extend(['Premium materials', 'Spa-like atmosphere', 'High-end fixtures', 'Elegant details'])
            features.extend(['Proper ventilation', 'Easy maintenance', 'Functional layout'])
        
        return features[:6]
    
    
    def _select_template(self, preferences):
            """Select template for kitchen or bathroom only"""
            room_type = preferences.get('room_type', 'kitchen')
            style = preferences.get('style', 'modern')
            
            # Only allow kitchen and bathroom
            if room_type not in ['kitchen', 'bathroom']:
                room_type = 'kitchen'  # Default to kitchen
            
            # Try exact match first
            template = LayoutTemplate.objects.filter(
                room_type=room_type,
                style=style
            ).first()
            
            if not template:
                template = LayoutTemplate.objects.filter(room_type=room_type).first()
            
            if not template:
                template = LayoutTemplate.objects.filter(room_type='kitchen').first()
            
            return template
        
    def _generate_design_reasoning(self, preferences, template, dimensions, budget):
            """Generate AI reasoning for design"""
            try:
                room_type = template.room_type
                style = template.style
                
                prompt = f"""
                As an expert {room_type} designer, create a detailed explanation for this design recommendation.

                User Preferences: {json.dumps(preferences)}
                Template: {template.name} - {template.template_description}
                Room Dimensions: {dimensions}
                Budget: ${budget:,}
                Style: {style}

                Provide a professional explanation (2-3 paragraphs) covering:
                1. Why this {room_type} layout and {style} style perfectly match the user's needs
                2. How the design maximizes functionality and aesthetics within the space
                3. How the budget ensures quality fixtures and finishes

                Make it engaging and informative.
                """
                
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=400
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                return f"""This {template.name} design perfectly captures the essence of {template.style} style while maximizing functionality for your {template.room_type}. The layout ensures optimal workflow and storage while maintaining the aesthetic appeal you desire. With a budget of ${budget:,}, this design focuses on quality fixtures and finishes that provide lasting value and beauty."""
    
    def _ai_select_best_product(self, products, slot, preferences, slot_budget):
        """Select best product based on criteria"""
        if len(products) == 1:
            return products.first()
        
        scored_products = []
        max_unit_price = slot_budget / slot.get('quantity', 1)
        
        for product in products[:10]:
            score = 0
            
            # Style match
            if preferences.get('style') == getattr(product, 'style', ''):
                score += 5
            
            # Room type match
            if preferences.get('room_type') == getattr(product, 'room_type', ''):
                score += 3
            
            # Price optimization - prioritize products that use more of the budget
            price_ratio = product.price / max_unit_price if max_unit_price > 0 else 0
            if 0.7 <= price_ratio <= 1.2:  # Prefer products that use 70-120% of allocated budget
                score += 5
            elif 0.5 <= price_ratio <= 0.7:
                score += 3
            elif price_ratio > 1.2:
                score += 2  # Still consider expensive items
            
            # Availability
            if getattr(product, 'is_available', True):
                score += 2
            
            # Quality indicators
            if hasattr(product, 'rating') and product.rating:
                score += min(product.rating, 3)
            
            scored_products.append((product, score))
        
        if scored_products:
            scored_products.sort(key=lambda x: x[1], reverse=True)
            return scored_products[0][0]
        
        return products.first()
    
    def generate_pdf_report(self, design_id):
        """Enhanced PDF generation with complete budget breakdown and labor costs."""
        try:
            design = DesignRecommendation.objects.get(id=design_id)
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
            styles = getSampleStyleSheet()
            story = []
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=26,
                spaceAfter=30,
                textColor=colors.HexColor('#2C3E50'),
                alignment=1  # Center alignment
            )
            
            subtitle_style = ParagraphStyle(
                'Subtitle',
                parent=styles['Heading2'],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=15,
                textColor=colors.HexColor('#34495E')
            )

            # Title and header
            story.append(Paragraph("Interior Design Recommendation", title_style))
            story.append(Paragraph(f"{design.layout_template.name} | {design.layout_template.style.title()} Style", styles['Heading3']))
            story.append(Spacer(1, 20))

            # Design overview section
            story.append(Paragraph("Design Overview", subtitle_style))
            room_dims = design.room_dimensions if isinstance(design.room_dimensions, dict) else {}
            
            # Calculate costs
            material_cost = sum(float(prod.total_price) for prod in design.product_recommendations.all())
            labor_cost = material_cost * 0.15  # 15% of material cost
            total_project_cost = material_cost + labor_cost
            
            overview_data = [
                ['Template:', design.layout_template.name],
                ['Room Type:', design.layout_template.room_type.replace('_', ' ').title()],
                ['Style:', design.layout_template.style.title()],
                ['Dimensions:', f"{room_dims.get('width', 'N/A')}' × {room_dims.get('length', 'N/A')}' × {room_dims.get('height', 'N/A')}'"],
                ['Area:', f"{room_dims.get('area_sqft', room_dims.get('width', 0) * room_dims.get('length', 0))} sq ft"],
                ['Material Cost:', f"${material_cost:,.2f}"],
                ['Labor & Installation:', f"${labor_cost:,.2f}"],
                ['Total Project Cost:', f"${total_project_cost:,.2f}"],
                ['Status:', design.status.title()],
            ]
            
            overview_table = Table(overview_data, colWidths=[2*inch, 3.5*inch])
            overview_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#BDC3C7'))
            ]))
            story.append(overview_table)
            story.append(Spacer(1, 25))

            # AI reasoning section
            story.append(Paragraph("Design Philosophy & Rationale", subtitle_style))
            story.append(Paragraph(design.ai_reasoning, styles['Normal']))
            story.append(Spacer(1, 25))

            # Product recommendations section
            story.append(Paragraph("Recommended Products & Materials", subtitle_style))
            
            if design.product_recommendations.exists():
                product_data = [['Item', 'Qty', 'Unit Price', 'Total Price', 'Category/Purpose']]
                
                for prod_rec in design.product_recommendations.all():
                    if prod_rec.product:
                        # Real product from database
                        product_name = prod_rec.product.name
                        category = prod_rec.product.category.name if hasattr(prod_rec.product, 'category') else prod_rec.slot_name.replace('_', ' ').title()
                    else:
                        # AI/Estimated product
                        product_name = f"{prod_rec.slot_name.replace('_', ' ').title()}"
                        category = self._get_category_from_slot(prod_rec.slot_name)
                    
                    product_data.append([
                        product_name,
                        str(prod_rec.quantity),
                        f"${prod_rec.unit_price:,.2f}",
                        f"${prod_rec.total_price:,.2f}",
                        category
                    ])
                
                # Add material subtotal row
                product_data.append(['', '', '', f"${material_cost:,.2f}", 'MATERIAL SUBTOTAL'])
                
                product_table = Table(product_data, colWidths=[2.2*inch, 0.6*inch, 1*inch, 1*inch, 1.7*inch])
                product_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('ALIGN', (0, 1), (0, -2), 'LEFT'),  # Left align product names
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#F8F9FA'), colors.white]),
                    # Style the subtotal row
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F4FD')),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ]))
                story.append(product_table)
            else:
                story.append(Paragraph("No products selected.", styles['Normal']))

            story.append(Spacer(1, 25))

            # Cost breakdown section
            story.append(Paragraph("Investment Summary", subtitle_style))
            
            # Create cost breakdown table
            cost_data = [
                ['Cost Category', 'Amount', 'Percentage'],
                ['Materials & Products', f"${material_cost:,.2f}", f"{(material_cost/total_project_cost)*100:.1f}%"],
                ['Labor & Installation', f"${labor_cost:,.2f}", f"{(labor_cost/total_project_cost)*100:.1f}%"],
                ['Total Project Investment', f"${total_project_cost:,.2f}", "100.0%"]
            ]
            
            cost_table = Table(cost_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            cost_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ECC71')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#F8F9FA'), colors.white]),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D5DBDB')),
            ]))
            story.append(cost_table)
            story.append(Spacer(1, 25))

            # Additional information
            story.append(Paragraph("Important Notes", subtitle_style))
            notes = [
                f"<b>Budget Optimization:</b> This design maximizes value within your budget range while maintaining style and quality.",
                f"<b>Flexibility:</b> Product recommendations can be adjusted based on availability and personal preferences.",
                f"<b>Next Steps:</b> Contact our design team to discuss implementation, delivery, and installation options.",
                f"<b>Warranty:</b> All recommended products come with manufacturer warranties and our quality guarantee."
            ]
            
            for note in notes:
                story.append(Paragraph(note, styles['Normal']))
                story.append(Spacer(1, 8))

            story.append(Spacer(1, 15))
            story.append(Paragraph("<i>This estimate includes materials and installation. Delivery costs may apply separately.</i>", styles['Normal']))
            
            # Footer with generation info
            story.append(Spacer(1, 30))
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.HexColor('#7F8C8D'),
                alignment=1
            )
            story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')} | Design ID: {design.id}", footer_style))

            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            return pdf_data
            
        except Exception as e:
            print(f"PDF generation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_category_from_slot(self, slot_name):
        """Get category name from slot name for better organization"""
        slot_name = slot_name.lower()
        
        if any(word in slot_name for word in ['cabinet', 'storage', 'vanity', 'shelf']):
            return 'Storage & Cabinetry'
        elif any(word in slot_name for word in ['light', 'lighting', 'chandelier', 'pendant']):
            return 'Lighting'
        elif any(word in slot_name for word in ['fixture', 'shower', 'faucet', 'tap']):
            return 'Fixtures & Plumbing'
        elif any(word in slot_name for word in ['appliance', 'hob', 'chimney', 'refrigerator']):
            return 'Appliances'
        elif any(word in slot_name for word in ['stool', 'chair', 'seating']):
            return 'Seating'
        elif any(word in slot_name for word in ['countertop', 'surface', 'granite', 'marble']):
            return 'Surfaces & Countertops'
        elif any(word in slot_name for word in ['sink', 'basin']):
            return 'Kitchen/Bath Fixtures'
        elif any(word in slot_name for word in ['mirror', 'accessory', 'towel']):
            return 'Accessories'
        else:
            return 'Miscellaneous'