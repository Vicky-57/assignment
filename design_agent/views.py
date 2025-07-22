from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from .models import DesignRecommendation, LayoutTemplate
from .services import DesignAIService
from showroom_agent.models import UserSession
from products.models import Product
import json
from datetime import datetime, timedelta

class GenerateDesignView(APIView):
    def post(self, request):
        """Generate enhanced design recommendation"""
        session_id = request.data.get('session_id')
        room_dimensions = request.data.get('room_dimensions')  # Optional
        budget_range = request.data.get('budget_range')  # Optional: {'min': 2000, 'max': 5000}
        layout_template_id = request.data.get('layout_template_id')  # New: Optional/Required
        print("ROOM DIMENSIONS VALUE:", room_dimensions)

        if not session_id:
            return Response(
                {'error': 'session_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if not layout_template_id:
            return Response(
                {'error': 'layout_template_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            # Validate session exists
            session = UserSession.objects.get(id=session_id)
            # Validate layout template exists
            try:
                layout_template = LayoutTemplate.objects.get(id=layout_template_id)
            except LayoutTemplate.DoesNotExist:
                return Response(
                    {'error': 'Invalid layout_template_id'},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Initialize design service
            design_service = DesignAIService()
            # Generate design recommendation
            result = design_service.generate_design_recommendation(
                session_id, 
                room_dimensions,
                budget_range,
                layout_template_id=layout_template_id
            )
            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
            # Add additional metadata
            result['generated_at'] = datetime.now().isoformat()
            result['session_preferences'] = session.preferences
            return Response(result, status=status.HTTP_201_CREATED)
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Invalid session_id'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Design generation failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DesignDetailsView(APIView):
    def get(self, request, design_id):
        """Get comprehensive design recommendation details"""
        try:
            design = DesignRecommendation.objects.select_related(
                'layout_template', 'session'
            ).prefetch_related(
                'product_recommendations__product__category'
            ).get(id=design_id)
            
            # Build product details
            product_details = []
            category_totals = {}
            
            for prod_rec in design.product_recommendations.all():
                # Product info
                product_info = {
                    'id': str(prod_rec.id),
                    'slot_name': prod_rec.slot_name,
                    'quantity': prod_rec.quantity,
                    'unit_price': float(prod_rec.unit_price),
                    'total_price': float(prod_rec.total_price),
                    'reasoning': prod_rec.reasoning,
                }
                
                # Add product details if available
                if prod_rec.product:
                    product_info.update({
                        'product_id': str(prod_rec.product.id),
                        'name': prod_rec.product.name,
                        'sku': prod_rec.product.sku,
                        'category': prod_rec.product.category.name,
                        'style': prod_rec.product.style,
                        'material': getattr(prod_rec.product, 'material', ''),
                        'description': getattr(prod_rec.product, 'description', ''),
                        'rating': getattr(prod_rec.product, 'rating', None),
                        'is_available': getattr(prod_rec.product, 'is_available', True),
                    })
                    
                    # Category totals
                    category = prod_rec.product.category.name
                    if category not in category_totals:
                        category_totals[category] = {'count': 0, 'total': 0}
                    category_totals[category]['count'] += prod_rec.quantity
                    category_totals[category]['total'] += float(prod_rec.total_price)
                else:
                    product_info.update({
                        'name': f"Estimated {prod_rec.slot_name.replace('_', ' ').title()}",
                        'category': 'Estimated',
                        'is_estimated': True
                    })
                
                product_details.append(product_info)
            
            # Calculate additional metrics
            total_items = sum(prod_rec.quantity for prod_rec in design.product_recommendations.all())
            avg_item_cost = float(design.total_cost) / total_items if total_items > 0 else 0
            try:
                room_dimensions = json.loads(design.room_dimensions) if isinstance(design.room_dimensions, str) else design.room_dimensions
            except Exception:
                room_dimensions = {}
            # Build response
            response_data = {
                'design_id': str(design.id),
                'template': {
                    'id': design.layout_template.id,
                    'name': design.layout_template.name,
                    'room_type': design.layout_template.room_type,
                    'style': design.layout_template.style,
                    'image': design.layout_template.image.url,
                    'description': design.layout_template.template_description,
                    'color_palette': getattr(design.layout_template, 'color_palette', []),
                    'estimated_budget': getattr(design.layout_template, 'estimated_budget', {}),
                },
                'room_details': {
                    'dimensions': room_dimensions,
                    'area_sqft': room_dimensions.get('area_sqft', 0),
                },
                'user_preferences': design.user_preferences,
                'ai_reasoning': design.ai_reasoning,
                'cost_analysis': {
                    'total_cost': float(design.total_cost),
                    'total_items': total_items,
                    'average_item_cost': round(avg_item_cost, 2),
                    'category_breakdown': category_totals,
                    'cost_per_sqft': round(float(design.total_cost) / max(design.room_dimensions.get('area_sqft', 1), 1), 2)
                },
                'products': product_details,
                'status': design.status,
                'timestamps': {
                    'created_at': design.created_at.isoformat(),
                    'updated_at': design.updated_at.isoformat(),
                },
                'metadata': {
                    'product_count': len(product_details),
                    'required_items_count': len([p for p in design.layout_template.product_slots if p.get('required', False)]),
                    'optional_items_count': len([p for p in design.layout_template.product_slots if not p.get('required', False)]),
                }
            }
            
            return Response(response_data)
            
        except DesignRecommendation.DoesNotExist:
            return Response(
                {'error': 'Design recommendation not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve design details: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ExportPDFView(APIView):
    def get(self, request, design_id):
        """Export design as enhanced PDF"""
        try:
            # Verify design exists
            design = DesignRecommendation.objects.get(id=design_id)
            
            design_service = DesignAIService()
            pdf_data = design_service.generate_pdf_report(design_id)
            
            if pdf_data:
                response = HttpResponse(pdf_data, content_type='application/pdf')
                filename = f"design_recommendation_{design.layout_template.name.lower().replace(' ', '_')}_{design_id}.pdf"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Content-Length'] = len(pdf_data)
                return response
            else:
                return Response(
                    {'error': 'PDF generation failed'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except DesignRecommendation.DoesNotExist:
            return Response(
                {'error': 'Design recommendation not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'PDF export failed: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TemplatesView(APIView):
    def get(self, request):
        """Get available layout templates"""
        templates = LayoutTemplate.objects.all()
        
        template_data = []
        for template in templates:
            template_data.append({
                'id': template.id,
                'image':template.image.url,
                'name': template.name,
                'room_type': template.room_type,
                'style': template.style,
                'dimensions': template.dimensions,
                'description': template.template_description,
                'product_slots': template.product_slots
            })
        
        return Response({'templates': template_data})

