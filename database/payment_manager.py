"""
Sistema de Pagos con PayPal REST API
Maneja pagos, facturas y recibos automáticos
"""

import os
import paypalrestsdk
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class PaymentManager:
    """Gestor de pagos con PayPal"""
    
    def __init__(self):
        """Inicializar SDK de PayPal"""
        self.configure_paypal()
    
    def configure_paypal(self):
        """Configurar API de PayPal"""
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),  # sandbox o live
            "client_id": os.getenv('PAYPAL_CLIENT_ID'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET')
        })
        print("✅ PayPal SDK configurado")
    
    def crear_pago(self, pedido_data, return_url, cancel_url):
        """
        Crear pago en PayPal
        
        Args:
            pedido_data: {
                'numero_pedido': 'PED-123',
                'items': [
                    {'nombre': 'Pizza', 'cantidad': 2, 'precio': 150.00}
                ],
                'subtotal': 300.00,
                'costo_envio': 35.00,
                'total': 335.00,
                'moneda': 'MXN'
            }
            return_url: URL de retorno cuando se aprueba el pago
            cancel_url: URL de cancelación
        
        Returns:
            dict: {'success': bool, 'approval_url': str, 'payment_id': str}
        """
        try:
            # Construir lista de items para PayPal
            items_list = []
            for item in pedido_data['items']:
                items_list.append({
                    "name": item['nombre'],
                    "sku": item.get('codigo', 'ITEM'),
                    "price": f"{item['precio']:.2f}",
                    "currency": pedido_data.get('moneda', 'MXN'),
                    "quantity": item['cantidad']
                })
            
            # Crear objeto de pago
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url,
                    "cancel_url": cancel_url
                },
                "transactions": [{
                    "item_list": {
                        "items": items_list
                    },
                    "amount": {
                        "total": f"{pedido_data['total']:.2f}",
                        "currency": pedido_data.get('moneda', 'MXN'),
                        "details": {
                            "subtotal": f"{pedido_data['subtotal']:.2f}",
                            "shipping": f"{pedido_data.get('costo_envio', 0):.2f}"
                        }
                    },
                    "description": f"Pedido #{pedido_data['numero_pedido']}",
                    "invoice_number": pedido_data['numero_pedido']
                }]
            })
            
            # Crear el pago en PayPal
            if payment.create():
                print(f"✅ Pago creado: {payment.id}")
                
                # Obtener URL de aprobación
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = str(link.href)
                        print(f"🔗 URL de pago: {approval_url}")
                        
                        return {
                            'success': True,
                            'payment_id': payment.id,
                            'approval_url': approval_url
                        }
                
                return {
                    'success': False,
                    'error': 'No se encontró URL de aprobación'
                }
            else:
                print(f"❌ Error creando pago: {payment.error}")
                return {
                    'success': False,
                    'error': payment.error
                }
                
        except Exception as e:
            print(f"❌ Error en crear_pago: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def ejecutar_pago(self, payment_id, payer_id):
        """
        Ejecutar pago después de que el cliente lo apruebe
        
        Args:
            payment_id: ID del pago de PayPal
            payer_id: ID del pagador (viene en la URL de retorno)
        
        Returns:
            dict: {'success': bool, 'transaction_id': str, 'estado': str}
        """
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                print(f"✅ Pago ejecutado exitosamente: {payment_id}")
                
                # Obtener ID de transacción
                transaction_id = payment.transactions[0].related_resources[0].sale.id
                
                return {
                    'success': True,
                    'transaction_id': transaction_id,
                    'estado': payment.state,
                    'payment_details': payment.to_dict()
                }
            else:
                print(f"❌ Error ejecutando pago: {payment.error}")
                return {
                    'success': False,
                    'error': payment.error
                }
                
        except Exception as e:
            print(f"❌ Error en ejecutar_pago: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def obtener_detalles_pago(self, payment_id):
        """
        Obtener detalles de un pago
        
        Args:
            payment_id: ID del pago de PayPal
        
        Returns:
            dict: Detalles completos del pago
        """
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            return {
                'success': True,
                'payment': payment.to_dict()
            }
        except Exception as e:
            print(f"❌ Error obteniendo detalles: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generar_factura(self, pedido_data, cliente_data):
        """
        Generar factura en PayPal
        
        Args:
            pedido_data: Datos del pedido
            cliente_data: Datos del cliente
        
        Returns:
            dict: {'success': bool, 'invoice_id': str, 'invoice_url': str}
        """
        try:
            # Construir items de la factura
            items_list = []
            for item in pedido_data['items']:
                items_list.append({
                    "name": item['nombre'],
                    "quantity": item['cantidad'],
                    "unit_price": {
                        "currency": pedido_data.get('moneda', 'MXN'),
                        "value": f"{item['precio']:.2f}"
                    }
                })
            
            # Crear factura
            invoice = paypalrestsdk.Invoice({
                "merchant_info": {
                    "email": os.getenv('EMAIL_USER', 'tu_email@ejemplo.com'),
                    "business_name": pedido_data.get('restaurante_nombre', 'Tu Restaurante'),
                },
                "billing_info": [{
                    "email": cliente_data.get('email', ''),
                    "first_name": cliente_data.get('nombre', 'Cliente'),
                    "phone": {
                        "country_code": "52",
                        "national_number": cliente_data.get('telefono', '')
                    },
                    "address": {
                        "line1": cliente_data.get('direccion', ''),
                        "city": cliente_data.get('ciudad', ''),
                        "state": cliente_data.get('estado', ''),
                        "postal_code": cliente_data.get('codigo_postal', ''),
                        "country_code": "MX"
                    }
                }],
                "items": items_list,
                "note": f"Pedido #{pedido_data['numero_pedido']}",
                "payment_term": {
                    "term_type": "NET_45"
                },
                "shipping_info": {
                    "first_name": cliente_data.get('nombre', ''),
                    "last_name": "",
                    "address": {
                        "line1": cliente_data.get('direccion', ''),
                        "city": cliente_data.get('ciudad', ''),
                        "state": cliente_data.get('estado', ''),
                        "postal_code": cliente_data.get('codigo_postal', ''),
                        "country_code": "MX"
                    }
                },
                "shipping_cost": {
                    "amount": {
                        "currency": pedido_data.get('moneda', 'MXN'),
                        "value": f"{pedido_data.get('costo_envio', 0):.2f}"
                    }
                }
            })
            
            # Crear factura en PayPal
            if invoice.create():
                print(f"✅ Factura creada: {invoice.id}")
                
                # Enviar factura al cliente por email
                if invoice.send():
                    print(f"✅ Factura enviada al cliente")
                    
                    return {
                        'success': True,
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.number,
                        'total': invoice.total_amount.value
                    }
                else:
                    print(f"⚠️ Factura creada pero no se pudo enviar")
                    return {
                        'success': True,
                        'invoice_id': invoice.id,
                        'warning': 'Factura creada pero no enviada'
                    }
            else:
                print(f"❌ Error creando factura: {invoice.error}")
                return {
                    'success': False,
                    'error': invoice.error
                }
                
        except Exception as e:
            print(f"❌ Error en generar_factura: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    def enviar_recibo(self, payment_id, email_cliente):
        """
        Enviar recibo de pago al cliente
        
        Args:
            payment_id: ID del pago de PayPal
            email_cliente: Email del cliente
        
        Returns:
            dict: {'success': bool}
        """
        try:
            # PayPal envía recibos automáticamente al payer
            # Pero podemos obtener los detalles para enviar nuestro propio recibo
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment:
                print(f"✅ Recibo disponible para pago: {payment_id}")
                print(f"   Cliente: {email_cliente}")
                print(f"   Estado: {payment.state}")
                
                # TODO: Aquí podrías enviar un recibo personalizado por email
                # usando tu sistema de emails (SMTP que ya tienes configurado)
                
                return {
                    'success': True,
                    'message': 'PayPal envía recibo automático al pagador'
                }
            else:
                return {
                    'success': False,
                    'error': 'Pago no encontrado'
                }
                
        except Exception as e:
            print(f"❌ Error en enviar_recibo: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reembolsar_pago(self, sale_id, amount=None):
        """
        Reembolsar un pago (total o parcial)
        
        Args:
            sale_id: ID de la venta (transaction_id)
            amount: Monto a reembolsar (None = reembolso total)
        
        Returns:
            dict: {'success': bool, 'refund_id': str}
        """
        try:
            sale = paypalrestsdk.Sale.find(sale_id)
            
            refund_data = {}
            if amount:
                refund_data = {
                    "amount": {
                        "total": f"{amount:.2f}",
                        "currency": "MXN"
                    }
                }
            
            refund = sale.refund(refund_data)
            
            if refund.success():
                print(f"✅ Reembolso procesado: {refund.id}")
                return {
                    'success': True,
                    'refund_id': refund.id,
                    'state': refund.state
                }
            else:
                print(f"❌ Error en reembolso: {refund.error}")
                return {
                    'success': False,
                    'error': refund.error
                }
                
        except Exception as e:
            print(f"❌ Error en reembolsar_pago: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Instancia global
payment_manager = PaymentManager()