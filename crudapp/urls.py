from django.urls import path
from . import views

urlpatterns = [
    path('', views.bus_booking, name='bus_booking'),
    path('report/', views.booking_report, name='booking_report'),  # make sure this matches the function
    path('download/<int:booking_id>/', views.download_ticket_pdf, name='download_ticket_pdf'),
    path('send_email/', views.send_ticket_email, name='send_ticket_email'),
    path('preview/<int:booking_id>/', views.ticket_preview, name='ticket_preview'),
]
