from django.urls import path
from .views import generate_email, home, send_email, send_bulk_email,get_templates  # Added send_bulk_email

urlpatterns = [
    path('', home, name='home'),
    path('generate_email/', generate_email, name='generate_email'),
    path('send_email/', send_email, name='send_email'),
    path('send_bulk_email/', send_bulk_email, name='send_bulk_email'),  # New route for bulk email sending
     path("templates/", get_templates, name="get_templates"),
]

