
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

class DesignAIService:
    def __init__(self):
        self.layout_templates = self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize comprehensive layout templates"""
        templates = {
            'living_room_modern': {
                'name': 'Modern Living Room',
                'room_type': 'living_room',
                'style': 'modern',
                'dimensions': {'width': 14, 'height': 12, 'area_sqft': 168},
                'product_slots': [
                    {'name': 'main_sofa', 'category': 'Seating', 'required': True, 'quantity': 1, 'budget_percentage': 35},
                    {'name': 'coffee_table', 'category': 'Tables', 'required': True, 'quantity': 1, 'budget_percentage': 15},
                    {'name': 'accent_chair', 'category': 'Seating', 'required': False, 'quantity': 1, 'budget_percentage': 20},
                    {'name': 'floor_lamp', 'category': 'Lighting', 'required': True, 'quantity': 1, 'budget_percentage': 10},
                    {'name': 'table_lamp', 'category': 'Lighting', 'required': False, 'quantity': 1, 'budget_percentage': 8},
                    {'name': 'tv_stand', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 12},
                ],
                'color_palette': ['#2C3E50', '#ECF0F1', '#3498DB', '#E74C3C'],
                'estimated_budget': {'min': 2500, 'max': 8000}
            },
            'living_room_scandinavian': {
                'name': 'Scandinavian Living Room',
                'room_type': 'living_room',
                'style': 'scandinavian',
                'dimensions': {'width': 13, 'height': 11, 'area_sqft': 143},
                'product_slots': [
                    {'name': 'sectional_sofa', 'category': 'Seating', 'required': True, 'quantity': 1, 'budget_percentage': 40},
                    {'name': 'wooden_coffee_table', 'category': 'Tables', 'required': True, 'quantity': 1, 'budget_percentage': 18},
                    {'name': 'accent_chair', 'category': 'Seating', 'required': False, 'quantity': 1, 'budget_percentage': 15},
                    {'name': 'pendant_light', 'category': 'Lighting', 'required': True, 'quantity': 1, 'budget_percentage': 12},
                    {'name': 'bookshelf', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 15},
                ],
                'color_palette': ['#FFFFFF', '#F5F5DC', '#D2B48C', '#8FBC8F'],
                'estimated_budget': {'min': 2000, 'max': 6500}
            },
            'bedroom_modern': {
                'name': 'Modern Bedroom',
                'room_type': 'bedroom',
                'style': 'modern',
                'dimensions': {'width': 12, 'height': 10, 'area_sqft': 120},
                'product_slots': [
                    {'name': 'platform_bed', 'category': 'Beds', 'required': True, 'quantity': 1, 'budget_percentage': 45},
                    {'name': 'nightstand', 'category': 'Tables', 'required': True, 'quantity': 2, 'budget_percentage': 20},
                    {'name': 'dresser', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 25},
                    {'name': 'bedside_lamp', 'category': 'Lighting', 'required': True, 'quantity': 2, 'budget_percentage': 10},
                ],
                'color_palette': ['#2C3E50', '#FFFFFF', '#BDC3C7', '#E67E22'],
                'estimated_budget': {'min': 1800, 'max': 5500}
            },
            'bedroom_minimalist': {
                'name': 'Minimalist Bedroom',
                'room_type': 'bedroom',
                'style': 'minimalist',
                'dimensions': {'width': 11, 'height': 9, 'area_sqft': 99},
                'product_slots': [
                    {'name': 'simple_bed', 'category': 'Beds', 'required': True, 'quantity': 1, 'budget_percentage': 50},
                    {'name': 'floating_nightstand', 'category': 'Tables', 'required': True, 'quantity': 1, 'budget_percentage': 15},
                    {'name': 'wall_mounted_light', 'category': 'Lighting', 'required': True, 'quantity': 2, 'budget_percentage': 20},
                    {'name': 'minimal_wardrobe', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 15},
                ],
                'color_palette': ['#FFFFFF', '#F8F9FA', '#495057', '#6C757D'],
                'estimated_budget': {'min': 1200, 'max': 3500}
            },
            'dining_room_contemporary': {
                'name': 'Contemporary Dining Room',
                'room_type': 'dining_room',
                'style': 'contemporary',
                'dimensions': {'width': 10, 'height': 12, 'area_sqft': 120},
                'product_slots': [
                    {'name': 'dining_table', 'category': 'Tables', 'required': True, 'quantity': 1, 'budget_percentage': 40},
                    {'name': 'dining_chairs', 'category': 'Seating', 'required': True, 'quantity': 6, 'budget_percentage': 30},
                    {'name': 'buffet', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 20},
                    {'name': 'chandelier', 'category': 'Lighting', 'required': True, 'quantity': 1, 'budget_percentage': 10},
                ],
                'color_palette': ['#34495E', '#FFFFFF', '#F39C12', '#E74C3C'],
                'estimated_budget': {'min': 2200, 'max': 7000}
            },
            'office_industrial': {
                'name': 'Industrial Home Office',
                'room_type': 'office',
                'style': 'industrial',
                'dimensions': {'width': 10, 'height': 8, 'area_sqft': 80},
                'product_slots': [
                    {'name': 'executive_desk', 'category': 'Tables', 'required': True, 'quantity': 1, 'budget_percentage': 35},
                    {'name': 'office_chair', 'category': 'Seating', 'required': True, 'quantity': 1, 'budget_percentage': 25},
                    {'name': 'bookshelf', 'category': 'Storage', 'required': True, 'quantity': 1, 'budget_percentage': 20},
                    {'name': 'desk_lamp', 'category': 'Lighting', 'required': True, 'quantity': 1, 'budget_percentage': 10},
                    {'name': 'filing_cabinet', 'category': 'Storage', 'required': False, 'quantity': 1, 'budget_percentage': 10},
                ],
                'color_palette': ['#2C3E50', '#95A5A6', '#E67E22', '#C0392B'],
                'estimated_budget': {'min': 1500, 'max': 4500}
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
                    'template_description': f"A {template_data['style']} {template_data['room_type'].replace('_', ' ')} layout with carefully selected furniture pieces.",
                    'color_palette': template_data.get('color_palette', []),
                    'estimated_budget': template_data.get('estimated_budget', {})
                }
            )
        
        return LayoutTemplate.objects.all()
    
    def generate_design_recommendation(self, session_id, room_dimensions=None, budget_range=None):
        """Generate a comprehensive design recommendation"""
        try:
            session = UserSession.objects.get(id=session_id)
            preferences = session.preferences
            
            try:
                if isinstance(budget_range, str):
                    import json
                    budget_range = json.loads(budget_range)
            except Exception:
                budget_range = None

            if isinstance(budget_range, int):
                budget_range = {"min": budget_range, "max": budget_range}
            elif not isinstance(budget_range, dict):
                budget_range = None

            # Select appropriate template
            template = self._select_template(preferences)
            if not template:
                return {'error': 'No suitable template found for your preferences'}
            
            # Use provided dimensions or template defaults
            dimensions = room_dimensions or template.dimensions
            
            # Determine budget
            if budget_range:
                total_budget = budget_range.get('max', 5000)
            else:
                estimated_budget = getattr(template, 'estimated_budget', {'min': 2000, 'max': 5000})
                total_budget = estimated_budget.get('max', 5000)
            
            print(f"Raw budget_range: {budget_range} ({type(budget_range)})")

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
            
            for slot in template.product_slots:
                slot_budget = (total_budget * slot.get('budget_percentage', 10)) / 100
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
                        product_id=None,  # Placeholder product
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
                'estimated_budget': getattr(template, 'estimated_budget', {}),
                'color_palette': getattr(template, 'color_palette', []),
                'ai_reasoning': ai_reasoning,
                'product_count': len(product_recommendations),
                'cost_breakdown': self._generate_cost_breakdown(product_recommendations),
                'design_features': self._generate_design_features(template, preferences),
                'status': 'success'
            }
            
        except Exception as e:
            print(f"Design generation error: {str(e)}")
            return {'error': f'Design generation failed: {str(e)}'}
    
    def _create_fallback_products(self, template, total_budget):
        """Create fallback products when no real products are found"""
        fallback_products = []
        
        # Sample product data based on template slots
        sample_products = {
            'main_sofa': {'name': 'Modern 3-Seat Sofa', 'price_range': (800, 2500)},
            'coffee_table': {'name': 'Glass Coffee Table', 'price_range': (200, 800)},
            'accent_chair': {'name': 'Accent Armchair', 'price_range': (300, 1200)},
            'floor_lamp': {'name': 'Modern Floor Lamp', 'price_range': (100, 400)},
            'platform_bed': {'name': 'Platform Bed Frame', 'price_range': (400, 1500)},
            'nightstand': {'name': 'Bedside Table', 'price_range': (150, 500)},
            'dining_table': {'name': 'Dining Table', 'price_range': (500, 2000)},
            'dining_chairs': {'name': 'Dining Chair', 'price_range': (80, 300)},
            'executive_desk': {'name': 'Executive Desk', 'price_range': (400, 1200)},
            'office_chair': {'name': 'Ergonomic Office Chair', 'price_range': (200, 800)},
        }
        
        for slot in template.product_slots:
            slot_name = slot['name']
            quantity = slot.get('quantity', 1)
            budget_percentage = slot.get('budget_percentage', 10)
            slot_budget = (total_budget * budget_percentage) / 100
            
            # Get sample product or create generic one
            if slot_name in sample_products:
                product_info = sample_products[slot_name]
                unit_price = min(slot_budget / quantity, random.uniform(*product_info['price_range']))
            else:
                # Generic product
                product_info = {'name': f'{slot_name.replace("_", " ").title()}'}
                unit_price = slot_budget / quantity
            
            fallback_products.append({
                'slot_name': slot_name,
                'name': product_info['name'],
                'quantity': quantity,
                'unit_price': round(unit_price, 2),
                'total_price': round(unit_price * quantity, 2),
                'reasoning': f"Selected {product_info['name']} to complete the {template.style} {template.room_type.replace('_', ' ')} design within budget constraints."
            })
        
        return fallback_products
    
    def _recommend_products_for_slot(self, slot, preferences, slot_budget):
        """Recommend products for a specific slot with improved logic"""
        try:
            # Start with broad category search
            products = Product.objects.filter(is_available=True)
            
            # Apply category filter (more flexible)
            category_keywords = slot['category'].lower()
            if 'seating' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(chair|sofa|seating|seat)'
                )
            elif 'table' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(table|desk)'
                )
            elif 'bed' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(bed|mattress)'
                )
            elif 'lighting' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(light|lamp)'
                )
            elif 'storage' in category_keywords:
                products = products.filter(
                    category__name__iregex=r'(storage|cabinet|shelf|dresser|wardrobe)'
                )
            
            # Apply budget filter
            max_unit_price = slot_budget / slot.get('quantity', 1)
            products = products.filter(price__lte=max_unit_price * 1.2)  # 20% tolerance
            
            # Apply style preference if available
            if preferences.get('style') and products.filter(style=preferences['style']).exists():
                products = products.filter(style=preferences['style'])
            
            # Apply room type preference if available
            if preferences.get('room_type') and products.filter(room_type=preferences['room_type']).exists():
                products = products.filter(room_type=preferences['room_type'])
            
            # Select best product(s) for this slot
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
            else:
                print(f"No products found for slot: {slot['name']}, category: {slot['category']}")
            
            return selected_products
            
        except Exception as e:
            print(f"Product recommendation error for slot {slot['name']}: {e}")
            return []
    
    def _generate_product_reasoning(self, product, slot, preferences):
        """Generate detailed reasoning for product selection"""
        reasons = []
        
        # Style match
        if preferences.get('style') == product.style:
            reasons.append(f"matches your preferred {product.style} style")
        
        # Functionality
        slot_name = slot['name'].replace('_', ' ')
        reasons.append(f"perfectly suited for {slot_name} functionality")
        
        # Quality/Material
        if hasattr(product, 'material') and product.material:
            reasons.append(f"high-quality {product.material} construction")
        
        # Budget consideration
        reasons.append("fits within the allocated budget")
        
        return f"This {product.name} was selected because it " + ", ".join(reasons) + "."
    
    def _generate_cost_breakdown(self, product_recommendations):
        """Generate detailed cost breakdown"""
        breakdown = {}
        total = 0
        
        for prod_rec in product_recommendations:
            category = getattr(prod_rec.product, 'category', 'Other') if prod_rec.product else 'Estimated'
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
        """Generate key design features"""
        features = []
        
        # Style-based features
        style = template.style.lower()
        if 'modern' in style:
            features.extend(['Clean lines', 'Minimalist approach', 'Neutral color palette', 'Functional design'])
        elif 'scandinavian' in style:
            features.extend(['Natural materials', 'Light colors', 'Cozy atmosphere', 'Sustainable choices'])
        elif 'industrial' in style:
            features.extend(['Raw materials', 'Metal accents', 'Urban aesthetic', 'Functional elements'])
        elif 'minimalist' in style:
            features.extend(['Clutter-free design', 'Essential furniture only', 'Calm environment', 'Quality over quantity'])
        
        # Room-based features
        room_type = template.room_type
        if room_type == 'living_room':
            features.extend(['Comfortable seating arrangement', 'Entertainment-focused layout', 'Social interaction zones'])
        elif room_type == 'bedroom':
            features.extend(['Relaxing atmosphere', 'Optimal storage solutions', 'Private retreat feel'])
        elif room_type == 'dining_room':
            features.extend(['Perfect for entertaining', 'Elegant dining experience', 'Proper lighting for meals'])
        elif room_type == 'office':
            features.extend(['Productivity-focused design', 'Ergonomic furniture', 'Professional appearance'])
        
        return features[:6]  # Return top 6 features
    
    def _select_template(self, preferences):
        """Enhanced template selection logic"""
        room_type = preferences.get('room_type', 'living_room')
        style = preferences.get('style', 'modern')
        budget = preferences.get('budget', 'medium')
        
        # Try exact match first
        template = LayoutTemplate.objects.filter(
            room_type=room_type,
            style=style
        ).first()
        
        if not template:
            # Try room type match
            template = LayoutTemplate.objects.filter(room_type=room_type).first()
        
        if not template:
            # Try style match
            template = LayoutTemplate.objects.filter(style=style).first()
        
        if not template:
            # Final fallback
            template = LayoutTemplate.objects.first()
        
        return template
    
    def _generate_design_reasoning(self, preferences, template, dimensions, budget):
        """Generate comprehensive AI explanation for design choices"""
        try:
            prompt = f"""
As an expert interior designer, create a detailed explanation for this design recommendation.

User Preferences: {json.dumps(preferences)}
Selected Template: {template.name} - {template.template_description}
Room Dimensions: {dimensions}
Budget: ${budget:,}
Style: {template.style}

Provide a professional, engaging explanation (3-4 paragraphs) covering:
1. Why this specific layout and style perfectly match the user's needs and space
2. How the color palette and materials create the desired atmosphere
3. The functional benefits and flow of this design approach
4. How the budget allocation ensures maximum value and impact

Make it personal, informative, and inspiring while staying professional.
"""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"""This {template.name} design perfectly captures the essence of {template.style} style while maximizing functionality for your space. 

The carefully selected color palette and materials create a harmonious environment that reflects your personal taste. Each furniture piece has been strategically placed to ensure optimal flow and usability.

With a total budget of ${budget:,}, this design offers exceptional value by prioritizing key pieces that make the biggest visual and functional impact. The result is a space that's both beautiful and highly livable."""
    
    def _ai_select_best_product(self, products, slot, preferences, slot_budget):
        """Enhanced AI product selection with better scoring"""
        if len(products) == 1:
            return products.first()
        
        # Score products based on multiple criteria
        scored_products = []
        max_unit_price = slot_budget / slot.get('quantity', 1)
        
        for product in products[:10]:  # Limit for performance
            score = 0
            
            # Style match (high priority)
            if preferences.get('style') == getattr(product, 'style', ''):
                score += 5
            
            # Room type match
            if preferences.get('room_type') == getattr(product, 'room_type', ''):
                score += 3
            
            # Price optimization (prefer products using 70-90% of slot budget)
            price_ratio = product.price / max_unit_price if max_unit_price > 0 else 0
            if 0.7 <= price_ratio <= 0.9:
                score += 4
            elif 0.5 <= price_ratio <= 1.0:
                score += 2
            
            # Availability
            if getattr(product, 'is_available', True):
                score += 2
            
            # Quality indicators (if available)
            if hasattr(product, 'rating') and product.rating:
                score += min(product.rating, 3)  # Cap at 3 points
            
            # Material preference (if specified)
            preferred_material = preferences.get('material')
            if preferred_material and hasattr(product, 'material'):
                if preferred_material.lower() in product.material.lower():
                    score += 2
            
            scored_products.append((product, score))
        
        # Return highest scoring product
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
            overview_data = [
                ['Template:', design.layout_template.name],
                ['Room Type:', design.layout_template.room_type.replace('_', ' ').title()],
                ['Style:', design.layout_template.style.title()],
                ['Dimensions:', f"{design.room_dimensions.get('width', 'N/A')}' × {design.room_dimensions.get('height', 'N/A')}'"],
                ['Area:', f"{design.room_dimensions.get('area_sqft', 'N/A')} sq ft"],
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