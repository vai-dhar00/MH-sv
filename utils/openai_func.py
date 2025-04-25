import sqlite3
import boto3
import requests
import json
import re
from datetime import datetime, timedelta, timezone
import msal
from msal import ConfidentialClientApplication
from datetime import datetime
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Add constants for Microsoft Graph API and AWS
OUTLOOK_CLIENT_ID = "25875349-a119-4be3-a20b-a7731714dc95"
OUTLOOK_CLIENT_SECRET = "ylT8Q~YsjMAci~cQzgF3zUtb44Uq8GmBFuKxIb5H"
OUTLOOK_TENANT_ID = "common"
OUTLOOK_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Mail.Send",
    "Mail.ReadWrite",
    "Calendars.ReadWrite",
]
S3_BUCKET_NAME = "outlook-authentication-tokens"
s3_client = boto3.client('s3', region_name='us-east-1')


def get_time():
    # Time in ISO 8601 format in IST timezone
    time = datetime.now().isoformat()
    time += "+05:30"
    return time

def get_summary(client, thread_id):
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    summary = ""
    for message in messages.data:
        if message.role == "user":
            summary = f"**User**: {message.content[0].text.value}\n" + summary
        else:
            summary = f"**Assistant**: {message.content[0].text.value}\n" + summary

    # Use LLM
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": ("The following is a conversation between a user and an insurance assistant. The conversation is divided into four parts: Firstly the user come on the webpage and Suresh greets him and asks for his name. This conversation goes on"
             " until Suresh provide the user with the application link and inputs user data into the database.\n\n The second part of the conversation is when the user fills out the form and Suresh helps him to fill the form\n\n"
             "The third part of thre conversation is when Suresh helps the user schedule a medical appointment and stays with user until insurance is issued\n\n"
             "The last and final part of the conversation is when user ask for something to change after the form is issued and Suresh helps him to change the details in the database\n\n"
             "Give summary of each section independently and it is okay if any part of insurance application is missing. Just omit it and move onto next part of the insurance application")},
            {"role": "user", "content": summary}
        ]
    )

    summary = response.choices[0].message.content
    return summary

def data_entry_user(name, phone_number, email, thread_id, file_path = "data.db", client = None, forward_link = None, smoke = 'no', sum_assured = 0, annual_income = 0, term = 0, gender = 'male'):
    conversation_summary = get_summary(client, thread_id)
    conn = sqlite3.connect(file_path)
    sqlite_cursor = conn.cursor()

    sqlite_cursor.execute("INSERT INTO insurance_applications (name, mobile, email, thread_id, conversation_summary, sum_assured, annual_income, smoking, term, gender) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, phone_number, email, thread_id, conversation_summary, sum_assured, annual_income, smoke, term, gender))
    conn.commit()
    next_steps = buy_now(forward_link, thread_id, client)
    return f"Thank you for your time, please find the next steps here: {next_steps}"

def sum_assured(age: int, annual_income: str,thread_id,  retirement_age: int = 60, client = None):
    try:
        final_value = int((1.07)**float((retirement_age - age)) * float(annual_income))
        return f"Results: Sum assured is {final_value}"
    except Exception as e:
        return f"Error: {str(e)}"


def calculate_term_insurance_premium(age, smoker, sum_assured, gender, thread_id, term=30, client = None):
    """
    Calculate term insurance premium based on age, smoking status, sum assured, gender and term.
    
    Args:
        age (int): Age of the insured person (18-60)
        smoker (str): 'yes' or 'no'
        sum_assured (float): Insurance amount in INR (min 500,000)
        gender (str): 'male' or 'female'
        term (int): Policy term in years (5-35)
    
    Returns:
        float or str: Annual premium amount rounded to 2 decimal places or error message
    """
    # Define base rates (male non-smoker rates per 1000 INR)
    age_brackets = [
        (18, 30, 0.85),
        (31, 35, 1.24),
        (36, 40, 1.88),
        (41, 45, 2.91),
        (46, 50, 3.9),
        (51, 55, 6.4),
        (56, 60, 8.5)  # Added missing bracket for ages 56-60
    ]

    # Validate inputs
    if not isinstance(age, (int, float)) or not isinstance(term, (int, float)):
        return "Age and term must be numbers"
    if not isinstance(sum_assured, (int, float)):
        return "Sum assured must be a number"
    if not isinstance(gender, str) or not isinstance(smoker, str):
        return "Gender and smoker status must be strings"
        
    # Convert inputs to proper format
    age = int(age)
    term = int(term)
    sum_assured = float(sum_assured)
    gender = gender.lower()
    smoker = smoker.lower()

    # Validate ranges and values
    if not (18 <= age <= 60):
        return "Age must be between 18-60"
    if term < 5 or term > 35:
        return "Policy term must be between 5-35 years"
    if age + term > 65:
        return "Age + policy term cannot exceed 65 years"
    if sum_assured < 500000:
        return "Minimum sum assured is INR 500,000"
    if gender not in ['male', 'female']:
        return "Invalid gender input"
    if smoker not in ['yes', 'no']:
        return "Invalid smoker status"
        
    # Find base rate based on age
    base_rate = None
    for min_age, max_age, rate in age_brackets:
        if min_age <= age <= max_age:
            base_rate = rate
            break
            
    if base_rate is None:
        return f"No rate found for age {age}"

    # Apply risk factors
    if smoker == 'yes':
        base_rate *= 1.25  # 25% loading for smokers
    if gender == 'female':
        base_rate *= 0.9  # 10% discount for females
        
    # Calculate annual premium
    annual_premium = (sum_assured / 1000) * base_rate
    
    # Apply term factor (longer terms might have different rates)
    if term > 20:
        annual_premium *= 1.1  # 10% loading for terms > 20 years
        
    return str(round(annual_premium, 2))


def retreive_chat_history(thread_id, client = None, name = 'user'):
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    output_str = ''
    for message in messages.data:
        role = str(message.role)
        if role=='user':
            role = name
        content = str(message.content[0].text.value)
        output_str = f"{role} > {content}\n" + output_str
    return output_str    


def send_email_kiran(name, email, reference_number, sum_assured, term, thread_id, client):
    ses_client = boto3.client('ses', region_name='us-east-1')
    subject = "Congratulations! Your policy is live"
    
    # Create message container
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = "kninnovate@outlook.com"
    msg['To'] = email

    # Email text body
    body = f"""Dear {name},
Congratulations! Your Future Generali Care Plus Plan policy has been successfully issued. We’re delighted to have you as a valued member of the Future Generali Life Insurance family.

Your Policy at a Glance
✅ Policy Number: {reference_number}
✅ Coverage Amount: ₹{sum_assured}
✅ Policy Term: {term} years

For full details, please refer to your attached policy document (PDF).

What’s Next?
- Keep this policy document safe for future reference.
- You can access your policy details anytime through our customer portal.

For any queries, feel free to contact our support team.

Thank you for choosing Future Generali Life Insurance. We’re committed to protecting your future and providing you with peace of mind.

Best regards,
Future Generali Life Insurance"""
    msg.attach(MIMEText(body, 'plain'))

    # PDF attachment
    filename = 'Sample.pdf'
    filepath = filename  # Assuming the file is in the same directory
    try:
        with open(filepath, 'rb') as attachment:
            part = MIMEApplication(attachment.read(), Name=os.path.basename(filename))
            part['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(filename))
            msg.attach(part)
    except Exception as e:
        return f"Error attaching PDF: {str(e)}"

    try:
        # Send the email
        response = ses_client.send_raw_email(
            Source="kninnovate@outlook.com",
            Destinations=[email],
            RawMessage={'Data': msg.as_string()}
        )
        return f"Email sent successfully to {email}"
    except Exception as e:
        return f"Error sending email: {str(e)}. Try again later."


def send_email_maya(name, form_data:str,  email, client, thread_id):
    ses_client = boto3.client('ses', region_name='us-east-1')
    subject = "Future Generali Care Plus Plan Application Received"
    body = f"""Dear {name},
Thank you for completing your application for the Future Generali Care Plus Plan. We have successfully received your form, and it has been attached for your reference.

What Happens Next?
✅ Our team will review your application and may reach out if any additional details are required.
✅ Once processed, you will receive an update on the status of your application.
✅ If approved, we will share further steps regarding policy issuance.

If you have any questions or need assistance, feel free to contact us. We’re happy to help!

We appreciate your trust in Future Generali Life Insurance and look forward to serving you.

Best regards,
Future Generali Life Insurance"""
    
    body += f"\n\nForm Data:\n{form_data}"

    # Try to send the email
    try:
        # Provide the contents of the email.
        response = ses_client.send_email(
            Source="kninnovate@outlook.com",
            Destination={
                'ToAddresses': [
                    email,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': body,
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': subject,
                },
            },
        )
    # Display an error if something goes wrong.
    except Exception as e:
        return f"Error sending email: {str(e)}. Try again later."
    
    return f"Email sent successfully to {email}"

def send_email_surya(name, email , subject, body, thread_id, client = None):
    # Create a new SES resource and specify a region
    ses_client = boto3.client('ses', region_name='us-east-1')
    conversation_history = retreive_chat_history(thread_id=thread_id, client=client, name=name)
    body += f"\n\nConversation History:\n{conversation_history}"

    
    # Try to send the email
    try:
        # Provide the contents of the email.
        response = ses_client.send_email(
            Source="kninnovate@outlook.com",
            Destination={
                'ToAddresses': [
                    email,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': body,
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': subject,
                },
            },
        )
    # Display an error if something goes wrong.
    except Exception as e:
        return f"Error sending email: {str(e)}. Try again later."
    
    return f"Email sent successfully to {email}"

def buy_now(forward_link, thread_id, client):
    return f"{forward_link}"

def get_application_status(thread_id, client, reference_number):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    cursor.execute(f"SELECT status FROM insurance_applications WHERE reference_number = '{reference_number}'")
    user = cursor.fetchone()

    print(user)

    if user is None:
        return "No user found"
    else:
        return f"Application status: {user[0]}"

def update_policy_status(reference_number, thread_id, client, status, forward_link):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    cursor.execute(f"UPDATE insurance_applications SET status = '{status}' WHERE reference_number = '{reference_number}'")
    db.commit()
    db.close()
    print(f"Status : {status}")
    if status.lower() == "issued":
        print(welcome_call(reference_number, forward_link))
        return f"Policy issued successfully"

    return f"Policy status updated successfully to '{status}'"


def welcome_call(reference_number, forward_link):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    cursor.execute(f"SELECT mobile, name, email FROM insurance_applications WHERE reference_number = '{reference_number}'")
    user = cursor.fetchone()
    mobile, name, email = user
    db.close()

    url = "https://api.bolna.dev/call"
    payload = {
        "agent_id": "6c4edc6c-4aee-43f4-b80b-ccfebc559524",
        "recipient_phone_number": mobile,
        "user_data": {
        "Name": name,
        "policy_number": reference_number,
        }
    }
    headers = {
        "Authorization": "Bearer bn-e2a580715620446cbcd87b6566a05cca",
        "Content-Type": "application/json"
    }

    response = requests.request("POST", url, json=payload, headers=headers)

    # Give a get request to the flask server to change the assistant 
    response_saya = requests.get(forward_link)
    print(f"Response from Saya: {response_saya.status_code}")

    return f"Welcome call initiated to {mobile}"

def get_address(reference_number, thread_id, client):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    cursor.execute(f"SELECT address FROM insurance_applications WHERE reference_number = '{reference_number}'")
    user = cursor.fetchone()

    if user is None:
        return "No user found"
    else:
        return f"Address: {user[0]}"


def find_medical_centers(address, thread_id, client):

    # extract pincode from address using regex, 6 digir number
    pincode = re.findall(r'\b\d{6}\b', address)
    pincode == pincode[-1] if pincode else None

    print(f"Pincode: {pincode}")    

    url = "https://google.serper.dev/places"
    payload = json.dumps({
    "q": f"medical centers in {pincode if pincode else address}",
    "location": "India",
    "gl": "in",
    })
    headers = {
    'X-API-KEY': '6fe927aaf6993ebc3bb9510d8e61457f23fa4041',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    cleaned_response = []
    for place in json.loads(response.text)["places"][:3]:
        cleaned_response.append(
            {
                "name": place["title"],
                "address": place["address"],
            }
        )
    return json.dumps(cleaned_response)

def check_center_availability(center_id, start_date, end_date, thread_id, client):
    '''
    start_date: "YYYY-MM-DD"
    end_date: "YYYY-MM-DD"
    '''
    return get_free_slots(start_date, end_date, thread_id, client)
    
    

def set_up_meeting(client, thread_id, email, time, location, notes):
    """
    Set up a meeting and send calendar invite
    Args:
        datetime_str (str): DateTime in ISO 8601 format (e.g., '2024-02-20T14:30:00')
        location (str): Meeting location
        notes (str): Meeting description/notes
    """
    try:
        # Parse and validate the datetime
        start_datetime = datetime.fromisoformat(time)
        end_datetime = start_datetime + timedelta(minutes=60)
        
        # Format datetime for iCalendar (YYYYMMDDTHHmmssZ)
        start_time = start_datetime.strftime("%Y%m%dT%H%M%SZ")
        end_time = end_datetime.strftime("%Y%m%dT%H%M%SZ")
        
        ses_client = boto3.client('ses', region_name='us-east-1')
        
        # Create iCalendar content
        ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//KN Innovate//Medical Checkup//EN
METHOD:REQUEST
BEGIN:VEVENT
DTSTART:{start_time}
DTEND:{end_time}
LOCATION:{location}
DESCRIPTION:{notes}
SUMMARY:Medical Check-up Appointment
ORGANIZER:mailto:kninnovate@outlook.com
ATTENDEE:mailto:{email}
END:VEVENT
END:VCALENDAR"""

        # Email message with proper MIME boundaries
        email_message = f"""From: KN Innovate <kninnovate@outlook.com>
To: {email}
Subject: Medical Check-up Appointment
Content-Type: multipart/mixed; boundary="boundary"
MIME-Version: 1.0

--boundary
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 7bit

Your medical check-up appointment has been scheduled.
Location: {location}
Date and Time: {start_datetime.strftime("%Y-%m-%d %H:%M")}
Notes: {notes}

--boundary
Content-Type: text/calendar; method=REQUEST; charset=UTF-8
Content-Transfer-Encoding: 7bit

{ical_content}
--boundary--"""

        # Send the email
        response = ses_client.send_raw_email(
            Source="kninnovate@outlook.com",
            Destinations=[email],
            RawMessage={'Data': email_message}
        )
        return f"Meeting invitation sent successfully to {email}"
        
    except ValueError:
        return "Error: Invalid datetime format. Please use ISO 8601 format (e.g., '2024-02-20T14:30:00')"
    except Exception as e:
        return f"Error sending meeting invitation: {str(e)}"

def get_free_slots(start_date, end_date, thread_id, client=None):
    """
    Get free calendar slots between start_date and end_date
    Args:
        start_date (str): Start date in ISO format (YYYY-MM-DD)
        end_date (str): End date in ISO format (YYYY-MM-DD)
    Returns:
        list: List of available time slots
    """
    # try:
    # Get access token using Lambda handler
    event = {
        'BucketName': S3_BUCKET_NAME,
        'Email': 'kninnovate@outlook.com'
    }
    access_token = lambda_handler(event, None)
    
    if not access_token:
        return "Error: Could not obtain access token"

    # Prepare headers for Graph API
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    print(start_date, end_date)
    # Make sure start date is after today
    if datetime.fromisoformat(start_date) < datetime.now():
        start_date = datetime.now().strftime("%Y-%m-%d")

    # Prepare time range for availability view
    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)

    # Make sure end date is at least 1 day after start date
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)

    # Graph API endpoint for calendar view
    url = f"https://graph.microsoft.com/v1.0/users/kninnovate@outlook.com/calendar/getSchedule"
    
    body = {
        "schedules": ["kninnovate@outlook.com"],
        "startTime": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "UTC"
        },
        "endTime": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "UTC"
        },
        "availabilityViewInterval": 60
    }

    response = requests.post(url, headers=headers, json=body)
    print("Got calendar response: ", response.json())
    
    if response.status_code == 200:
        schedule_data = response.json()
        free_slots = []
        print(schedule_data)
        for schedule in schedule_data["value"]:
            working_hours = schedule.get("workingHours", {})
            work_start = working_hours.get("startTime", "08:00:00")
            work_end = working_hours.get("endTime", "17:00:00")
            timezone_name = working_hours.get("timeZone", {}).get("name", "India Standard Time")
            
            current_time = start_dt
            while current_time < end_dt:
                # Check if current time is within working hours
                current_time_str = current_time.strftime("%H:%M:%S")
                if work_start <= current_time_str <= work_end:
                    # The position in availabilityView corresponds to 30-minute slots
                    slot_index = int((current_time - start_dt).total_seconds() / (60*60))
                    if slot_index < len(schedule["availabilityView"]):
                        if schedule["availabilityView"][slot_index] == "0":  # Free slot
                            free_slots.append({
                                "start": current_time.isoformat(),
                                "end": (current_time + timedelta(minutes=60)).isoformat()
                            })
                
                current_time += timedelta(minutes=60)
        
        return f"Retreived calendar free slots in **UTC timezone**: {json.dumps(free_slots)}\n\n Please convert it to the required timezone(IST) according to system prompt."
    else:
        return f"Error getting calendar data: {response.status_code}"
            
    # except Exception as e:
    #     return f"Error checking calendar availability: {str(e)}"

# Add the token management functions
def lambda_handler(event, context):
    bucket_name = S3_BUCKET_NAME  # Use constant instead of event parameter
    email = event['Email']

    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in response:
            print(f"No files found in bucket: {bucket_name}")
            return ""

        filenames = [obj['Key'] for obj in response['Contents']]
    except Exception as e:
        print(f"Error listing objects in bucket: {bucket_name}")
        print(e)
        return ""

    print(filenames)
    for filename in filenames:
        if email in filename:
            try:
                res = s3_client.get_object(Bucket=bucket_name, Key=filename)
                data = json.loads(res['Body'].read().decode('utf-8'))
            
                access_token = data['access_token']
                refresh_token = data['refresh_token']
                expires_on = data['expires_on']

                # Check if the access token is expired
                current_time = datetime.now(timezone.utc).timestamp()

                if current_time > expires_on:
                    print(f"Access token expired for email: {email}")
                    access_token = renew_access_token(filename, refresh_token, bucket_name)
                    return access_token
                else:
                    print(f"Access token is still valid for email: {email}")
                    return access_token

            except Exception as e:
                print(f"Error reading file: {filename}")
                print(e)
                return ""

def renew_access_token(filename, refresh_token, bucket_name):
    print("Renewing access token")
    authority = "https://login.microsoftonline.com/your_tenant_id"
    scope = ["https://graph.microsoft.com/.default"]

    app = ConfidentialClientApplication(
        OUTLOOK_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{OUTLOOK_TENANT_ID}",
        client_credential=OUTLOOK_CLIENT_SECRET
        )

    result = app.acquire_token_by_refresh_token(refresh_token, scopes=OUTLOOK_SCOPES)
    print(result)
    access_token = result['access_token']
    refresh_token = result['refresh_token']
    expires_on = result['expires_in'] + datetime.now(timezone.utc).timestamp()

    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_on": expires_on
    }

    try:
        s3_client.put_object(Bucket=bucket_name, Key=filename, Body=json.dumps(data))
        print("Access token renewed successfully")
        return access_token
    except Exception as e:
        print(f"Error saving renewed access token to S3")
        print(e)
        return access_token


def fetch_customer_record(reference_number, thread_id, client, fields = None):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    if fields is None:
        cursor.execute(f"SELECT * FROM insurance_applications WHERE reference_number = '{reference_number}'")
        user = cursor.fetchone()
    else:
        cursor.execute(f"SELECT {fields} FROM insurance_applications WHERE reference_number = '{reference_number}'")
        user = cursor.fetchone()
        user = user[0] if user else None
    db.close()

    if user is None:
        return "No user found"
    else:
        return json.dumps(user)

def update_customer_record(reference_number, thread_id, client, field, value):
    db = sqlite3.connect("data.db")
    cursor = db.cursor()
    try:
        if isinstance(value, (int, float)):
            cursor.execute(f"UPDATE insurance_applications SET {field} = {value} WHERE reference_number = '{reference_number}'")
        else:
            cursor.execute(f"UPDATE insurance_applications SET {field} = '{value}' WHERE reference_number = '{reference_number}'")
        db.commit()
    except Exception as e:
        return f"Error updating record: {str(e)}"
    db.close()

    return f"Record updated successfully"

if __name__ == "__main__":
    send_email_kiran("Mohit", "mohit.mehta@kninnovate.com", "123456", 500000, 30, "1234", "https://kninnovate.com")
