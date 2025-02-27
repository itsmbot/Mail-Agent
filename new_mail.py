# import imaplib
# import email
# import os
# from email.header import decode_header
# import time
# from datetime import datetime
# import html
# from dotenv import load_dotenv
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import re
# from pymilvus import Collection, connections
# from sentence_transformers import SentenceTransformer
# import google.generativeai as genai
 
# class MilvusEmailQueryResponder:
#     def __init__(self, collection_name='it_collection'):
#         load_dotenv()
 
#         self.email_address = os.getenv('EMAIL_ADDRESS')
#         self.password = os.getenv('EMAIL_PASSWORD')
#         self.imap_server = "imap.gmail.com"
#         self.smtp_server = "smtp.gmail.com"
#         self.imap_port = "993"
#         self.smtp_port = 587
 
#         self.milvus_host = os.getenv('MILVUS_HOST')
#         self.milvus_port = os.getenv('MILVUS_PORT')
#         self.collection_name = collection_name
 
#         self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
#         self.embedding_dimension = 384
 
#         genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
 
#         self.last_checked = datetime.now()
#         self.processed_emails = set()
 
#         self.setup_milvus_connection()
 
#     def setup_milvus_connection(self):
#         try:
#             connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port)
#             self.collection = Collection(name=self.collection_name)
#             self.collection.load()
#             print(f"Connected to Milvus collection: {self.collection_name}")
#         except Exception as e:
#             print(f"Milvus connection error: {str(e)}")
#             self.collection = None
 
#     def generate_embedding(self, text):
#         """Generate embedding for text using sentence transformer."""
#         return self.embedding_model.encode(text)
 
#     def semantic_search(self, query, top_k=5):
#         """Perform semantic search in Milvus collection"""
#         try:
#             # Verify Milvus connection
#             if not connections.has_connection(alias="default"):
#                 self.setup_milvus_connection()
            
#             # Ensure collection is loaded
#             if not self.collection:
#                 return "No collection found for semantic search."
            
#             # print(" issuec:", query)
 
#             # Generate embedding for the query
#             query_embedding = self.generate_embedding(query)
            
#             # Search parameters
#             search_params = {
#                 "metric_type": "L2",
#                 "params": {"nprobe": 10}
#             }
            
#             # Perform search
#             results = self.collection.search(
#                 data=[query_embedding],
#                 anns_field="embedding",
#                 param=search_params,
#                 limit=top_k,
#                 output_fields=["content"]
#             )
            
#             if not results or not results[0]:
#                 return "No relevant information found in the collection."
            
#             # Extract and combine contexts
#             contexts = []
#             for hits in results:
#                 for hit in hits:
#                     try:
#                         content = str(hit.fields['content'])
#                         if content and content.strip():
#                             contexts.append(content)
#                     except (KeyError, AttributeError) as e:
#                         print(f"Error accessing hit content: {e}")
#                         continue
            
#             if not contexts:
#                 return f"No readable content found in  pdf documents."
#             combined_context = " ".join(contexts)
#             # print("milus answer : ",combined_context)
 
#             answer = self.query_gemini_llm(query, combined_context)
#             print("gemini :", answer)
#             return answer        
        
#         except Exception as e:
#             print(f"Detailed error in semantic search: {e}")
#             return f"Semantic search error: {str(e)}"
        
#     def query_gemini_llm(self, issue, context):
#         """Enhanced Gemini prompt for formatting answers"""
#         model = genai.GenerativeModel('gemini-1.5-flash')
    
#         prompt = f"""
#         Please format the following solution in a clear and concise manner to address the user's query:

#         Query: {issue}

#         Solution (from Milvus): {context}

#         Provide the solution as a single, concise, and well-structured paragraph that directly addresses the query.
#         Ensure the response is easy to understand, avoids multiple answers, and is not formatted as an email or letter.
#         If the context does not contain sufficient information, state: "The solution for your issue is not there in the Milvus DB."
#         After stating the above, retrieve a relevant solution to the issue using the Gemini model and present it as a well-structured paragraph.
#         Avoid providing unrelated solutions or information that does not pertain directly to the issue.
#         """
#         try:
#             response = model.generate_content(prompt)
#             return response.text.strip()
#         except Exception as e:
#             print(f"Error generating LLM response: {e}")
#             return "I apologize, but I encountered an error processing your question. Please try again."

#     def connect_email(self):
#         try:
#             self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
#             self.imap.login(self.email_address, self.password)
#             return True
#         except Exception as e:
#             print(f"Error connecting to email: {str(e)}")
#             return False
 
#     def decode_email_subject(self, subject):
#         decoded_list = decode_header(subject)
#         return ''.join(
#             part.decode(encoding if encoding else 'utf-8', 'ignore') if isinstance(part, bytes) else part
#             for part, encoding in decoded_list
#         )
 
#     def get_email_body(self, msg):
#         if msg.is_multipart():
#             for part in msg.walk():
#                 if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
#                     return html.unescape(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         else:
#             return html.unescape(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         return "[No readable content found]"
 
#     def check_new_emails(self):
#         try:
#             self.imap.select('INBOX')
#             date_str = self.last_checked.strftime("%d-%b-%Y")
#             # _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str})')
#             _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str} UNSEEN)')
 
 
#             self.last_checked = datetime.now()
 
#             for uid in message_numbers[0].split():
#                 if uid in self.processed_emails:
#                     continue
 
#                 _, msg_data = self.imap.uid('FETCH', uid, '(RFC822)')
#                 msg = email.message_from_bytes(msg_data[0][1])
 
#                 subject = self.decode_email_subject(msg['subject'])
#                 sender = msg['from']
#                 body = self.get_email_body(msg)
 
#                 name_match = re.search(r'^([^<]+)', sender)
#                 name = name_match.group(1).strip() if name_match else 'User'
 
#                 if body.strip():
#                     milvus_contexts = self.semantic_search(body)
 
#                     self.send_reply(sender, subject, body, milvus_contexts, name)
 
#                     self.processed_emails.add(uid)
#                     self.imap.store(uid, '+FLAGS', '\\Seen')
 
#         except Exception as e:
#             print(f"Error checking emails: {str(e)}")
 
#     def send_reply(self, recipient, original_subject, user_query, solution, name):
#         try:
#             with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
#                 server.starttls()
#                 server.login(self.email_address, self.password)
 
#                 reply_message = f"""
# Hello {name},
 
# Your query :  {user_query}
 
# Solution :  {solution}
                
 
# Let me know if this solution resolved your issue or not!
 
# Best regards,
# NetAnalytiks Technologies Limited
# """
 
#                 message = MIMEMultipart()
#                 message["From"] = self.email_address
#                 message["To"] = recipient
#                 # message["Subject"] = f"Re: {original_subject}"
#                 message["Subject"] = f"Reply to: {original_subject}"
#                 message.attach(MIMEText(reply_message, "plain"))
 
#                 server.sendmail(self.email_address, recipient, message.as_string())
#                 print(f"Reply sent to {recipient}.")
 
#         except Exception as e:
#             print(f"Error sending reply: {str(e)}")
 
#     def start_polling(self, interval=60):
#         print(f"Starting email polling every {interval} seconds...")
#         while True:
#             if self.connect_email():
#                 self.check_new_emails()
#                 self.imap.logout()
#             else:
#                 print("Failed to connect. Retrying in 60 seconds...")
#             time.sleep(interval)
 
# if __name__ == "__main__":
#     responder = MilvusEmailQueryResponder()
#     responder.start_polling()  



# import imaplib
# import email
# import os
# from email.header import decode_header
# import time
# from datetime import datetime
# import html
# from dotenv import load_dotenv
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import re
# from pymilvus import Collection, connections
# from sentence_transformers import SentenceTransformer
# import google.generativeai as genai
# from model import DepartmentClassifier
# import nltk

# class MilvusEmailQueryResponder:
#     def __init__(self, collection_name='it_collection'):
#         load_dotenv()
 
#         self.email_address = os.getenv('EMAIL_ADDRESS')
#         self.password = os.getenv('EMAIL_PASSWORD')
        # self.imap_server = "imap.gmail.com"
        # self.smtp_server = "smtp.gmail.com"
        # self.imap_port = "993"
        # self.smtp_port = 587
 
#         self.milvus_host = os.getenv('MILVUS_HOST')
#         self.milvus_port = os.getenv('MILVUS_PORT')
#         self.collection_name = collection_name
 
#         self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
#         self.embedding_dimension = 384
 
#         genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
 
#         self.last_checked = datetime.now()
#         self.processed_emails = set()
 
#         # Initialize the department classifier
#         model_path = os.getenv('CLASSIFIER_MODEL_PATH', 'dp_classifier_model.h5')
#         embedding_model_name = os.getenv('CLASSIFIER_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
#         labels_path = os.getenv('CLASSIFIER_LABELS_PATH', 'labels.json')
#         self.department_classifier = DepartmentClassifier(model_path, embedding_model_name, labels_path)
 
#         self.setup_milvus_connection()
 
#     def setup_milvus_connection(self):
#         try:
#             connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port)
#             self.collection = Collection(name=self.collection_name)
#             self.collection.load()
#             print(f"Connected to Milvus collection: {self.collection_name}")
#         except Exception as e:
#             print(f"Milvus connection error: {str(e)}")
#             self.collection = None
 
#     def generate_embedding(self, text):
#         """Generate embedding for text using sentence transformer."""
#         return self.embedding_model.encode(text)
 
#     def semantic_search(self, query, top_k=5):
#         """Perform semantic search in Milvus collection"""
#         try:
#             # Verify Milvus connection
#             if not connections.has_connection(alias="default"):
#                 self.setup_milvus_connection()
            
#             # Ensure collection is loaded
#             if not self.collection:
#                 return "No collection found for semantic search."
            
#             # print(" issuec:", query)
 
#             # Generate embedding for the query
#             query_embedding = self.generate_embedding(query)
            
#             # Search parameters
#             search_params = {
#                 "metric_type": "L2",
#                 "params": {"nprobe": 10}
#             }
            
#             # Perform search
#             results = self.collection.search(
#                 data=[query_embedding],
#                 anns_field="embedding",
#                 param=search_params,
#                 limit=top_k,
#                 output_fields=["content"]
#             )
            
#             if not results or not results[0]:
#                 return "No relevant information found in the collection."
            
#             # Extract and combine contexts
#             contexts = []
#             for hits in results:
#                 for hit in hits:
#                     try:
#                         content = str(hit.fields['content'])
#                         if content and content.strip():
#                             contexts.append(content)
#                     except (KeyError, AttributeError) as e:
#                         print(f"Error accessing hit content: {e}")
#                         continue
            
#             if not contexts:
#                 return f"No readable content found in pdf documents."
#             combined_context = " ".join(contexts)
#             # print("milus answer : ",combined_context)
 
#             answer = self.query_gemini_llm(query, combined_context)
#             print("gemini :", answer)
#             return answer        
        
#         except Exception as e:
#             print(f"Detailed error in semantic search: {e}")
#             return f"Semantic search error: {str(e)}"
        
#     def query_gemini_llm(self, issue, context):
#         """Enhanced Gemini prompt for formatting answers"""
#         model = genai.GenerativeModel('gemini-1.5-flash')
    
#         prompt = f"""
#         Please format the following solution in a clear and concise manner to address the user's query:

#         Query: {issue}

#         Solution (from Milvus): {context}

#         Provide the solution as a single, concise, and well-structured paragraph that directly addresses the query.
#         Ensure the response is easy to understand, avoids multiple answers, and is not formatted as an email or letter.
#         If the context does not contain sufficient information, state: "The solution for your issue is not there in the Milvus DB."
#         After stating the above, retrieve a relevant solution to the issue using the Gemini model and present it as a well-structured paragraph.
#         Avoid providing unrelated solutions or information that does not pertain directly to the issue.
#         """
#         try:
#             response = model.generate_content(prompt)
#             return response.text.strip()
#         except Exception as e:
#             print(f"Error generating LLM response: {e}")
#             return "I apologize, but I encountered an error processing your question. Please try again."

#     def connect_email(self):
#         try:
#             self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
#             self.imap.login(self.email_address, self.password)
#             return True
#         except Exception as e:
#             print(f"Error connecting to email: {str(e)}")
#             return False
 
#     def decode_email_subject(self, subject):
#         decoded_list = decode_header(subject)
#         return ''.join(
#             part.decode(encoding if encoding else 'utf-8', 'ignore') if isinstance(part, bytes) else part
#             for part, encoding in decoded_list
#         )
 
#     def get_email_body(self, msg):
#         if msg.is_multipart():
#             for part in msg.walk():
#                 if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
#                     return html.unescape(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         else:
#             return html.unescape(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         return "[No readable content found]"
 
#     def check_new_emails(self):
#         try:
#             self.imap.select('INBOX')
#             date_str = self.last_checked.strftime("%d-%b-%Y")
#             # _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str})')
#             _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str} UNSEEN)')
 
#             self.last_checked = datetime.now()
 
#             for uid in message_numbers[0].split():
#                 if uid in self.processed_emails:
#                     continue
 
#                 _, msg_data = self.imap.uid('FETCH', uid, '(RFC822)')
#                 msg = email.message_from_bytes(msg_data[0][1])
 
#                 subject = self.decode_email_subject(msg['subject'])
#                 sender = msg['from']
#                 body = self.get_email_body(msg)
 
#                 name_match = re.search(r'^([^<]+)', sender)
#                 name = name_match.group(1).strip() if name_match else 'User'
 
#                 if body.strip():
#                     # Classify the email department
#                     department = self.department_classifier.predict_department(body)
#                     print(f"Email classified as: {department}")
                    
#                     # Get response from Milvus or LLM
#                     milvus_contexts = self.semantic_search(body)
 
#                     # Send reply with department info and solution
#                     self.send_reply(sender, subject, body, milvus_contexts, name, department)
 
#                     self.processed_emails.add(uid)
#                     self.imap.store(uid, '+FLAGS', '\\Seen')
 
#         except Exception as e:
#             print(f"Error checking emails: {str(e)}")
 
#     def send_reply(self, recipient, original_subject, user_query, solution, name, department):
#         try:
#             with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
#                 server.starttls()
#                 server.login(self.email_address, self.password)
 
#                 reply_message = f"""
# Hello {name},
 
# Your query has been classified as: {department}
 
# Your query: {user_query}
 
# Solution: {solution}
                
 
# Let me know if this solution resolved your issue or not!
 
# Best regards,
# NetAnalytiks Technologies Limited
# """
 
#                 message = MIMEMultipart()
#                 message["From"] = self.email_address
#                 message["To"] = recipient
#                 # message["Subject"] = f"Re: {original_subject}"
#                 message["Subject"] = f"Reply to: {original_subject}"
#                 message.attach(MIMEText(reply_message, "plain"))
 
#                 server.sendmail(self.email_address, recipient, message.as_string())
#                 print(f"Reply sent to {recipient} for {department} department.")
 
#         except Exception as e:
#             print(f"Error sending reply: {str(e)}")
 
#     def start_polling(self, interval=60):
#         print(f"Starting email polling every {interval} seconds...")
#         while True:
#             if self.connect_email():
#                 self.check_new_emails()
#                 self.imap.logout()
#             else:
#                 print("Failed to connect. Retrying in 60 seconds...")
#             time.sleep(interval)
 
# if __name__ == "__main__":
#     responder = MilvusEmailQueryResponder()
#     responder.start_polling()



# import imaplib
# import email
# import os
# from email.header import decode_header
# import time
# from datetime import datetime
# import html
# from dotenv import load_dotenv
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import re
# from pymilvus import Collection, connections
# from sentence_transformers import SentenceTransformer
# import google.generativeai as genai
# from model import DepartmentClassifier
# import nltk
 
# class MilvusEmailQueryResponder:
#     def __init__(self, collection_name='it_collection'):
#         load_dotenv('key.env')
 
#         self.email_address = os.getenv('EMAIL_ADDRESS')
#         self.password = os.getenv('EMAIL_PASSWORD')
        
 
#         self.milvus_host = os.getenv('MILVUS_HOST')
#         self.milvus_port = os.getenv('MILVUS_PORT')
#         self.collection_name = collection_name
 
#         self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
#         self.embedding_dimension = 384
 
#         genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
 
#         self.last_checked = datetime.now()
#         self.processed_emails = set()
 
#         # Initialize the department classifier
#         model_path = os.getenv('CLASSIFIER_MODEL_PATH', 'dp_classifier_model.h5')
#         embedding_model_name = os.getenv('CLASSIFIER_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
#         labels_path = os.getenv('CLASSIFIER_LABELS_PATH', 'labels.json')
#         self.department_classifier = DepartmentClassifier(model_path, embedding_model_name, labels_path)
 
#         self.setup_milvus_connection()
 
#     def setup_milvus_connection(self):
#         try:
#             connections.connect(alias="default", host=self.milvus_host, port=self.milvus_port)
#             self.collection = Collection(name=self.collection_name)
#             self.collection.load()
#             print(f"Connected to Milvus collection: {self.collection_name}")
#         except Exception as e:
#             print(f"Milvus connection error: {str(e)}")
#             self.collection = None
 
#     def generate_embedding(self, text):
#         """Generate embedding for text using sentence transformer."""
#         return self.embedding_model.encode(text)
 
#     def semantic_search(self, query, top_k=5):
#         """Perform semantic search in Milvus collection"""
#         try:
#             # Verify Milvus connection
#             if not connections.has_connection(alias="default"):
#                 self.setup_milvus_connection()
            
#             # Ensure collection is loaded
#             if not self.collection:
#                 return "No collection found for semantic search."
            
#             # print(" issuec:", query)
 
#             # Generate embedding for the query
#             query_embedding = self.generate_embedding(query)
            
#             # Search parameters
#             search_params = {
#                 "metric_type": "L2",
#                 "params": {"nprobe": 10}
#             }
            
#             # Perform search
#             results = self.collection.search(
#                 data=[query_embedding],
#                 anns_field="embedding",
#                 param=search_params,
#                 limit=top_k,
#                 output_fields=["content"]
#             )
            
#             if not results or not results[0]:
#                 return "No relevant information found in the collection."
            
#             # Extract and combine contexts
#             contexts = []
#             for hits in results:
#                 for hit in hits:
#                     try:
#                         content = str(hit.fields['content'])
#                         if content and content.strip():
#                             contexts.append(content)
#                     except (KeyError, AttributeError) as e:
#                         print(f"Error accessing hit content: {e}")
#                         continue
            
#             if not contexts:
#                 return f"No readable content found in pdf documents."
#             combined_context = " ".join(contexts)
#             # print("milus answer : ",combined_context)
 
#             answer = self.query_gemini_llm(query, combined_context)
#             print("gemini :", answer)
#             return answer        
        
#         except Exception as e:
#             print(f"Detailed error in semantic search: {e}")
#             return f"Semantic search error: {str(e)}"
        
#     def query_gemini_llm(self, issue, context):
#         """Enhanced Gemini prompt for formatting answers"""
#         model = genai.GenerativeModel('gemini-1.5-flash')
 
#         prompt = f"""
#         Please format the following solution in a clear and concise manner to address the user's query:
 
#         Query: {issue}
 
#         Solution (from Milvus): {context}
 
#         Provide the solution as a single, concise, and well-structured paragraph that directly addresses the query.
#         Ensure the response is easy to understand, avoids multiple answers, and is not formatted as an email or letter.
#         If the context is 'No relevant data found in Milvus.' then generate a complete response using your knowledge.
#         Avoid generic responses; make sure the answer is directly relevant and useful and simple.
      
#         """
#         try:
#             response = model.generate_content(prompt)
#             return response.text.strip()
#         except Exception as e:
#             print(f"Error generating LLM response: {e}")
#             return "I apologize, but I encountered an error processing your question. Please try again."
 
 
#     def connect_email(self):
#         try:
#             self.imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
#             self.imap.login(self.email_address, self.password)
#             return True
#         except Exception as e:
#             print(f"Error connecting to email: {str(e)}")
#             return False
 
#     def decode_email_subject(self, subject):
#         decoded_list = decode_header(subject)
#         return ''.join(
#             part.decode(encoding if encoding else 'utf-8', 'ignore') if isinstance(part, bytes) else part
#             for part, encoding in decoded_list
#         )
 
#     def get_email_body(self, msg):
#         if msg.is_multipart():
#             for part in msg.walk():
#                 if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
#                     return html.unescape(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         else:
#             return html.unescape(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
#         return "[No readable content found]"
 
#     def check_new_emails(self):
#         try:
#             self.imap.select('INBOX')
#             date_str = self.last_checked.strftime("%d-%b-%Y")
#             # _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str})')
#             _, message_numbers = self.imap.uid('SEARCH', None, f'(SINCE {date_str} UNSEEN)')
 
#             self.last_checked = datetime.now()
 
#             for uid in message_numbers[0].split():
#                 if uid in self.processed_emails:
#                     continue
 
#                 _, msg_data = self.imap.uid('FETCH', uid, '(RFC822)')
#                 msg = email.message_from_bytes(msg_data[0][1])
 
#                 subject = self.decode_email_subject(msg['subject'])
#                 sender = msg['from']
#                 body = self.get_email_body(msg)
 
#                 name_match = re.search(r'^([^<]+)', sender)
#                 name = name_match.group(1).strip() if name_match else 'User'
 
#                 if body.strip():
#                     # Classify the email department
#                     department = self.department_classifier.predict_department(body)
#                     print(f"Email classified as: {department}")
                    
#                     # Get response from Milvus or LLM
#                     milvus_contexts = self.semantic_search(body)
 
#                     # Send reply with department info and solution
#                     self.send_reply(sender, subject, body, milvus_contexts, name, department)
 
#                     self.processed_emails.add(uid)
#                     self.imap.store(uid, '+FLAGS', '\\Seen')
 
#         except Exception as e:
#             print(f"Error checking emails: {str(e)}")
 
#     def send_reply(self, recipient, original_subject, user_query, solution, name, department):
#         try:
#             with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
#                 server.starttls()
#                 server.login(self.email_address, self.password)
 
#                 reply_message = f"""
# Hello {name},
 
# Your query has been classified as: {department}
 
# Your query: {user_query}
 
# Solution: {solution}
                
 
# Let me know if this solution resolved your issue or not!
 
# Best regards,
# NetAnalytiks Technologies Limited
# """
 
#                 message = MIMEMultipart()
#                 message["From"] = self.email_address
#                 message["To"] = recipient
#                 # message["Subject"] = f"Re: {original_subject}"
#                 message["Subject"] = f"Reply to: {original_subject}"
#                 message.attach(MIMEText(reply_message, "plain"))
 
#                 server.sendmail(self.email_address, recipient, message.as_string())
#                 print(f"Reply sent to {recipient} for {department} department.")
 
#         except Exception as e:
#             print(f"Error sending reply: {str(e)}")
 
#     def start_polling(self, interval=60):
#         print(f"Starting email polling every {interval} seconds...")
#         while True:
#             if self.connect_email():
#                 self.check_new_emails()
#                 self.imap.logout()
#             else:
#                 print("Failed to connect. Retrying in 60 seconds...")
#             time.sleep(interval)
 
# if __name__ == "__main__":
#     responder = MilvusEmailQueryResponder()
#     responder.start_polling()
