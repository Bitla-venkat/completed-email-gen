import json
import os
import logging
import csv
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import EmailMessage
from django.core.files.storage import default_storage
from huggingface_hub import InferenceClient
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load API key from environment variable
HF_API_KEY = "replace with ur key"

# Email templates
TEMPLATES = {
    "job_application": "Write a professional email applying for a software engineer position.",
    "business_proposal": "Write a formal email proposing a business collaboration.",
    "client_followup": "Write a polite follow-up email to a client about a previous discussion.",
    "product_promotion": "Write a compelling email promoting a new product and encouraging the recipient to buy.",
    "webinar_invitation": "Write an engaging email inviting people to a webinar and urging them to register.",
    "newsletter_signup": "Write a friendly email encouraging users to sign up for a newsletter.",
    "event_registration": "Write a persuasive email urging people to register for an upcoming event.",
    "free_trial_offer": "Write a persuasive email offering a free trial of a service and urging the recipient to sign up.",
    "company_rejection": "Write a professional and empathetic rejection email to a job candidate, appreciating their time and effort."
}

def home(request):
    return render(request, "generator/index.html")

@csrf_exempt
def generate_email(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            user_details = data.get("custom_details", "")
            template_key = data.get("template", "job_application")
            template_prompt = TEMPLATES.get(template_key, "")

            prompt = f"""
            Please write a professional email with the following details:
            - **Context:** {template_prompt}
            - **User Input:** {user_details}
            The email must be complete, professional, and include a clear call-to-action.
            """

            client = InferenceClient(api_key=HF_API_KEY)
            response = client.text_generation(
                model="mistralai/Mistral-7B-Instruct-v0.3",
                prompt=prompt,
                max_new_tokens=500,
                temperature=0.7
            )

            generated_email_content = response.strip() if response else "Error: AI did not return a response."
            logger.info("AI Response: %s", generated_email_content)

            return JsonResponse({"message": "Email generated successfully!", "email_preview": generated_email_content})
        except Exception as e:
            logger.error("Error generating email: %s", str(e))
            return JsonResponse({"error": f"Exception occurred: {str(e)}"}, status=500)
    return JsonResponse({"error": "Only POST requests allowed"}, status=405)

@csrf_exempt
def send_email(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            recipient_email = data.get("recipient", "").strip()
            recipient_name = data.get("name", "").strip() or "Valued Customer"
            template_key = data.get("template", "job_application").strip()
            custom_details = data.get("custom_details", "").strip()

            if not recipient_email:
                return JsonResponse({"error": "Recipient email is required"}, status=400)

            template_prompt = TEMPLATES.get(template_key, "")
            prompt = f"""
            Please write an email with the following details:
            - **Context:** {template_prompt +"in 300 tokens"}
            - **User Input:** {custom_details}
            - **Recipient Name:** {recipient_name}
            
            The email must be professional, personalized, and include a warm greeting.
            """

            client = InferenceClient(api_key=HF_API_KEY)
            response = client.text_generation(
                model="mistralai/Mistral-7B-Instruct-v0.3",
                prompt=prompt,
                max_new_tokens=300,
                temperature=0.7
            )

            email_body = response.strip() if response else "Error: AI did not return a response."
            personalized_email = f"Dear {recipient_name},\n\n{email_body}"

            email = EmailMessage(
                subject="Your AI-Generated Email",
                body=personalized_email,
                from_email=os.getenv("EMAIL_HOST_USER", "your-email@gmail.com"),
                to=[recipient_email]
            )
            email.send(fail_silently=False)

            logger.info(f"Email sent successfully to {recipient_email}")
            return JsonResponse({"message": "Email sent successfully!"})

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return JsonResponse({"error": f"Error sending email: {str(e)}"}, status=500)

    return JsonResponse({"error": "Only POST requests allowed"}, status=405)

@csrf_exempt
def send_bulk_email(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        try:
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode("utf-8")
            csv_reader = csv.DictReader(decoded_file.splitlines())

            ui_template = request.POST.get("template", "").strip()
            ui_custom_details = request.POST.get("custom_details", "").strip()

            recipients = []
            for row in csv_reader:
                name = row.get("name", "").strip() or "Valued Customer"
                email = row.get("email", "").strip()
                template = row.get("template", "").strip() or ui_template or "job_application"

                csv_custom_details = row.get("custom_details", "").strip()
                custom_details = f"{csv_custom_details}\n{ui_custom_details}".strip() if csv_custom_details or ui_custom_details else ""

                if email:
                    recipients.append({"name": name, "email": email, "template": template, "custom_details": custom_details})

            if not recipients:
                return JsonResponse({"error": "CSV file is empty or invalid"}, status=400)

            results = []
            client = InferenceClient(api_key=HF_API_KEY)

            for recipient in recipients:
                template_prompt = TEMPLATES.get(recipient["template"], "")
                prompt = f"""
                Please write an email with the following details:
                - **Context:** {template_prompt + "in 300 tokens"}
                - **User Input:** {recipient['custom_details']}
                - **Recipient Name:** {recipient['name']}
                
                The email must be professional, personalized, and include a warm greeting.
                """

                try:
                    response = client.text_generation(
                        model="mistralai/Mistral-7B-Instruct-v0.3",
                        prompt=prompt,
                        max_new_tokens=300,
                        temperature=0.7
                    )

                    email_body = response.strip() if response else "Error: AI did not return a response."
                except Exception as e:
                    logger.error(f"AI Generation failed for {recipient['email']}: {str(e)}")
                    email_body = "Error: AI failed to generate an email."

                personalized_email = f"Dear {recipient['name']},\n\n{email_body}"

                try:
                    email = EmailMessage(
                        subject="Your AI-Generated Email",
                        body=personalized_email,
                        from_email=os.getenv("EMAIL_HOST_USER", "your-email@gmail.com"),
                        to=[recipient["email"]]
                    )
                    email.send(fail_silently=False)
                    results.append({"email": recipient["email"], "status": "Sent"})
                except Exception as e:
                    logger.error(f"Error sending email to {recipient['email']}: {str(e)}")
                    results.append({"email": recipient["email"], "status": f"Failed - {str(e)}"})

                time.sleep(1)  # Prevents API rate limiting

            return JsonResponse({"message": "Bulk emails processed!", "results": results})
        except Exception as e:
            logger.error(f"Bulk email processing error: {str(e)}")
            return JsonResponse({"error": f"Bulk email error: {str(e)}"}, status=500)
    
    return JsonResponse({"error": "Only POST requests with a CSV file allowed"}, status=405)

def open_page(request):
    return render(request,"generator/first_page.html")

def get_templates(request):
    return JsonResponse({"templates": TEMPLATES})
