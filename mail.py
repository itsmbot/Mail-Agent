import imaplib
import email
import os
from email.header import decode_header
import time
from datetime import datetime
import html
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import requests
from model import DepartmentClassifier
 
 
# Load environment variables
load_dotenv('key.env')
 
# ServiceNow API credentials and URL
SERVICE_NOW_INSTANCE = os.getenv('SERVICE_NOW_INSTANCE')
SERVICE_NOW_USER = os.getenv('SERVICE_NOW_USER')
SERVICE_NOW_PASSWORD = os.getenv('SERVICE_NOW_PASSWORD')
 
 
# ServiceNow API functions
def create_servicenow_incident(description="Some problem", urgency='2', impact='2'):
    
    # Ensure the URL is properly formatted
    if not SERVICE_NOW_INSTANCE.startswith('https://'):
        url = f'https://{SERVICE_NOW_INSTANCE}/api/now/table/incident'
    else:
        url = f'{SERVICE_NOW_INSTANCE}/api/now/table/incident'
 
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
   
    data = {
        'short_description': description,
        'urgency': urgency,
        'impact': impact,
    }
   
    try:
        response = requests.post(
            url,
            auth=(SERVICE_NOW_USER, SERVICE_NOW_PASSWORD),
            headers=headers,
            json=data,
            timeout=10  # Add timeout
        )
 
        if response.status_code == 201:
            result = response.json()['result']
            return {
                'number': result['number'],
                'sys_id': result['sys_id'],
                'status': 'New',
                'short_description':result['short_description']
            }
        else:
            if "Instance Hibernating" in response.text:
                return {
                    'error': 'ServiceNow instance is hibernating. Please log in to your instance to wake it up: ' +
                            'https://developer.servicenow.com/dev.do#!/home?wu=true'
                }
            try:
                error_detail = response.json()
                return {'error': f"Status code: {response.status_code}, Details: {error_detail}"}
            except:
                return {'error': f"Status code: {response.status_code}, Response: {response.text}"}
    except requests.exceptions.RequestException as e:
        return {'error': f"Connection error: {str(e)}"}
 
def view_ticket_detailed(number=None, sys_id=None):
    """
    View detailed ServiceNow ticket information
    Args:
        number: The incident number (e.g., 'INC0010002')
        sys_id: The system ID
    Returns:
        Dictionary containing detailed ticket information or error message
    """
 
    # Ensure the URL is properly formatted
    base_url = f'https://{SERVICE_NOW_INSTANCE}' if not SERVICE_NOW_INSTANCE.startswith('https://') else SERVICE_NOW_INSTANCE
    url = f'{base_url}/api/now/table/incident'
 
    # Set up parameters with comprehensive fields
    params = {
        'sysparm_display_value': 'true',
        'sysparm_fields': ','.join([
            'number',
            'sys_id',
            'state',
            'short_description',
            'description',
            'priority',
            'urgency',
            'impact',
            'assigned_to',
        ])
    }
 
    # Add query parameters based on input
    if number:
        params['sysparm_query'] = f'number={number}'
    elif sys_id:
        url = f'{url}/{sys_id}'
    else:
        return {'error': 'Please provide either number or sys_id'}
 
    headers = {
        'Accept': 'application/json'
    }
 
    try:
        response = requests.get(
            url,
            auth=(SERVICE_NOW_USER, SERVICE_NOW_PASSWORD),
            headers=headers,
            params=params,
            timeout=10
        )
 
        if response.status_code == 200:
            response_data = response.json()
            
            if 'result' in response_data:
                result = response_data['result']
                
                if isinstance(result, list):
                    if not result:
                        return {'error': 'No ticket found'}
                    ticket = result[0]
                else:
                    ticket = result
 
                return {
                    'number': ticket.get('number'),
                    'sys_id': ticket.get('sys_id'),
                    'state': ticket.get('state'),
                    'short_description': ticket.get('short_description'),
                    'description': ticket.get('description'),
                    'priority': ticket.get('priority'),
                    'urgency': ticket.get('urgency'),
                    'impact': ticket.get('impact'),
                }
            else:
                return {'error': 'Unexpected response format'}
 
        else:
            if "Instance Hibernating" in response.text:
                return {
                    'error': 'ServiceNow instance is hibernating. Please log in to your instance to wake it up: ' +
                            'https://developer.servicenow.com/dev.do#!/home?wu=true'
                }
            try:
                error_detail = response.json()
                return {'error': f"Status code: {response.status_code}, Details: {error_detail}"}
            except:
                return {'error': f"Status code: {response.status_code}, Response: {response.text}"}
 
    except requests.exceptions.RequestException as e:
        return {'error': f"Connection error: {str(e)}"}
 
class MilvusEmailQueryResponder:
    def __init__(self, collection_name='it_collection'):
        load_dotenv()
 
        self.email_address = os.getenv('EMAIL_ADDRESS')
        self.password = os.getenv('EMAIL_PASSWORD')
        self.imap_server = "imap.gmail.com"
        self.smtp_server = "smtp.gmail.com"
        self.imap_port = "993"
        self.smtp_port = 587
 
        self.milvus_host = os.getenv('MILVUS_HOST')
        self.milvus_port = os.getenv('MILVUS_PORT')
        self.collection_name = collection_name
 
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_dimension = 384
 
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
 
        self.last_checked = datetime.now()
        self.processed_emails = set()
 
        # Initialize the department classifier
        model_path = os.getenv('CLASSIFIER_MODEL_PATH', 'dp_classifier_model.h5')
        embedding_model_name = os.getenv('CLASSIFIER_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        labels_path = os.getenv('CLASSIFIER_LABELS_PATH', 'labels.json')
        self.department_classifier = DepartmentClassifier(model_path, embedding_model_name, labels_path)
 
        self.setup_milvus_connection()
 
    def setup_milvus_connection(self):
        try:
            connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port)
            self.collection = Collection(name=self.collection_name)
            self.collection.load()
            print(f"Connected to Milvus collection: {self.collection_name}")
        except Exception as e:
            print(f"Milvus connection error: {str(e)}")
            self.collection = None
 
    def generate_embedding(self, text):
        """Generate embedding for text using sentence transformer."""
        return self.embedding_model.encode(text)
 
    def semantic_search(self, query, top_k=5):
        """Perform semantic search in Milvus collection"""
        try:
            # Verify Milvus connection
            if not connections.has_connection(alias="default"):
                self.setup_milvus_connection()
            
            # Ensure collection is loaded
            if not self.collection:
                return "No collection found for semantic search."
            
            # Generate embedding for the query
            query_embedding = self.generate_embedding(query)
            
            # Search parameters
            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10}
            }
            
            # Perform search
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["content"]
            )
            
            if not results or not results[0]:
                return "No relevant information found in the collection."
            
            # Extract and combine contexts
            contexts = []
            for hits in results:
                for hit in hits:
                    try:
                        content = str(hit.fields['content'])
                        if content and content.strip():
                            contexts.append(content)
                    except (KeyError, AttributeError) as e:
                        print(f"Error accessing hit content: {e}")
                        continue
            
            if not contexts:
                return f"No readable content found in pdf documents."
            combined_context = " ".join(contexts)
 
            answer = self.query_gemini_llm(query, combined_context)
            print("gemini :", answer)
            return answer        
        
        except Exception as e:
            print(f"Detailed error in semantic search: {e}")
            return f"Semantic search error: {str(e)}"
        
    def query_gemini_llm(self, issue, context):
        """Enhanced Gemini prompt for formatting answers"""
        model = genai.GenerativeModel('gemini-1.5-flash')
    
        prompt = f"""
        Please format the following solution in a clear and concise manner to address the user's query:
 
        Query: {issue}
 
        Solution (from Milvus): {context}
 
        Provide the solution as a single, concise, and well-structured paragraph that directly addresses the query.
        Ensure the response is easy to understand, avoids multiple answers, and is not formatted as an email or letter.
        If the context does not contain sufficient information, state: "The solution for your issue is not there in the Milvus DB."
        After stating the above, retrieve a relevant solution to the issue using the Gemini model and present it as a well-structured paragraph.
        Avoid providing unrelated solutions or information that does not pertain directly to the issue.
        """
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Error generating LLM response: {e}")
            return "I apologize, but I encountered an error processing your question. Please try again."
 
    def connect_email(self):
        try:
            self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap.login(self.email_address, self.password)
            return True
        except Exception as e:
            print(f"Error connecting to email: {str(e)}")
            return False
 
    def decode_email_subject(self, subject):
        decoded_list = decode_header(subject)
        return ''.join(
            part.decode(encoding if encoding else 'utf-8', 'ignore') if isinstance(part, bytes) else part
            for part, encoding in decoded_list
        )
 
    def get_email_body(self, msg):
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                    return html.unescape(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
        else:
            return html.unescape(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
        return "[No readable content found]"
 
    def is_incident_request(self, subject, body):
        """Check if email contains requests for ticket or incident creation"""
        subject_lower = subject.lower()
        body_lower = body.lower()
        
        ticket_keywords = ['create ticket', 'create incident', 'open ticket', 'open incident',
                           'raise ticket', 'raise incident', 'new ticket', 'new incident']
        
        # Check subject
        if any(keyword in subject_lower for keyword in ticket_keywords):
            return True
            
        # Check body
        if any(keyword in body_lower for keyword in ticket_keywords):
            return True
            
        return False
    
    def is_status_request(self, subject, body):
        """Check if email is requesting status of an existing incident"""
        subject_lower = subject.lower()
        body_lower = body.lower()
        
        status_keywords = ['ticket status', 'incident status', 'check status', 'status update',
                          'update on ticket', 'update on incident', 'follow up']
        
        # Check subject
        if any(keyword in subject_lower for keyword in status_keywords):
            return True
            
        # Check body
        if any(keyword in body_lower for keyword in status_keywords):
            return True
            
        # Also check for presence of incident number format
        incident_pattern = re.compile(r'\b(INC\d+)\b', re.IGNORECASE)
        if incident_pattern.search(subject) or incident_pattern.search(body):
            return True
            
        return False
    
    def extract_incident_number(self, subject, body):
        """Extract incident number from email subject or body"""
        # Common format for ServiceNow incident numbers is INC followed by numbers
        incident_pattern = re.compile(r'\b(INC\d+)\b', re.IGNORECASE)
        
        # First check subject
        subject_match = incident_pattern.search(subject)
        if subject_match:
            return subject_match.group(1)
            
        # Then check body
        body_match = incident_pattern.search(body)
        if body_match:
            return body_match.group(1)
            
        return None
    
    def check_new_emails(self):
        try:
            self.imap.select('INBOX')
            date_str = self.last_checked.strftime("%d-%b-%Y")
            # Search for unread emails since last check
            _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str} UNSEEN)')
 
            self.last_checked = datetime.now()
 
            for uid in message_numbers[0].split():
                if uid in self.processed_emails:
                    continue
 
                _, msg_data = self.imap.uid('FETCH', uid, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])
 
                subject = self.decode_email_subject(msg['subject'])
                sender = msg['from']
                body = self.get_email_body(msg)
 
                name_match = re.search(r'^([^<]+)', sender)
                name = name_match.group(1).strip() if name_match else 'User'
 
                if body.strip():
                    # Check if this is a status request
                    department = self.department_classifier.predict_department(body)
                    print("Email classified as :" , department)
                    
                    if self.is_status_request(subject, body):
                        # Extract incident number
                        incident_number = self.extract_incident_number(subject, body)
                        
                        if incident_number:
                            # Get incident details
                            incident_info = view_ticket_detailed(number=incident_number)
                            
                            if 'error' in incident_info:
                                # Send error response
                                error_message = incident_info['error']
                                self.send_reply(
                                    sender,
                                    subject,
                                    body,
                                    f"Failed to retrieve incident status: {error_message}",
                                    name,
                                    is_incident=True,
                                    incident_info=None,
                                    is_status_update=True
                                )
                            else:
                                # Send status update
                                self.send_reply(
                                    sender,
                                    subject,
                                    body,
                                    "Here is the current status of your incident.",
                                    name,
                                    is_incident=True,
                                    incident_info=incident_info,
                                    is_status_update=True
                                )
                        else:
                            # No incident number found
                            self.send_reply(
                                sender,
                                subject,
                                body,
                                "Could not find an incident number in your request. Please include your incident number (format: INCxxxxx) to check status.",
                                name,
                                is_incident=False,
                                incident_info=None
                            )
                    
                    # Check if this is a ticket/incident creation request
                    elif self.is_incident_request(subject, body):
                        # Create ServiceNow incident
                        print("Creating incident for email request")
                        incident_response = create_servicenow_incident(
                            description=body or "Issue from email",  # Full email body
                            urgency='2',
                            impact='2'
                        )
 
                        if 'error' in incident_response:
                            error_message = incident_response['error']
                            self.send_reply(
                                sender,
                                subject,
                                body,
                                f"Failed to create incident: {error_message}",
                                name,
                                is_incident=True,
                                incident_info=None
                            )
                        else:
                            # Send reply with incident details
                            self.send_reply(
                                sender,
                                subject,
                                body,
                                "Your incident has been created successfully.",
                                name,
                                is_incident=True,
                                incident_info=incident_response
                            )
                    else:
                        # Get response from Milvus for regular queries
                        milvus_contexts = self.semantic_search(body)
                        
                        # Send regular reply with solution
                        self.send_reply(
                            sender,
                            subject,
                            body,
                            milvus_contexts,
                            name,
                            is_incident=False,
                            incident_info=None
                        )
 
                    # Mark email as processed and read
                    self.processed_emails.add(uid)
                    self.imap.store(uid, '+FLAGS', '\\Seen')
 
        except Exception as e:
            print(f"Error checking emails: {str(e)}")
 
    def send_reply(self, recipient, original_subject, user_query, solution, name,
                  is_incident=False, incident_info=None, is_status_update=False):
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.password)
                
                if is_incident and incident_info:
                    if is_status_update:
                        # Format for status update response
                        reply_message = f"""
Hello {name},
 
Here is the current status of your incident:
 
Incident Number: {incident_info.get('number', 'N/A')}
Short Description: {incident_info.get('short_description', 'N/A')}
Status: {incident_info.get('state', 'N/A')}
Priority: {incident_info.get('priority', 'N/A')}
Urgency: {incident_info.get('urgency', 'N/A')}
Impact: {incident_info.get('impact', 'N/A')}
 
If you have any questions or need further assistance, please reply to this email.
 
Best regards,
NetAnalytiks Technologies Limited
"""
                    else:
                        # Format for new incident creation
                        reply_message = f"""
Hello {name},
 
Incident Number: {incident_info.get('number', 'N/A')}
Short Description: {incident_info.get('short_description', 'N/A')}
Status: {incident_info.get('status', 'N/A')}
 
Best regards,
NetAnalytiks Technologies Limited
"""
                else:
                    # Format reply for regular queries or errors
                    reply_message = f"""
Hello {name},
 
Your query: {user_query}
 
Solution: {solution}
                
Let me know if this solution resolved your issue or not!  If not, send a mail with your issue(with proper description) by saying create incident.
 
Best regards,
NetAnalytiks Technologies Limited
"""
 
                message = MIMEMultipart()
                message["From"] = self.email_address
                message["To"] = recipient
                message["Subject"] = f"Reply to: {original_subject}"
                message.attach(MIMEText(reply_message, "plain"))
 
                server.sendmail(self.email_address, recipient, message.as_string())
                print(f"Reply sent to {recipient}")
 
        except Exception as e:
            print(f"Error sending reply: {str(e)}")
 
    def start_polling(self, interval=60):
        print(f"Starting email polling every {interval} seconds...")
        while True:
            if self.connect_email():
                self.check_new_emails()
                self.imap.logout()
            else:
                print("Failed to connect. Retrying in 60 seconds...")
            time.sleep(interval)
 
if __name__ == "__main__":
    responder = MilvusEmailQueryResponder()
    responder.start_polling()