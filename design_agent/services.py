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
        """Generate design recommendation with single budget value"""
        try:
            session = UserSession.objects.get(id=session_id)
            preferences = session.preferences
            # Handle budget - use single value instead of min/max
            if isinstance(budget, dict) and 'max' in budget:
                total_budget = float(budget['max'])
            elif isinstance(budget, (int, float)):
                total_budget = float(budget)
            else:
                # Use default based on room type
                room_type = preferences.get('room_type', 'kitchen')
                total_budget = 8000 if room_type == 'kitchen' else 4500

            # Select appropriate template
            if layout_template_id:
                template = LayoutTemplate.objects.get(id=layout_template_id)
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
            # Generate AI reasoning for the design
            ai_reasoning = self._generate_design_reasoning(preferences, template, dimensions, total_budget)
            # Create design recommendation
            design = DesignRecommendation.objects.create(
                session=session,
                layout_template=template,
                room_dimensions=dimensions,
                user_preferences=preferences,
                ai_reasoning=ai_reasoning,
                status='generated'
            )
            # Generate product recommendations for each slot
            total_cost = 0
            product_recommendations = []
            for slot_name, slot_info in product_slots_dict.items():
                budget_percent = slot_info.get('budget_percentage', 10)
                slot_budget = total_budget * budget_percent / 100
                slot = {
                    'name': slot_name,
                    'category': slot_info.get('category'),
                    'quantity': slot_info.get('quantity', 1),
                    'max_budget': slot_budget
                }
                products = self._recommend_products_for_slot(slot, preferences, slot_budget)
                for product_data in products:
                    try:
                        product = Product.objects.get(id=product_data['product_id'])
                        quantity = product_data['quantity']
                        unit_price = product.price
                        total_price = unit_price * quantity
                        product_rec = ProductRecommendation.objects.create(
                            design=design,
                            product=product,
                            quantity=quantity,
                            slot_name=slot['name'],
                            reasoning=product_data['reasoning'],
                            unit_price=unit_price,
                            total_price=total_price
                        )
                        product_recommendations.append(product_rec)
                        total_cost += total_price
                    except Product.DoesNotExist:
                        print(f"Product with ID {product_data['product_id']} not found")
                        continue
            # If no products found, use fallback products
            if total_cost == 0:
                print("No products found, using fallback...")
                fallback_products = self._create_fallback_products(template, total_budget)
                for product_data in fallback_products:
                    product_rec = ProductRecommendation.objects.create(
                        design=design,
                        product_id=None,
                        quantity=product_data['quantity'],
                        slot_name=product_data['slot_name'],
                        reasoning=product_data['reasoning'],
                        unit_price=product_data['unit_price'],
                        total_price=product_data['total_price']
                    )
                    product_recommendations.append(product_rec)
                    total_cost += product_data['total_price']
            
            design.total_cost = total_cost
            design.save()
            
            return {
                'design_id': str(design.id),
                'template': template.name,
                'room_type': template.room_type,
                'style': template.style,
                'dimensions': dimensions,
                'total_cost': float(total_cost),
                'budget_used': float(total_budget),
                'color_palette': getattr(template, 'color_palette', []),
                'ai_reasoning': ai_reasoning,
                'product_count': len(product_recommendations),
                'cost_breakdown': self._generate_cost_breakdown(product_recommendations),
                'design_features': self._generate_design_features(template, preferences),
                'status': 'success'
            }
            
        except Exception as e:
            print(f"Design generation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'error': f'Design generation failed: {str(e)}'}

    def _create_fallback_products(self, template, total_budget):
        """Create fallback products for kitchen and bathroom"""
        fallback_products = []
        
        # Kitchen and bathroom specific products
        sample_products = {
            # Kitchen products
            'kitchen_cabinet': {'name': 'Modern Kitchen Cabinets', 'price_range': (1500, 4000)},
            'kitchen_island': {'name': 'Kitchen Island with Storage', 'price_range': (800, 2500)},
            'bar_stools': {'name': 'Kitchen Bar Stool', 'price_range': (80, 250)},
            'pendant_lights': {'name': 'Kitchen Pendant Light', 'price_range': (100, 300)},
            'kitchen_appliances': {'name': 'Kitchen Appliance Package', 'price_range': (500, 1500)},
            'wooden_cabinets': {'name': 'Traditional Wood Cabinets', 'price_range': (2000, 5000)},
            'dining_table': {'name': 'Kitchen Dining Table', 'price_range': (400, 1200)},
            'dining_chairs': {'name': 'Kitchen Dining Chair', 'price_range': (100, 400)},
            'chandelier': {'name': 'Kitchen Chandelier', 'price_range': (200, 800)},
            
            # Bathroom products
            'vanity_cabinet': {'name': 'Bathroom Vanity Cabinet', 'price_range': (500, 1800)},
            'double_vanity': {'name': 'Double Sink Vanity', 'price_range': (1200, 3500)},
            'mirror': {'name': 'Bathroom Mirror', 'price_range': (150, 600)},
            'luxury_mirror': {'name': 'Luxury Bathroom Mirror', 'price_range': (300, 1000)},
            'shower_fixtures': {'name': 'Shower Fixture Set', 'price_range': (400, 1500)},
            'premium_fixtures': {'name': 'Premium Bathroom Fixtures', 'price_range': (1500, 4000)},
            'bathroom_lighting': {'name': 'Bathroom Light Fixture', 'price_range': (80, 300)},
            'luxury_lighting': {'name': 'Luxury Bathroom Lighting', 'price_range': (200, 600)},
            'storage_shelves': {'name': 'Bathroom Storage Shelf', 'price_range': (100, 400)},
            'towel_warmer': {'name': 'Electric Towel Warmer', 'price_range': (200, 800)},
        }
        
        # Handle product_slots format
        if isinstance(template.product_slots, list):
            product_slots_dict = {}
            for i, slot in enumerate(template.product_slots):
                if isinstance(slot, dict):
                    slot_name = slot.get('name', f'slot_{i}')
                    product_slots_dict[slot_name] = slot
        else:
            product_slots_dict = template.product_slots
        
        for slot_name, slot_info in product_slots_dict.items():
            quantity = slot_info.get('quantity', 1)
            budget_percentage = slot_info.get('budget_percentage', 10)
            slot_budget = total_budget * budget_percentage / 100
                    
            # Get sample product or create generic one
            if slot_name in sample_products:
                product_info = sample_products[slot_name]
                price_range = product_info['price_range']
                unit_price = min(slot_budget / quantity, random.uniform(*price_range))
            else:
                product_info = {'name': f'{slot_name.replace("_", " ").title()}'}
                unit_price = slot_budget / quantity
            
            fallback_products.append({
                'slot_name': slot_name,
                'name': product_info['name'],
                'quantity': quantity,
                'unit_price': round(unit_price, 2),
                'total_price': round(unit_price * quantity, 2),
                'reasoning': f"Selected {product_info['name']} to complete the {template.style} {template.room_type} design within budget."
            })
        
        return fallback_products
    
    def _recommend_products_for_slot(self, slot, preferences, slot_budget):
        """Recommend products for kitchen and bathroom slots"""
        try:
            products = Product.objects.filter(is_available=True)
            
            # Apply category filter for kitchen and bathroom
            category_keywords = slot['category'].lower()
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
            
            # Apply budget filter
            max_unit_price = slot_budget / slot.get('quantity', 1)
            products = products.filter(price__lte=max_unit_price * 1.1)  # 10% tolerance
            
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
        
        reasons.append("within your budget allocation")
        
        return f"This {product.name} was selected because it " + ", ".join(reasons) + "."
    
    def _generate_cost_breakdown(self, product_recommendations):
        """Generate cost breakdown"""
        breakdown = {}
        total = 0
        
        for prod_rec in product_recommendations:
            category = getattr(prod_rec.product, 'category', 'Estimated') if prod_rec.product else 'Estimated'
            category_name = category.name if hasattr(category, 'name') else str(category)
            
            if category_name not in breakdown:
                breakdown[category_name] = {'items': [], 'subtotal': 0}
            
            item_info = {
                'name': prod_rec.product.name if prod_rec.product else f"Estimated {prod_rec.slot_name}",
                'quantity': prod_rec.quantity,
                'unit_price': float(prod_rec.unit_price),
                'total_price': float(prod_rec.total_price)
            }
            
            breakdown[category_name]['items'].append(item_info)
            breakdown[category_name]['subtotal'] += float(prod_rec.total_price)
            total += float(prod_rec.total_price)
        
        return {
            'categories': breakdown,
            'total': total
        }
    
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
            return f"""This {template.name} design perfectly captures the essence of {template.style} style while maximizing functionality for your {template.room_type}. 

The layout ensures optimal workflow and storage while maintaining the aesthetic appeal you desire. With a budget of ${budget:,}, this design focuses on quality fixtures and finishes that provide lasting value and beauty."""
    
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
            
            # Price optimization
            price_ratio = product.price / max_unit_price if max_unit_price > 0 else 0
            if 0.8 <= price_ratio <= 1.0:
                score += 4
            elif 0.6 <= price_ratio <= 0.8:
                score += 2
            
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
        """Enhanced PDF generation with better formatting"""
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
            print("Raw room_dimensions:", design.room_dimensions)
            room_dims = parse_room_dimensions(design.room_dimensions)

            overview_data = [
                ['Template:', design.layout_template.name],
                ['Room Type:', design.layout_template.room_type.replace('_', ' ').title()],
                ['Style:', design.layout_template.style.title()],
                ['Dimensions:', f"{room_dims.get('width', 'N/A')}' × {room_dims.get('height', 'N/A')}'"],
                ['Area:', f"{room_dims.get('area_sqft', 'N/A')} sq ft"],
                ['Total Investment:', f"${design.total_cost:,.2f}"],
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
            story.append(Paragraph("Recommended Furniture & Decor", subtitle_style))
            
            if design.product_recommendations.exists():
                product_data = [['Item', 'Qty', 'Unit Price', 'Total', 'Purpose']]
                
                for prod_rec in design.product_recommendations.all():
                    product_name = prod_rec.product.name if prod_rec.product else f"Estimated {prod_rec.slot_name}"
                    product_data.append([
                        product_name,
                        str(prod_rec.quantity),
                        f"${prod_rec.unit_price:,.2f}",
                        f"${prod_rec.total_price:,.2f}",
                        prod_rec.slot_name.replace('_', ' ').title()
                    ])
                
                product_table = Table(product_data, colWidths=[2.5*inch, 0.6*inch, 1*inch, 1*inch, 1.4*inch])
                product_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Left align product names
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8F9FA'), colors.white])
                ]))
                
                story.append(product_table)
            else:
                story.append(Paragraph("No specific products selected - using estimated pricing.", styles['Normal']))
            
            story.append(Spacer(1, 25))
            
            # Cost breakdown section
            story.append(Paragraph("Investment Summary", subtitle_style))
            
            # Calculate cost breakdown
            cost_breakdown = {}
            for prod_rec in design.product_recommendations.all():
                category = "Estimated Items"
                if prod_rec.product and hasattr(prod_rec.product, 'category'):
                    category = prod_rec.product.category.name
                
                if category not in cost_breakdown:
                    cost_breakdown[category] = 0
                cost_breakdown[category] += float(prod_rec.total_price)
            
            if cost_breakdown:
                breakdown_data = [['Category', 'Amount', 'Percentage']]
                total_cost = float(design.total_cost)
                
                for category, amount in cost_breakdown.items():
                    percentage = (amount / total_cost * 100) if total_cost > 0 else 0
                    breakdown_data.append([
                        category,
                        f"${amount:,.2f}",
                        f"{percentage:.1f}%"
                    ])
                
                breakdown_data.append(['', '', ''])  # Empty row
                breakdown_data.append(['Total Investment', f"${total_cost:,.2f}", '100.0%'])
                
                breakdown_table = Table(breakdown_data, colWidths=[3*inch, 1.5*inch, 1*inch])
                breakdown_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8F6F3')),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#2ECC71')),
                    ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -2), 1, colors.HexColor('#BDC3C7')),
                    ('GRID', (0, -1), (-1, -1), 2, colors.HexColor('#27AE60')),
                ]))
                
                story.append(breakdown_table)
            
            story.append(Spacer(1, 25))
            
            # Additional notes section
            story.append(Paragraph("Important Notes", subtitle_style))
            notes_text = f"""
            <b>Budget Optimization:</b> This design maximizes value within your budget range while maintaining style and quality.<br/><br/>
            <b>Flexibility:</b> Product recommendations can be adjusted based on availability and personal preferences.<br/><br/>
            <b>Next Steps:</b> Contact our design team to discuss implementation, delivery, and installation options.<br/><br/>
            <b>Warranty:</b> All recommended products come with manufacturer warranties and our quality guarantee.<br/><br/>
            <i>This estimate includes furniture only. Delivery, assembly, and installation costs may apply separately.</i>
            """
            
            story.append(Paragraph(notes_text, styles['Normal']))
            
            # Footer
            story.append(Spacer(1, 30))
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#7F8C8D'),
                alignment=1
            )
            story.append(Paragraph(f"Generated on {design.created_at.strftime('%B %d, %Y')} | Design ID: {design.id}", footer_style))
            
            # Build PDF
            doc.build(story)
            pdf_data = buffer.getvalue()
            buffer.close()
            
            return pdf_data
            
        except Exception as e:
            print(f"PDF generation error: {e}")
            return None
